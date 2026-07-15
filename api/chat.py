"""
V-Agent 0.9.3 — Backend seguro (Vercel Serverless)
Keys ficam APENAS em Vercel Environment Variables.
O utilizador nunca tem acesso às keys.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import json as pyjson
import os
import time
from collections import defaultdict

app = FastAPI(title="V-Agent API", version="0.9.3")

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

# ── Modo agente vs chat ───────────────────────────────────────────────────────
# O Compound é ele próprio um sistema agêntico: corre o seu loop interno e
# devolve prosa polida — NÃO segue o protocolo <tool_call> do V-Agent (chega a
# alucinar listagens de ficheiros em vez de chamar as ferramentas). Pedidos do
# agente (mode="agent") vão para um modelo plano que segue instruções à letra;
# o chat normal mantém o Compound (web search embutido). Cada modelo tem
# bucket de rate limit próprio na Groq, por isso as chains também servem de
# fallback quando a key partilhada satura.
CHAT_CHAIN  = ["groq/compound", "groq/compound-mini", "openai/gpt-oss-120b"]
# Modo agente: gpt-oss-120b segue o protocolo <tool_call> quando instruído
# com firmeza (verificado); llama-4-scout é o fallback recomendado pela Groq
# para tool use; compound-mini é o último recurso.
AGENT_CHAIN = ["openai/gpt-oss-120b", "meta-llama/llama-4-scout-17b-16e-instruct", "groq/compound-mini"]

# Modelos servidos por este backend.
ALLOWED_GROQ_MODELS = ["groq/compound", "groq/compound-mini", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "meta-llama/llama-4-scout-17b-16e-instruct"]

# ── Schema ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    model: str = GROQ_MODEL
    history: list = []  # Histórico de mensagens [{role, content}]
    system: str = ""    # System prompt opcional (personalidade/regras do cliente)
    mode: str = "chat"  # "chat" (Compound) | "agent" (modelo plano p/ tool calls)

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
        "version": "0.9.3",
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
    # Llama foi descontinuado pela Groq. A chain depende do modo: agente →
    # modelo plano (segue o protocolo de ferramentas), chat → Compound.
    chain = AGENT_CHAIN if req.mode == "agent" else CHAT_CHAIN
    model = chain[0]

    # ── Validação da mensagem ─────────────────────────────────────────────────
    # Truncar em vez de rejeitar: a mensagem pode ser um bloco de resultados
    # de ferramentas do agente (ex.: read_file de um ficheiro grande) — um 400
    # aqui mataria o loop de ferramentas a meio da tarefa.
    message = req.message.strip() if req.message else ""
    if not message:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")
    if len(message) > 24_000:
        message = message[:24_000] + "\n…(truncado)"

    # ── Verificar key (configurada no Vercel) ─────────────────────────────────
    if not GROQ_API_KEY:
        # Não expõe detalhes — apenas erro genérico
        raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível.")

    # ── Construir histórico ───────────────────────────────────────────────────
    messages = []
    # System prompt do cliente (identidade + protocolo de ferramentas + contexto).
    # 6000 era curto demais: o TOOLS_DOC ficava truncado quando havia um ficheiro
    # aberto e o agente nunca "aprendia" a sintaxe das ferramentas.
    system = (req.system or "").strip()[:20_000]
    if system:
        messages.append({"role": "system", "content": system})
    # Adicionar histórico (max últimas 10 mensagens; 6k chars cada — resultados
    # de ferramentas a 2k perdiam o conteúdo dos ficheiros lidos)
    if req.history:
        safe_history = [
            {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:6000]}
            for m in req.history[-10:]
            if m.get("role") in ("user", "assistant")
        ]
        messages.extend(safe_history)
    # Mensagem atual
    messages.append({"role": "user", "content": message})

    # ── Chamada Groq ──────────────────────────────────────────────────────────
    def _call_groq(m: str):
        body = {
            "model": m,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.15,
            "stream": False,
        }
        # gpt-oss são modelos de reasoning — com esforço alto a resposta útil
        # pode ficar toda no canal de raciocínio e o content sair vazio.
        if m.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        return requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60,
        )

    def _extract(resp):
        """Texto útil da resposta, ou None se vier vazia.
        Os gpt-oss por vezes emitem tool calls NATIVAS (fora do content,
        mesmo sem 'tools' declaradas) — traduz para o protocolo textual
        <tool_call> do V-Agent para o agente as conseguir executar."""
        try:
            msg = resp.json()["choices"][0]["message"]
        except Exception:
            return None
        parts = []
        content = (msg.get("content") or "").strip()
        if content:
            parts.append(content)
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            try:
                args = pyjson.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            if name:
                parts.append(
                    "<tool_call>" + pyjson.dumps({"tool": name, "args": args}) + "</tool_call>"
                )
        text = "\n".join(parts).strip()
        return text or None

    def _try_chain():
        """Percorre a chain do modo. Devolve (texto|None, modelo, response).
        Avança em QUALQUER falha — erro HTTP (a Groq descontinua modelos com
        frequência) OU resposta vazia (reasoning engoliu o output)."""
        r = None
        for m in chain:
            r = _call_groq(m)
            if r.status_code == 200:
                text = _extract(r)
                if text:
                    return text, m, r
        return None, chain[-1], r

    try:
        content, model, response = _try_chain()

        # O limite da Groq no free tier é ao nível da CONTA (todos os modelos
        # ao mesmo tempo) e por minuto — janelas reabrem em segundos. Uma
        # única espera curta (Retry-After, máx. 6s) resgata a maioria dos
        # bursts sem estourar o tempo da função serverless.
        if content is None and response is not None and response.status_code == 429:
            retry_after = response.headers.get("retry-after", "")
            try:
                wait = min(float(retry_after), 6.0) if retry_after else 2.5
            except ValueError:
                wait = 2.5
            time.sleep(max(wait, 1.0))
            content, model, response = _try_chain()

        # ── Tratar erros sem expor detalhes internos ──────────────────────────
        if content is None:
            status = response.status_code if response is not None else 0
            if status == 401:
                raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível.")
            if status == 429:
                raise HTTPException(status_code=429, detail="Limite de pedidos atingido. Tenta mais tarde.")
            raise HTTPException(status_code=502, detail="Erro ao processar pedido.")

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
