#!/usr/bin/env python3
"""
Dify 一键初始化脚本（dify-init 容器入口）
================================================
功能：
  1. 等待 Dify api 就绪
  2. 自动创建/登录 Dify 管理员
  3. 安装/确认 OpenAI-API-compatible 模型供应商插件 + 配置模型凭据
  4. 导入 dify/apps/ 下的所有应用 DSL yml（幂等）
     - advanced-chat: DSL 导入 + 发布工作流
     - agent-chat: 创建空应用 + POST model-config（DSL 缺 model_config 块无法直接导入）
  5. 为所有应用绑定模型（含 advanced-chat 草稿工作流 hash 补丁重绑）
  6. 输出 app key 到共享 Docker 卷，供 backend 启动时自动加载

依赖：httpx, pyyaml
运行环境：dify-init 容器内（与 Dify api 同 docker 网络）
"""

import base64
import glob
import json
import os
import sys
import time
from pathlib import Path

import httpx
import yaml

# ── 环境变量 ──────────────────────────────────────────────
DIFY_API_URL = os.environ.get("DIFY_API_URL", "http://api:5001")
DIFY_ADMIN_EMAIL = os.environ.get("DIFY_ADMIN_EMAIL", "admin@example.com")
DIFY_ADMIN_PASSWORD = os.environ.get("DIFY_ADMIN_PASSWORD", "")
DIFY_MODEL_API_KEY = os.environ.get("DIFY_MODEL_API_KEY", "")
DIFY_MODEL_BASE_URL = os.environ.get("DIFY_MODEL_BASE_URL", "")
DIFY_MODEL_NAME = os.environ.get("DIFY_MODEL_NAME", "")
AUTO_IMPORT = os.environ.get("DIFY_INIT_AUTO_IMPORT", "true").lower() == "true"
AUTO_BIND = os.environ.get("DIFY_INIT_AUTO_BIND_MODEL", "true").lower() == "true"
APPS_DIR = os.environ.get("DIFY_APPS_DIR", "/apps")
APP_KEYS_FILE = os.environ.get("DIFY_APP_KEYS_FILE", "/shared/app_keys.env")

# 模型供应商标识（OpenAI-API-compatible）
MODEL_PROVIDER = "langgenius/openai_api_compatible/openai_api_compatible"
MODEL_MODE = "chat"  # 业务应用均用对话模型
MARKETPLACE_API = "https://marketplace.dify.ai/api/v1"
PROVIDER_PLUGIN_ID = "langgenius/openai_api_compatible"

ARCHIVED_APP_FILES = {"智能报告__agent-chat.yml"}

APP_KEY_ENV_NAMES = {
    ("粤教客服Agent", "advanced-chat"): "DIFY_CUSTOMER_AGENT_KEY",
    ("企业员工助手", "agent-chat"): "DIFY_EMPLOYEE_AGENT_KEY",
    ("留学生智能管家", "agent-chat"): "DIFY_STUDENT_AGENT_KEY",
    ("智能报告", "advanced-chat"): "DIFY_REPORT_AGENT_KEY",
}


def log(msg: str) -> None:
    print(f"[dify-init] {msg}", flush=True)


def fail(msg: str) -> None:
    log(f"❌ {msg}")
    sys.exit(1)


# ── 步骤 1：等待 Dify 就绪 ────────────────────────────────
def wait_for_dify(timeout: int = 180) -> None:
    log(f"等待 Dify api 就绪：{DIFY_API_URL}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{DIFY_API_URL}/health", timeout=10)
            if r.status_code == 200:
                log("✅ Dify api 已就绪")
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    fail(f"Dify api 在 {timeout}s 内未就绪")


# ── 步骤 2：登录/创建管理员 ───────────────────────────────
def get_access_token(client: httpx.Client) -> str:
    """返回 console access_token"""
    if not DIFY_ADMIN_PASSWORD:
        fail("DIFY_ADMIN_PASSWORD 为空，请在 dify/docker/.env 中设置强密码")
    # 先检测是否已初始化
    try:
        r = client.get(f"{DIFY_API_URL}/console/api/setup", timeout=15)
        if r.status_code == 200:
            data = r.json()
            not_configured = data.get("step") == "not_started"
            if not_configured:
                log("Dify 未初始化，自动创建管理员...")
                r = client.post(
                    f"{DIFY_API_URL}/console/api/setup",
                    json={
                        "email": DIFY_ADMIN_EMAIL,
                        "name": "Admin",
                        "password": DIFY_ADMIN_PASSWORD,
                    },
                    timeout=30,
                )
                if r.status_code not in (200, 201):
                    fail(f"创建管理员失败: {r.status_code} {r.text[:300]}")
                log("✅ 管理员创建成功")
            else:
                log("Dify 已初始化，使用预设账号登录")
        else:
            log(f"setup 检测返回 {r.status_code}，尝试直接登录")
    except httpx.HTTPError as e:
        fail(f"检测 Dify 初始化状态失败: {e}")

    # 登录
    r = client.post(
        f"{DIFY_API_URL}/console/api/login",
        json={
            "email": DIFY_ADMIN_EMAIL,
            "password": base64.b64encode(DIFY_ADMIN_PASSWORD.encode("utf-8")).decode("ascii"),
            "remember_me": True,
        },
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"登录失败: {r.status_code} {r.text[:300]}（检查 DIFY_ADMIN_EMAIL/PASSWORD）")
    csrf_token = client.cookies.get("csrf_token")
    if csrf_token:
        client.headers["X-CSRF-Token"] = csrf_token
    log("✅ 管理员登录成功")
    return ""


# ── 步骤 3：安装模型供应商插件 + 配置模型凭据 ──────────────
def ensure_provider_plugin(client: httpx.Client) -> None:
    """确保 OpenAI-API-compatible 插件已安装；未安装则从 marketplace 安装并轮询"""
    r = client.get(
        f"{DIFY_API_URL}/console/api/workspaces/current/plugin/list",
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
        f"{DIFY_API_URL}/console/api/workspaces/current/plugin/install/marketplace",
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
        r = client.get(f"{DIFY_API_URL}/console/api/workspaces/current/plugin/tasks/{task_id}", timeout=30)
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


def setup_model_provider(client: httpx.Client) -> None:
    """确认插件已安装，然后配置模型凭据并激活模型"""
    # 先确认插件已安装
    ensure_provider_plugin(client)

    credentials_url = f"{DIFY_API_URL}/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}/models/credentials"
    params = {"model": DIFY_MODEL_NAME, "model_type": "llm", "config_from": "custom-model"}
    r = client.get(credentials_url, params=params, timeout=30)
    if r.status_code != 200:
        fail(f"查询模型凭据失败: {r.status_code} {r.text[:200]}")

    credential_data = r.json()
    credential_id = credential_data.get("current_credential_id")
    if not credential_id:
        # 不存在则创建
        r = client.post(
            credentials_url,
            json={
                "model": DIFY_MODEL_NAME,
                "model_type": "llm",
                "name": DIFY_MODEL_NAME,
                "credentials": {
                    "api_key": DIFY_MODEL_API_KEY,
                    "endpoint_url": DIFY_MODEL_BASE_URL,
                    "api_type": "chat_completions",
                },
            },
            timeout=120,
        )
        if r.status_code not in (200, 201):
            fail(f"保存模型凭据失败: {r.status_code} {r.text[:400]}")
        r = client.get(credentials_url, params=params, timeout=30)
        if r.status_code != 200:
            fail(f"确认模型凭据失败: {r.status_code} {r.text[:200]}")
        credential_data = r.json()
        credential_id = credential_data.get("current_credential_id")

    if not credential_id:
        available = credential_data.get("available_credentials") or []
        credential_id = next((item.get("credential_id") for item in available if item.get("credential_id")), None)
    if not credential_id:
        fail("模型凭据已提交，但 Dify 未返回 credential_id")

    # 激活模型
    r = client.post(
        f"{DIFY_API_URL}/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}/models",
        json={
            "model": DIFY_MODEL_NAME,
            "model_type": "llm",
            "config_from": "custom-model",
            "credential_id": credential_id,
        },
        timeout=30,
    )
    if r.status_code not in (200, 201):
        fail(f"激活模型失败: {r.status_code} {r.text[:200]}")
    log(f"✅ 模型已配置并激活（{DIFY_MODEL_NAME}）")


# ── 步骤 4：导入应用 yml ──────────────────────────────────
def _app_identity(dsl: dict) -> tuple[str, str]:
    """从 Dify DSL 读取稳定应用标识（显示名称 + 模式）。"""
    app = dsl.get("app") or {}
    name = str(app.get("name") or "").strip()
    mode = str(app.get("mode") or "").strip()
    if not name or not mode:
        raise ValueError("DSL 缺少 app.name 或 app.mode")
    return name, mode


def list_existing_apps(client: httpx.Client) -> dict[str, str]:
    """返回 {app_name: app_id}。"""
    r = client.get(f"{DIFY_API_URL}/console/api/apps?page=1&limit=100", timeout=30)
    if r.status_code != 200:
        fail(f"查询应用列表失败: {r.status_code} {r.text[:300]}")
    apps = r.json().get("data", []) or []
    return {str(a["name"]).strip(): a["id"] for a in apps if a.get("name") and a.get("id")}


def _agent_chat_model_config(dsl: dict) -> dict:
    """由 DSL 骨架构造 1.16 agent-chat 的完整 model-config（GET 该接口对 agent-chat 返回 405，直接 POST）"""
    prompt = dsl.get("prompt") or {}
    model = dsl.get("model") or {}
    return {
        "model": {
            "provider": MODEL_PROVIDER,
            "name": DIFY_MODEL_NAME,
            "mode": MODEL_MODE,
            "completion_params": model.get("completion_params") or {"temperature": 0.7, "max_tokens": 4096},
        },
        "pre_prompt": prompt.get("pre_prompt", ""),
        "opening_statement": prompt.get("opening_statement", ""),
        "suggested_questions": prompt.get("suggested_questions", []),
        "prompt_type": "simple",
        "chat_prompt_config": {},
        "completion_prompt_config": {},
        "user_input_form": [],
        "agent_mode": {"enabled": True, "max_iteration": 5, "strategy": "function_call", "tools": []},
        "dataset_configs": {"retrieval_model": "single", "reranking_enable": False, "datasets": {"datasets": []}},
    }


def _import_advanced_chat(client: httpx.Client, name: str, dsl_content: str) -> str:
    """advanced-chat（Chatflow）走 DSL 导入；1.16 导入后需手动发布工作流"""
    r = client.post(
        f"{DIFY_API_URL}/console/api/apps/imports",
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
        r2 = client.post(f"{DIFY_API_URL}/console/api/apps/imports/{import_id}/confirm", json={}, timeout=60)
        if r2.status_code in (200, 201):
            d2 = r2.json()
            app_id = app_id or d2.get("app_id") or (d2.get("data") or {}).get("app_id") or ""
    if not app_id:
        log(f"  ⚠️  {name} 导入后未获得 app_id: {r.text[:200]}")
        return ""
    # 导入后工作流处于草稿态，必须发布才生效
    r3 = client.post(f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/publish", json={}, timeout=60)
    if r3.status_code in (200, 201):
        log(f"  ✅ {name} 导入并发布成功 (id={app_id})")
    else:
        log(f"  ⚠️  {name} 导入成功但发布返回 {r3.status_code}: {r3.text[:200]}")
    return app_id


def _create_agent_chat(client: httpx.Client, name: str, app_meta: dict, cfg: dict) -> str:
    """agent-chat 的 DSL 骨架缺 1.16 model_config 块无法导入，改为创建空应用 + 写 model-config"""
    r = client.post(
        f"{DIFY_API_URL}/console/api/apps",
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
    r2 = client.post(f"{DIFY_API_URL}/console/api/apps/{app_id}/model-config", json=cfg, timeout=60)
    if r2.status_code in (200, 201):
        log(f"  ✅ {name} 创建并配置成功 (id={app_id})")
    else:
        log(f"  ⚠️  {name} 创建成功但 model-config 返回 {r2.status_code}: {r2.text[:200]}")
    return app_id


def import_apps(client: httpx.Client) -> dict[str, dict]:
    """导入/创建 dify/apps 下所有应用（幂等：按 yml 内 app.name 判重）。

    返回 {name: {"id": ..., "mode": ..., "dsl"?}}，dsl 仅 agent-chat 保留（重绑模型时用）。
    """
    all_existing = list_existing_apps(client)
    yml_files = sorted(glob.glob(str(Path(APPS_DIR) / "*.yml")))
    managed_names = set()
    for yml_path in yml_files:
        path = Path(yml_path)
        if path.name in ARCHIVED_APP_FILES:
            continue
        try:
            dsl = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            managed_names.add(_app_identity(dsl)[0])
        except (yaml.YAMLError, ValueError):
            continue
    existing = {
        name: {"id": app_id, "mode": ""}
        for name, app_id in all_existing.items() if name in managed_names
    }
    log(f"Dify 现有应用: {list(existing.keys()) or '(无)'}")
    if not yml_files:
        log(f"⚠️  {APPS_DIR} 下未找到 yml 文件")
        return existing

    for yml_path in yml_files:
        path = Path(yml_path)
        if path.name in ARCHIVED_APP_FILES:
            log(f"  跳过留档应用: {path.name}")
            continue
        content = path.read_text(encoding="utf-8")
        # 模型名占位符替换：yml 内统一写 your-model-name，导入前替换为客户配置的模型名
        content = content.replace("your-model-name", DIFY_MODEL_NAME)
        try:
            dsl = yaml.safe_load(content) or {}
            name, mode = _app_identity(dsl)
        except (yaml.YAMLError, ValueError) as e:
            log(f"  ⚠️  {path.name} DSL 无效，跳过: {e}")
            continue

        if name in existing:
            log(f"  跳过已存在应用: {name}（{path.stem}）")
            if mode == "agent-chat":
                existing[name]["dsl"] = dsl
            continue

        log(f"  导入应用: {name}（{mode}）...")
        if mode == "advanced-chat":
            app_id = _import_advanced_chat(client, name, content)
        elif mode == "agent-chat":
            app_id = _create_agent_chat(client, name, dsl.get("app") or {}, _agent_chat_model_config(dsl))
        else:
            log(f"  ⚠️  {name} 未知 mode={mode}，跳过")
            continue
        if app_id:
            existing[name] = {"id": app_id, "mode": mode}
            if mode == "agent-chat":
                existing[name]["dsl"] = dsl

    return existing


# ── 步骤 5：为已存在应用重新绑定模型 ───────────────────────
def _rebind_advanced_chat(client: httpx.Client, name: str, app_id: str) -> None:
    """advanced-chat 的 LLM 节点模型在草稿工作流里：补丁草稿 → 发布"""
    r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/draft", timeout=30)
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
    r2 = client.post(f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/draft", json=payload, timeout=60)
    if r2.status_code not in (200, 201):
        log(f"    草稿更新返回 {r2.status_code}: {r2.text[:200]}")
        return
    r3 = client.post(f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/publish", json={}, timeout=60)
    if r3.status_code in (200, 201):
        log(f"    ✅ {name} 已重绑 {DIFY_MODEL_NAME} 并发布")
    else:
        log(f"    ⚠️  发布返回 {r3.status_code}: {r3.text[:200]}")


def bind_model_to_apps(client: httpx.Client, apps: dict) -> None:
    """把当前 DIFY_MODEL_NAME 绑定到所有应用（幂等）"""
    for name, info in apps.items():
        log(f"  检查 {name} 的模型绑定 ...")
        if info.get("mode") == "advanced-chat":
            _rebind_advanced_chat(client, name, info["id"])
        elif info.get("mode") == "agent-chat" and info.get("dsl"):
            cfg = _agent_chat_model_config(info["dsl"])
            r = client.post(f"{DIFY_API_URL}/console/api/apps/{info['id']}/model-config", json=cfg, timeout=60)
            if r.status_code in (200, 201):
                log(f"    ✅ {name} 已绑定 {DIFY_MODEL_NAME}")
            else:
                log(f"    ⚠️  绑定返回 {r.status_code}: {r.text[:200]}")
        else:
            # 通用回退：尝试 GET model-config（部分模式可能支持）
            app_id = info["id"]
            r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}/model-config", timeout=30)
            if r.status_code != 200:
                log(f"    获取 model-config 失败: {r.status_code}，跳过")
                continue
            current = r.json()
            current["model"]["provider"] = MODEL_PROVIDER
            current["model"]["name"] = DIFY_MODEL_NAME
            current["model"]["mode"] = MODEL_MODE
            r = client.post(f"{DIFY_API_URL}/console/api/apps/{app_id}/model-config", json=current, timeout=30)
            if r.status_code in (200, 201):
                log(f"    ✅ {name} 已绑定 {DIFY_MODEL_NAME}")
            else:
                log(f"    ⚠️  绑定返回 {r.status_code}: {r.text[:200]}")


# ── 步骤 6：输出 app key ──────────────────────────────────
def export_app_keys(client: httpx.Client, apps: dict) -> None:
    lines = [
        "# Dify 应用 API Key（由 dify-init 自动生成）",
        "# 由 backend 容器启动时自动加载；不要提交或公开此文件。",
        "",
    ]
    for name, info in apps.items():
        app_id = info["id"]
        r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}/api-keys", timeout=30)
        key = ""
        if r.status_code == 200:
            keys = r.json().get("data", []) or []
            if keys:
                key = keys[0].get("token", "")
        if not key:
            # 没有 key 则创建一个
            r = client.post(f"{DIFY_API_URL}/console/api/apps/{app_id}/api-keys", json={}, timeout=30)
            if r.status_code in (200, 201):
                key = r.json().get("token", "")
        env_name = APP_KEY_ENV_NAMES.get((name, "agent-chat")) or APP_KEY_ENV_NAMES.get((name, "advanced-chat"))
        if env_name:
            lines.append(f"{env_name}={key}")
            lines.append("")

    output = "\n".join(lines)
    Path(APP_KEYS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(APP_KEYS_FILE, "w", encoding="utf-8") as f:
        f.write(output)
    try:
        os.chmod(APP_KEYS_FILE, 0o600)
    except OSError:
        pass  # Windows 环境忽略
    log(f"✅ App key 已写入 {APP_KEYS_FILE}")
    log("App key 已保存到受限共享卷，backend 将在启动时自动加载；密钥不输出到日志。")


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
        get_access_token(client)
        setup_model_provider(client)

        apps = {}
        if AUTO_IMPORT:
            log("导入应用 ...")
            apps = import_apps(client)
        else:
            apps = list_existing_apps(client)

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
