from fastapi import FastAPI, Request
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
