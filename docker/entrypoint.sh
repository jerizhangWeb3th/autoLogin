#!/bin/bash
set -e

# ===== 1. 启动 FalkorDB =====
echo "Starting FalkorDB..."
redis-server \
  --loadmodule /var/lib/falkordb/bin/falkordb.so \
  --protected-mode no \
  --bind 0.0.0.0 \
  --port 6379 \
  --dir /var/lib/falkordb/data \
  --daemonize yes

echo "Waiting for FalkorDB to be ready..."
until redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; do
  echo "FalkorDB not ready yet, waiting..."
  sleep 1
done
echo "FalkorDB is ready!"

# ===== 2. 启动本地 embedding 服务（BGE 模型，OpenAI 兼容） =====
if ! curl -s -o /dev/null http://127.0.0.1:8100/health 2>/dev/null; then
  echo "[entrypoint] 启动本地 embedding 服务 (8100)..."
  nohup /app/mcp/.venv/bin/python -m uvicorn embed_server:app \
    --app-dir /app/mcp --host 0.0.0.0 --port 8100 \
    > /tmp/embed_server.log 2>&1 &
  for i in $(seq 1 60); do
    if curl -s -o /dev/null http://127.0.0.1:8100/health 2>/dev/null; then
      echo "[entrypoint] embedding 服务就绪"
      break
    fi
    sleep 2
  done
fi

# ===== 3. 启动 FalkorDB Browser（默认开启） =====
if [ "${BROWSER:-1}" = "1" ]; then
  if [ -d "/var/lib/falkordb/browser" ] && [ -f "/var/lib/falkordb/browser/server.js" ]; then
    echo "Starting FalkorDB Browser on port 3000..."
    cd /var/lib/falkordb/browser
    HOSTNAME="0.0.0.0" node server.js > /var/log/graphiti/browser.log 2>&1 &
    echo "FalkorDB Browser started in background"
  else
    echo "Warning: FalkorDB Browser files not found, skipping browser startup"
  fi
fi

# ===== 4. 启动 MCP server（前台） =====
echo "Starting MCP server..."
cd /app/mcp
exec /root/.local/bin/uv run --no-sync main.py
