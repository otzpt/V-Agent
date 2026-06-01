# 🔒 Política de Segurança — V-Agent 0.7.1

## Arquitetura de Segurança

```
V-Agent Desktop (sem keys)
        ↓
        POST /chat
        ↓
Backend Vercel (keys em Environment Variables)
        ↓
Groq API
```

O utilizador **nunca** tem acesso às API keys.  
As keys ficam **exclusivamente** em Vercel Environment Variables.

---

## API Keys

### ❌ NUNCA fazer
- Commitar `.env` no GitHub
- Partilhar keys em chats, fóruns ou emails
- Colocar keys diretamente no código Python
- Guardar keys em `config.json` ou ficheiros públicos

### ✅ SEMPRE fazer
- Keys ficam **apenas** em Vercel → Settings → Environment Variables
- `.env` local (se usar) fica protegido pelo `.gitignore`
- Revogar keys comprometidas imediatamente

---

## Segurança do Backend

| Feature | Detalhe |
|---|---|
| **Rate limiting** | 30 requests/min por IP |
| **Whitelist de modelos** | Só modelos Groq gratuitos permitidos |
| **Validação de input** | Max 8000 chars por mensagem |
| **Timeout** | 60s máximo |
| **CORS** | Configurado |
| **Error handling** | Nunca expõe detalhes internos ou keys |
| **Histórico** | Max 10 mensagens por request |

---

## Se a key for comprometida

1. Vai a https://console.groq.com/keys
2. **Delete** a key comprometida
3. **Create** uma nova key
4. Vai a Vercel → Settings → Environment Variables
5. **Update** o valor de `GROQ_API_KEY`
6. Deploy automático em 1-2 min

---

## Reportar Vulnerabilidades

Abre uma **Issue privada** no GitHub:  
https://github.com/otzpt/V-Agent/issues

**Não** publicar vulnerabilidades em fóruns públicos antes de ser resolvida.

---

## Rate Limiting

O backend protege contra abuso automático:
- **Limite:** 30 requests/min por IP
- **Resposta:** HTTP 429 "Too many requests"
- **Reset:** Automático a cada minuto

---

## Dados e Privacidade

- ✅ Nenhum dado é guardado no backend
- ✅ Sem tracking ou analytics
- ✅ Histórico de conversa apenas em memória (por request)
- ✅ Open source — código auditável
