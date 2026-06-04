# Promoções Web 2000

Sistema de gerenciamento de promoções distribuído com **RabbitMQ**, **FastAPI** e **Microsserviços**.

---

## Arquitetura

```
┌─────────────────┐
│    Frontend     │ (HTML/JS/SSE)
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  MS Gateway API     │ (FastAPI)
└──┬──────────────┬───┘
   │              │
   ▼              ▼
┌──────────────┐ ┌──────────────┐
│ MS Promoção  │ │ MS Ranking   │ ┌──────────────┐
└──────┬───────┘ └──────┬───────┘ │MS Notificação│
       │                │         └──────────────┘
       └────────┬───────┘
                ▼
        ┌────────────────┐
        │   RabbitMQ     │
        │    (Docker)    │
        └────────────────┘
```

---

## Pré-requisitos

### 1 - Instalar `uv` (Gerenciador de Pacotes Python)

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verificar instalação:**
```bash
uv --version
```

### 2 - Instalar Docker & Docker Compose

**Linux:**
```bash
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
```

**macOS/Windows:** Baixar [Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Verificar instalação:**
```bash
docker --version
docker compose version
```

---

## Configuração Inicial

### 1. Clonar o repositório
```bash
git clone https://github.com/MateusSilva00/p04.git
cd p04
```

### 2. Instalar dependências Python
```bash
uv sync
```

### 3. Gerar chaves criptográficas
```bash
uv run python -m src.core.security
```

---

## Iniciar RabbitMQ (Docker)

### 1. Iniciar container
```bash
docker compose up -d
```

### 2. Verificar status
```bash
docker compose ps
```

### 3. Acessar Dashboard do RabbitMQ
- URL: http://localhost:15672
- Usuário: `guest`
- Senha: `guest`

### 4. Parar container (quando terminar)
```bash
docker compose down
```

---

## Executar os Microsserviços

> **⚠️ IMPORTANTE:** Execute cada comando em um **terminal separado**

### Terminal 1: MS Gateway API
```bash
uv run uvicorn src.ms_gateway.main:app --reload --port 8000
```
- API disponível em: http://localhost:8000
- Swagger (testes): http://localhost:8000/docs

### Terminal 2: MS Promoção
```bash
uv run python -m src.ms_promocao.main
```

### Terminal 3: MS Ranking
```bash
uv run python -m src.ms_ranking.main
```

### Terminal 4: MS Notificação
```bash
uv run python -m src.ms_notificacao.main
```

---

## Usar a Interface Web

### 1. Abrir no navegador

**Linux/macOS:**
```bash
open frontend/index.html
# ou
firefox frontend/index.html
```

**Windows (PowerShell):**
```powershell
start frontend\index.html
```

### 2. Abas disponíveis

#### Loja
- Cadastrar novas promoções
- Validação automática

#### Consumidor
- Conectar com SSE para receber notificações
- Adicionar interesses (categorias)
- Visualizar promoções aprovadas
- Votar (👍 positivo / 👎 negativo)

---

## Fluxo de Dados Completo

1. **Frontend publica promoção** → POST `/promocoes`
2. **Gateway publica evento** → `routing_key="promocao.recebida"`
3. **MS Promoção consome** e valida
4. **MS Promoção publica** → `routing_key="promocao.publicada"`
5. **Gateway consome** e armazena em `approved_promotions`
6. **GET `/promocoes`** retorna promoções aprovadas ✅
7. **Frontend conecta SSE** → recebe eventos em tempo real
8. **Consumidor vota** → `routing_key="promocao.voto"`
9. **MS Ranking consome** votos e publica Hot Deals
10. **Gateway publica evento SSE** → Frontend notifica usuário

---

## Endpoints Principais

### Gateway API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/promocoes` | Listar promoções aprovadas |
| `POST` | `/promocoes` | Cadastrar nova promoção |
| `POST` | `/promocoes/{id}/votos` | Registrar voto |
| `GET` | `/docs` | Swagger interativo |
| `GET` | `/clientes/{id}/sse` | WebSocket SSE |

---

