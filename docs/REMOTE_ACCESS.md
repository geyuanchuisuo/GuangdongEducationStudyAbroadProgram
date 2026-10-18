# 远程访问指南

> 如何让你本地运行的项目通过公网 URL 被他人访问

---

## 方案一：localtunnel 内网穿透（免注册，实测最快）

> v6.9.1 实测成功的主力方案，无需注册任何账号，npx 直跑。

### 步骤
```powershell
# 1. 确认 nginx 已启动（8080）
curl http://localhost:8080

# 2. 启动穿透（或直接跑脚本）
.\scripts\start-localtunnel.ps1
# 等价于：npx localtunnel --port 8080

# 3. 输出形如 https://xxxx-yyyy-zzzz.loca.lt 即公网地址
```

### 已知问题（重要）
- **随机域名，每次启动变化**——重启后 URL 会变，需重新分发给访问者
- **免费服务端会话不稳定**：运行中可能中途掉线返回 **503**（本地 8080 仍正常）。排查顺序：先确认 `http://localhost:8080` 是 200，再重跑穿透脚本拿新 URL 即可，本地服务无需重启
- 首次打开会显示 localtunnel 确认页，点 Continue 进入
- 极少数网络环境（公司防火墙）可能拦截 loca.lt 域名，此时换方案二

## 方案二：ngrok 内网穿透（需注册 authtoken）

### 适用场景
- 本地开发机演示给同事/客户
- 临时测试，无需购买服务器和域名
- 快速验证功能

### 步骤

#### 1. 安装 ngrok

**方式 A：winget（Windows 推荐）**
```powershell
winget install ngrok.ngrok
```

**方式 B：手动下载**
1. 访问 https://ngrok.com/download
2. 下载 Windows 64-bit 版本
3. 解压 `ngrok.exe` 到任意目录（如 `C:\tools\ngrok\`）
4. 把该目录加入系统 PATH 环境变量

#### 2. 配置 authtoken（首次使用）

1. 注册 ngrok 账号：https://dashboard.ngrok.com/signup
2. 获取 authtoken：https://dashboard.ngrok.com/get-started/your-authtoken
3. 在项目根目录运行：
   ```powershell
   .\scripts\start-ngrok.ps1
   ```
   脚本会提示输入 authtoken，输入一次后永久保存。

#### 3. 启动本地服务

```powershell
.\scripts\build-and-serve.ps1
```

该脚本会：
- 检查并安装前端依赖
- 构建前端生产版本（`frontend/dist/`）
- 启动 Docker 服务（mysql + redis + backend + nginx）
- 等待服务就绪

启动成功后，本地访问地址：**http://localhost**

#### 4. 启动 ngrok 穿透

```powershell
.\scripts\start-ngrok.ps1
```

你会看到类似输出：
```
Forwarding  https://abc123.ngrok.io -> http://localhost:80
```

**把 `https://abc123.ngrok.io` 发给任何人，即可直接访问你的项目！**

---

## 方案三：Cloudflare Tunnel（备选，更稳定）

### 适用场景
- 需要长期稳定的公网访问
- 有自己的域名（可选）
- 国内访问速度要求较高

### 步骤

#### 1. 安装 cloudflared

```powershell
winget install cloudflare.cloudflared
```

或访问 https://github.com/cloudflare/cloudflared/releases 下载 Windows 版。

#### 2. 快速隧道（无需域名）

```powershell
cloudflared tunnel --url http://localhost:80
```

会输出一个临时 URL（如 `https://xxx.trycloudflare.com`），任何人可访问。

#### 3. 绑定域名（可选，更专业）

1. 把域名 DNS 托管到 Cloudflare
2. 创建隧道：`cloudflared tunnel create edu`
3. 配置 DNS 路由：`cloudflared tunnel route dns edu edu.yourdomain.com`
4. 启动：`cloudflared tunnel run edu`

---

## 方案四：云服务器部署（生产环境）

如果你已有云服务器（阿里云/腾讯云/AWS 等），直接部署：

```bash
# 1. 服务器上安装 Docker 和 Docker Compose
# 2. 克隆代码
git clone http://47.106.207.27:3000/longtrying/GuangdongEducationStudyAbroadProgram.git
cd GuangdongEducationStudyAbroadProgram

# 3. 配置后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，修改 DATABASE_URL 等

# 4. 构建前端
cd frontend
npm install
npm run build
cd ..

# 5. 启动全部服务
docker compose up -d

# 6. 配置 Nginx 反向代理 + SSL（可选）
# 参考 nginx.conf，或改用 Caddy/Traefik
```

服务器安全组放行 **80 端口**，即可通过 `http://服务器IP` 访问。

---

## 当前架构说明

```
用户浏览器
    ↓
[公网 URL]（ngrok / cloudflared / 云服务器 IP）
    ↓
[本地/服务器] Nginx :80
    ├─ /api/* → backend:8000（FastAPI）
    └─ /*     → frontend/dist（Vue3 静态文件）
```

- **前端**：Vue3 + Element Plus，构建后为纯静态文件
- **后端**：FastAPI，端口 8000（容器内）
- **数据库**：MySQL 8.0，端口 59000（宿主机映射）
- **缓存**：Redis 7
- **AI**：Dify（需单独部署，见 `docs/接口契约v1.md`）

---

## 常见问题

### Q: ngrok 免费版有什么限制？
- 随机域名（每次启动变化）
- 每分钟 40 个请求限制
- 如需固定域名，升级付费版或改用 Cloudflare Tunnel

### Q: 为什么前端要重新构建？
生产环境使用 `.env.production` 中的 `VITE_API_BASE_URL=/api/v1`，确保 API 请求走相对路径，由 Nginx 统一转发。

### Q: 数据库数据会丢失吗？
不会。`docker-compose.yml` 使用了命名卷（`mysql_data`），容器重建数据保留。

### Q: 如何停止服务？
```powershell
docker compose down          # 停止并删除容器
docker compose down -v       # 同时删除数据卷（慎用）
```

---

**最后更新**：2026-10-17
**维护人**：开发团队
