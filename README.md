# GroundCoverGroup Customer Support Chatbot

A professional, Eurostyle-branded customer support chatbot for GroundCoverGroup. This application features a RAG (Retrieval-Augmented Generation) backend to answer questions strictly from your documents, and a mock shipping status API.

## Project Structure

```
GroundCoverChatbot/
├── backend/
│   ├── app.py              # Main Flask Application
│   ├── rag_engine.py       # RAG Logic (LangChain + Chroma)
│   ├── shipping_api.py     # Mock Shipping API
│   ├── knowledge_base/     # DROP YOUR PDF/TXT DOCUMENTS HERE
│   └── requirements.txt    # Python Dependencies
├── frontend/
│   ├── templates/
│   │   └── index.html      # Chat Widget HTML
│   └── static/
│       ├── style.css       # Styling
│       └── script.js       # Frontend Logic
└── README.md
```

## Prerequisites

- Python 3.8+
- An OpenAI API Key (for the RAG functionality)

## Setup Instructions

1.  **Navigate to the backend directory:**
    ```bash
    cd GroundCoverChatbot/backend
    ```

2.  **Create and Activate a Virtual Environment (Optional but Recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Environment Variables:**
    Create a file named `.env` in the `backend/` folder and add your OpenAI Key:
    ```env
    OPENAI_API_KEY=sk-your-api-key-here
    ```

5.  **Add Knowledge Documents:**
    Place your PDF or TXT files into the `backend/knowledge_base/` folder. The bot will automatically read these on startup to build its knowledge base.

## Running the Application

1.  **Start the Server:**
    From the `backend/` directory:
    ```bash
    python app.py
    ```

2.  **Access the Chatbot:**
    Open your web browser and go to:
    `http://127.0.0.1:5000`

## Features

- **Chat Widget:** Click the green chat bubble in the bottom right to open the support window.
- **RAG Q&A:** Ask questions based on the files you put in `knowledge_base`.
- **Shipment Tracking:** Type "Status for order 123" (or similar) to test the mock API.
- **Persona:** The bot acts as a polite, professional "Eurostyle" expert.
