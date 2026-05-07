#!/bin/bash

echo "=== AMP Platform Status ==="
echo ""

# 检查 Web UI
if curl -s http://127.0.0.1:8899/health > /dev/null; then
    echo "✓ Web UI: Running (http://127.0.0.1:8899)"
    curl -s http://127.0.0.1:8899/health | jq -r '"  Version: \(.version) | Status: \(.status)"' 2>/dev/null || echo "  (jq not installed)"
else
    echo "✗ Web UI: Not running"
fi

echo ""

# 检查 MCP 命令
if command -v amp-mcp &> /dev/null; then
    echo "✓ MCP command: Available"
else
    echo "✗ MCP command: Not found"
fi

echo ""

# 检查数据库
if [ -f amp.db ]; then
    echo "✓ Database: Exists"
    sqlite3 amp.db "SELECT COUNT(*) FROM tunnels" 2>/dev/null | xargs echo "  Tunnels:" || echo "  (sqlite3 not installed)"
    sqlite3 amp.db "SELECT COUNT(*) FROM shells" 2>/dev/null | xargs echo "  Shells:" || echo "  (sqlite3 not installed)"
else
    echo "✗ Database: Not found"
fi

echo ""
echo "==========================="
