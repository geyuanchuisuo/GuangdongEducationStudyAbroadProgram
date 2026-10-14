# AGENTS.md - 项目接手指南

> 给下一个接手这个项目的人/AI 的完整指南

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
- **数据库**：PostgreSQL 15+
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
- **平台**：Dify 0.8+
- **能力**：Agent编排、RAG知识库、工作流

### 部署
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx
- **对象存储**：MinIO

---

## 三、项目结构

```
GuangdongEducationStudyAbroadProgram/
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
│   ├── 项目需求文档.md
│   ├── 更新记录.md
│   ├── AGENTS.md              # 本文件
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

| 角色 | 说明 | 核心功能 |
|------|------|----------|
| STUDENT | 学生 | 请假、考务查询、心理测评、反馈提交 |
| EMPLOYEE | 员工 | CRM管理、日报、成绩录入、审批 |
| ADMIN | 管理员 | 用户管理、系统配置、数据导出 |

### 4.2 数据库表（11张核心表）

1. **sys_user** - 统一用户表
2. **student_admin_service** - 学生行政服务表
3. **student_psych_profile** - 心理健康画像表
4. **student_psych_alert** - 心理预警表
5. **student_feedback_ticket** - 售后反馈工单表
6. **crm_lead** - 意向客户表
7. **employee_daily_report** - 员工日报表
8. **student_score** - 学生成绩表
9. **course_project** - 课程与项目表
10. **event_lecture** - 活动与讲座表
11. **event_registration** - 活动报名表

### 4.3 API接口分组

- `/api/v1/auth/*` - 认证相关
- `/api/v1/users/*` - 用户管理
- `/api/v1/students/*` - 学生服务
- `/api/v1/employees/*` - 员工服务
- `/api/v1/crm/*` - CRM客户管理
- `/api/v1/courses/*` - 课程项目
- `/api/v1/events/*` - 活动管理
- `/api/v1/ai/*` - AI服务（Dify）

### 4.4 AI Agent（3个）

1. **留学生智能管家** - 请假、考务、心理监测、反馈、知识问答
2. **企业员工助手** - CRM、日报、成绩、待办、业务知识
3. **客服Agent** - 课程推荐、活动报名、FAQ、留学咨询

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
#   DATABASE_URL - PostgreSQL数据库连接地址
#   REDIS_URL - Redis连接地址
#   SECRET_KEY - JWT密钥（请用随机字符串）
#   DIFY_BASE_URL - Dify服务地址
#   DIFY_*_AGENT_KEY - 各Agent的API Key
```

#### 第七步：初始化数据库

```bash
# 确保 PostgreSQL 已启动且数据库已创建
# 执行数据库迁移
alembic upgrade head
```

#### 第八步：启动开发服务器

```bash
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
# 数据库
DATABASE_URL=postgresql+asyncpg://admin:password@localhost:5432/education

# Redis
REDIS_URL=redis://localhost:6379

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Dify
DIFY_BASE_URL=http://localhost:3000
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
- `main` - 生产
- `develop` - 开发
- `feature/*` - 功能
- `fix/*` - 修复

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
| 40101 | 未登录或Token过期 |
| 40301 | 无权限 |
| 50001 | 服务器错误 |

---

## 八、常见问题

### Q1: 数据库连接失败？

检查：
1. PostgreSQL是否启动
2. DATABASE_URL配置是否正确
3. 数据库是否已创建
4. 用户名密码是否正确

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
| 项目需求文档 | docs/项目需求文档.md | 完整需求、架构、接口、数据库 |
| 更新记录 | docs/更新记录.md | 版本变更记录 |
| AGENTS.md | docs/AGENTS.md | 本文件，项目接手指南 |
| 开发路线图 | docs/开发路线图.md | 分期任务表 |
| 运行日志 | docs/运行日志.md | 排查记录与教训 |

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

**最后更新**：2026-10-14  
**维护人**：开发团队
