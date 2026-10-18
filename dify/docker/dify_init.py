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
  6. 输出 app key 到共享 Docker 卷，供 backend 启动时自动加载

依赖：httpx, pyyaml
运行环境：dify-init 容器内（与 Dify api 同 docker 网络）
"""

import glob
import base64
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


# ── 步骤 3：添加模型供应商 ────────────────────────────────
def setup_model_provider(client: httpx.Client, token: str) -> None:
    # Dify 1.16 的供应商来自插件，先确认 OpenAI 兼容插件已安装。
    r = client.get(
        f"{DIFY_API_URL}/console/api/workspaces/current/model-providers?model_type=llm",
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"查询模型供应商失败: {r.status_code} {r.text[:300]}")

    providers = r.json().get("data", []) or []
    exists = any(p.get("provider") == MODEL_PROVIDER for p in providers)
    if not exists:
        fail(
            "Dify 1.16 尚未安装 OpenAI-API-compatible Marketplace 插件，"
            "无法配置模型。请先恢复 Marketplace 访问并安装插件后重试。"
        )

    credentials_url = f"{DIFY_API_URL}/console/api/workspaces/current/model-providers/{MODEL_PROVIDER}/models/credentials"
    params = {"model": DIFY_MODEL_NAME, "model_type": "llm", "config_from": "custom-model"}
    r = client.get(credentials_url, params=params, timeout=30)
    if r.status_code != 200:
        fail(f"查询模型凭据失败: {r.status_code} {r.text[:200]}")

    credential_data = r.json()
    credential_id = credential_data.get("current_credential_id")
    if not credential_id:
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
            timeout=45,
        )
        if r.status_code not in (200, 201):
            fail(f"保存模型凭据失败: {r.status_code} {r.text[:200]}")
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
    log(f"✅ 模型已配置（{DIFY_MODEL_NAME}）")


# ── 步骤 4：导入应用 yml ──────────────────────────────────
def _app_identity(dsl: dict) -> tuple[str, str]:
    """从 Dify DSL 读取稳定应用标识（显示名称 + 模式）。"""
    app = dsl.get("app") or {}
    name = str(app.get("name") or "").strip()
    mode = str(app.get("mode") or "").strip()
    if not name or not mode:
        raise ValueError("DSL 缺少 app.name 或 app.mode")
    return name, mode


def _find_existing_app(apps: dict[str, str], name: str) -> str | None:
    """按共用应用名称去重，同名应用只保留一个实例。"""
    return apps.get(name)


def list_existing_apps(client: httpx.Client, token: str) -> dict[str, str]:
    """返回 {app_name: app_id}。"""
    headers = {}
    r = client.get(f"{DIFY_API_URL}/console/api/apps?page=1&limit=100", headers=headers, timeout=30)
    if r.status_code != 200:
        fail(f"查询应用列表失败: {r.status_code} {r.text[:300]}")
    apps = r.json().get("data", []) or []
    return {str(a["name"]).strip(): a["id"] for a in apps if a.get("name") and a.get("id")}


def import_apps(client: httpx.Client, token: str) -> dict[str, str]:
    """导入在用 DSL；按 DSL 应用名去重，跳过留档应用。"""
    headers = {}
    all_existing = list_existing_apps(client, token)
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
        name: app_id for name, app_id in all_existing.items() if name in managed_names
    }
    log(f"Dify 现有应用: {list(existing.keys())}")
    if not yml_files:
        log(f"⚠️  {APPS_DIR} 下未找到 yml 文件")
        return existing

    for yml_path in yml_files:
        path = Path(yml_path)
        if path.name in ARCHIVED_APP_FILES:
            log(f"  跳过留档应用: {path.name}")
            continue
        with open(yml_path, "r", encoding="utf-8") as f:
            dsl_content = f.read()
        # 模型名占位符替换：yml 内统一写 your-model-name，导入前替换为客户配置的模型名
        # （Chatflow 工作流 LLM 节点的模型取自 DSL 本身，app 级 model-config 改不到它，必须导入时注入）
        dsl_content = dsl_content.replace("your-model-name", DIFY_MODEL_NAME)
        # 尝试解析 yaml 确认格式合法
        try:
            dsl = yaml.safe_load(dsl_content) or {}
            identity = _app_identity(dsl)
        except (yaml.YAMLError, ValueError) as e:
            log(f"  ⚠️  {path.name} DSL 无效，跳过: {e}")
            continue

        name, mode = identity
        existing_id = _find_existing_app(existing, name)
        if existing_id:
            log(f"  跳过已存在应用: {name}")
            continue
        log(f"  导入应用: {name} ({mode}) ...")

        r = client.post(
            f"{DIFY_API_URL}/console/api/apps/import",
            headers=headers,
            json={"data": dsl_content},
            timeout=60,
        )
        if r.status_code in (200, 201):
            app_id = r.json().get("id")
            existing[name] = app_id
            log(f"  ✅ {name} 导入成功 (id={app_id})")
        else:
            log(f"  ⚠️  {name} 导入返回 {r.status_code}: {r.text[:200]}，尝试继续")

    return existing


# ── 步骤 5：绑定模型 ──────────────────────────────────────
def bind_model_to_apps(client: httpx.Client, token: str, apps: dict) -> None:
    headers = {}
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


# ── 步骤 6：输出 app key ──────────────────────────────────
def export_app_keys(client: httpx.Client, token: str, apps: dict) -> None:
    headers = {}
    lines = [
        "# Dify 应用 API Key（由 dify-init 自动生成）",
        "# 由 backend 容器启动时自动加载；不要提交或公开此文件。",
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
        env_name = APP_KEY_ENV_NAMES.get((name, "agent-chat")) or APP_KEY_ENV_NAMES.get((name, "advanced-chat"))
        if env_name:
            lines.append(f"{env_name}={key}")

    output = "\n".join(lines) + "\n"
    Path(APP_KEYS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(APP_KEYS_FILE, "w", encoding="utf-8") as f:
        f.write(output)
    os.chmod(APP_KEYS_FILE, 0o600)
    log(f"✅ App key 已写入 {APP_KEYS_FILE}")
    log("App key 已保存到受限共享卷，backend 将在启动时自动加载；密钥不输出到日志。")


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

        if apps:
            export_app_keys(client, token, apps)
        else:
            log("⚠️  无应用可导出 key")

    log("🎉 Dify 初始化全部完成")


if __name__ == "__main__":
    main()
