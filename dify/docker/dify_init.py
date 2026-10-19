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
import re
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

# ── app key 输出的 shell 环境变量名映射（v6.11.21 补充，LOG-079） ──
# app_keys.env 由 backend 容器以 `sh -c 'set -a && . /run/dify-keys/app_keys.env'` 自动加载，
# 键名必须是合法的 POSIX shell 变量名，不能用中文应用名（否则 source 失败阻断 backend 启动）。
# 应用名基干（yml 文件名去掉 __agent-chat / __advanced-chat 后缀）→ backend 读取的环境变量名
APP_KEY_ENV_MAP = {
    "留学生智能管家": "DIFY_STUDENT_AGENT_KEY",
    "企业员工助手": "DIFY_EMPLOYEE_AGENT_KEY",
    "粤教客服": "DIFY_CUSTOMER_AGENT_KEY",
    "智能报告": "DIFY_REPORT_AGENT_KEY",
}
# 留档版应用不输出 key（与"4 个应用 key（除留档版外）"口径一致）
ARCHIVED_APPS = {"智能报告__agent-chat"}
# 核心三 Agent 的 key 为空时初始化必须失败（阻塞 backend 启动），报告 Agent 允许留空（恒 unavailable）
REQUIRED_KEY_ENVS = {"DIFY_CUSTOMER_AGENT_KEY", "DIFY_STUDENT_AGENT_KEY", "DIFY_EMPLOYEE_AGENT_KEY"}

# ── HTTP 节点后端地址自愈（v6.11.37，LOG-096） ─────────────
# Chatflow 的 HTTP 节点在 Dify 容器网络内访问宿主机后端；旧地址（VMware NAT 时代写死的
# 192.168.184.1 等）容器内不可达，每轮对话白等连接超时，是「客服响应慢」的根因。
# 初始化时把草稿图中所有指向后端 :8000 的旧地址自动改写为 DIFY_BACKEND_URL。
DIFY_BACKEND_URL = os.environ.get("DIFY_BACKEND_URL", "http://host.docker.internal:8000").rstrip("/")
_UNREACHABLE_BACKEND_PREFIXES = (
    "http://192.168.",
    "http://172.17.0.1:",
    "http://172.18.0.1:",
    "http://localhost:",
    "http://127.0.0.1:",
)


def _rewrite_backend_endpoint(url) -> str | None:
    """容器内不可达的后端旧地址 → DIFY_BACKEND_URL + 原路径；无需改写返回 None。"""
    if not isinstance(url, str) or not url:
        return None
    if not url.startswith(_UNREACHABLE_BACKEND_PREFIXES) or ":8000/" not in url:
        return None
    path = url.split(":8000", 1)[1]
    return DIFY_BACKEND_URL + path


def _existing_key_tokens() -> set[str]:
    """读取上一次写出的 app_keys.env 中的 token，同名应用去重时保持 key 连续性。"""
    try:
        text = Path(APP_KEYS_FILE).read_text(encoding="utf-8")
    except OSError:
        return set()
    return {
        line.split("=", 1)[1].strip()
        for line in text.splitlines()
        if "=" in line and not line.lstrip().startswith("#") and line.split("=", 1)[1].strip()
    }


def _env_name_for(app_name: str) -> str | None:
    """应用名 → shell 环境变量名；留档版/未登记返回 None（跳过输出）。

    兼容两种命名：yml 主干名（粤教客服__advanced-chat）与裸应用名（粤教客服Agent）。
    名字可带【调用中】/【废案】状态标记（v6.11.38 命名规则），基名前缀匹配不受影响。
    """
    if app_name in ARCHIVED_APPS or "留档" in app_name or "废案" in app_name:
        return None
    base = app_name.split("__", 1)[0]
    if base in APP_KEY_ENV_MAP:
        return APP_KEY_ENV_MAP[base]
    for key, env in APP_KEY_ENV_MAP.items():  # 前缀容错（如 粤教客服Agent → 粤教客服）
        if base.startswith(key):
            return env
    return None


def log(msg: str) -> None:
    print(f"[dify-init] {msg}", flush=True)


def fail(msg: str) -> None:
    log(f"❌ {msg}")
    sys.exit(1)


# ── 步骤 1：等待 Dify 就绪 ────────────────────────────────
def wait_for_dify(timeout: int = 600) -> None:
    log(f"等待 Dify api 就绪：{DIFY_API_URL}（全新实例首次启动需完成 DB 迁移，最长等 {timeout}s）")
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
                        # 任务态与实际安装可能竞态（daemon 后台恢复完成），以 provider 就位为最终判据
                        r2 = client.get(
                            f"{DIFY_API_URL}/console/api/workspaces/current/model-providers",
                            headers=headers,
                            params={"model_type": "llm"},
                            timeout=30,
                        )
                        if r2.status_code == 200 and any(
                            q.get("provider") == MODEL_PROVIDER for q in (r2.json().get("data") or [])
                        ):
                            log("✅ 模型插件实际已就位（任务态滞后），继续")
                            return
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

    # 供应商已存在时也要刷新凭证：早期版本直接跳过，导致 .env 改掉 api_key/base_url 后
    # Dify 仍沿用旧供应商凭证，Agent 请求继续走旧渠道（历史缺陷：旧渠道免费档 429 拖垮全部 Agent）
    action = "更新" if exists else "添加"
    log(f"{action}模型供应商 {MODEL_PROVIDER} 凭证 ...")
    # Dify 1.16：POST .../credentials 保存供应商凭证（服务端校验凭证有效性；同 provider 同名 `default` 为 upsert）
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
    if r.status_code in (200, 201):
        log(f"✅ 模型供应商凭证已{action}（base_url={DIFY_MODEL_BASE_URL}）")
    elif "provider_credential_schema" in r.text:
        # openai_api_compatible 是模型级凭证插件，供应商级凭证接口天然不支持（结构差异，非配置错误）；
        # 实际生效的凭证在下方模型级 credentials 中注册/刷新
        log(f"    ⚠️ {MODEL_PROVIDER} 为模型级凭证插件，跳过供应商级凭证（模型级凭证在下方注册/刷新）")
    else:
        fail(f"{action}模型供应商失败: {r.status_code} {r.text[:300]}")

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
    # 自定义模型供应商：模型级凭证是实际生效的鉴权（Dify 1.16 models/credentials；数值字段为字符串）。
    # 始终 POST 一次：若接口为 upsert 则完成凭证刷新（.env 改 api_key 后重拉起即生效）；
    # 若对已存在模型报错，等价于凭证在位，不视为失败。仅当模型不存在且注册失败才阻断初始化。
    log(f"注册/刷新自定义模型 {DIFY_MODEL_NAME} 凭证 ...")
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
        log(f"✅ 自定义模型 {DIFY_MODEL_NAME} 凭证已注册/刷新")
    elif DIFY_MODEL_NAME not in model_names:
        fail(f"注册自定义模型失败: {r.status_code} {r.text[:300]}")
    else:
        log(f"    ✅ 自定义模型 {DIFY_MODEL_NAME} 已存在（凭证接口返回 {r.status_code}，视为凭证在位）")


# ── 步骤 4：导入应用 yml ──────────────────────────────────
def list_existing_apps(client: httpx.Client, token: str) -> dict:
    """返回 {app_name: app_id}；同名多应用（历史重复导入）时确定性选定一个。

    v6.11.37（LOG-096）：原先 dict 直接收敛，同名应用谁排后面谁生效，
    重拉起后导出的 key 可能漂移到旧应用（后端调用错应用=交付事故）。
    现按「已签发 API key 优先 → 与上次 app_keys.env 中 token 一致者优先 → 创建最新」确定性选定。
    """
    headers = build_headers(client, token)
    r = client.get(f"{DIFY_API_URL}/console/api/apps?page=1&limit=100", headers=headers, timeout=30)
    if r.status_code != 200:
        fail(f"查询应用列表失败: {r.status_code} {r.text[:300]}")
    apps = r.json().get("data", []) or []
    by_name: dict[str, list] = {}
    for a in apps:
        by_name.setdefault(a["name"], []).append(a)

    known_tokens = _existing_key_tokens()
    result: dict[str, str] = {}
    for name, group in by_name.items():
        if len(group) == 1:
            result[name] = group[0]["id"]
            continue
        keyed: list[tuple[dict, str]] = []
        for a in group:
            kr = client.get(f"{DIFY_API_URL}/console/api/apps/{a['id']}/api-keys", headers=headers, timeout=30)
            if kr.status_code == 200:
                for k in (kr.json().get("data") or []):
                    if k.get("token"):
                        keyed.append((a, k["token"]))
                        break
        if keyed:
            live = [a for a, t in keyed if t in known_tokens] or [a for a, _ in keyed]
            chosen = live[0]
        else:
            chosen = max(group, key=lambda a: a.get("created_at") or 0)
        result[name] = chosen["id"]
        log(f"  ⚠️ 同名应用 {name} ×{len(group)}，确定性选定 {chosen['id']}（已签发 key/延续 token 优先）")
    return result


def _dsl_app_name(dsl_content: str) -> str:
    """取 DSL 内的 app.name（Dify 侧的应用显示名），解析失败返回空串"""
    try:
        data = yaml.safe_load(dsl_content) or {}
    except yaml.YAMLError:
        return ""
    return str((data.get("app") or {}).get("name") or "").strip()


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
        with open(yml_path, "r", encoding="utf-8") as f:
            dsl_content = f.read()
        # 幂等判定必须用 DSL 内的 app.name：文件名形如「智能报告__advanced-chat」，
        # 与 Dify 中的应用显示名「智能报告」并不相同；用文件名比对永远匹配不上，
        # 每跑一次就重复导入一份副本（历史缺陷：曾累积到 5 个应用 × 3 份副本）
        name = _dsl_app_name(dsl_content) or Path(yml_path).stem
        # 已存在判定按基名（剥掉【调用中】/【废案】状态标记与·N 序号）：应用被命名规范化改名后
        # 仍视为同一应用，不重复导入（v6.11.38 命名规则配套）
        base = re.sub(r"【(调用中|废案)】|·\d+$", "", name)
        if name in existing or any(re.sub(r"【(调用中|废案)】|·\d+$", "", en) == base for en in existing):
            log(f"  跳过已存在应用: {name}（{Path(yml_path).name}）")
            continue
        log(f"  导入应用: {name}（{Path(yml_path).name}）...")
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


# ── 步骤 5：绑定模型（强制对齐到 DIFY_MODEL_NAME）──────────
def _align_workflow_model(client: httpx.Client, headers: dict, name: str, app_id: str) -> bool:
    """advanced-chat（Chatflow）：模型写在 workflow 各 LLM 节点里。

    app 级 model-config 不存在（GET 返回 405），DSL 占位符又只在「首次导入」时注入，
    因此历史遗留副本会一直绑着旧模型，必须改写 draft 图才能真正切换。返回 True 表示是工作流应用。
    """
    r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/draft", headers=headers, timeout=30)
    if r.status_code != 200:
        return False
    draft = r.json()
    nodes = (draft.get("graph") or {}).get("nodes") or []
    changed = 0
    for node in nodes:
        data = node.get("data") or {}
        model = data.get("model") or {}
        if model.get("name") and model.get("name") != DIFY_MODEL_NAME:
            model["name"] = DIFY_MODEL_NAME
            model["provider"] = MODEL_PROVIDER
            changed += 1
        # HTTP 节点后端地址自愈（v6.11.37，LOG-096）：容器内不可达的旧地址 → DIFY_BACKEND_URL
        if data.get("type") == "http-request":
            new_url = _rewrite_backend_endpoint(data.get("url", ""))
            if new_url:
                log(f"    ✅ {name} HTTP 节点地址自愈: {data['url']} → {new_url}")
                data["url"] = new_url
                changed += 1
    if not changed:
        log(f"    ✅ {name} 节点模型与端点地址均已正确")
        return True
    # Dify 乐观锁：不回传 hash 会返回 409 draft_workflow_not_sync
    r = client.post(
        f"{DIFY_API_URL}/console/api/apps/{app_id}/workflows/draft",
        headers=headers,
        json={
            "graph": draft.get("graph"),
            "features": draft.get("features"),
            "environment_variables": draft.get("environment_variables"),
            "conversation_variables": draft.get("conversation_variables"),
            "hash": draft.get("hash"),
        },
        timeout=120,
    )
    if r.status_code not in (200, 201):
        log(f"    ⚠️  {name} 工作流模型改写失败: {r.status_code} {r.text[:200]}")
        return True
    log(f"    ✅ {name} 已改写 {changed} 处（节点模型/端点地址，由后续「发布工作流」生效）")
    return True


def _align_app_model(client: httpx.Client, headers: dict, name: str, app_id: str) -> None:
    """chat / agent-chat：模型存在 app 级 model-config，直接覆盖回写。"""
    r = client.get(f"{DIFY_API_URL}/console/api/apps/{app_id}", headers=headers, timeout=30)
    if r.status_code != 200:
        log(f"    ⚠️  {name} 读取应用详情失败: {r.status_code}")
        return
    config = (r.json() or {}).get("model_config") or {}
    if not config:
        log(f"    （{name} 无 app 级 model-config，跳过）")
        return
    # 审计字段不接受回写
    for key in ("created_by", "created_at", "updated_by", "updated_at"):
        config.pop(key, None)
    current = config.get("model") or {}
    if current.get("name") == DIFY_MODEL_NAME and current.get("provider") == MODEL_PROVIDER:
        log(f"    ✅ {name} 应用级模型已是 {DIFY_MODEL_NAME}")
        return
    config.setdefault("model", {})
    config["model"]["provider"] = MODEL_PROVIDER
    config["model"]["name"] = DIFY_MODEL_NAME
    config["model"]["mode"] = MODEL_MODE
    r = client.post(
        f"{DIFY_API_URL}/console/api/apps/{app_id}/model-config",
        headers=headers,
        json=config,
        timeout=30,
    )
    if r.status_code in (200, 201):
        log(f"    ✅ {name} 已绑定 {DIFY_MODEL_NAME}")
    else:
        log(f"    ⚠️  绑定返回 {r.status_code}: {r.text[:200]}")


def bind_model_to_apps(client: httpx.Client, token: str, apps: dict) -> None:
    """把每个应用的模型统一对齐到 DIFY_MODEL_NAME（chat/agent-chat 与 advanced-chat 分别处理）。"""
    headers = build_headers(client, token)
    for name, app_id in apps.items():
        log(f"  对齐 {name} 的模型 ...")
        if _align_workflow_model(client, headers, name, app_id):
            continue
        _align_app_model(client, headers, name, app_id)


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


# ── 步骤 5.6：应用命名规范化（硬性规则：名字必须写明【调用中】/【废案】）──
def normalize_app_names(client: httpx.Client, token: str, apps: dict) -> None:
    """Dify 应用名必须带状态标记，每次初始化自动核对写明（幂等）。

    规则（AGENTS.md §7.5，v6.11.38）：
      - 调用中（后端按 App Key 实际调用）→「原名【调用中】」
      - 其余（废案/留档/重复副本）      →「原名【废案】」
    每次修改 Dify 应用（导入/换 key/停用）后必须重新写明标记；本步骤在每次
    dify-init 运行时自动规范化，保证重拉起后标记不丢失、不错误。
    """
    headers = build_headers(client, token)
    r = client.get(f"{DIFY_API_URL}/console/api/apps?page=1&limit=100", headers=headers, timeout=30)
    if r.status_code != 200:
        log(f"    ⚠️ 应用命名规范化跳过（应用列表获取失败 {r.status_code}）")
        return
    all_apps = r.json().get("data", []) or []
    # 调用中判定：被选定且会输出 App Key 的应用（_env_name_for 非空）
    active_ids = {app_id for name, app_id in apps.items() if _env_name_for(name)}
    # 排序保证同基名废案副本的序号分配稳定（幂等）
    all_apps.sort(key=lambda a: str(a.get("id") or ""))
    used: set[str] = set()
    renamed = 0
    for a in all_apps:
        raw = a.get("name") or ""
        base = re.sub(r"【(调用中|废案)】|·\d+$", "", raw).strip()
        marker = "【调用中】" if a.get("id") in active_ids else "【废案】"
        target = f"{base}{marker}"
        if target in used:  # 同基名多个废案副本：加序号区分
            idx = 2
            while f"{base}{marker}·{idx}" in used:
                idx += 1
            target = f"{base}{marker}·{idx}"
        used.add(target)
        if target == raw:
            continue
        r2 = client.put(
            f"{DIFY_API_URL}/console/api/apps/{a['id']}",
            headers=headers,
            json={"name": target},
            timeout=30,
        )
        if r2.status_code in (200, 201):
            log(f"    ✅ 应用命名规范化: {raw} → {target}")
            renamed += 1
        else:
            log(f"    ⚠️ 应用改名失败 {r2.status_code}: {r2.text[:120]}")
    if not renamed:
        log("    ✅ 全部应用命名已符合【调用中】/【废案】标记规则")


# ── 步骤 6：输出 app key ──────────────────────────────────
def export_app_keys(client: httpx.Client, token: str, apps: dict) -> None:
    headers = build_headers(client, token)
    lines = [
        "# Dify 应用 API Key（由 dify-init 自动生成）",
        "# 本文件由 backend 容器启动时自动加载（挂载为 /run/dify-keys/app_keys.env），无需手工复制：",
        "#   留学生智能管家 -> DIFY_STUDENT_AGENT_KEY",
        "#   企业员工助手   -> DIFY_EMPLOYEE_AGENT_KEY",
        "#   粤教客服Agent  -> DIFY_CUSTOMER_AGENT_KEY",
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
        env_name = _env_name_for(name)
        if not env_name:
            log(f"    （{name} 为留档版或未登记环境变量名，跳过 key 输出）")
            continue
        # 防御（LOG-094）：键名必须是合法 POSIX shell 变量名，中文名会使 backend 的 sh source 崩溃
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            fail(f"app key 环境变量名非法（必须为 POSIX shell 变量名）: {env_name!r}（应用: {name}）")
        if not key:
            if env_name in REQUIRED_KEY_ENVS:
                fail(f"核心应用 {name} 的 API key 为空，拒绝写出残缺配置（会阻断 backend 启动）")
            log(f"    ⚠️ {name} 的 API key 为空（允许留空，对应能力恒 unavailable）")
        lines.append(f"{env_name}={key}")

    output = "\n".join(lines) + "\n"
    Path(APP_KEYS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(APP_KEYS_FILE, "w", encoding="utf-8") as f:
        f.write(output)
    log(f"✅ App key 已写入 {APP_KEYS_FILE}")
    log("-" * 60)
    log(output)
    log("-" * 60)
    log("✅ backend 容器启动时自动加载本文件，无需手工复制")


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
            log("应用命名规范化（调用中/废案）...")
            normalize_app_names(client, token, apps)
            export_app_keys(client, token, apps)
        else:
            log("⚠️  无应用可导出 key")

    log("🎉 Dify 初始化全部完成")


if __name__ == "__main__":
    main()
