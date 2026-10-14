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
│   └── requirements.txt
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

### 5.1 后端

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填写配置

# 5. 数据库初始化
# 确保PostgreSQL已启动
alembic upgrade head

# 6. 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. 访问API文档
# http://localhost:8000/docs
```

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
- [ ] 搭建开发环境，确保能正常运行
- [ ] 阅读核心代码，理解架构
- [ ] 联系项目负责人，了解背景

---

**最后更新**：2026-10-14  
**维护人**：开发团队
