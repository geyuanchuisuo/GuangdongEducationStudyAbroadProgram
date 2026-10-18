# Dify 接入说明与资产清单（v6.11.2，2026-10-18）

> ⚠️ **现状更新（v6.11.6~8，2026-10-18/19）**：本文档描述的 **VM 实例（192.168.184.128:80）为旧时代配置，已废弃**。Dify 现已一体化打包进项目 docker-compose（`dify/docker/`，服务名 `dify_nginx`，控制台/Service API 端口 **8081**），`DIFY_BASE_URL`：本机 `http://localhost:8081` / 容器内 `http://dify_nginx`；模型 key/url/模型名客户在 `dify/docker/.env` 自定义，dify-init 自动配置。**现行配置与调用规则见 [Dify部署与调用指南.md](./Dify部署与调用指南.md)**。下文保留为 VM 时代接入记录（资产 id/导出 DSL 流程仍可参考）。

> **现行决策（v6.11.9）**：默认模型为 Mimo；按用户确认 M0 不登记 `AgentType.REPORT` / `DIFY_REPORT_AGENT_KEY`，M5 报告恢复动态 session ID，报告 AI 通过现有降级路径处理。以下 VM 实测与 REPORT 接入内容仅作历史记录。

> 范围：**只接「智能报告」**。M2 客服 / M3 员工 / M4 学生 的 Agent 按用户要求保持原状（`.env` 里仍是占位 key），本次不动。

---

## 1. 实例信息

| 项 | 值 |
|---|---|
| 地址 | `http://192.168.184.128`（本地 VMware 虚拟机，NAT 网段） |
| 暴露端口 | 仅 **80**（`3000` / `5001` / `8080` 未对外开放） |
| 控制台 API | `/console/api`：**cookie 认证 + `X-CSRF-Token`**（登录密码需 base64；只回 `{"result":"success"}` 不下发 token） |
| 容器可达性 | ✅ `docker exec edu-backend` 可直连 `192.168.184.128:80` |
| 管理账号 | 由项目负责人维护，**不入库、不写入本文档** |

## 2. 应用现状：两个同名「智能报告」

| 应用 | id | mode | 说明 |
|---|---|---|---|
| 智能报告（**在用**） | `2598b21f-5b8a-438e-9165-6b1ce603dca2` | **`advanced-chat`（Chatflow）** | ✅ 支持 `blocking`；已用控制台 API 发布；M5 走这个 |
| 智能报告（旧） | `c15aad68-6c73-4d5c-b2d7-25f64b7ad233` | `agent-chat`（Agent） | ❌ `blocking` 返回 400，已不作为接入目标 |

**为什么必须用 Chatflow**：Dify 对 `agent-chat` 类型禁用 `blocking`（`Agent Chat App does not support blocking mode`），而项目网关 `AIService.chat()` 用的就是 `blocking`。`advanced-chat` / `chat` 才支持。

### 接口实测

| 调用 | 结果 |
|---|---|
| `GET /v1/parameters` | ✅ 200 |
| `POST /v1/chat-messages`（chatflow, `blocking`） | ✅ **200**，`prompt_tokens 177 / completion_tokens 722` |
| JSON 契约 | ✅ 真实返回经 M5 `_parse_json` + `_validate` **PASS**（`summary/trend/analysis/suggestions` 齐全） |
| 输出形态 | ⚠️ 正文前有 `<think>…</think>` + `<!--dify-deepseek-reasoning-->` → M5 已加 `_strip_reasoning()` 剥离（含单测） |

### 待改进（建议，不影响当前可用）

- Chatflow 的 LLM 节点 **system prompt 为空**，目前完全依赖 M5 在 `query` 里带指令。建议把约束写进 system prompt（并引用 `{{#sys.query#}}`），减少模型漂移；`temperature` 建议降到 0.2 以下，让 JSON 更稳。
- 旧的 `agent-chat` 版应用建议归档或删除，避免以后误用。

## 3. 本项目配置

| 位置 | 配置 | 说明 |
|---|---|---|
| `backend/.env`（gitignore） | `DIFY_BASE_URL=http://192.168.184.128`<br>`DIFY_REPORT_AGENT_KEY=app-…`（chatflow 的真实 key） | 其余 3 个 Agent key 保持占位 `app-xxx/yyy/zzz` |
| `docker-compose.yml` | `DIFY_BASE_URL: http://192.168.184.128` | 原 `http://host.docker.internal`，容器内读不到 VM 就改这 1 行 |
| DSL 资产 | `dify/apps/智能报告__advanced-chat.yml`（在用）<br>`dify/apps/智能报告__agent-chat.yml`（旧，留档） | 均为 `include_secret=false` 导出，已核验**不含** API key |

> `DIFY_BASE_URL` 不带 `/v1`：网关内部拼 `{base}/v1/chat-messages`。

## 4. M0 接入（v6.11.6 已补齐 ✅）

网关里没有报告 Agent：实测容器内 `AgentType 成员 = [CUSTOMER, EMPLOYEE, STUDENT]`、`hasattr(settings,'DIFY_REPORT_AGENT_KEY') = False`。

```python
# backend/app/config.py  —— Settings 内
    DIFY_REPORT_AGENT_KEY: str = ""

# backend/app/services/ai_service.py
class AgentType(str, Enum):
    CUSTOMER = "CUSTOMER"
    EMPLOYEE = "EMPLOYEE"
    STUDENT = "STUDENT"
    REPORT = "REPORT"          # v6.11.2：M5 报告专用

_AGENT_KEY_MAP = {
    ...
    AgentType.REPORT: settings.DIFY_REPORT_AGENT_KEY,
}
```

已补齐并实测：`ai_source=dify`、`ai_status=available`。补丁原文如下（已落地，保留作说明）。

**M0 加完后的一条验证命令**：

```powershell
# 生成一份投诉周报，检查 ai_source / ai_status
$tok = (irm http://localhost:8000/api/v1/auth/login -Method Post -ContentType 'application/json' -Body '{"username":"13810000004","password":"Test@123456"}').data.access_token
irm http://localhost:8000/api/v1/reports/generate -Method Post -ContentType 'application/json' -Headers @{Authorization="Bearer $tok"} -Body '{"report_type":"complaint_weekly"}'
# 期望 report_content.ai_source == "dify"、ai_status == "available"
```

## 5. 上云 / 合并其他人的 Dify

**应用级合并（推荐）**
1. 目标实例 Studio →「导入 DSL」→ 选 `dify/apps/智能报告__advanced-chat.yml`
2. 重新绑定模型（DSL 不含模型凭据）
3. **发布**（未发布的 Chatflow 调 API 会报 `Workflow not published`——本轮就踩过）
4. 在「访问 API」页重新生成 key，写入各人 `backend/.env`

**整实例迁移（保留历史/知识库）**：版本一致 + `SECRET_KEY` 沿用原值 + Postgres/存储卷/向量库一起搬。

**团队共用最短路径**：一台大家都能访问的机器（桥接 / 云主机 / Cloudflare Tunnel 固定域名）+ 一个 workspace，各人只拿 key。

## 6. 内网穿透（本次未启用）

项目已有 `scripts/start-ngrok.ps1`、`scripts/start-localtunnel.ps1`、`docs/REMOTE_ACCESS.md`。当前本机未装 ngrok/cloudflared，`edu-nginx` 容器未起、8080 未监听，现有脚本直接跑会失败。
临时方案：宿主机执行 `cloudflared tunnel --url http://192.168.184.128:80`，把 `DIFY_BASE_URL` 换成 `https://xxx.trycloudflare.com`（不带 `/v1`）。⚠️ 会把 Dify 控制台一并暴露，穿透前须改弱口令或只放行 `/v1`。

## 7. 副作用与清理提示

取证时在 Dify 上额外创建过 3 把 API key（都不再使用，建议撤销）：

| 应用 | key（打码） |
|---|---|
| 学生管理系统智能助手（89 KB 版） | `app-mUWN****XzIJ` |
| 学生管理系统智能助手（12 KB 版） | `app-fKPD****HCZI` |
| 情感助手 | `app-8kQL****R9LO` |

`DIFY_STUDENT_AGENT_KEY` 已恢复占位 `app-xxx`；`app-yyy` / `app-zzz` 未改动。

## 8. 本轮验证记录

| 时间 | 动作 | 结果 |
|---|---|---|
| 2026-10-18 | 定位实例、校验 key | `192.168.184.128` `/v1/parameters` 200（云端 `api.dify.ai` 对同一 key 返回 401，说明 key 绑实例） |
| 2026-10-18 | 控制台登录 | 文档旧口令 401；用户账号 + base64 密码 + cookie + `X-CSRF-Token` 通过 |
| 2026-10-18 | 旧 Agent 版实测 | `blocking` → 400 `does not support blocking mode` |
| 2026-10-18 | 新建 Chatflow 后 | 首调 400 `Workflow not published` → 用 `POST /console/api/apps/{id}/workflows/publish` 发布 → `blocking` **200** |
| 2026-10-18 | JSON 契约 | `_parse_json` + `_validate` PASS，`<think>` 已剥离 |
| 2026-10-18 | 网关现状 | `AgentType` 无 `REPORT`、`config` 无对应字段 → 交由 M0 补 4 行 |
