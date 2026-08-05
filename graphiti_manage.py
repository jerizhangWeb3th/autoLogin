#!/usr/bin/env python3
"""Graphiti 容器管理脚本 — 固化配置，容器重启后自动恢复

用法:
  python3 graphiti_manage.py start    # 启动容器（含 embedding 服务）
  python3 graphiti_manage.py status   # 查看状态
  python3 graphiti_manage.py test     # 端到端验证
  python3 graphiti_manage.py rebuild  # 重建容器（保留配置）
"""
import subprocess, sys, time, os

CONTAINER = "graphiti-mcp"
IMAGE = "zepai/knowledge-graph-mcp:latest"
HOST_PORT = 8000
EMBED_PORT = 8100
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def get_deepseek_key():
    with open("/root/.hermes/.env") as f:
        for line in f:
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.strip().split("=", 1)[1]
    return ""

def setup_container():
    """创建容器 + 配置（依赖、config、patch、entrypoint）"""
    ds_key = get_deepseek_key()
    print(f"1. DeepSeek key: {ds_key[:8]}...")
    rc, out, err = run(f"docker run -d --name {CONTAINER} --restart unless-stopped -p {HOST_PORT}:8000 -e OPENAI_API_KEY={ds_key} -e FALKORDB_URI=redis://localhost:6379 -e FALKORDB_DATABASE=default_db -e GRAPHITI_GROUP_ID=main -e SEMAPHORE_LIMIT=10 {IMAGE} 2>&1 | tail -2", timeout=120)
    print(f"2. 容器创建: {out[-100:]}")

    # 等容器起来
    rc, out, err = run(f"docker exec {CONTAINER} sh -c 'echo ready'", timeout=60)
    for _ in range(20):
        if out == "ready":
            break
        time.sleep(3)
        rc, out, err = run(f"docker exec {CONTAINER} sh -c 'echo ready'", timeout=30)

    # 装依赖
    print("3. 安装依赖...")
    run(f"docker exec {CONTAINER} sh -c 'cd /app/mcp && VIRTUAL_ENV=/app/mcp/.venv uv pip install sentence-transformers fastapi uvicorn 2>&1 | tail -2'", timeout=550)

    # embedding server
    print("4. 配置 embedding server...")
    embed_server = '''from fastapi import FastAPI, Request
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np

app = FastAPI()
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

class EmbedRequest(BaseModel):
    input: list | str
    model: str = "bge-small-zh-v1.5"

@app.post("/v1/embeddings")
async def embeddings(req: EmbedRequest):
    texts = req.input if isinstance(req.input, list) else [req.input]
    vecs = model.encode(texts, normalize_embeddings=True)
    data = [{"object": "embedding", "index": i, "embedding": vec.tolist()} for i, vec in enumerate(vecs)]
    return {"object": "list", "data": data, "model": req.model, "usage": {"prompt_tokens": 0, "total_tokens": 0}}

@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "bge-small-zh-v1.5", "object": "model"}]}

@app.get("/health")
async def health():
    return {"status": "ok"}
'''
    with open(os.path.join(BASE_DIR, "embed_server.py"), "w") as f:
        f.write(embed_server)
    run(f"docker cp {os.path.join(BASE_DIR, 'embed_server.py')} {CONTAINER}:/app/mcp/embed_server.py")

    # config.yaml
    config_yaml = f'''server:
  transport: "http"
  host: "0.0.0.0"
  port: 8000

llm:
  provider: "openai"
  model: "deepseek-chat"
  max_tokens: 4096
  structured_output_mode: "json_schema"
  providers:
    openai:
      api_key: "{ds_key}"
      api_url: "https://api.deepseek.com/v1"

embedder:
  provider: "openai"
  model: "bge-small-zh-v1.5"
  dimensions: 512
  providers:
    openai:
      api_key: "local"
      api_url: "http://127.0.0.1:{EMBED_PORT}/v1"

database:
  provider: "falkordb"
  providers:
    falkordb:
      uri: "redis://localhost:6379"
      password: ""
      database: "default_db"

graphiti:
  group_id: "main"
  user_id: "hermes_user"
  entity_types:
    - name: "Preference"
      description: "User preferences, choices, opinions, or selections"
    - name: "Requirement"
      description: "Requirements, constraints, or conditions"
    - name: "Procedure"
      description: "Procedures, processes, or step-by-step instructions"
    - name: "Organization"
      description: "Organizations, teams, or groups"
    - name: "Person"
      description: "People, users, or individuals"
    - name: "Location"
      description: "Locations, places, or regions"
    - name: "Event"
      description: "Events, occurrences, or incidents"
    - name: "Document"
      description: "Documents, files, or written content"
'''
    with open(os.path.join(BASE_DIR, "config.yaml"), "w") as f:
        f.write(config_yaml)
    run(f"docker cp {os.path.join(BASE_DIR, 'config.yaml')} {CONTAINER}:/app/mcp/config/config.yaml")

    # patch factories.py（LLM base_url）
    print("5. patch factories.py...")
    run(f"docker cp {CONTAINER}:/app/mcp/src/services/factories.py {BASE_DIR}/factories.py")
    with open(os.path.join(BASE_DIR, "factories.py")) as f:
        content = f.read()
    old = """                llm_config = CoreLLMConfig(
                    api_key=api_key,
                    model=config.model,
                    small_model=small_model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )"""
    new = """                llm_config = CoreLLMConfig(
                    api_key=api_key,
                    model=config.model,
                    small_model=small_model,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    base_url=config.providers.openai.api_url,
                )"""
    if old in content:
        content = content.replace(old, new)
        with open(os.path.join(BASE_DIR, "factories.py"), "w") as f:
            f.write(content)
        run(f"docker cp {BASE_DIR}/factories.py {CONTAINER}:/app/mcp/src/services/factories.py")
        print("   ✅ factories.py patched")
    else:
        print("   ⚠️ 目标代码未找到（可能已 patch）")

    # entrypoint（持久化 embedding）
    print("6. 配置 entrypoint...")
    entrypoint = f'''#!/bin/sh
if ! curl -s -o /dev/null http://127.0.0.1:{EMBED_PORT}/health 2>/dev/null; then
    echo "[entrypoint] 启动本地 embedding 服务 ({EMBED_PORT})..."
    nohup /app/mcp/.venv/bin/python -m uvicorn embed_server:app \\
        --app-dir /app/mcp --host 0.0.0.0 --port {EMBED_PORT} \\
        > /tmp/embed_server.log 2>&1 &
    for i in $(seq 1 60); do
        if curl -s -o /dev/null http://127.0.0.1:{EMBED_PORT}/health 2>/dev/null; then
            echo "[entrypoint] embedding 服务就绪"
            break
        fi
        sleep 2
    done
fi
echo "[entrypoint] 启动 Graphiti MCP server..."
exec /root/.local/bin/uv run --no-sync main.py
'''
    with open(os.path.join(BASE_DIR, "entrypoint.sh"), "w") as f:
        f.write(entrypoint)
    run(f"docker cp {BASE_DIR}/entrypoint.sh {CONTAINER}:/app/mcp/entrypoint.sh")
    run(f"docker exec {CONTAINER} sh -c 'chmod +x /app/mcp/entrypoint.sh'")

    print("✅ 配置完成")

def start():
    rc, out, err = run(f"docker ps -a --filter name={CONTAINER} --format '{{{{.Names}}}}'")
    if out == CONTAINER:
        run(f"docker start {CONTAINER}")
        print("容器已启动")
    else:
        print("容器不存在，先 setup...")
        setup_container()

    # 重启容器让 entrypoint 生效（自动拉起 embedding）
    time.sleep(5)
    run(f"docker restart {CONTAINER}")
    print("等待容器 + embedding 服务启动（约90秒）...")
    time.sleep(90)
    rc, out, err = run(f"docker exec {CONTAINER} sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\" http://127.0.0.1:{EMBED_PORT}/health'", timeout=30)
    print(f"embedding 健康: {out}")
    rc, out, err = run(f"docker logs {CONTAINER} --tail 3")
    print("日志:", out[-300:])

def status():
    rc, out, err = run(f"docker ps --filter name={CONTAINER} --format '{{{{.Names}}}} {{{{.Status}}}}'")
    print("容器:", out)
    rc, out, err = run(f"docker exec {CONTAINER} sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\" http://127.0.0.1:{EMBED_PORT}/health'", timeout=30)
    print("embedding:", out)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start()
    elif cmd == "status":
        status()
    elif cmd == "rebuild":
        run(f"docker rm -f {CONTAINER}")
        setup_container()
        start()
    else:
        print(__doc__)
