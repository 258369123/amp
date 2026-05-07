#!/bin/bash
cd /home/xp/test/0506

# 停止 Web UI 服务器
if [ -f web_ui.pid ]; then
    PID=$(cat web_ui.pid)
    echo "Stopping Web UI (PID: $PID)..."
    kill $PID 2>/dev/null
    rm web_ui.pid
    echo "✓ Web UI stopped"
else
    echo "No Web UI PID file found"
    pkill -f "python amp/mcp/run_server.py"
fi

echo "AMP Platform stopped"
