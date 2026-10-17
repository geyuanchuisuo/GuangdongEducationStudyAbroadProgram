﻿# AGENTS.md - 项目接手指南

> 给下一个接手这个项目的人/AI 的完整指南

---

## 零、快速定位（打开项目先看这里）

**当前进度**：Phase 0 公共地基已完成（v6.0.1），Phase 1 模块并行开发中；M3 员工模块全部交付（v6.5.0 收官）；v6.6.0 需求对齐差异全部落地；v6.7.0~v6.7.2 管理层端三项+需求核对 52/52；**M4 学生模块第一批已落地（v6.8.0，longtrying_stu 分支：请假/心理关怀/售后/考务/进度/生活FAQ/更多服务，9 paths / 11 endpoints）**；master 已合并 longtrying 全部工作（62d4cff，2026-10-17，无冲突）  
**数据库**：31张表，72条路由路径（71 API + 1 health；employee 42 paths，student 9 paths/11 endpoints），MVC分层结构就绪  
**主基线文档**：`promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md`（v1.2.0，28项决策）

**接手阅读顺序**：
1. 本文件（AGENTS.md）— 项目全貌、技术栈、环境搭建
2. `docs/项目需求文档.md` — 完整业务需求
3. `promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md` — **主基线，权重最高**
4. `docs/开发路线图.md` — 当前进度、下一步任务
5. `docs/接口契约v1.md` — API接口契约（v2.8.0）
6. `docs/更新记录.md` — 最近变更（v6.8.0）

**重要规则**：
- 主基线文档（基础架构方案）权重 > 其他参考文档（共用基座方案、公共框架等）
- 每次迭代完成后必须同步更新 docs/ 下全部6个文件
- 代码写完必须先测试验证，再报告完成

**开发硬性规则（所有人/Agent 接手后必须逐条遵守）**：
1. **文档同步**：每次执行完毕都要同步更新对应的 6 份文档——更新记录.md、AGENTS.md（根目录+docs副本）、接口契约v1.md、开发路线图.md、项目需求文档.md、运行日志.md，方便后续人员/新窗口接手（每个 Agent 和人开工前必须先读 AGENTS.md）
2. **必须测试**：每次执行完毕都要进行测试（本地快速验证优先：compileall + verify_all + 静态功能脚本；不优先启动 docker）
3. **先记录再推送**：测试没有问题，先把测试结果写入文档（更新记录.md「测试结果」行 + 运行日志），然后推送到 git 云仓分支
4. **分支绑定模块**：各自的分支接手各自的模块，其他人的模块不要动（longtrying=M3，longtrying_stu=M4，ZNBG/anhoa/architecture/研判等分支勿动）
5. **共用模块先确认**：如果改动影响到共用模块（M0 审批引擎/事件总线/AI网关/通知中心等），暂时绕过并主动提醒，经确认之后才可以动——否则会影响其他模块开发
6. **固定开发顺序**：开发 → 写入相应的文档（更新、agents等）→ 测试 → 测试问题修复 → 写入相应的文档（更新、agents等）→ 推送 git
7. **牢记硬性规则**：开发过程中随时对照本清单执行，不得跳步

---

## 一、项目概述

**项目名称**：粤教留学项目管理平台  
**公司名称**：广东省教育服务有限公司（粤教服务）  
**项目目标**：构建智能化教育服务管理平台，集成AI能力（Dify）+ 传统业务功能（Python后端）

**核心业务**：
1. 德国双元制职业教育项目
2. 新加坡国际本硕升学项目
3. 国际留学项目（全球）
4. 国际研学项目

---

## 二、技术栈

### 后端
- **框架**：FastAPI 0.109+
- **ORM**：SQLAlchemy 2.0+（异步）
- **数据库**：MySQL 8.0+（端口59000，库名GuangdongEducationStudyAbroadProgram）
- **数据库驱动**：aiomysql（异步MySQL驱动）
- **缓存**：Redis 7+
- **认证**：JWT（python-jose）
- **密码加密**：bcrypt（passlib）
- **Python版本**：3.11（锁定）
- **包管理**：uv（替代pip，速度快10-100倍）
- **依赖管理**：pyproject.toml + uv.lock（确保团队依赖版本一致）

### 前端
- **框架**：Vue 3.4+（Composition API）
- **语言**：TypeScript 5.3+
- **UI库**：Element Plus 2.5+
- **状态管理**：Pinia 2.1+
- **路由**：Vue Router 4.2+
- **HTTP**：Axios 1.6+

### AI能力
- **平台**：Dify 1.16.0-rc1
- **协议**：OpenAI协议接口
- **能力**：Agent编排、RAG知识库、工作流

### 部署
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx
- **对象存储**：MinIO

---

## 三、项目结构

```
GuangdongEducationStudyAbroadProgram/
├── AGENTS.md                   # 项目接手指南（根目录，agent自动读取）
├── backend/                    # Python后端
│   ├── app/
│   │   ├── api/v1/            # API路由
│   │   ├── core/              # 核心模块（安全、异常、中间件）
│   │   ├── models/            # 数据模型（SQLAlchemy）
│   │   ├── schemas/           # Pydantic模型
│   │   ├── services/          # 业务逻辑
│   │   ├── repositories/      # 数据访问
│   │   └── utils/             # 工具函数
│   ├── migrations/            # 数据库迁移（Alembic）
│   ├── tests/                 # 测试
│   ├── .venv/                 # 虚拟环境（已加入.gitignore，不提交）
│   ├── pyproject.toml         # 依赖配置（替代requirements.txt）
│   ├── uv.lock                # 依赖锁定（提交，确保团队版本一致）
│   └── .python-version        # Python版本锁定（3.11）
│
├── frontend/                   # Vue前端
│   ├── src/
│   │   ├── api/               # API接口
│   │   ├── components/        # 组件
│   │   ├── views/             # 页面
│   │   ├── stores/            # Pinia状态
│   │   ├── router/            # 路由
│   │   └── types/             # TS类型
│   └── package.json
│
├── dify/                       # Dify配置
│   ├── workflows/             # Agent工作流
│   └── knowledge_base/        # 知识库文档
│
├── docs/                       # 项目文档
│   ├── AGENTS.md              # 本文件副本（与根目录AGENTS.md保持同步）
│   ├── 项目需求文档.md
│   ├── 更新记录.md
│   ├── 接口契约v1.md          # API接口契约（v2.0）
│   ├── 开发路线图.md
│   └── 运行日志.md
│
├── .gitignore                  # Git忽略配置
├── docker-compose.yml
└── nginx.conf
```

---

## 四、核心模块说明

### 4.1 用户角色

| 角色 | 编码 | 说明 | 账号来源 | 核心功能 |
|------|------|------|----------|----------|
| 意向客户 | `PROSPECT` | 陌生访客、意向客户，尚未与公司有业务往来 | 自行注册（功能权限需由员工开通） | 浏览课程/活动、提交咨询、活动报名 |
| 留学生 | `STUDENT` | 公司核心服务对象 | 员工申请 → 经理审批后转化 | 请假、考务查询、心理关怀、反馈提交、课程报名、进度追踪、生活支持、更多服务 |
| 员工 | `EMPLOYEE` | 公司工作人员（普通员工） | 管理层创建 | CRM录入/跟进（支持文字/PDF/照片/Word/Excel多格式）、代客户申请留学生（需经理审批）、审批学生流程、口述日报、成绩录入 |
| 管理层 | `MANAGER` | 公司管理人员（含经理/总裁） | 系统管理员创建（测试用）或其他管理层创建 | 全部客户查询、经营看板、智能报告、审批员工流程、员工管理、权限配置 |

**权限模型**：
- PROSPECT/STUDENT/EMPLOYEE：固定权限集
- MANAGER：基础权限 + `sys_user.permissions` JSON 字段中定义的额外权限（由系统管理员逐人配置）
- 系统管理员账号：仅测试用，不参与业务流程
- 意向客户注册后状态为"待开通"，需员工审核开通
- 员工审批学生流程（单层审批）；留学生转化需经理审批
- 员工数据隔离：普通员工只能看到自己名下的客户
- 二期拆分为3个独立角色：人事（HR，不可看客户/经营）、经理（MANAGER_DIRECTOR，只看下属+自己客户）、总裁（MANAGER_PRESIDENT，看全部）

### 4.2 数据库表（31张，v6.5.0更新）

> **数据库**：MySQL 8.0+，端口59000，库名 `GuangdongEducationStudyAbroadProgram`
> **自动建表**：应用启动时自动创建所有表，无需手动执行SQL

**公共基础表（M0管理）**：
1. **sys_user** - 统一用户表（含permissions JSON字段）
2. **sys_notification** - 站内消息表
3. **sys_event** - 事件总线表
4. **approval_instance** - 审批实例表（v6.0.0 双表设计）
5. **approval_task** - 审批任务表（v6.0.0 双表设计）
6. **sys_operation_log** - 操作日志表

**客户主数据表（v6.0.0 新增）**：
7. **customer** - 客户主表（全系统客户主数据，手机号为业务唯一键）
8. **pending_lead** - 待补全线索表（微信号等无手机号）

**客户模块表（M1）**：
9. **crm_lead** - 线索表（v6.0.0 改为引用 customer）
10. **customer_assessment** - 客户研判记录表
11. **crm_follow_up** - 客户跟进记录表（v6.0.0 改为引用 customer）

**客服模块表（M2）**：
12. **course_project** - 课程与项目表（公共共用，M2维护）
13. **event_lecture** - 活动与讲座表（公共共用，M2维护）
14. **event_registration** - 活动报名表
15. **cs_chat_session** - 客服会话表
16. **cs_chat_message** - 客服消息表
17. **cs_intent_log** - 意图/转化日志表
18. **cs_faq** - 常见问答对表

**员工模块表（M3）**：
19. **employee_daily_report** - 员工日报表（v6.3.0 加 status/is_late）
20. **student_score** - 学生成绩表
21. **employee_org** - 组织架构表
22. **employee_todo** - 员工待办事项表
23. **daily_report_annotation** - 日报批示表（v6.4.0 新增）

**学生模块表（M4）**：
24. **student_admin_service** - 学生行政服务表
25. **student_psych_profile** - 心理健康画像表
26. **student_psych_alert** - 心理预警表
27. **student_feedback_ticket** - 售后反馈工单表
28. **student_academic** - 学生学业考务表
29. **student_application_progress** - 留学申请进度表

**报告模块表（M5）**：
30. **ai_report** - 智能报告表
31. **ai_report_attachment** - 报告附件表

### 4.3 API接口分组

- `/api/v1/auth/*` - 认证相关
- `/api/v1/users/*` - 用户管理
- `/api/v1/customers/*` - 客户主数据管理（v6.0.0新增）
- `/api/v1/students/*` - 学生服务
- `/api/v1/employees/*` - 员工服务
- `/api/v1/crm/*` - CRM客户管理
- `/api/v1/courses/*` - 课程项目
- `/api/v1/events/*` - 活动管理
- `/api/v1/ai/*` - AI服务（统一网关，禁止直连Dify）
- `/api/v1/approvals/*` - 审批引擎（v6.0.0 升级双表设计）
- `/api/v1/notifications/*` - 通知中心
- `/api/v1/files/*` - 文件存储

### 4.3.1 模块划分与职责边界（v5.0.0新增）

> 详见 `promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md`

| 模块 | 核心职责 | 对外查询接口（供M5报告取数） |
|------|---------|---------------------------|
| **M0 公共基础设施** | 认证鉴权、统一响应/异常、AI网关、事件总线、审批引擎、通知中心、文件存储、数据权限 | - |
| **M1 客户模块** | 客户主数据管理、画像研判、线索跟进、6态状态流转 | `GET /api/v1/customers/{id}`, `GET /api/v1/customers` |
| **M2 客服模块** | 7大场景对话、知识库RAG、活动报名闭环、转线索 | `GET /api/v1/cs/courses`, `GET /api/v1/cs/events` |
| **M3 员工模块** | CRM管理、日报、成绩、审批、口述日报 | `GET /api/v1/employee/reports`, `GET /api/v1/employee/reports/summary` |
| **M4 学生模块** | 请假、心理关怀、售后反馈、学业考务 | `GET /api/v1/student/psych/stats`, `GET /api/v1/student/tickets/stats` |
| **M5 报告模块** | 5类报告生成、经营看板 | 只调各模块接口取数，不直接查别人的表 |

**模块间解耦原则**：
- 模块间业务流转走事件总线（`sys_event`），不直接import对方service
- 报告模块只调各模块暴露的查询接口，不直接查别人的表
- 所有模块共用M0的AI网关，禁止直连Dify

### 4.4 AI Agent（3个，均置顶显示）

1. **智能客服Agent** — 公开主页置顶，7大场景智能应答 + 主动信息采集 + 年轻化人设
2. **企业智能助手Agent** — 员工端置顶，CRM管理、口述日报整理、待办提醒、指令式处理（需二次确认）、权限感知（员工/管理层不同能力）
3. **学生智能助手Agent** — 留学生端置顶，行政服务代办、心理关怀（限制预期：不承诺退费/不给出医疗级建议）、学业提醒、主动推送

### 4.5 页面结构概览

**公开主页（无需登录）**：
- 公司介绍、业务展示、课程/活动浏览、留学政策、FAQ
- 注册/登录入口
- 智能客服Agent窗口（右下角置顶）

**员工端（登录后）**：
- 普通员工：工作台 → CRM录入/查询 → 代客申请 → 审批学生 → 成绩录入 → 口述日报 → 组织架构 → 新人指引 → 待办 → 个人信息
- 管理层（一期）：经营看板 → 全部客户 → 智能报告(5类) → 审批中心 → 用户管理 → 权限配置 → 个人信息
- 企业智能助手Agent窗口（右下角置顶）

**留学生端（登录后）**：
- 工作台 → 请假 → 心理关怀 → 售后反馈 → 学业考务 → 进度追踪 → 生活支持 → 更多服务 → 个人信息
- 学生智能助手Agent窗口（右下角置顶）

### 4.6 关键业务规则

**客户信息采集**：
- 三渠道：意向客户自行注册 / 员工录入（多格式：文字/PDF/照片/Word/Excel） / 管理层录入
- 有效性判断：电话号码为唯一有效性标准，有电话号码=有效线索，无联系方式=仅记录咨询日志
- 客户去重：按电话号码去重，先录入的员工获得跟进权；管理层可变更归属
- 研判结果：仅员工和管理层可见，意向客户和留学生不可查看

**审批流程**：
- 学生请假等流程：负责的员工单层审批
- 意向客户→留学生转化：员工申请 → 经理审批

**消息通知**：站内消息 + Agent主动推送（学生登录后）

**活动报名**：必须注册登录后才可报名，未登录跳转登录页，登录后跳回继续

**指令式业务处理**：Agent执行前需二次确认

### 4.7 一期/二期范围

**一期（核心业务闭环，15周）**：
- 公开主页 + 智能客服Agent
- 员工端（CRM/审批/日报/成绩）+ 企业助手Agent
- 管理层端（看板/报告/审批/权限配置）
- 留学生端（7个子模块）+ 学生助手Agent
- 4个业务角色：PROSPECT/STUDENT/EMPLOYEE/MANAGER

**二期（扩展功能）**：
- 人事模块拆分（独立HR角色）
- 经理/总裁拆分（MANAGER_DIRECTOR + MANAGER_PRESIDENT）
- 专业心理测评量表
- NL2SQL增强
- 语音输入增强

### 4.8 已确认的设计决策

| # | 决策 |
|---|------|
| 1 | 电话号码为客户信息唯一有效性标准 |
| 2 | 客户研判结果页面可见（员工+管理层） |
| 3 | 一期用AI对话式情绪评估，二期引入专业量表 |
| 4 | 学生界面用"更多服务"替代"增值转化" |
| 5 | 一期人事并入MANAGER，二期拆分 |
| 6 | 新增customer客户主表，crm_lead改为引用customer_id（v6.0.0） |
| 7 | 审批引擎升级为双表设计：approval_instance + approval_task（v6.0.0） |
| 8 | 保持code:200响应码风格（v6.0.0） |
| 9 | 图片OCR二期实现，一期不做（v6.0.0） |
| 10 | 保持EMPLOYEE/MANAGER/ADMIN三角色体系，按主文件来（v6.0.0） |
| 11 | 单Vue应用，通过路由守卫区分三端（v6.0.0） |
| 12 | 保持5位HTTP风格错误码（v6.0.0） |

---

## 五、开发环境搭建

### 5.1 后端（使用 uv 管理 Python 虚拟环境）

> **重要**：本项目使用 `uv` 替代传统的 `pip + venv`，速度更快、依赖管理更可靠。
> 所有团队成员必须使用相同的 Python 版本（3.11）和依赖版本（通过 uv.lock 锁定）。

#### 第一步：安装 uv

**Windows（PowerShell，以管理员身份运行）**：
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Mac/Linux**：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**验证安装成功**：
```bash
uv --version
# 应输出版本号，如：uv 0.12.14
```

#### 第二步：克隆项目并进入后端目录

```bash
git clone http://47.106.207.27:3000/longtrying/GuangdongEducationStudyAbroadProgram.git
cd GuangdongEducationStudyAbroadProgram/backend
```

#### 第三步：安装 Python 3.11

```bash
uv python install
```

> 说明：uv 会读取 `backend/.python-version` 文件（内容为 `3.11`），自动安装对应的 Python 版本。
> 如果已安装会跳过，不会重复安装。

**验证**：
```bash
uv python list
# 应看到 3.11.x 版本标记为已安装
```

#### 第四步：创建虚拟环境并安装依赖

```bash
uv sync
```

> 说明：这一步会做三件事：
> 1. 在 `backend/.venv/` 创建虚拟环境（Python 3.11）
> 2. 根据 `pyproject.toml` 安装所有依赖
> 3. 生成/更新 `uv.lock` 锁定文件（确保团队依赖版本完全一致）

**验证**：
```bash
.venv/Scripts/python --version    # Windows
# 或 source .venv/bin/python --version  # Mac/Linux
# 应输出：Python 3.11.x

uv pip list
# 应看到所有已安装的依赖包列表
```

#### 第五步：激活虚拟环境

**Windows**：
```bash
.venv\Scripts\activate
```

**Mac/Linux**：
```bash
source .venv/bin/activate
```

**验证激活成功**（命令行前面会出现 `(base)` 或 `.venv` 标识）：
```bash
python --version
# 应输出：Python 3.11.x

pip list
# 应看到所有已安装的依赖包
```

#### 第六步：配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写实际配置
# 必须配置的项：
#   DATABASE_URL - MySQL数据库连接地址（端口59000，库名GuangdongEducationStudyAbroadProgram）
#   REDIS_URL - Redis连接地址
#   SECRET_KEY - JWT密钥（请用随机字符串）
#   DIFY_BASE_URL - Dify服务地址（版本1.16.0-rc1，OpenAI协议）
#   DIFY_*_AGENT_KEY - 各Agent的API Key
```

#### 第七步：启动开发服务器

```bash
# 确保 MySQL 已启动且数据库 GuangdongEducationStudyAbroadProgram 已创建
# 应用启动时会自动创建所有17张表，无需手动执行迁移
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**验证**：浏览器访问 http://localhost:8000/docs ，应看到 FastAPI 自动生成的 API 文档页面。

#### 日常开发命令速查

| 操作 | 命令 | 说明 |
|------|------|------|
| 激活虚拟环境 | `.venv\Scripts\activate` (Win) / `source .venv/bin/activate` (Mac/Linux) | 每次打开新终端都要执行 |
| 添加生产依赖 | `uv add <包名>` | 自动更新 pyproject.toml 和 uv.lock |
| 添加开发依赖 | `uv add --dev <包名>` | 如 pytest、black 等 |
| 同步依赖 | `uv sync` | 拉取代码后执行，确保依赖一致 |
| 查看已安装依赖 | `uv pip list` | - |
| 代码格式化 | `black app/` | - |
| 代码检查 | `ruff check app/ --fix` | - |
| 运行测试 | `pytest` | - |
| 退出虚拟环境 | `deactivate` | - |

#### 常见问题排查

**Q: `uv sync` 报错 "Unable to determine which files to ship"**
A: 确保 `backend/app/__init__.py` 文件存在。

**Q: 激活虚拟环境后 `python --version` 不是 3.11**
A: 删除 `.venv/` 目录，重新执行 `uv sync`。

**Q: 依赖冲突怎么办？**
A: 删除 `uv.lock` 和 `.venv/`，重新执行 `uv sync`。

**Q: 拉取代码后项目跑不起来？**
A: 执行 `uv sync` 同步依赖（可能有人添加了新依赖）。

**Q: Windows 下激活脚本报错 "无法加载文件，因为在此系统上禁止运行脚本"？**
A: PowerShell 以管理员身份运行：`Set-ExecutionPolicy RemoteSigned`，然后重新激活。

### 5.2 前端

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 配置环境变量
cp .env.example .env

# 4. 运行开发服务器
npm run dev

# 5. 访问页面
# http://localhost:5173
```

### 5.3 Dify

```bash
# 1. 部署Dify（参考官方文档）
# https://docs.dify.ai/getting-started/install-self-hosted

# 2. 创建3个Agent应用
# - 留学生智能管家
# - 企业员工助手
# - 客服Agent

# 3. 导入知识库文档
# 将 dify/knowledge_base/ 下的文档导入Dify知识库

# 4. 获取API Key
# 在Dify后台获取每个应用的API Key，填入后端 .env
```

### 5.4 Docker一键启动

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 六、关键配置文件

### 6.1 后端环境变量（.env）

```bash
# 数据库（MySQL 8.0+，端口59000）
DATABASE_URL=mysql+aiomysql://root:your_password@localhost:59000/GuangdongEducationStudyAbroadProgram

# Redis
REDIS_URL=redis://localhost:6379

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Dify（版本1.16.0-rc1，使用OpenAI协议）
DIFY_BASE_URL=http://localhost:3000
DIFY_VERSION=1.16.0-rc1
DIFY_API_PROTOCOL=openai
DIFY_STUDENT_AGENT_KEY=app-xxx
DIFY_EMPLOYEE_AGENT_KEY=app-yyy
DIFY_CUSTOMER_AGENT_KEY=app-zzz

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password
```

### 6.2 前端环境变量（.env）

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 七、开发规范

### 7.1 Git规范

**分支**：
- `master` - 主干（**2026-10-17 两次合并 longtrying：cba3303（v6.5.0+v6.6.0）→ 62d4cff（v6.7.0~v6.7.2+硬性规则文档），均无冲突**；保护分支已解除，当前可直推）
- `longtrying` - 开发分支（M3 员工模块，已全部收官并合入 master）
- `longtrying_stu` - 开发分支（**M4 学生模块，2026-10-17 从 longtrying e3b0160 新建**，进度追踪统一实现归此分支）
- `develop` - 开发（预留）
- `feature/*` - 功能
- `fix/*` - 修复
- 其他成员分支：ZNBG / anhoa / architecture / 研判 等（勿动他人分支）

**longtrying → master 合并流程**（实测记录见运行日志 LOG-007）：
```
git fetch gitea
git checkout master
git merge --ff-only gitea/master          # 1. 先同步远端 master 最新
git merge longtrying -X theirs --no-edit  # 2. 合并（冲突以 longtrying 为准；站在 master 上，theirs=longtrying）
git push gitea master                     # 3. 推送
git checkout longtrying                   # 4. 切回开发分支
```

**Commit格式**：
```
feat: 新功能
fix: 修复
docs: 文档
style: 格式
refactor: 重构
perf: 性能
test: 测试
chore: 构建
```

### 7.2 代码规范

**Python**：
- 遵循PEP 8
- 使用类型提示
- black格式化
- ruff lint检查

**Vue**：
- Composition API
- TypeScript严格模式
- ESLint + Prettier

### 7.3 统一响应格式

```json
{
    "code": 200,
    "message": "success",
    "data": {},
    "timestamp": 1697270400
}
```

### 7.4 错误码

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 40001 | 用户名或密码错误 |
| 40002 | 参数验证失败 |
| 40003 | 账号已被禁用 |
| 40004 | 用户名已存在 |
| 40006 | 账号待开通 |
| 40101 | 未登录或Token过期 |
| 40301 | 无权限 |
| 40901 | 数据冲突（客户重复录入） |
| 50001 | 服务器错误 |

---

## 八、常见问题

### Q1: 数据库连接失败？

检查：
1. MySQL是否启动（端口59000）
2. DATABASE_URL配置是否正确
3. 数据库 `GuangdongEducationStudyAbroadProgram` 是否已创建
4. 用户名密码是否正确
5. MySQL字符集是否为utf8mb4

### Q2: Dify接口调用失败？

检查：
1. DIFY_BASE_URL是否正确
2. API Key是否正确
3. Agent应用是否已发布
4. 网络是否可达

### Q3: 前端跨域问题？

开发环境：vite.config.ts配置proxy
生产环境：Nginx反向代理

### Q4: Token过期怎么处理？

前端拦截器会自动跳转到登录页，用户重新登录即可。

---

## 九、重要联系人

| 角色 | 姓名 | 联系方式 |
|------|------|----------|
| 项目负责人 | 待定 | - |
| 后端开发 | 待定 | - |
| 前端开发 | 待定 | - |
| AI工程师 | 待定 | - |
| 测试工程师 | 待定 | - |

---

## 十、文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| **AGENTS.md** | **./AGENTS.md**（根目录） | **项目接手指南（agent自动读取，这是主文件）** |
| AGENTS.md 副本 | docs/AGENTS.md | 与根目录保持同步的副本 |
| 项目需求文档 | docs/项目需求文档.md | 完整需求、架构、接口、数据库 |
| 更新记录 | docs/更新记录.md | 版本变更记录（当前v6.8.0） |
| 开发路线图 | docs/开发路线图.md | 分期任务表（Phase 0已完成，M3 收官，Phase 1.4 M4 第一批已落地） |
| 运行日志 | docs/运行日志.md | 排查记录与教训 |
| 接口契约v2 | docs/接口契约v1.md | API接口契约（v2.8.0，31张表，72路由路径） |
| **基础架构方案** | **promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md** | **主基线文档（v1.2.0，28项决策），所有参考文档权重低于此文件** |

> **文档优先级**：基础架构方案_五人并行开发.md > 其他参考文档（共用基座方案、公共框架等）
> **接手顺序**：本文件 → 项目需求文档 → 基础架构方案 → 开发路线图 → 接口契约

---

## 十一、接手检查清单

新接手项目时，按顺序检查：

- [ ] 阅读本文件（AGENTS.md）
- [ ] 阅读项目需求文档
- [ ] 查看开发路线图，了解当前进度
- [ ] 查看更新记录，了解最近变更
- [ ] 查看运行日志，了解已知问题
- [ ] 安装 uv（参考 5.1 节第一步）
- [ ] 进入 `backend/` 目录，执行 `uv python install` 安装 Python 3.11
- [ ] 执行 `uv sync` 创建虚拟环境并安装依赖
- [ ] 激活虚拟环境，验证 `python --version` 输出 3.11.x
- [ ] 配置 `.env` 环境变量
- [ ] 启动开发服务器，访问 http://localhost:8000/docs 验证
- [ ] 阅读核心代码，理解架构
- [ ] 联系项目负责人，了解背景

---

**最后更新**：2026-10-17 14:05（M4 学生模块第一批 v6.8.0 落地 longtrying_stu 分支——新增 backend/app/schemas/student.py、services/student_service.py、api/v1/students.py，main.py 注册双 router；路由 63→72（student 9 paths/11 endpoints）；verify_all 23/23 + M4 静态 18/18 通过；第二批待开发：学生助手 Agent、学业 DDL 主动推送）  
**维护人**：开发团队
