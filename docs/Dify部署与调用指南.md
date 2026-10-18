# Dify 部署与调用指南

> v6.11.10 起，Dify 已一体化打包进项目 docker-compose，并提供 **dify-init 一键初始化服务**。先复制 `dify/docker/.env.example` 为本地 `.env`，设置模型 API Key、管理员密码及 Dify 内部服务强密钥，再启动服务；本地 `.env` 不入库。

---

## 一、封装概览

### 1.1 一体化打包内容

Dify 1.16.0-rc1 官方 compose 已纳入项目 `dify/docker/` 目录，随主 `docker-compose.yml` 一键启动。

| 封装项 | 路径 | 说明 |
|--------|------|------|
| Dify compose | `dify/docker/docker-compose.yaml` | Dify 全套服务定义 |
| Dify 环境变量模板 | `dify/docker/.env.example` | 复制为本地 `.env` 后填写模型 Key、管理员密码及内部服务强密钥 |
| Dify 初始化脚本 | `dify/docker/dify_init.py` | 一键初始化（管理员/模型/应用/绑定/导出 key） |
| Dify init 镜像 | `dify/docker/Dockerfile.init` | init 容器镜像（python:3.11-slim + httpx + pyyaml） |
| Dify envs 片段 | `dify/docker/envs/` | 各服务可选 env 片段（required: false） |
| Dify nginx 配置 | `dify/docker/nginx/` | 反代模板 |
| Dify ssrf_proxy | `dify/docker/ssrf_proxy/` | 沙箱代理 |
| Agent 应用 DSL | `dify/apps/*.yml` | 3 个业务 Agent + 1 个智能报告 Chatflow；另有 1 个留档 DSL |
| 主 compose 引用 | `docker-compose.yml` 顶层 `include` | 自动引入 Dify compose |

### 1.2 dify-init 服务

`dify-init` 是项目新增的一次性初始化容器，启动时自动执行：

```
等待 Dify api 就绪
    ↓
创建/登录 Dify 管理员（用 dify/docker/.env 中的账号）
    ↓
添加 OpenAI-API-compatible 模型供应商（用客户填的 Key/URL/模型名）
    ↓
按 DSL 内应用名导入并去重在用应用（跳过留档 DSL）
    ↓
为所有应用绑定模型
    ↓
将 3 个业务 Agent key 写入受限 Docker 命名卷；backend 启动时自动读取，无需手动回填
```

**硬性约束**：backend 依赖 `dify-init: service_completed_successfully`，即 init 失败则 backend 不启动（长期挂载场景，配置必须完整）。

### 1.3 服务重命名（避免冲突）

项目本身已有 `nginx` 和 `redis` 服务，Dify 的同名服务已重命名：

| Dify 原服务名 | 重命名后 | 说明 |
|--------------|---------|------|
| `nginx` | `dify_nginx` | Dify 控制台反代，端口 8081 |
| `redis` | `dify_redis` | Dify 专用 Redis（密码需在本地 `.env` 设置），与项目 Redis 独立 |

### 1.4 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| 项目 nginx（前端） | 8080 | 前端页面 |
| backend API | 8000 | 后端 API |
| Dify 控制台 | 8081 | Dify web 控制台 + Service API |
| MySQL | 59000 | 项目数据库 |
| Redis | 6379 | 项目缓存 |

---

## 二、启动方式

### 2.1 一键启动全部（含 AI）

首次启动前，先复制模板并设置所有空白密钥：

```powershell
Copy-Item dify/docker/.env.example dify/docker/.env
```

`dify/docker/.env` 已忽略，不会提交。Compose 需要支持 `include`（Docker Compose v2.20+）。

```bash
docker compose up -d
```

启动后服务清单：

```
项目核心：mysql、redis、backend、nginx
Dify 全套：api、worker、worker_beat、web、dify_nginx、dify_redis、
          db_postgres、weaviate、sandbox、plugin_daemon、agent_backend、
          local_sandbox、ssrf_proxy
Dify 初始化：dify-init（一次性，成功后退出）
```

> 首次启动需等待 Dify PostgreSQL 迁移 + dify-init 执行完毕，约 2-3 分钟 backend 才会启动。

### 2.2 不使用 AI 的部署

```bash
docker compose up -d
```

当前 backend 依赖 `dify-init` 成功完成后才启动，因此仍需按 2.1 配置并启动 Dify。业务上不调用 AI 的端点可继续使用登录、成绩、CRM 等功能；此部署包目前没有单独跳过 Dify 的核心服务启动命令。

### 2.3 访问入口

| 入口 | URL |
|------|-----|
| 前端页面 | http://localhost:8080 |
| 后端 API | http://localhost:8000 |
| Dify 控制台 | http://localhost:8081 |
| Dify Service API | http://localhost:8081/v1 |

---

## 三、配置清单

### 3.1 dify/docker/.env — 客户需配置区域（重点）

先复制模板，然后设置模型、管理员、数据库和内部服务密码：

```bash
# ── 模型供应商（OpenAI-API-compatible 通用协议，支持任一兼容服务，不绑定任何特定模型）──
DIFY_MODEL_API_KEY=                  # ⚠️ 必填，你的模型 API Key
DIFY_MODEL_BASE_URL=                 # ⚠️ 必填，OpenAI 兼容接口地址（通常以 /v1 结尾）
DIFY_MODEL_NAME=                     # ⚠️ 必填，服务商模型列表中的模型名

# ── Dify 管理员（dify-init 首次自动创建；已存在则用此账号登录）──
DIFY_ADMIN_EMAIL=admin@example.com
DIFY_ADMIN_PASSWORD=                 # ⚠️ 必填，设置本地强密码

# ── Dify 内部服务（必须使用本地随机强密钥）──
DB_PASSWORD=                         # ⚠️ 必填
REDIS_PASSWORD=                      # ⚠️ 必填
SANDBOX_API_KEY=                     # ⚠️ 必填；与 CODE_EXECUTION_API_KEY 保持一致
CODE_EXECUTION_API_KEY=              # ⚠️ 必填；与 SANDBOX_API_KEY 保持一致
PLUGIN_DAEMON_KEY=                   # ⚠️ 必填
PLUGIN_DIFY_INNER_API_KEY=           # ⚠️ 必填
DIFY_AGENT_SERVER_SECRET_KEY=        # ⚠️ 必填
WEAVIATE_API_KEY=                    # ⚠️ 必填；与 WEAVIATE_AUTHENTICATION_APIKEY_ALLOWED_KEYS 保持一致
WEAVIATE_AUTHENTICATION_APIKEY_ALLOWED_KEYS=  # ⚠️ 必填；与 WEAVIATE_API_KEY 保持一致

# ── dify-init 行为开关 ──
DIFY_INIT_AUTO_IMPORT=true           # 自动导入 dify/apps/ 下的 yml
DIFY_INIT_AUTO_BIND_MODEL=true       # 自动为所有应用绑定模型
```

> 模型三项均**默认留空**，由客户按自己所使用的服务商填写（不绑定任何特定模型）；任一项缺失则 dify-init 初始化失败并阻塞 backend 启动。

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DIFY_MODEL_API_KEY` | ✅ | 空 | 模型 API Key（客户凭据，勿入库）。留空则 init 失败 |
| `DIFY_MODEL_BASE_URL` | ✅ | 空 | OpenAI-API-compatible 接口地址（客户自定义，通常以 /v1 结尾） |
| `DIFY_MODEL_NAME` | ✅ | 空 | 模型名称（客户自定义，需在服务商模型列表中存在） |
| `DIFY_ADMIN_EMAIL` | ✅ | `admin@example.com` | Dify 管理员邮箱 |
| `DIFY_ADMIN_PASSWORD` | ✅ | 无 | 本地 Dify 管理员强密码 |
| `DIFY_INIT_AUTO_IMPORT` | 可选 | `true` | 是否自动导入 `dify/apps/*.yml` |
| `DIFY_INIT_AUTO_BIND_MODEL` | 可选 | `true` | 是否自动为应用绑定模型 |

`DB_PASSWORD`、`REDIS_PASSWORD`、`SANDBOX_API_KEY`、`CODE_EXECUTION_API_KEY`、`PLUGIN_DAEMON_KEY`、`PLUGIN_DIFY_INNER_API_KEY`、`DIFY_AGENT_SERVER_SECRET_KEY`、`WEAVIATE_API_KEY` 和 `WEAVIATE_AUTHENTICATION_APIKEY_ALLOWED_KEYS` 均需在本机配置；成对的沙箱/Weaviate key 必须相同。

### 3.2 backend/.env — Dify 相关变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DIFY_BASE_URL` | ✅ | `http://localhost:8081` | Dify Service API 地址。Docker 容器内由 compose 覆盖为 `http://dify_nginx` |
| `DIFY_VERSION` | ✅ | `1.16.0-rc1` | Dify 版本号 |
| `DIFY_API_PROTOCOL` | ✅ | `openai` | API 协议 |
| `DIFY_STUDENT_AGENT_KEY` | 按需 | 空 | 留学生智能管家 Agent 的 app key，从 `dify/docker/app_keys.txt` 复制 |
| `DIFY_EMPLOYEE_AGENT_KEY` | 按需 | 空 | 企业员工助手 Agent 的 app key |
| `DIFY_CUSTOMER_AGENT_KEY` | 按需 | 空 | 粤教客服 Agent 的 app key |
| `DIFY_REPORT_AGENT_KEY` | 按需 | 空 | 智能报告 Agent 的 app key（v6.11.11 起支持，报告 AI 分析用；留空则报告 AI 恒 `unavailable`） |
| `DIFY_MODEL_API_KEY` | 可选 | 空 | 直连模型降级用的 API Key。留空则跳过直连降级，走本地话术 |
| `DIFY_MODEL_BASE_URL` | 可选 | 空 | 直连模型地址（OpenAI-API-compatible，客户自定义） |
| `DIFY_MODEL_NAME` | 可选 | 空 | 直连模型名称（客户自定义） |

> 四个 `DIFY_*_AGENT_KEY` 留空时，对应 Agent 端点返回 401 并触发降级；不影响其他功能。

### 3.3 Dify 内部服务密码

项目不跟踪本地 `dify/docker/.env`，也不提供可直接使用的默认密码。复制模板后，必须为以下服务配置本地强密钥；Compose 会在缺少必填值时停止并指出变量名：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EXPOSE_NGINX_PORT` | `8081` | Dify 控制台端口 |
| `DB_PASSWORD` | 必填 | Dify PostgreSQL 密码 |
| `REDIS_PASSWORD` | 必填 | Dify Redis 密码 |
| `SANDBOX_API_KEY` / `CODE_EXECUTION_API_KEY` | 必填且一致 | Dify 沙箱访问密钥 |
| `PLUGIN_DAEMON_KEY`、`PLUGIN_DIFY_INNER_API_KEY` | 必填 | 插件守护进程和内部 API 密钥 |
| `DIFY_AGENT_SERVER_SECRET_KEY` | 必填 | Agent 服务签名密钥 |
| `WEAVIATE_API_KEY` / `WEAVIATE_AUTHENTICATION_APIKEY_ALLOWED_KEYS` | 必填且一致 | 向量库访问密钥 |
| `DB_HOST` | `db_postgres` | Dify 元数据库 service 名 |
| `REDIS_HOST` | `dify_redis` | Dify Redis service 名 |
| `VECTOR_STORE` | `weaviate` | 向量数据库类型 |

---

## 四、调用规则

项目有 **两套 AI 调用机制**，构成三级降级链：

```
Dify Agent 网关（主路径）
    ↓ 失败/超时
直连模型降级（model_ai_service）
    ↓ 未配置/失败
本地话术兜底（各 service 内置规则）
```

### 4.1 机制一：Dify Agent 网关（主路径）

**实现文件**：`backend/app/services/ai_service.py`（`AIService`）+ `backend/app/services/dify_client.py`（`DifyClient`）

**协议**：Dify 原生 `POST /v1/chat-messages`（blocking 模式）

**鉴权**：`Authorization: Bearer {DIFY_*_AGENT_KEY}`

**请求体**：
```json
{
  "inputs": {},           // 上下文（人设、能力清单、限制预期）
  "query": "用户消息",
  "response_mode": "blocking",
  "user": "user-id",
  "conversation_id": "可选，续会话用"
}
```

**响应**：`data.answer` 为回复内容，`data.conversation_id` 为会话 ID。

**Agent 与 key 映射**：

| AgentType | 环境变量 | 对应 Dify 应用 |
|-----------|---------|---------------|
| `CUSTOMER` | `DIFY_CUSTOMER_AGENT_KEY` | 粤教客服 |
| `EMPLOYEE` | `DIFY_EMPLOYEE_AGENT_KEY` | 企业员工助手 |
| `STUDENT` | `DIFY_STUDENT_AGENT_KEY` | 留学生智能管家 |

### 4.2 机制二：直连模型降级

**实现文件**：`backend/app/services/model_ai_service.py`（`ModelAIService`）

**触发条件**：Dify Agent 调用抛出异常（连接失败、超时、401 等）时。

**协议**：OpenAI-compatible `POST {DIFY_MODEL_BASE_URL}/chat/completions`

**鉴权**：`Authorization: Bearer {DIFY_MODEL_API_KEY}`

**前提**：`DIFY_MODEL_API_KEY` 非空，否则跳过此级降级。

### 4.3 各业务场景调用链

| 业务场景 | API 端点 | 主路径 | 降级路径 | 最终兜底 |
|---------|---------|--------|---------|---------|
| 客服对话 | `POST /cs/chat` | `DifyClient` → 客服 Agent | 本地正则提取画像 SLOTS | 本地话术 |
| 员工助手会话 | `POST /employee/agent/chat` | `ai_service.chat(EMPLOYEE)` | `model_ai_service.chat` | 本地 fallback reply |
| 员工指令解析 | `POST /employee/agent/command` | `ai_service.chat(EMPLOYEE)` | 本地关键词+正则规则 | 报错提示 |
| 员工新人指引 | `POST /employee/guide/ask` | `ai_service.chat(EMPLOYEE)` | `model_ai_service.chat` | 本地关键词匹配 |
| 学生助手会话 | `POST /student/agent/chat` | `ai_service.chat(STUDENT)` | `model_ai_service.chat` | `_AGENT_FALLBACK_REPLY` |
| 学生心理关怀 | `POST /student/psych/chat` | `ai_service.chat(STUDENT)` | `model_ai_service.chat` | 本地情绪词库 |
| 智能报告 AI 分析 | `POST /report/...` | `ai_service.chat` | `model_ai_service.analyze` | 确定性报告（无 AI 摘要） |

### 4.4 上下文注入规则

人设/能力/限制预期由**后端代码注入**到 Dify `inputs`，不写死在 Dify 控制台：

| Agent | 注入字段 | 来源 |
|-------|---------|------|
| 员工助手 | `inputs.capabilities` | `employee_service.py` 按角色动态生成能力清单 |
| 学生助手 | `inputs.restrictions` / `inputs.capabilities` | `student_service.py`（不承诺退费/不给医疗级建议） |
| 客服 | 无（pre_prompt 在 Dify 控制台） | `cs_agent_service.py` 解析 `[intent:]/[RECOMMEND]/[SLOTS]` 三标记 |

---

## 五、降级机制说明

所有 AI 端点均实现三级降级，**任何一级失败都不阻断核心业务**：

| 级别 | 触发条件 | 表现 |
|------|---------|------|
| L1 Dify Agent | 正常配置且可达 | 真实 AI 回复 |
| L2 直连模型 | Dify 失败 + `DIFY_MODEL_API_KEY` 已配 | 直连模型生成回复 |
| L3 本地兜底 | 上述均不可用 | 本地话术/规则/关键词匹配 |

验证降级是否生效：停止 Dify 容器后调用任一 AI 端点，应返回 `source: "fallback"` 的本地回复而非 500。

---

## 六、接手者配置步骤（自动化）

### 步骤 1：填写模型配置

编辑 `dify/docker/.env`，填入模型 API Key 和本地强密码：

```bash
DIFY_MODEL_API_KEY=sk-your-actual-key
DIFY_ADMIN_PASSWORD=your-local-strong-password
```

### 步骤 2：一键启动

```bash
docker compose up -d
```

dify-init 容器会自动完成：创建管理员 → 配模型供应商 → 按 DSL 应用名导入并去重、跳过留档 `agent-chat` DSL → 绑定模型 → 将 3 个业务 Agent key 写入权限为 `0600` 的共享卷供 backend 自动加载。

查看 init 进度：
```bash
docker compose logs -f dify-init
```

成功标志：日志出现 `🎉 Dify 初始化全部完成`。

### 步骤 3：验证

dify-init 将 5 个 app key 写入 `dify/docker/app_keys.txt`（已 gitignore）。打开该文件，复制四个应用的 key 到 `backend/.env`：

```bash
# 从 dify/docker/app_keys.txt 复制对应行
DIFY_CUSTOMER_AGENT_KEY=app-xxxx      # 粤教客服
DIFY_EMPLOYEE_AGENT_KEY=app-yyyy      # 企业员工助手
DIFY_STUDENT_AGENT_KEY=app-zzzz       # 留学生智能管家
DIFY_REPORT_AGENT_KEY=app-rrrr        # 智能报告（留空则报告 AI 恒 unavailable）
```

> 注：backend 容器「启动时自动加载 /run/dify-keys/app_keys.env」的设计因 docker-compose 缺 `dify_app_keys:/run/dify-keys` 挂载暂不可用（已记录于 LOG-070（ZNBG）/开发路线图移交清单第 25 项，按用户决定暂不修复）；当前以 `backend/.env` 回填为可用路径。

### 步骤 4：重启 backend

```bash
docker compose restart backend
```

### 步骤 5：验证

调用三个 AI 端点各发一条消息，确认返回 `source: "dify"` 而非 `fallback`：

```bash
# 客服
curl -X POST http://localhost:8000/api/v1/cs/chat -H "Content-Type: application/json" -d '{"query":"你好","user":"test"}'
```

### 步骤 4（可选）：配置直连模型降级

在 `backend/.env` 填入：
```bash
DIFY_MODEL_API_KEY=sk-your-actual-key
```
当 Dify Agent 不可用时，自动直连模型生成兜底回复。留空则跳过此级。

---

## 七、dify-init 失败排查

> 长期挂载场景下，dify-init 失败会导致 backend 不启动。按以下步骤排查：

### 7.1 查看 init 日志

```bash
docker compose logs dify-init
```

### 7.2 常见失败原因

| 错误信息 | 原因 | 解决 |
|---------|------|------|
| `DIFY_MODEL_API_KEY 为空` | 未在 `dify/docker/.env` 填模型 Key | 填入 Key 后 `docker compose up dify-init` |
| `登录失败: 401` | Dify 管理员密码不匹配 | 修改 `dify/docker/.env` 的 `DIFY_ADMIN_PASSWORD`，或进控制台重置 |
| `添加模型供应商失败` | API Key 无效或 base_url 错误 | 检查 Key 和 URL，`docker compose up dify-init` 重试 |
| `Dify api 在 180s 内未就绪` | Dify 启动慢或 PostgreSQL 迁移卡住 | `docker compose ps` 检查 Dify 服务状态，等待后重试 |
| `导入应用失败` | yml 格式问题 | 检查 `dify/apps/*.yml` 是否合法，或设 `DIFY_INIT_AUTO_IMPORT=false` 跳过 |

### 7.3 重新执行 init

修改 `dify/docker/.env` 后，重新运行 init：

```bash
docker compose up dify-init
# init 成功后 backend 会自动启动（因 depends_on 条件已满足）
```

### 7.4 跳过 AI 启动核心服务

如暂时不需要 AI，可只启动核心服务：

```bash
docker compose up -d mysql redis backend
```

---

## 八、常见问题

**Q: Dify 控制台打不开？**
A: 检查 `dify_nginx` 容器是否 healthy：`docker compose ps dify_nginx`。首次启动需等待 PostgreSQL 迁移完成。

**Q: AI 端点返回 fallback？**
A: 检查①`dify-init` 是否成功 ②backend 日志中是否有加载 app key 的错误 ③模型供应商 API Key 是否有效。查看 `docker compose logs backend` 确认降级原因。

**Q: 想换其他模型？**
A: 修改 `dify/docker/.env` 的 `DIFY_MODEL_BASE_URL` / `DIFY_MODEL_NAME` / `DIFY_MODEL_API_KEY`，然后 `docker compose up dify-init` 重新绑定。支持任何 OpenAI-API-compatible 模型，无需改代码。

**Q: Dify 数据存在哪？**
A: `dify/docker/volumes/`（已 gitignore），包含 PostgreSQL、Redis、Weaviate、上传文件等。删除会丢失所有 Dify 配置和知识库。

**Q: app key 需要手动复制吗？**
A: 不需要。`dify-init` 将 app key 写入 Docker 命名卷，backend 启动时自动加载；密钥不会写进仓库或容器日志。

**Q: 为什么 backend 一直不启动？**
A: 检查 `dify-init` 是否成功完成（`docker compose logs dify-init`）。backend 依赖 init 成功，init 失败则 backend 不启动。
