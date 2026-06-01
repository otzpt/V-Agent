# V-Agent 0.7.1 🚀

Assistente AI desktop com backend seguro em Vercel — keys nunca expostas ao utilizador.

## ✨ Novo em 0.7.1

- ✅ Backend FastAPI em Vercel (sem custos)
- ✅ API keys seguras — nunca visíveis ao utilizador
- ✅ Rate limiting automático (30 req/min)
- ✅ Validação e sanitização de input
- ✅ Works out-of-the-box — sem configuração necessária

## 🏗️ Arquitetura

```
V-Agent Desktop (sem keys)
        ↓
        POST /chat
        ↓
Backend Vercel (keys em Environment Variables)
        ↓
Groq API (gratuito)
```

## 🚀 Setup Rápido (utilizador)

```bash
# 1. Descarrega o ZIP da última release
# 2. Extrai
# 3. Instala dependências
pip install -r requirements.txt

# 4. Executa
python vagent.py
```

**Pronto! Não é necessária nenhuma configuração de keys.**

## 🛠️ Setup Desenvolvimento Local

```bash
# Clona o repositório
git clone https://github.com/otzpt/V-Agent.git
cd V-Agent

# Instala dependências
pip install -r requirements.txt

# Cria .env (opcional — só para backend local)
cp .env.example .env

# Executa
python vagent.py
```

## 🌐 Backend — Deploy Vercel

O backend é **deployed automaticamente** a cada push no GitHub.

Para configurar as keys (apenas o maintainer):
1. Vercel Dashboard → V-Agent → Settings → Environment Variables
2. Add: `GROQ_API_KEY` = `gsk_...`
3. Deploy automático em 1-2 min

## 🔒 Segurança

- Keys **nunca** são visíveis ao utilizador
- Rate limiting automático
- Validação de modelos e input
- Ver [SECURITY.md](SECURITY.md)

## 🤝 Suporte e Contribuições

- Issues: https://github.com/otzpt/V-Agent/issues
- Pull Requests são bem-vindos!

## 📝 Licença

MIT — Ver [LICENSE](LICENSE)
