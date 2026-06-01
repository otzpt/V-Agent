"""
V-Agent 0.7.1 — Backend seguro (Vercel Serverless)
Keys ficam APENAS em Vercel Environment Variables.
O utilizador nunca tem acesso às keys.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import time
from collections import defaultdict

app = FastAPI(title="V-Agent API", version="0.7.1")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
_request_counts: dict = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 30

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Limpa requests antigos (>1 min)
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if now - t < 60
    ]
    if len(_request_counts[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Max 30/min per IP."
        )
    _request_counts[client_ip].append(now)
    return await call_next(request)

# ── Config segura ─────────────────────────────────────────────────────────────
# Keys vêm APENAS de Vercel Environment Variables — nunca do código
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Modelos Groq permitidos (gratuitos)
ALLOWED_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "gemma-7b-it",
]

# ── Schema ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    model: str = "llama-3.3-70b-versatile"
    history: list = []  # Histórico de mensagens [{role, content}]

class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str = "groq"

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Health check — não expõe keys nem detalhes internos."""
    return {
        "status": "ok",
        "version": "0.7.1",
        "provider": "groq",
        "models": ALLOWED_GROQ_MODELS,
    }

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Processa mensagem via Groq.
    Keys nunca são expostas ao utilizador.
    """
    # ── Validação do modelo ───────────────────────────────────────────────────
    if req.model not in ALLOWED_GROQ_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo não permitido. Use um de: {ALLOWED_GROQ_MODELS}"
        )

    # ── Validação da mensagem ─────────────────────────────────────────────────
    message = req.message.strip() if req.message else ""
    if not message:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")
    if len(message) > 8000:
        raise HTTPException(status_code=400, detail="Mensagem demasiado longa (max 8000 chars).")

    # ── Verificar key (configurada no Vercel) ─────────────────────────────────
    if not GROQ_API_KEY:
        # Não expõe detalhes — apenas erro genérico
        raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível.")

    # ── Construir histórico ───────────────────────────────────────────────────
    messages = []
    # Adicionar histórico (max últimas 10 mensagens para não exceder tokens)
    if req.history:
        safe_history = [
            {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:2000]}
            for m in req.history[-10:]
            if m.get("role") in ("user", "assistant")
        ]
        messages.extend(safe_history)
    # Mensagem atual
    messages.append({"role": "user", "content": message})

    # ── Chamada Groq ──────────────────────────────────────────────────────────
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": req.model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.15,
                "stream": False,
            },
            timeout=60,
        )

        # ── Tratar erros sem expor detalhes internos ──────────────────────────
        if response.status_code == 401:
            raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível.")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Limite de pedidos atingido. Tenta mais tarde.")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Erro ao processar pedido.")

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        return ChatResponse(
            content=content,
            model=req.model,
            provider="groq",
        )

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Timeout — o servidor demorou demasiado.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Não foi possível conectar ao serviço.")
    except HTTPException:
        raise
    except Exception:
        # ❌ NUNCA expor a exception real (pode conter keys ou detalhes internos)
        raise HTTPException(status_code=500, detail="Erro interno do servidor.")
