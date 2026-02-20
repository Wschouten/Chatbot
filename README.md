# RAG Customer Support Chatbot

A customizable customer support chatbot powered by RAG (Retrieval-Augmented Generation). This application answers questions strictly from your documents, making it easy to deploy a knowledge-based assistant for any business or use case.

## Features

- **Document-Based Q&A:** Answers questions using only your provided documents (TXT/PDF), with no hallucination beyond the knowledge base
- **Embeddable Chat Widget:** Clean, professional chat interface that can be embedded in any website
- **Shipment Tracking:** Real-time order status via the Van Den Heuvel StatusWeb API (falls back to mock mode)
- **Email Escalation:** MailerSend integration for escalating to human support (Zendesk also supported)
- **Admin Portal:** Web-based portal to browse conversations and analytics with JSON export
- **Multi-language:** Responds in Dutch or English, auto-detected per user message
- **Docker Support:** Easy deployment with Docker Compose and Gunicorn
- **Configurable Branding:** Customize persona, colors, welcome messages, and company details via environment variables
- **GDPR Compliance:** Configurable data retention for sessions and logs; PII redaction in logs
- **Security Hardened:** CSP headers, CORS whitelisting, rate limiting, constant-time key comparison, startup validation

## Project Structure

```
├── backend/
│   ├── app.py                  # Flask application, security headers, routes, admin portal
│   ├── rag_engine.py           # RAG logic (ChromaDB, metadata, retrieval, LLM calls)
│   ├── brand_config.py         # Branding and persona configuration
│   ├── email_client.py         # MailerSend email escalation
│   ├── zendesk_client.py       # Zendesk ticket escalation (alternative)
│   ├── shipping_api.py         # Van Den Heuvel StatusWeb shipping API
│   ├── admin_db.py             # Admin portal SQLite database
│   ├── data_retention.py       # GDPR data retention cleanup
│   ├── evaluate_rag.py         # RAG evaluation script
│   ├── evaluation/
│   │   ├── test_set.json       # 28-question evaluation test set
│   │   └── evaluation_report.md
│   ├── knowledge_base/         # Place your TXT/PDF documents here (36 files)
│   ├── .env.example            # Environment variable template
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── templates/
│   │   └── index.html          # Chat widget HTML
│   └── static/
│       ├── style.css           # Styling (customizable)
│       ├── script.js           # Frontend logic
│       └── widget.js           # Embeddable widget script
├── .dockerignore
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Prerequisites

- Python 3.11 (or Docker, recommended). Note: Python 3.13+ has ChromaDB compatibility issues.
- OpenAI API Key

## Quick Start

### Option 1: Docker (Recommended)

1. Clone the repository
2. Copy and configure the environment file:
   ```bash
   cp backend/.env.example backend/.env
   ```
   At minimum, set `OPENAI_API_KEY` and `ADMIN_API_KEY`.
3. Add your documents to `backend/knowledge_base/`
4. Run:
   ```bash
   docker-compose up --build
   ```
5. Open http://localhost:5000

### Option 2: Local Development

1. **Navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env — set OPENAI_API_KEY and ADMIN_API_KEY at minimum
   ```

5. **Add knowledge documents:**
   Place TXT or PDF files in `backend/knowledge_base/`

6. **Start the server:**
   ```bash
   python app.py
   ```

7. **Access the chatbot:**
   Open http://127.0.0.1:5000

## Configuration

### Branding & Persona

All branding is controlled through environment variables — no code changes needed:

| Variable | Description |
|---|---|
| `BRAND_NAME` | Company name (e.g., `GroundCoverGroup`) |
| `BRAND_ASSISTANT_NAME` | Name shown in the chat widget |
| `BRAND_PERSONALITY_NL` | Dutch persona prompt for the LLM |
| `BRAND_PERSONALITY_EN` | English persona prompt for the LLM |
| `BRAND_WELCOME_NL` | Dutch greeting message |
| `BRAND_WELCOME_EN` | English greeting message |
| `BRAND_RELEVANT_TOPICS` | Comma-separated topics for scope validation |
| `BRAND_USE_EMOJIS` | `true` / `false` — enable emoji in responses |
| `BRAND_SUPPORT_HEADER` | Admin portal header text |

### Environment Variables

See `backend/.env.example` for a full annotated template. Key variables:

| Variable | Description | Required |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and chat | Yes |
| `ADMIN_API_KEY` | API key for protected admin endpoints | Yes |
| `OPENAI_CHAT_MODEL` | Chat model (default: `gpt-5.2`) | No |
| `OPENAI_EMBEDDING_MODEL` | Embedding model (default: `text-embedding-3-small`) | No |
| `RAG_RELEVANCE_THRESHOLD` | Distance cutoff for retrieval (default: `1.2`) | No |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | No |
| `ESCALATION_METHOD` | `email` (default) or `zendesk` | No |
| `MAILERSEND_API_KEY` | MailerSend API key for email escalation | No |
| `SMTP_FROM_EMAIL` | From address for escalation emails | No |
| `SMTP_TO_EMAIL` | Support inbox address for escalation emails | No |
| `ZENDESK_SUBDOMAIN` | Zendesk subdomain (if using Zendesk escalation) | No |
| `ZENDESK_EMAIL` | Zendesk account email | No |
| `ZENDESK_API_TOKEN` | Zendesk API token | No |
| `SHIPPING_API_KEY` | Van Den Heuvel StatusWeb API key (mock if empty) | No |
| `SHIPPING_API_PASSWORD` | StatusWeb API password | No |
| `DATA_RETENTION_SESSIONS_DAYS` | Session retention in days (default: `30`) | No |
| `DATA_RETENTION_LOGS_DAYS` | Log retention in days (default: `90`) | No |
| `FLASK_DEBUG` | `true` only for local development | No |

> **Note on `ADMIN_API_KEY`:** The app refuses to start in production if this is missing or set to the placeholder value. Generate one with:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

> **Note on embedding model:** Changing `OPENAI_EMBEDDING_MODEL` requires clearing `backend/chroma_db/` and restarting to re-ingest all documents. The chat model can be swapped freely.

## Usage

- **Chat Widget:** Click the chat bubble in the bottom-right corner
- **Ask Questions:** Query your knowledge base in Dutch or English
- **Track Orders:** Ask about order status — the bot queries the shipping API (or mock) automatically
- **Escalate:** Ask to speak to a human — the bot collects your details and sends an escalation email
- **Admin Portal:** Visit `/admin` (requires `ADMIN_API_KEY`) to browse conversations and analytics

## Embedding the Widget

To embed the chat widget on another website:

```html
<script src="https://your-domain.com/static/widget.js"></script>
```

## RAG Evaluation

The project includes a built-in evaluation framework. To run it:

```bash
cd backend
python evaluate_rag.py
```

Results are written to `backend/evaluation/evaluation_report.md` and `evaluation_results.json`. The current test set covers 28 questions across product info, FAQ/policy, cross-product recommendations, English queries, and hallucination checks.

Latest results (2026-02-06): **100% pass rate**, avg latency 3.02s.

## License

MIT
