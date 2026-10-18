#!/usr/bin/env python3
"""
Dify 一键初始化脚本（dify-init 容器入口，适配 Dify 1.16）
================================================
Dify 1.16 Console API 与旧版差异（本脚本按实测 API 编写）：
  - Console 路径全部为 /console/api/*（旧版 /api/console/*、/api/apps/* 均已 404）
  - 登录密码需 Base64 编码；token 不在响应体，而在 Set-Cookie（access_token/csrf_token）
  - 后续请求需带请求头：Authorization: Bearer <access_token> + X-CSRF-TOKEN: <csrf_token>
  - 模型供应商为插件制：先装 openai_api_compatible 插件（marketplace），再添加模型凭据；
    添加凭据时服务端会实时调用模型校验（余额不足返回 402）
  - advanced-chat 应用走 DSL 导入（/console/api/apps/imports），导入后工作流不会自动发布，
    需再调 /console/api/apps/{id}/workflows/publish
  - agent-chat 应用 DSL 骨架缺 1.16 的 model_config 块，无法导入，
    改为「创建空应用 + POST /console/api/apps/{id}/model-config」

功能：
  1. 等待 Dify api 就绪
  2. 自动创建/登录 Dify 管理员
  3. 安装 OpenAI-API-compatible 模型供应商插件 + 添加模型凭据（幂等）
  4. 导入 dify/apps/ 下的应用（advanced-chat 导入+发布；agent-chat 创建+model-config，幂等）
  5. 为已存在的应用重新绑定模型（agent-chat 重写 model-config；advanced-chat 补丁草稿+发布）
  6. 输出 app key 到 dify/docker/app_keys.txt

依赖：httpx, pyyaml
运行环境：dify-init 容器内（与 Dify api 同 docker 网络）
"""

import base64
import glob
import os
import sys
import time
from pathlib import Path

import httpx
import yaml

# ── 环境变量 ──────────────────────────────────────────────
DIFY_API_URL = os.environ.get("DIFY_API_URL", "http://api:5001").rstrip("/")
DIFY_ADMIN_EMAIL = os.environ.get("DIFY_ADMIN_EMAIL", "admin@example.com")
DIFY_ADMIN_PASSWORD = os.environ.get("DIFY_ADMIN_PASSWORD", "Difyadmin2026")
DIFY_MODEL_API_KEY = os.environ.get("DIFY_MODEL_API_KEY", "")
DIFY_MODEL_BASE_URL = os.environ.get("DIFY_MODEL_BASE_URL", "")
DIFY_MODEL_NAME = os.environ.get("DIFY_MODEL_NAME", "")
AUTO_IMPORT = os.environ.get("DIFY_INIT_AUTO_IMPORT", "true").lower() == "true"
AUTO_BIND = os.environ.get("DIFY_INIT_AUTO_BIND_MODEL", "true").lower() == "true"
APPS_DIR = os.environ.get("DIFY_APPS_DIR", "/apps")
APP_KEYS_FILE = os.environ.get("DIFY_APP_KEYS_FILE", "/output/app_keys.txt")

# 模型供应商插件（OpenAI-API-compatible，Dify 1.16 起为插件制）
PROVIDER_PLUGIN_ID = "langgenius/openai_api_compatible"
MODEL_PROVIDER = "langgenius/openai_api_compatible/openai_api_compatible"
MODEL_MODE = "chat"  # 业务应用均用对话模型
MARKETPLACE_API = "https://marketplace.dify.ai/api/v1"

# 应用名 -> backend/.env 变量名（导出 key 时写注释用）
APP_KEY_ENV_MAP = {
    "留学生智能管家": "DIFY_STUDENT_AGENT_KEY",
    "企业员工助手": "DIFY_EMPLOYEE_AGENT_KEY",
    "粤教客服Agent": "DIFY_CUSTOMER_AGENT_KEY",
    "智能报告": "DIFY_REPORT_AGENT_KEY",
}


def log(msg: str) -> None:
    print(f"[dify-init] {msg}", flush=True)


def fail(msg: str) -> None:
    log(f"❌ {msg}")
    sys.exit(1)


# ── 步骤 1：等待 Dify 就绪 ────────────────────────────────
def wait_for_dify(timeout: int = 300) -> None:
    log(f"等待 Dify api 就绪：{DIFY_API_URL}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for path in ("/health", "/console/api/setup"):
            try:
                r = httpx.get(f"{DIFY_API_URL}{path}", timeout=10)
                if r.status_code == 200:
                    log(f"✅ Dify api 已就绪（{path}）")
                    return
            except httpx.HTTPError:
                pass
        time.sleep(3)
    fail(f"Dify api 在 {timeout}s 内未就绪")


# ── 步骤 2：登录/创建管理员 ───────────────────────────────
def setup_and_login(client: httpx.Client) -> None:
    """检测初始化状态，必要时创建管理员；然后登录并设置鉴权请求头"""
    # 2.1 初始化状态
    r = client.get("/console/api/setup", timeout=15)
    if r.status_code != 200:
        fail(f"检测 Dify 初始化状态失败: {r.status_code} {r.text[:300]}")
    step = r.json().get("step", "")
    if step != "finished":
        log("Dify 未初始化，自动创建管理员...")
        pw64 = base64.b64encode(DIFY_ADMIN_PASSWORD.encode()).decode()
        created = False
        # 1.16 与登录同走 base64 加密；个别版本 setup 收明文，失败则回退
        for pw in (pw64, DIFY_ADMIN_PASSWORD):
            r = client.post(
                "/console/api/setup",
                json={"email": DIFY_ADMIN_EMAIL, "name": "Admin", "password": pw},
                timeout=30,
            )
            if r.status_code in (200, 201):
                created = True
                break
        if not created:
            fail(f"创建管理员失败: {r.status_code} {r.text[:300]}")
        log("✅ 管理员创建成功")
    else:
        log("Dify 已初始化，使用预设账号登录")

    # 2.2 登录（密码 base64；token 经 Set-Cookie 下发）
    pw64 = base64.b64encode(DIFY_ADMIN_PASSWORD.encode()).decode()
    r = client.post(
        "/console/api/login",
        json={"email": DIFY_ADMIN_EMAIL, "password": pw64, "remember_me": True},
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"登录失败: {r.status_code} {r.text[:300]}（检查 DIFY_ADMIN_EMAIL/PASSWORD）")
    access_token = client.cookies.get("access_token")
    csrf_token = client.cookies.get("csrf_token")
    if not access_token or not csrf_token:
        fail("登录响应未下发 access_token/csrf_token cookie")
    client.headers.update({
        "Authorization": f"Bearer {access_token}",
        "X-CSRF-TOKEN": csrf_token,
    })
    log("✅ 管理员登录成功")


# ── 步骤 3：模型供应商插件 + 模型凭据 ──────────────────────
def ensure_provider_plugin(client: httpx.Client) -> None:
    """Dify 1.16 模型供应商为插件制：未安装则从 marketplace 安装并轮询任务"""
    r = client.get(
        "/console/api/workspaces/current/plugin/list",
        params={"page": 1, "page_size": 100},
        timeout=30,
    )
    if r.status_code == 200:
        plugins = r.json().get("plugins") or []
        if any(p.get("plugin_id") == PROVIDER_PLUGIN_ID for p in plugins):
            log(f"✅ 插件 {PROVIDER_PLUGIN_ID} 已安装，跳过")
            return
    else:
        log(f"⚠️  查询插件列表返回 {r.status_code}，尝试直接安装")

    # marketplace 搜索最新版本标识
    log(f"从 marketplace 搜索插件 {PROVIDER_PLUGIN_ID} ...")
    try:
        r = httpx.post(
            f"{MARKETPLACE_API}/plugins/search/advanced",
            json={
                "query": "openai_api_compatible",
                "page": 1,
                "page_size": 20,
                "sort_by": "install_count",
                "sort_order": "DESC",
                "type": "plugin",
            },
            timeout=30,
        )
    except httpx.HTTPError as e:
        fail(f"访问 Dify marketplace 失败（需要外网）: {e}")
    if r.status_code != 200:
        fail(f"marketplace 搜索失败: {r.status_code} {r.text[:300]}")
    candidates = (r.json().get("data") or {}).get("plugins") or []
    identifier = next(
        (p.get("latest_package_identifier") for p in candidates
         if p.get("plugin_id") == PROVIDER_PLUGIN_ID and p.get("latest_package_identifier")),
        None,
    )
    if not identifier:
        fail(f"marketplace 未找到插件 {PROVIDER_PLUGIN_ID}")
    log(f"  安装版本: {identifier}")

    # 发起安装
    r = client.post(
        "/console/api/workspaces/current/plugin/install/marketplace",
        json={"plugin_unique_identifiers": [identifier]},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        fail(f"插件安装请求失败: {r.status_code} {r.text[:300]}")
    task_id = r.json().get("task_id")
    if not task_id:
        fail(f"插件安装响应无 task_id: {r.text[:300]}")

    # 轮询安装任务（实测约 90s）
    log(f"  安装任务 {task_id} 执行中，轮询等待 ...")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(5)
        r = client.get(f"/console/api/workspaces/current/plugin/tasks/{task_id}", timeout=30)
        if r.status_code != 200:
            log(f"  任务查询返回 {r.status_code}，继续等待")
            continue
        task = r.json().get("task") or r.json()
        status = task.get("status", "")
        total = task.get("total_plugins", "?")
        done = task.get("completed_plugins", "?")
        log(f"  任务状态: {status} ({done}/{total})")
        if status == "success":
            log(f"✅ 插件 {PROVIDER_PLUGIN_ID} 安装完成")
            return
        if status == "failed":
            fail(f"插件安装失败: {r.text[:300]}")
    fail("插件安装超时（300s）")


def ensure_model_credential(client: httpx.Client) -> None:
    """添加 OpenAI-API-compatible 模型凭据（服务端实时校验模型可用性）"""
    base = f"/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}"
    # 幂等：已有同名模型凭据则跳过
    r = client.get(
        f"{base}/models/credentials",
        params={"model": DIFY_MODEL_NAME, "model_type": "llm"},
        timeout=30,
    )
    if r.status_code == 200 and r.json().get("credentials"):
        log(f"✅ 模型 {DIFY_MODEL_NAME} 凭据已存在，跳过添加")
        return

    log(f"添加模型凭据: {DIFY_MODEL_NAME} @ {DIFY_MODEL_BASE_URL} ...")
    r = client.post(
        f"{base}/models/credentials",
        json={
            "model": DIFY_MODEL_NAME,
            "model_type": "llm",
            "name": DIFY_MODEL_NAME,
            "credentials": {
                "api_key": DIFY_MODEL_API_KEY,
                "endpoint_url": DIFY_MODEL_BASE_URL,
                "mode": MODEL_MODE,
                "context_size": "8192",
                "max_tokens_to_sample": "4096",
                "function_calling_type": "tool_call",
                "stream_function_calling": "supported",
                "vision_support": "no_support",
            },
        },
        timeout=120,  # 服务端实时调用模型校验，可能较慢
    )
    if r.status_code not in (200, 201):
        fail(
            f"添加模型凭据失败: {r.status_code} {r.text[:400]}"
            "（服务端会实时调用模型校验；402=余额不足，请检查 DIFY_MODEL_* 配置与账户余额）"
        )
    log(f"✅ 模型凭据已添加（{DIFY_MODEL_NAME}）")


# ── 步骤 4：导入/创建应用 ─────────────────────────────────
def list_existing_apps(client: httpx.Client) -> dict:
    """返回 {app_name: {"id": ..., "mode": ...}}"""
    r = client.get("/console/api/apps", params={"page": 1, "limit": 100}, timeout=30)
    if r.status_code != 200:
        fail(f"查询应用列表失败: {r.status_code} {r.text[:300]}")
    return {a["name"]: {"id": a["id"], "mode": a.get("mode", "")}
            for a in r.json().get("data", []) or []}


def _import_advanced_chat(client: httpx.Client, name: str, dsl_content: str) -> str:
    """advanced-chat（Chatflow）走 DSL 导入；1.16 导入后需手动发布工作流"""
    r = client.post(
        "/console/api/apps/imports",
        json={"mode": "yaml-content", "yaml_content": dsl_content},
        timeout=120,
    )
    if r.status_code not in (200, 201):
        log(f"  ⚠️  {name} 导入返回 {r.status_code}: {r.text[:200]}")
        return ""
    d = r.json()
    app_id = d.get("app_id") or (d.get("data") or {}).get("app_id") or ""
    status = d.get("status") or (d.get("data") or {}).get("status")
    import_id = d.get("id") or (d.get("data") or {}).get("id")
    if status == "pending" and import_id:
        r2 = client.post(f"/console/api/apps/imports/{import_id}/confirm", json={}, timeout=60)
        if r2.status_code in (200, 201):
            d2 = r2.json()
            app_id = app_id or d2.get("app_id") or (d2.get("data") or {}).get("app_id") or ""
    if not app_id:
        log(f"  ⚠️  {name} 导入后未获得 app_id: {r.text[:200]}")
        return ""
    # 导入后工作流处于草稿态，必须发布才生效
    r3 = client.post(f"/console/api/apps/{app_id}/workflows/publish", json={}, timeout=60)
    if r3.status_code in (200, 201):
        log(f"  ✅ {name} 导入并发布成功 (id={app_id})")
    else:
        log(f"  ⚠️  {name} 导入成功但发布返回 {r3.status_code}: {r3.text[:200]}")
    return app_id


def _agent_chat_model_config(dsl: dict) -> dict:
    """由 DSL 骨架构造 1.16 agent-chat 的完整 model-config（GET 该接口对 agent-chat 返回 405，直接 POST）"""
    prompt = dsl.get("prompt") or {}
    model = dsl.get("model") or {}
    return {
        "model": {
            "provider": MODEL_PROVIDER,
            "name": DIFY_MODEL_NAME,
            "mode": MODEL_MODE,
            "completion_params": model.get("completion_params")
                                 or {"temperature": 0.7, "max_tokens": 4096},
        },
        "pre_prompt": prompt.get("pre_prompt", ""),
        "opening_statement": prompt.get("opening_statement", ""),
        "suggested_questions": prompt.get("suggested_questions", []),
        "prompt_type": "simple",
        "chat_prompt_config": {},
        "completion_prompt_config": {},
        "user_input_form": [],
        "agent_mode": {"enabled": True, "max_iteration": 5, "strategy": "function_call", "tools": []},
        "dataset_configs": {"retrieval_model": "single", "reranking_enable": False,
                            "datasets": {"datasets": []}},
    }


def _create_agent_chat(client: httpx.Client, name: str, app_meta: dict, cfg: dict) -> str:
    """agent-chat 的 DSL 骨架缺 1.16 model_config 块无法导入，改为创建空应用 + 写 model-config"""
    r = client.post(
        "/console/api/apps",
        json={
            "name": name,
            "description": app_meta.get("description", ""),
            "mode": "agent-chat",
            "icon_type": "emoji",
            "icon": app_meta.get("icon", "🤖"),
            "icon_background": app_meta.get("icon_background", "#FFEAD5"),
        },
        timeout=60,
    )
    if r.status_code not in (200, 201):
        log(f"  ⚠️  {name} 创建返回 {r.status_code}: {r.text[:200]}")
        return ""
    app_id = r.json().get("id", "")
    r2 = client.post(f"/console/api/apps/{app_id}/model-config", json=cfg, timeout=60)
    if r2.status_code in (200, 201):
        log(f"  ✅ {name} 创建并配置成功 (id={app_id})")
    else:
        log(f"  ⚠️  {name} 创建成功但 model-config 返回 {r2.status_code}: {r2.text[:200]}")
    return app_id


def import_apps(client: httpx.Client) -> dict:
    """导入/创建 dify/apps 下所有应用（幂等：按 yml 内 app.name 判重）。

    返回 {name: {"id", "mode", "dsl"?}}，dsl 仅 agent-chat 保留（重绑模型时用）。
    """
    existing = list_existing_apps(client)
    log(f"Dify 现有应用: {list(existing.keys()) or '(无)'}")

    apps = {name: dict(info) for name, info in existing.items()}
    yml_files = sorted(glob.glob(str(Path(APPS_DIR) / "*.yml")))
    if not yml_files:
        log(f"⚠️  {APPS_DIR} 下未找到 yml 文件")
        return apps

    for yml_path in yml_files:
        stem = Path(yml_path).stem
        content = Path(yml_path).read_text(encoding="utf-8")
        # 模型名占位符替换：yml 内统一写 your-model-name，导入前替换为实际模型名
        # （Chatflow 工作流 LLM 节点的模型取自 DSL 本身，app 级 model-config 改不到它，必须导入时注入）
        content = content.replace("your-model-name", DIFY_MODEL_NAME)
        try:
            dsl = yaml.safe_load(content)
        except yaml.YAMLError as e:
            log(f"  ⚠️  {stem} yml 解析失败: {e}，跳过")
            continue
        app_meta = dsl.get("app") or {}
        name = app_meta.get("name", stem)
        mode = app_meta.get("mode", "")
        if name in apps:
            log(f"  跳过已存在应用: {name}（{stem}）")
            if mode == "agent-chat":
                apps[name]["dsl"] = dsl
            continue
        if not AUTO_IMPORT:
            continue

        log(f"  导入应用: {name}（{mode}）...")
        if mode == "advanced-chat":
            app_id = _import_advanced_chat(client, name, content)
        elif mode == "agent-chat":
            app_id = _create_agent_chat(client, name, app_meta, _agent_chat_model_config(dsl))
        else:
            log(f"  ⚠️  {name} 未知 mode={mode}，跳过")
            continue
        if app_id:
            apps[name] = {"id": app_id, "mode": mode}
            if mode == "agent-chat":
                apps[name]["dsl"] = dsl

    return apps


# ── 步骤 5：为已存在应用重新绑定模型 ───────────────────────
def _rebind_advanced_chat(client: httpx.Client, name: str, app_id: str) -> None:
    """advanced-chat 的 LLM 节点模型在草稿工作流里：补丁草稿 → 发布"""
    r = client.get(f"/console/api/apps/{app_id}/workflows/draft", timeout=30)
    if r.status_code != 200:
        log(f"    获取草稿失败: {r.status_code}，跳过重绑")
        return
    draft = r.json()
    graph = draft.get("graph") or {}
    changed = False
    for node in graph.get("nodes", []):
        data = node.get("data") or {}
        if data.get("type") != "llm":
            continue
        data.setdefault("context", {"enabled": False, "variable_selector": []})
        data.setdefault("vision", {"enabled": False})
        m = data.setdefault("model", {})
        if m.get("provider") != MODEL_PROVIDER or m.get("name") != DIFY_MODEL_NAME:
            m["provider"] = MODEL_PROVIDER
            m["name"] = DIFY_MODEL_NAME
            m["mode"] = MODEL_MODE
            changed = True
    if not changed:
        log(f"    {name} 模型已是最新，跳过")
        return
    payload = {
        "graph": graph,
        "features": draft.get("features") or {},
        "environment_variables": draft.get("environment_variables") or [],
        "conversation_variables": draft.get("conversation_variables") or [],
        "hash": draft.get("hash") or draft.get("unique_hash"),  # 不带 hash 报 409
    }
    r2 = client.post(f"/console/api/apps/{app_id}/workflows/draft", json=payload, timeout=60)
    if r2.status_code not in (200, 201):
        log(f"    草稿更新返回 {r2.status_code}: {r2.text[:200]}")
        return
    r3 = client.post(f"/console/api/apps/{app_id}/workflows/publish", json={}, timeout=60)
    if r3.status_code in (200, 201):
        log(f"    ✅ {name} 已重绑 {DIFY_MODEL_NAME} 并发布")
    else:
        log(f"    ⚠️  发布返回 {r3.status_code}: {r3.text[:200]}")


def bind_model_to_apps(client: httpx.Client, apps: dict) -> None:
    """把当前 DIFY_MODEL_NAME 绑定到所有应用（幂等；新建应用导入时已绑定，自动跳过）"""
    for name, info in apps.items():
        log(f"  检查 {name} 的模型绑定 ...")
        if info.get("mode") == "advanced-chat":
            _rebind_advanced_chat(client, name, info["id"])
        elif info.get("mode") == "agent-chat" and info.get("dsl"):
            cfg = _agent_chat_model_config(info["dsl"])
            r = client.post(f"/console/api/apps/{info['id']}/model-config", json=cfg, timeout=60)
            if r.status_code in (200, 201):
                log(f"    ✅ {name} 已绑定 {DIFY_MODEL_NAME}")
            else:
                log(f"    ⚠️  绑定返回 {r.status_code}: {r.text[:200]}")
        else:
            log(f"    无 DSL 来源或未知 mode，跳过重绑")


# ── 步骤 6：输出 app key ──────────────────────────────────
def export_app_keys(client: httpx.Client, apps: dict) -> None:
    lines = [
        "# Dify 应用 API Key（由 dify-init 自动生成）",
        "# 请将下方 key 复制到 backend/.env 对应变量：",
    ]
    for app_name, env_name in APP_KEY_ENV_MAP.items():
        extra = "（留空则报告 AI 恒 unavailable）" if env_name == "DIFY_REPORT_AGENT_KEY" else ""
        lines.append(f"#   {app_name} -> {env_name}{extra}")
    lines.append("")

    for name, info in apps.items():
        app_id = info["id"]
        r = client.get(f"/console/api/apps/{app_id}/api-keys", timeout=30)
        key = ""
        if r.status_code == 200:
            keys = r.json().get("data", []) or []
            if keys:
                key = keys[0].get("token", "")
        if not key:
            # 没有 key 则创建一个
            r = client.post(f"/console/api/apps/{app_id}/api-keys", json={}, timeout=30)
            if r.status_code in (200, 201):
                key = r.json().get("token", "")
        lines.append(f"{name}={key}")

    output = "\n".join(lines) + "\n"
    Path(APP_KEYS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(APP_KEYS_FILE, "w", encoding="utf-8") as f:
        f.write(output)
    log(f"✅ App key 已写入 {APP_KEYS_FILE}")
    log("-" * 60)
    log(output)
    log("-" * 60)
    log("⚠️  请将上方业务 Agent 的 key 复制到 backend/.env，然后重启 backend")


# ── 主流程 ────────────────────────────────────────────────
def main() -> None:
    log("=" * 60)
    log("Dify 一键初始化开始（适配 Dify 1.16 Console API）")
    log(f"  DIFY_API_URL       = {DIFY_API_URL}")
    log(f"  DIFY_ADMIN_EMAIL   = {DIFY_ADMIN_EMAIL}")
    log(f"  DIFY_MODEL_NAME    = {DIFY_MODEL_NAME or '(空)'}")
    log(f"  DIFY_MODEL_BASE_URL= {DIFY_MODEL_BASE_URL or '(空)'}")
    log(f"  DIFY_MODEL_API_KEY = {'***' if DIFY_MODEL_API_KEY else '(空)'}")
    log(f"  AUTO_IMPORT        = {AUTO_IMPORT}")
    log(f"  AUTO_BIND_MODEL    = {AUTO_BIND}")
    log("=" * 60)

    # 模型配置完整性校验（fail-fast：配置不完整则初始化失败，阻塞 backend 启动）
    missing = [
        k for k, v in (
            ("DIFY_MODEL_API_KEY", DIFY_MODEL_API_KEY),
            ("DIFY_MODEL_BASE_URL", DIFY_MODEL_BASE_URL),
            ("DIFY_MODEL_NAME", DIFY_MODEL_NAME),
        ) if not v
    ]
    if missing:
        fail(
            f"模型配置不完整，缺少: {', '.join(missing)}。"
            "请在 dify/docker/.env 中填写三项模型配置（OpenAI-API-compatible，由客户自定义）"
        )

    wait_for_dify()

    with httpx.Client(base_url=DIFY_API_URL, timeout=60) as client:
        setup_and_login(client)
        ensure_provider_plugin(client)
        ensure_model_credential(client)

        log("导入/创建应用 ...")
        apps = import_apps(client)

        if AUTO_BIND and apps:
            log("绑定模型到应用 ...")
            bind_model_to_apps(client, apps)

        if apps:
            export_app_keys(client, apps)
        else:
            log("⚠️  无应用可导出 key")

    log("🎉 Dify 初始化全部完成")


if __name__ == "__main__":
    main()
