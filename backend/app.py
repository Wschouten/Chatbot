"""GroundCoverGroup Chatbot - Flask Application."""
import logging
import os
import re
import json
import datetime
import secrets
import uuid
from typing import Any

from flask import Flask, render_template, request, jsonify, Response, g, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv

from rag_engine import RagEngine
from shipping_api import get_shipment_status
from zendesk_client import ZendeskClient
from brand_config import get_brand_config
from data_retention import run_data_retention_cleanup

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")

# =============================================================================
# SECURITY: CORS Configuration
# Only allow requests from whitelisted domains (update for production)
# =============================================================================
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5000,http://127.0.0.1:5000"
).split(",")

CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)


# =============================================================================
# SECURITY: Response Headers Middleware
# =============================================================================
@app.after_request
def add_security_headers(response: Response) -> Response:
    """Add security headers to all responses."""
    # Build frame-ancestors from allowed origins for CSP
    frame_ancestors = ' '.join(ALLOWED_ORIGINS) if ALLOWED_ORIGINS else "'self'"

    # X-Frame-Options: Use ALLOWALL for widget embedding (CSP frame-ancestors is more secure)
    # Note: X-Frame-Options is deprecated in favor of CSP frame-ancestors
    # We skip X-Frame-Options and rely on CSP for modern browsers

    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS Protection (legacy browsers)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Permissions policy (disable unused features)
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # Content Security Policy - allow framing from allowed origins
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self' " + ' '.join(ALLOWED_ORIGINS) + "; "
        f"frame-ancestors 'self' {frame_ancestors}"
    )
    return response


# Rate limiting configuration
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Constants
MAX_MESSAGE_LENGTH = 1000

# Initialize RAG Engine
rag_engine = RagEngine()

logger.info("Initializing RAG Engine...")

# SAFETY CHECK: Prevent running locally (Zombie processes)
if not os.path.exists('/.dockerenv'):
    logger.warning(
        "Running locally (not in Docker). "
        "RAG features may fail due to Python version. "
        "Consider running via 'docker-compose up' instead."
    )

logger.info(rag_engine.ingest_documents())

# =============================================================================
# GDPR: Data Retention Cleanup (runs on startup)
# =============================================================================
run_data_retention_cleanup(
    sessions_dir="sessions",
    logs_dir="logs",
    sessions_retention_days=int(os.getenv("DATA_RETENTION_SESSIONS_DAYS", "30")),
    logs_retention_days=int(os.getenv("DATA_RETENTION_LOGS_DAYS", "90"))
)

@app.before_request
def assign_request_id() -> None:
    """Assign a unique request ID to each request for tracing."""
    g.request_id = str(uuid.uuid4())[:8]  # Short ID for readability


@app.route('/')
def index():
    return render_template('index.html', brand=get_brand_config())


@app.route('/widget.js')
def serve_widget():
    """Serve the embeddable widget script with proper CORS headers."""
    response = send_from_directory(
        app.static_folder,
        'widget.js',
        mimetype='application/javascript'
    )
    # Allow caching for 1 hour
    response.headers['Cache-Control'] = 'public, max-age=3600'
    # Allow loading from any origin (widget needs to load on Shopify)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/api/session', methods=['POST'])
@limiter.limit("10 per minute")
def create_session() -> Response:
    """Generate a cryptographically secure session ID."""
    # Generate secure random session ID (32 bytes = 256 bits of entropy)
    session_id = f"sess_{secrets.token_urlsafe(24)}"
    return jsonify({"session_id": session_id})

# State Machine for Ticket Flow
zendesk = ZendeskClient()
SESSION_DIR = "sessions"
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

def sanitize_session_id(session_id: str) -> str:
    """Sanitize session_id to prevent path traversal attacks."""
    # Only allow alphanumeric characters, underscores, and hyphens
    return re.sub(r'[^a-zA-Z0-9_\-]', '', session_id)[:100]


def is_valid_email(email: str) -> bool:
    """Validate email address format using RFC 5322 simplified regex."""
    return bool(EMAIL_REGEX.match(email))


def get_session_state(session_id: str) -> dict[str, Any]:
    """Load session state from disk."""
    safe_id = sanitize_session_id(session_id)
    path = os.path.join(SESSION_DIR, f"{safe_id}.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Error loading session %s: %s", safe_id, e)
    return {'state': 'inactive'}


def save_session_state(session_id: str, state: dict[str, Any]) -> None:
    """Save session state to disk."""
    safe_id = sanitize_session_id(session_id)
    path = os.path.join(SESSION_DIR, f"{safe_id}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f)

@app.route('/api/chat', methods=['POST'])
@limiter.limit("30 per minute")
def chat() -> Response:
    """Handle chat messages from the frontend."""
    request_id = g.request_id
    data = request.json
    user_message: str = data.get('message', '') if data else ''
    session_id: str = data.get('session_id', 'unknown_session') if data else 'unknown_session'

    logger.info("[%s] Chat request from session %s", request_id, sanitize_session_id(session_id)[:20])

    # Input validation FIRST (before any processing)
    if not user_message:
        return jsonify({"response": "Please say something!", "request_id": request_id})

    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "response": f"Your message is too long. Please keep it under {MAX_MESSAGE_LENGTH} characters.",
            "request_id": request_id
        })

    # Load State from Disk
    state_data = get_session_state(session_id)
    current_state = state_data.get('state', 'inactive')
    user_lang = state_data.get('language', 'en')
    chat_history: list[dict[str, str]] = state_data.get('chat_history', [])

    # ---------------------------------------------------------
    # CANCEL DETECTION: Allow users to exit ticket flow
    # ---------------------------------------------------------
    cancel_keywords = {
        'cancel', 'stop', 'quit', 'exit', 'no', 'never mind', 'nevermind',
        'annuleren', 'stoppen', 'nee', 'laat maar', 'niet nodig'
    }
    user_lower = user_message.lower().strip()

    if current_state in ('awaiting_name', 'awaiting_email') and user_lower in cancel_keywords:
        # Reset state and preserve chat history
        state_data = {
            'state': 'inactive',
            'chat_history': chat_history
        }
        save_session_state(session_id, state_data)

        if user_lang == 'nl':
            return jsonify({"response": "Geen probleem! Het ticket is geannuleerd. Waarmee kan ik je verder helpen?", "request_id": request_id})
        return jsonify({"response": "No problem! The ticket has been cancelled. How else can I help you?", "request_id": request_id})

    # ---------------------------------------------------------
    # STATE: AWAITING_NAME
    # ---------------------------------------------------------
    if current_state == 'awaiting_name':
        clean_name = rag_engine.extract_name(user_message)
        state_data['name'] = clean_name
        state_data['state'] = 'awaiting_email'
        save_session_state(session_id, state_data)

        if user_lang == 'nl':
            return jsonify({"response": f"Bedankt {clean_name}. Wat is je e-mailadres?", "request_id": request_id})
        return jsonify({"response": f"Thanks {clean_name}. What is your email address?", "request_id": request_id})

    # ---------------------------------------------------------
    # STATE: AWAITING_EMAIL
    # ---------------------------------------------------------
    if current_state == 'awaiting_email':
        email = user_message.strip()
        if not is_valid_email(email):
            if user_lang == 'nl':
                return jsonify({"response": "Dat lijkt geen geldig e-mailadres. Probeer het opnieuw.", "request_id": request_id})
            return jsonify({"response": "That doesn't look like a valid email. Please try again.", "request_id": request_id})
            
        state_data['email'] = email
        name = state_data.get('name', 'Unknown')
        original_q = state_data.get('question', '')
        
        # Create Ticket (pass chat history for context)
        result = zendesk.create_ticket(name, email, original_q, chat_history)

        # Reset State but preserve chat history
        state_data = {
            'state': 'inactive',
            'chat_history': chat_history
        }
        save_session_state(session_id, state_data)
        
        if result:
            ticket_id = result.get('ticket', {}).get('id', '???')
            if user_lang == 'nl':
                return jsonify({"response": f"Top! Ik heb ticket #{ticket_id} voor je aangemaakt. Een collega neemt zo snel mogelijk contact op.", "request_id": request_id})
            else:
                return jsonify({"response": f"Great! I've created ticket #{ticket_id} for you. A colleague will be in touch shortly.", "request_id": request_id})
        else:
            if user_lang == 'nl':
                return jsonify({"response": "Sorry, er ging iets mis bij het aanmaken van het ticket. Bel ons alsjeblieft even.", "request_id": request_id})
            else:
                return jsonify({"response": "I'm sorry, something went wrong creating the ticket. Please call us directly.", "request_id": request_id})


    # Simple Intent Detection for Shipping
    order_match = re.search(r'order\s*#?\s*(\d+)', user_message.lower())
    
    if order_match:
        order_id = order_match.group(1)
        response_text = get_shipment_status(order_id)
        return jsonify({"response": response_text, "request_id": request_id})

    # Fallback to RAG (with conversation history for context)
    logger.debug("Querying RAG for: %s", user_message)
    response_text = rag_engine.get_answer(user_message, chat_history=chat_history)

    # Check for Unknown Signal - offer to create support ticket
    if "__UNKNOWN__" in response_text:
        state_data['state'] = 'awaiting_name'
        state_data['question'] = user_message

        # Detect language using LLM (more reliable than word matching)
        detected_lang = rag_engine.detect_language(user_message)
        state_data['language'] = detected_lang

        if detected_lang == 'nl':
            response_text = (
                "Ik kan het antwoord in mijn documentatie niet vinden. "
                "Wil je dat ik een support ticket aanmaak? Zo ja, wat is je naam? "
                "(Typ 'nee' of 'annuleren' om te stoppen)"
            )
        else:
            response_text = (
                "I don't have the answer to that in my documentation. "
                "Would you like me to create a support ticket? If so, what is your name? "
                "(Type 'no' or 'cancel' to go back)"
            )

        save_session_state(session_id, state_data)

    # Update conversation history for context in future messages
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": response_text})
    # Keep only last 10 messages to avoid token bloat
    state_data['chat_history'] = chat_history[-10:]
    save_session_state(session_id, state_data)

    # LOGGING: Save conversation to file
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Simple logging format with request ID for tracing
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "request_id": request_id,
            "user": user_message,
            "bot": response_text
        }
        
        # File per session (use sanitized ID for safety)
        safe_id = sanitize_session_id(session_id)
        log_file = os.path.join(log_dir, f"chat_{safe_id}.json")

        # Read existing or start new
        history = []
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning("Corrupt log file %s, resetting: %s", log_file, e)
        
        history.append(log_entry)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error("[%s] Conversation logging failed: %s", request_id, e)

    logger.info("[%s] Response sent successfully", request_id)
    return jsonify({"response": response_text, "request_id": request_id})

@app.route('/api/ingest', methods=['POST'])
def ingest():
    """Endpoint to trigger re-ingestion of documents (requires admin API key)."""
    # Check for admin API key
    admin_key = os.environ.get('ADMIN_API_KEY')
    provided_key = request.headers.get('X-Admin-Key')

    if not admin_key:
        logger.warning("ADMIN_API_KEY not configured - /api/ingest is disabled")
        return jsonify({"error": "Endpoint not configured"}), 503

    if not provided_key or provided_key != admin_key:
        logger.warning("Unauthorized /api/ingest attempt from %s", get_remote_address())
        return jsonify({"error": "Unauthorized"}), 401

    result = rag_engine.ingest_documents()
    logger.info("Document re-ingestion triggered successfully")
    return jsonify({"status": result})

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
