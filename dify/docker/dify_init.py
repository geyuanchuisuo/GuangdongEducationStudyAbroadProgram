#!/usr/bin/env python3
"""
Dify 一键初始化脚本（dify-init 容器入口）
================================================
功能：
  1. 等待 Dify api 就绪
  2. 自动创建/登录 Dify 管理员
  3. 添加 OpenAI-API-compatible 模型供应商
  4. 导入 dify/apps/ 下的所有应用 DSL yml（幂等）
  5. 为所有应用绑定模型
  6. 输出 app key 到 dify/docker/app_keys.txt

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
DIFY_ADMIN_PASSWORD = os.environ.get("DIFY_ADMIN_PASSWORD", "Difyadmin2026")
DIFY_MODEL_API_KEY = os.environ.get("DIFY_MODEL_API_KEY", "")
DIFY_MODEL_BASE_URL = os.environ.get("DIFY_MODEL_BASE_URL", "")
DIFY_MODEL_NAME = os.environ.get("DIFY_MODEL_NAME", "")
AUTO_IMPORT = os.environ.get("DIFY_INIT_AUTO_IMPORT", "true").lower() == "true"
AUTO_BIND = os.environ.get("DIFY_INIT_AUTO_BIND_MODEL", "true").lower() == "true"
APPS_DIR = os.environ.get("DIFY_APPS_DIR", "/apps")
APP_KEYS_FILE = os.environ.get("DIFY_APP_KEYS_FILE", "/output/app_keys.txt")

# 模型供应商标识（Dify 1.16 插件化：OpenAI-API-compatible 供应商 = 模型插件，三段式标识）
MODEL_PROVIDER = "langgenius/openai_api_compatible/openai_api_compatible"
MODEL_PLUGIN_ID = "langgenius/openai_api_compatible"
MARKETPLACE_API_URL = "https://marketplace.dify.ai"
MODEL_MODE = "chat"  # 业务应用均用对话模型


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
            # 探 /console/api/setup（业务级探活）：/health 不查 DB，DB 未就绪时会「假 healthy」
            r = httpx.get(f"{DIFY_API_URL}/console/api/setup", timeout=10)
            if r.status_code == 200:
                log("✅ Dify api 已就绪")
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    fail(f"Dify api 在 {timeout}s 内未就绪")


def _b64pwd(password: str) -> str:
    """Dify console 接口要求密码字段 base64 编码（前端 btoa 行为）"""
    return base64.b64encode(password.encode("utf-8")).decode("ascii")


# ── 步骤 2：登录/创建管理员 ───────────────────────────────
def _create_admin(client: httpx.Client) -> None:
    log("Dify 未初始化，自动创建管理员...")
    # 注意：setup 接口无解码装饰器，password 传明文（valid_password 校验+原样哈希存储）；
    # login 接口则要求 base64（decrypt_password_field 服务端解码）——两者契约不同
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


def get_access_token(client: httpx.Client) -> str:
    """返回 console access_token"""
    # 先检测是否已初始化
    try:
        r = client.get(f"{DIFY_API_URL}/console/api/setup", timeout=15)
        if r.status_code == 200:
            data = r.json() or {}
            # Dify 1.16 状态 schema：{"step": "not_started"|"finished", "setup_at": ...}
            step = data.get("step")
            not_configured = (
                step == "not_started"
                if step is not None
                else (data.get("not_configured") or not (data.get("setup_at") or data.get("setup_time")))
            )
            if not_configured:
                _create_admin(client)
            else:
                log("Dify 已初始化，使用预设账号登录")
        else:
            log(f"setup 检测返回 {r.status_code}，尝试直接登录")
    except httpx.HTTPError as e:
        fail(f"检测 Dify 初始化状态失败: {e}")

    # 登录（401 not_setup 时兜底：自动初始化后重试一次）
    r = client.post(
        f"{DIFY_API_URL}/console/api/login",
        json={"email": DIFY_ADMIN_EMAIL, "password": _b64pwd(DIFY_ADMIN_PASSWORD), "remember_me": True},
        timeout=30,
    )
    if r.status_code != 200 and "not_setup" in r.text:
        log("登录返回 not_setup，执行初始化后重试...")
        _create_admin(client)
        r = client.post(
            f"{DIFY_API_URL}/console/api/login",
            json={"email": DIFY_ADMIN_EMAIL, "password": _b64pwd(DIFY_ADMIN_PASSWORD), "remember_me": True},
            timeout=30,
        )
    if r.status_code != 200:
        fail(f"登录失败: {r.status_code} {r.text[:300]}（检查 DIFY_ADMIN_EMAIL/PASSWORD）")
    token = r.json().get("access_token") or ""
    if token:
        log("✅ 管理员登录成功（token 模式）")
    else:
        # Dify 1.16 控制台登录只回 {"result":"success"}，会话走 cookie + X-CSRF-Token（不下发 token）
        log("✅ 管理员登录成功（cookie 会话模式）")
    return token


def build_headers(client: httpx.Client, token: str) -> dict:
    """认证头：兼容 token 模式（Bearer）与 cookie 会话模式（X-CSRF-Token）"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    csrf = client.cookies.get("csrf_token") or client.cookies.get("X-CSRF-Token")
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return headers


# ── 步骤 2.5：确保模型插件已安装（Dify 1.16 插件化，OpenAI-API-compatible 供应商=插件）──
def ensure_model_plugin(client: httpx.Client, token: str) -> None:
    headers = build_headers(client, token)
    r = client.get(
        f"{DIFY_API_URL}/console/api/workspaces/current/model-providers",
        headers=headers,
        params={"model_type": "llm"},
        timeout=30,
    )
    if r.status_code == 200 and any(
        p.get("provider") == MODEL_PROVIDER for p in (r.json().get("data") or [])
    ):
        log(f"模型插件 {MODEL_PLUGIN_ID} 已就位，跳过安装")
        return

    log(f"模型插件 {MODEL_PLUGIN_ID} 未安装，从 marketplace 获取最新包标识 ...")
    try:
        r = httpx.post(
            f"{MARKETPLACE_API_URL}/api/v1/plugins/batch",
            json={"plugin_ids": [MODEL_PLUGIN_ID]},
            headers={"X-Dify-Version": "1.16.0-rc1"},
            timeout=30,
        )
        plugins = (r.json().get("data") or {}).get("plugins") or []
        ident = plugins[0].get("latest_package_identifier") if plugins else None
        if not ident:
            fail(f"marketplace 未返回 {MODEL_PLUGIN_ID} 的包标识")
    except httpx.HTTPError as e:
        fail(f"访问 marketplace 失败（需外网）: {e}")

    log(f"安装模型插件: {ident} ...")
    r = client.post(
        f"{DIFY_API_URL}/console/api/workspaces/current/plugin/install/marketplace",
        headers=headers,
        json={"plugin_unique_identifiers": [ident]},
        timeout=60,
    )
    if r.status_code != 200:
        fail(f"安装模型插件失败: {r.status_code} {r.text[:300]}")

    # 轮询安装任务直到 success（插件含依赖编译，最长等 240s）
    for _ in range(40):
        time.sleep(6)
        r = client.get(
            f"{DIFY_API_URL}/console/api/workspaces/current/plugin/tasks",
            headers=headers,
            params={"page": 1, "page_size": 5},
            timeout=30,
        )
        if r.status_code != 200:
            continue
        for task in (r.json().get("tasks") or []):
            for p in task.get("plugins") or []:
                if p.get("plugin_id") == MODEL_PLUGIN_ID:
                    if p.get("status") == "success":
                        log("✅ 模型插件安装完成")
                        return
                    if p.get("status") in ("failed", "error"):
                        fail(f"模型插件安装失败: {p.get('message')}")
    fail("模型插件安装超时（240s）")


# ── 步骤 3：添加模型供应商 ────────────────────────────────
def setup_model_provider(client: httpx.Client, token: str) -> None:
    headers = build_headers(client, token)
    # 查询现有模型供应商（Dify 1.16：/workspaces/current/model-providers），避免重复
    r = client.get(
        f"{DIFY_API_URL}/console/api/workspaces/current/model-providers",
        headers=headers,
        params={"model_type": "llm"},
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"查询模型供应商失败: {r.status_code} {r.text[:300]}")

    providers = r.json().get("data", []) or []
    exists = any(p.get("provider") == MODEL_PROVIDER for p in providers)

    if exists:
        log(f"模型供应商 {MODEL_PROVIDER} 已存在，跳过添加")
    else:
        log(f"添加模型供应商 {MODEL_PROVIDER} 凭证 ...")
        # Dify 1.16：POST .../credentials 保存供应商凭证（服务端会校验凭证有效性）
        r = client.post(
            f"{DIFY_API_URL}/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}/credentials",
            headers=headers,
            json={
                "credentials": {
                    "api_key": DIFY_MODEL_API_KEY,
                    "base_url": DIFY_MODEL_BASE_URL,
                    "mode": MODEL_MODE,
                },
                "name": "default",
            },
            timeout=60,
        )
        if r.status_code not in (200, 201):
            fail(f"添加模型供应商失败: {r.status_code} {r.text[:300]}")
        log(f"✅ 模型供应商已添加（base_url={DIFY_MODEL_BASE_URL}）")

    # 查询该供应商下的可用模型，确认模型名存在
    r = client.get(
        f"{DIFY_API_URL}/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}/models",
        headers=headers,
        timeout=30,
    )
    model_names = []
    if r.status_code == 200:
        models = r.json().get("data", []) or []
        model_names = [m.get("model") for m in models]
    if DIFY_MODEL_NAME not in model_names:
        # 自定义模型型供应商：需单独注册模型（Dify 1.16 models/credentials；数值字段为字符串）
        log(f"注册自定义模型 {DIFY_MODEL_NAME} ...")
        r = client.post(
            f"{DIFY_API_URL}/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}/models/credentials",
            headers=headers,
            json={
                "model": DIFY_MODEL_NAME,
                "model_type": "llm",
                "credentials": {
                    "api_key": DIFY_MODEL_API_KEY,
                    "endpoint_url": DIFY_MODEL_BASE_URL,
                    "mode": MODEL_MODE,
                    "context_size": "8192",
                    "max_tokens_to_sample": "4096",
                },
            },
            timeout=60,
        )
        if r.status_code in (200, 201):
            log(f"✅ 自定义模型 {DIFY_MODEL_NAME} 注册成功")
        else:
            fail(f"注册自定义模型失败: {r.status_code} {r.text[:300]}")


# ── 步骤 4：导入应用 yml ──────────────────────────────────
def list_existing_apps(client: httpx.Client, token: str) -> dict:
    """返回 {app_name: app_id}"""
    headers = build_headers(client, token)
    r = client.get(f"{DIFY_API_URL}/console/api/apps?page=1&limit=100", headers=headers, timeout=30)
    if r.status_code != 200:
        fail(f"查询应用列表失败: {r.status_code} {r.text[:300]}")
    apps = r.json().get("data", []) or []
    return {a["name"]: a["id"] for a in apps}


def import_apps(client: httpx.Client, token: str) -> dict:
    """导入 yml，返回 {app_name: app_id}（含已存在的）"""
    headers = build_headers(client, token)
    existing = list_existing_apps(client, token)
    log(f"Dify 现有应用: {list(existing.keys())}")

    yml_files = sorted(glob.glob(str(Path(APPS_DIR) / "*.yml")))
    if not yml_files:
        log(f"⚠️  {APPS_DIR} 下未找到 yml 文件")
        return existing

    for yml_path in yml_files:
        name = Path(yml_path).stem  # 文件名（去掉 .yml）
        if name in existing:
            log(f"  跳过已存在应用: {name}")
            continue
        log(f"  导入应用: {name} ...")
        with open(yml_path, "r", encoding="utf-8") as f:
            dsl_content = f.read()
        # 模型占位符替换：yml 内统一写 your-model-name / your-model-provider，导入前替换为客户配置值
        # （Chatflow 工作流 LLM 节点的模型取自 DSL 本身，app 级 model-config 改不到它，必须导入时注入）
        dsl_content = dsl_content.replace("your-model-name", DIFY_MODEL_NAME)
        dsl_content = dsl_content.replace("your-model-provider", MODEL_PROVIDER)
        # 尝试解析 yaml 确认格式合法
        try:
            yaml.safe_load(dsl_content)
        except yaml.YAMLError as e:
            log(f"  ⚠️  {name} yml 格式警告: {e}")

        r = client.post(
            f"{DIFY_API_URL}/console/api/apps/imports",
            headers=headers,
            json={"mode": "yaml-content", "yaml_content": dsl_content},
            timeout=120,
        )
        if r.status_code in (200, 201, 202):
            log(f"  ✅ {name} 导入成功")
        else:
            log(f"  ⚠️  {name} 导入返回 {r.status_code}: {r.text[:200]}，尝试继续")

    # 导入后统一重查应用列表，拿最新 name→id 映射（导入接口两步式，不依赖响应体）
    return list_existing_apps(client, token)


# ── 步骤 5：绑定模型 ──────────────────────────────────────
def bind_model_to_apps(client: httpx.Client, token: str, apps: dict) -> None:
    headers = build_headers(client, token)
    for name, app_id in apps.items():
        log(f"  绑定模型到 {name} ...")
        # 先获取当前 model-config 结构
        r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}/model-config", headers=headers, timeout=30)
        if r.status_code != 200:
            log(f"    获取 model-config 失败: {r.status_code}，跳过")
            continue
        current = r.json()
        # 用新模型覆盖
        current["model"]["provider"] = MODEL_PROVIDER
        current["model"]["name"] = DIFY_MODEL_NAME
        current["model"]["mode"] = MODEL_MODE
        r = client.post(
            f"{DIFY_API_URL}/console/api/apps/{app_id}/model-config",
            headers=headers,
            json=current,
            timeout=30,
        )
        if r.status_code in (200, 201):
            log(f"    ✅ {name} 已绑定 {DIFY_MODEL_NAME}")
        else:
            log(f"    ⚠️  绑定返回 {r.status_code}: {r.text[:200]}")


# ── 步骤 5.5：发布工作流（advanced-chat 导入后未发布，调 API 报 Workflow not published）──
def publish_workflows(client: httpx.Client, token: str, apps: dict) -> None:
    headers = build_headers(client, token)
    for name, app_id in apps.items():
        r = client.post(
            f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/publish",
            headers=headers,
            json={},
            timeout=30,
        )
        if r.status_code in (200, 201):
            log(f"    ✅ {name} 工作流已发布")
        else:
            log(f"    （{name} 非工作流应用或已发布，跳过：{r.status_code}）")


# ── 步骤 6：输出 app key ──────────────────────────────────
def export_app_keys(client: httpx.Client, token: str, apps: dict) -> None:
    headers = build_headers(client, token)
    lines = [
        "# Dify 应用 API Key（由 dify-init 自动生成）",
        "# 请将下方 key 复制到 backend/.env 对应变量：",
        "#   留学生智能管家 -> DIFY_STUDENT_AGENT_KEY",
        "#   企业员工助手   -> DIFY_EMPLOYEE_AGENT_KEY",
        "#   粤教客服       -> DIFY_CUSTOMER_AGENT_KEY",
        "#   智能报告       -> DIFY_REPORT_AGENT_KEY（留空则报告 AI 恒 unavailable）",
        "",
    ]
    for name, app_id in apps.items():
        r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}/api-keys", headers=headers, timeout=30)
        key = ""
        if r.status_code == 200:
            keys = r.json().get("data", []) or []
            if keys:
                key = keys[0].get("token", "")
        if not key:
            # 没有 key 则创建一个
            r = client.post(
                f"{DIFY_API_URL}/console/api/apps/{app_id}/api-keys",
                headers=headers,
                json={},
                timeout=30,
            )
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
    log("⚠️  请将上方三个业务 Agent 的 key 复制到 backend/.env，然后重启 backend")


# ── 主流程 ────────────────────────────────────────────────
def main() -> None:
    log("=" * 60)
    log("Dify 一键初始化开始")
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

    with httpx.Client() as client:
        token = get_access_token(client)
        ensure_model_plugin(client, token)
        setup_model_provider(client, token)

        apps = {}
        if AUTO_IMPORT:
            log("导入应用 DSL ...")
            apps = import_apps(client, token)
        else:
            apps = list_existing_apps(client, token)

        if AUTO_BIND and apps:
            log("绑定模型到应用 ...")
            bind_model_to_apps(client, token, apps)
            log("发布工作流 ...")
            publish_workflows(client, token, apps)

        if apps:
            export_app_keys(client, token, apps)
        else:
            log("⚠️  无应用可导出 key")

    log("🎉 Dify 初始化全部完成")


if __name__ == "__main__":
    main()
