# RAG Customer Support Chatbot

A customizable customer support chatbot powered by RAG (Retrieval-Augmented Generation). This application answers questions strictly from your documents, making it easy to deploy a knowledge-based assistant for any business or use case.

## Features

- **Document-Based Q&A:** Answers questions using only your provided documents (PDF/TXT)
- **Embeddable Chat Widget:** Clean, professional chat interface that can be embedded in any website
- **Shipment Tracking:** Mock shipping API for order status queries (customizable)
- **Ticket Creation:** Optional Zendesk integration for escalating to human support
- **Docker Support:** Easy deployment with Docker Compose
- **Configurable Branding:** Easily customize colors, persona, and company details

## Project Structure

```
├── backend/
│   ├── app.py              # Main Flask application
│   ├── rag_engine.py       # RAG logic (LangChain + ChromaDB)
│   ├── brand_config.py     # Branding and persona configuration
│   ├── shipping_api.py     # Mock shipping API
│   ├── zendesk_client.py   # Zendesk ticket integration
│   ├── knowledge_base/     # Place your PDF/TXT documents here
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── templates/
│   │   └── index.html      # Chat widget HTML
│   └── static/
│       ├── style.css       # Styling (customizable)
│       ├── script.js       # Frontend logic
│       └── widget.js       # Embeddable widget script
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
2. Create `backend/.env`:
   ```env
   OPENAI_API_KEY=your-api-key-here
   ```
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
   Create `.env` in the `backend/` folder:
   ```env
   OPENAI_API_KEY=your-api-key-here
   ```

5. **Add knowledge documents:**
   Place PDF or TXT files in `backend/knowledge_base/`

6. **Start the server:**
   ```bash
   python app.py
   ```

7. **Access the chatbot:**
   Open http://127.0.0.1:5000

## Configuration

### Branding & Persona

Edit `backend/brand_config.py` to customize:
- Company name and persona
- Response tone and style
- Greeting messages

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and chat | Yes |
| `ZENDESK_SUBDOMAIN` | Zendesk subdomain for ticket creation | No |
| `ZENDESK_EMAIL` | Zendesk admin email | No |
| `ZENDESK_API_TOKEN` | Zendesk API token | No |

## Usage

- **Chat Widget:** Click the chat bubble in the bottom-right corner
- **Ask Questions:** Query your knowledge base naturally
- **Track Orders:** Type "Status for order [number]" to test shipping lookup
- **Create Tickets:** Request human support to create a Zendesk ticket

## Embedding the Widget

To embed the chat widget on another website:

```html
<script src="https://your-domain.com/static/widget.js"></script>
```

## License

MIT
