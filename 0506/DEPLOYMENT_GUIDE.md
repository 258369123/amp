# 🚀 AMP 平台部署和分享指南

## 概述

本指南介绍如何让其他人使用 AMP 平台，包括本地部署、远程部署和团队协作。

---

## 📦 方式 1: GitHub 分享（推荐）

### 步骤 1: 推送到 GitHub

```bash
cd /home/xp/test/0506

# 添加远程仓库
git remote add origin https://github.com/your-username/amp-platform.git

# 推送代码
git push -u origin claude
```

### 步骤 2: 其他人克隆

```bash
# 克隆仓库
git clone https://github.com/your-username/amp-platform.git
cd amp-platform

# 切换到 claude 分支
git checkout claude

# 安装依赖
pip install -e .

# 初始化数据库
python init_db.py

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动 Web UI
./start_amp.sh

# 配置 Claude Code（可选）
# 使用 claude_code_mcp_config.json 中的配置
```

---

## 📦 方式 2: Docker 部署（生产环境）

### 创建 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . /app

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 初始化数据库
RUN python init_db.py

# 暴露端口
EXPOSE 8899

# 启动命令
CMD ["python", "amp/mcp/run_server.py"]
```

### 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  amp-web:
    build: .
    ports:
      - "8899:8899"
    environment:
      - AMP_DATABASE__URL=sqlite:///data/amp.db
      - AMP_CONTEXT__VECTOR_DB_PATH=/data/chroma_db
      - AMP_MCP__HOST=0.0.0.0
      - AMP_MCP__PORT=8899
    volumes:
      - amp-data:/data
    restart: unless-stopped

volumes:
  amp-data:
```

### 使用 Docker

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 📦 方式 3: 打包分发

### 创建分发包

```bash
cd /home/xp/test/0506

# 创建分发目录
mkdir -p dist/amp-platform

# 复制必要文件
cp -r amp dist/amp-platform/
cp -r examples dist/amp-platform/
cp pyproject.toml dist/amp-platform/
cp README.md dist/amp-platform/
cp .env dist/amp-platform/.env.example
cp init_db.py dist/amp-platform/
cp *.sh dist/amp-platform/
cp *.md dist/amp-platform/

# 创建安装脚本
cat > dist/amp-platform/install.sh << 'EOF'
#!/bin/bash
echo "Installing AMP Platform..."

# 检查 Python 版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# 安装依赖
pip install -e .

# 初始化数据库
python init_db.py

# 配置环境变量
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please edit it with your settings."
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your settings"
echo "2. Run: ./start_amp.sh"
echo "3. Access Web UI at: http://127.0.0.1:8899"
EOF

chmod +x dist/amp-platform/install.sh

# 打包
cd dist
tar -czf amp-platform.tar.gz amp-platform/
echo "Package created: dist/amp-platform.tar.gz"
```

### 其他人使用

```bash
# 解压
tar -xzf amp-platform.tar.gz
cd amp-platform

# 安装
./install.sh

# 启动
./start_amp.sh
```

---

## 🌐 方式 4: 远程服务器部署

### 在服务器上部署

```bash
# SSH 到服务器
ssh user@your-server.com

# 克隆代码
git clone https://github.com/your-username/amp-platform.git
cd amp-platform

# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
nano .env  # 编辑配置

# 初始化数据库
python init_db.py

# 使用 systemd 管理服务
sudo nano /etc/systemd/system/amp-web.service
```

### systemd 服务文件

```ini
[Unit]
Description=AMP Platform Web UI
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/amp-platform
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python amp/mcp/run_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 启动服务

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start amp-web

# 开机自启
sudo systemctl enable amp-web

# 查看状态
sudo systemctl status amp-web
```

### 配置 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name amp.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8899;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 👥 方式 5: 团队协作

### 多用户配置

#### 1. 使用不同的认证 Token

编辑 `.env`:
```bash
# 用户 1
AMP_MCP__AUTH_TOKEN=user1_token_here

# 用户 2
AMP_MCP__AUTH_TOKEN=user2_token_here
```

#### 2. 使用数据库权限

```bash
# 创建只读用户
sqlite3 amp.db "CREATE USER readonly WITH PASSWORD 'password';"
sqlite3 amp.db "GRANT SELECT ON ALL TABLES TO readonly;"
```

#### 3. 使用 Git 协作

```bash
# 团队成员克隆仓库
git clone https://github.com/your-username/amp-platform.git

# 创建功能分支
git checkout -b feature/new-tool

# 提交更改
git add .
git commit -m "Add new tool"
git push origin feature/new-tool

# 创建 Pull Request
```

---

## 📚 文档分享

### 必须提供的文档

1. **README.md** - 项目介绍
2. **QUICKSTART.md** - 快速开始
3. **CLAUDE_CODE_MCP_SETUP.md** - Claude Code 配置
4. **USING_MCP_AND_WEBUI.md** - 使用指南
5. **DEPLOYMENT_GUIDE.md** - 本文档

### 创建用户手册

```bash
# 生成 PDF 文档（需要 pandoc）
pandoc README.md -o AMP_User_Manual.pdf

# 或创建 HTML 文档
pandoc README.md -o AMP_User_Manual.html
```

---

## 🔐 安全考虑

### 1. 环境变量

不要提交 `.env` 文件到 Git：

```bash
# .gitignore
.env
*.db
*.log
web_ui.pid
chroma_db/
```

### 2. 认证配置

生产环境使用强密码：

```bash
# 生成随机 token
openssl rand -hex 32
```

### 3. 网络安全

```bash
# 只允许本地访问
AMP_MCP__HOST=127.0.0.1

# 或使用防火墙
sudo ufw allow from 192.168.1.0/24 to any port 8899
```

---

## 📊 监控和日志

### 日志配置

```bash
# 查看 Web UI 日志
tail -f web_ui.log

# 查看系统日志
journalctl -u amp-web -f
```

### 监控脚本

```bash
# 定期检查状态
*/5 * * * * /path/to/amp-platform/check_amp.sh >> /var/log/amp-check.log
```

---

## 🎓 培训材料

### 创建演示视频

1. 录制 Web UI 使用演示
2. 录制 Claude Code 集成演示
3. 录制常见操作流程

### 创建教程

1. **基础教程**: 安装和配置
2. **进阶教程**: 创建隧道链
3. **高级教程**: 自定义工具开发

---

## 📦 发布清单

在分享之前，确认：

- [ ] 代码已推送到 Git
- [ ] 文档已完善
- [ ] 测试已通过
- [ ] 示例配置已提供
- [ ] 安装脚本已测试
- [ ] 安全配置已检查
- [ ] 依赖版本已固定
- [ ] 许可证已添加

---

## 🚀 快速分享命令

### 分享给同事（本地网络）

```bash
# 启动服务器，监听所有接口
AMP_MCP__HOST=0.0.0.0 python amp/mcp/run_server.py

# 告诉同事访问
# http://your-ip:8899
```

### 分享给远程用户

```bash
# 使用 ngrok 创建公网隧道
ngrok http 8899

# 分享 ngrok URL
# https://xxxxx.ngrok.io
```

---

## 📖 示例：完整部署流程

### 场景：部署到团队服务器

```bash
# 1. 在服务器上克隆代码
ssh team-server
git clone https://github.com/your-username/amp-platform.git
cd amp-platform

# 2. 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -e .

# 3. 配置环境
cp .env.example .env
nano .env  # 编辑配置

# 4. 初始化数据库
python init_db.py

# 5. 启动服务
./start_amp.sh

# 6. 配置防火墙
sudo ufw allow 8899/tcp

# 7. 通知团队
echo "AMP Platform is ready at: http://team-server:8899"
```

---

## 🎉 总结

现在您可以通过以下方式分享 AMP 平台：

1. ✅ **GitHub** - 开源分享
2. ✅ **Docker** - 容器化部署
3. ✅ **打包** - 离线分发
4. ✅ **服务器** - 团队部署
5. ✅ **协作** - Git 工作流

选择最适合您团队的方式！

---

## 📞 获取帮助

如果遇到问题：

1. 查看文档目录中的相关指南
2. 运行 `./check_amp.sh` 检查状态
3. 查看日志文件 `web_ui.log`
4. 运行测试 `python amp/mcp/test_mcp_server.py`

---

**祝您部署顺利！** 🚀
