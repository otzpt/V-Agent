"""
V-Agent 0.9.2 — Backend seguro (Vercel Serverless)
Keys ficam APENAS em Vercel Environment Variables.
O utilizador nunca tem acesso às keys.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import time
from collections import defaultdict

app = FastAPI(title="V-Agent API", version="0.9.2")

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

def _client_ip(request: Request) -> str:
    # Atrás do proxy da Vercel, request.client.host é o proxy — TODOS os
    # utilizadores cairiam no mesmo bucket. O IP real vem no x-forwarded-for.
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # /health é um ping barato (o cliente verifica antes de cada chat) —
    # não deve consumir o limite.
    if request.url.path == "/health":
        return await call_next(request)
    client_ip = _client_ip(request)
    now = time.time()
    # Limpa requests antigos (>1 min)
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if now - t < 60
    ]
    if len(_request_counts[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
        # HTTPException dentro de middleware vira 500 (não passa pelos
        # exception handlers) — devolve a resposta 429 diretamente.
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Max 30/min per IP."},
        )
    _request_counts[client_ip].append(now)
    return await call_next(request)

# ── Config segura ─────────────────────────────────────────────────────────────
# Keys vêm APENAS de Vercel Environment Variables — nunca do código
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Modelo ────────────────────────────────────────────────────────────────────
# V-Agent usa o Groq Compound: sistema agêntico com web search + execução de
# código embutidos, ideal para tarefas de programação.
# Os modelos Llama foram descontinuados pela Groq, por isso TODOS os pedidos
# — incluindo clientes antigos (≤0.9.0) que ainda enviam "llama-..." — são
# servidos por Compound. Garante que apps 0.9.0 já instaladas continuam a
# funcionar sem reinstalar.
GROQ_MODEL = "groq/compound"

# Fallbacks quando o Compound atinge o rate limit da key partilhada, por
# ordem: compound-mini (mesma família agêntica, quota própria) e depois
# gpt-oss-120b (modelo plano com limites muito maiores — último recurso
# para o backend nunca ficar mudo). Cada modelo tem bucket próprio na Groq.
FALLBACK_GROQ_MODELS = ["groq/compound-mini", "openai/gpt-oss-120b"]

# Modelos servidos por este backend.
ALLOWED_GROQ_MODELS = [GROQ_MODEL, *FALLBACK_GROQ_MODELS]

# ── Schema ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    model: str = GROQ_MODEL
    history: list = []  # Histórico de mensagens [{role, content}]
    system: str = ""    # System prompt opcional (personalidade/regras do cliente)

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
        "version": "0.9.2",
        "provider": "groq",
        "models": ALLOWED_GROQ_MODELS,
    }

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Processa mensagem via Groq.
    Keys nunca são expostas ao utilizador.
    """
    # ── Modelo ────────────────────────────────────────────────────────────────
    # Llama foi descontinuado pela Groq: qualquer pedido — de clientes novos ou
    # antigos (que ainda enviam "llama-...") — é servido pelo Groq Compound.
    model = GROQ_MODEL

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
    # System prompt do cliente (regras de estilo/ferramentas do V-Agent)
    system = (req.system or "").strip()[:6000]
    if system:
        messages.append({"role": "system", "content": system})
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
    def _call_groq(m: str):
        return requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": m,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.15,
                "stream": False,
            },
            timeout=60,
        )

    try:
        response = _call_groq(model)

        # 429 → percorre os fallbacks (cada um tem quota separada na Groq)
        # antes de desistir. Sem sleep: no máximo duas chamadas extra.
        if response.status_code == 429:
            for fb in FALLBACK_GROQ_MODELS:
                if fb == model:
                    continue
                response = _call_groq(fb)
                if response.status_code != 429:
                    model = fb
                    break

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
            model=model,
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
