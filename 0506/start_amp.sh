#!/bin/bash
cd /home/xp/test/0506

# 启动 Web UI 服务器
echo "Starting Web UI server..."
python amp/mcp/run_server.py > web_ui.log 2>&1 &
WEB_PID=$!
echo $WEB_PID > web_ui.pid
echo "Web UI started (PID: $WEB_PID)"
echo "Access at: http://127.0.0.1:8899"

# 等待服务器启动
sleep 3

# 检查服务器状态
if curl -s http://127.0.0.1:8899/health > /dev/null; then
    echo "✓ Web UI is healthy"
else
    echo "✗ Web UI failed to start"
    exit 1
fi

echo ""
echo "AMP Platform is ready!"
echo "- Web UI: http://127.0.0.1:8899"
echo "- MCP: Configure Claude Code and restart"
echo ""
echo "To stop: ./stop_amp.sh"
