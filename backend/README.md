# 粤教留学项目管理平台 - 后端

本项目后端基于 FastAPI 框架开发。

## 快速开始

### 1. 安装 uv（如果还没安装）

**Windows (PowerShell)**:
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Mac/Linux**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

验证安装：
```bash
uv --version
```

### 2. 安装 Python 3.11

```bash
uv python install
```

这会读取 `.python-version` 文件并安装 Python 3.11。

### 3. 创建虚拟环境并安装依赖

```bash
uv sync
```

这会：
- 在项目目录创建 `.venv/` 虚拟环境
- 安装 `pyproject.toml` 中定义的所有依赖
- 生成 `uv.lock` 锁定文件（确保团队依赖版本一致）

### 4. 激活虚拟环境

**Windows**:
```bash
.venv\Scripts\activate
```

**Mac/Linux**:
```bash
source .venv/bin/activate
```

验证：
```bash
python --version  # 应该显示 Python 3.11.x
uv pip list       # 查看已安装的依赖
```

### 5. 运行开发服务器

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档：http://localhost:8000/docs

## 日常开发

### 添加新依赖

```bash
# 添加生产依赖
uv add <package-name>

# 添加开发依赖
uv add --dev <package-name>
```

### 更新依赖

```bash
uv sync
```

### 代码格式化

```bash
black app/
ruff check app/ --fix
```

### 运行测试

```bash
pytest
```

## 项目结构

```
backend/
├── app/
│   ├── api/          # API路由
│   ├── core/         # 核心模块（安全、异常、中间件）
│   ├── models/       # 数据模型
│   ├── schemas/      # Pydantic模型
│   ├── services/     # 业务逻辑
│   ├── repositories/ # 数据访问
│   ├── utils/        # 工具函数
│   └── main.py       # 应用入口
├── migrations/       # 数据库迁移
├── tests/            # 测试
├── pyproject.toml    # 依赖配置
├── uv.lock           # 依赖锁定
└── .python-version   # Python版本
```

## 常见问题

### Q: 虚拟环境在哪里？
A: 在 `backend/.venv/` 目录下，已加入 `.gitignore`，不会提交到仓库。

### Q: 为什么用 uv 而不是 pip？
A: uv 速度快 10-100 倍，支持 pyproject.toml，依赖锁定更可靠。

### Q: 依赖冲突怎么办？
A: 删除 `uv.lock` 和 `.venv/`，重新运行 `uv sync`。

### Q: 如何查看已安装的依赖？
A: 激活虚拟环境后运行 `uv pip list`。

## 技术栈

- **框架**: FastAPI 0.109+
- **ORM**: SQLAlchemy 2.0+
- **数据库**: PostgreSQL 15+
- **缓存**: Redis 7+
- **认证**: JWT
- **Python**: 3.11
