# 服务器部署手册

本文档介绍如何将「命理通」Web App 部署到生产服务器。

## 环境准备

### 1. 服务器选择

推荐配置：

- 1 核 2GB 内存以上
- 20GB 以上磁盘
- 公网 IP 与一个域名（可选但推荐，用于 HTTPS）

支持的操作系统：Ubuntu 22.04 LTS / Debian 12 / CentOS 7+ 等主流 Linux 发行版。

### 2. 安装 Docker 与 Docker Compose

以 Ubuntu 为例：

```bash
# 更新包索引
sudo apt-get update

# 安装依赖
sudo apt-get install -y ca-certificates curl gnupg

# 添加 Docker 官方 GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 添加 Docker 软件源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine 与 Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 验证安装
sudo docker --version
sudo docker compose version
```

## 项目部署

### 1. 上传代码

将项目代码上传到服务器，例如 `/opt/metaphysics`：

```bash
sudo mkdir -p /opt/metaphysics
cd /opt/metaphysics

# 方式一：git 克隆
sudo git clone https://github.com/your-repo/metaphysics.git .

# 方式二：直接上传（如 rsync、scp）
# scp -r . user@your-server:/opt/metaphysics
```

### 2. 配置环境变量

```bash
cd /opt/metaphysics
sudo cp .env.example .env
sudo nano .env
```

至少填写以下关键配置：

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

DB_PASSWORD=your_secure_db_password
DATABASE_URL=postgresql+asyncpg://metaphysics:your_secure_db_password@postgres:5432/metaphysics
```

如果使用国产模型，可配置 `openai_compatible`：

```bash
LLM_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_COMPATIBLE_API_KEY=sk-xxxxxxxx
OPENAI_COMPATIBLE_MODEL=qwen-vl-max
```

### 3. 启动服务

```bash
sudo docker compose up -d --build
```

首次构建可能需要几分钟。构建完成后：

- 前端页面：http://your-server-ip
- 后端 API 文档：http://your-server-ip:8000/docs

### 4. 查看日志

```bash
# 所有服务日志
sudo docker compose logs -f

# 仅后端日志
sudo docker compose logs -f backend

# 仅前端日志
sudo docker compose logs -f frontend
```

## HTTPS 配置（推荐）

### 使用 Nginx + Let's Encrypt

如果服务器已经暴露 80/443 端口，建议通过独立 Nginx 或 Traefik 提供 HTTPS。

#### 安装 certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx nginx
```

#### Nginx 反向代理配置

编辑 `/etc/nginx/sites-available/metaphysics`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/metaphysics /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 申请 SSL 证书

```bash
sudo certbot --nginx -d your-domain.com
```

certbot 会自动修改 Nginx 配置并启用 HTTPS。

### 使用 Traefik（容器化方案）

如需完全容器化，可将 docker-compose.yml 中的前端 Nginx 替换为 Traefik，自动管理 Let's Encrypt 证书。

## 更新与维护

### 更新代码后重新部署

```bash
cd /opt/metaphysics
sudo git pull
sudo docker compose down
sudo docker compose up -d --build
```

### 备份数据

PostgreSQL 与 Redis 数据通过 Docker volumes 持久化。定期备份：

```bash
# 备份 PostgreSQL
sudo docker exec metaphysics-postgres pg_dump -U metaphysics metaphysics > backup.sql

# 备份 Redis（如启用持久化）
sudo docker exec metaphysics-redis redis-cli SAVE
sudo docker cp metaphysics-redis:/data/dump.rdb ./dump.rdb
```

### 重启服务

```bash
sudo docker compose restart
```

### 停止服务

```bash
sudo docker compose down
```

## 安全建议

1. **API Key 管理**：切勿将 `.env` 文件提交到 Git。生产环境建议使用 Docker secrets 或密钥管理服务。
2. **防火墙**：仅开放 80/443 端口，关闭不必要的端口。
3. **CORS**：生产环境将 `CORS_ORIGINS` 设置为实际域名，不要使用 `*`。
4. **日志保护**：LLM 输出可能包含用户敏感信息，注意日志保存与访问权限。
5. **内容合规**：命理内容涉及「灾厄」「寿数」等敏感词，建议在页面显著位置添加免责声明。

## 故障排查

### 后端无法启动

```bash
sudo docker compose logs backend
```

常见原因：
- API Key 未配置或错误
- 依赖安装失败
- 端口 8000 被占用

### 前端无法访问 API

检查前端容器是否能连通后端：

```bash
sudo docker exec metaphysics-frontend wget -qO- http://backend:8000/health
```

### 图片上传失败

- 检查图片大小是否超过 Nginx `client_max_body_size`（默认 20M）。
- 检查后端 `ImageProcessor.MAX_FILE_SIZE_MB` 限制。

### LLM 调用超时

大模型响应可能较慢，Nginx 与后端均已设置 300 秒超时。如仍超时，可考虑：
- 使用更快的模型
- 前端改为流式输出（后续版本支持）

## 后续扩展

- 接入 RAG：将命理古籍向量化存入 PGVector，Retriever 检索后注入 Prompt。
- 用户系统：基于 PostgreSQL 实现注册登录、历史记录。
- 流式输出：将 LLM stream 接口暴露为 SSE。
- 监控告警：接入 Prometheus + Grafana 或简单 uptime 监控。
