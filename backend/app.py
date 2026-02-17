"""GroundCoverGroup Chatbot - Flask Application."""
import logging
import os
import re
import json
import datetime
import secrets
import uuid
from functools import wraps
from typing import Any

from flask import Flask, render_template, request, jsonify, Response, g, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv

from rag_engine import RagEngine, get_openai_health
from shipping_api import get_shipment_status, get_shipping_client
from zendesk_client import ZendeskClient
from email_client import EmailClient
from brand_config import get_brand_config
from data_retention import run_data_retention_cleanup
import admin_db
from pathlib import Path


# Load environment variables
load_dotenv()

# =============================================================================
# SECURITY: ADMIN_API_KEY Startup Validation
# =============================================================================
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')
PLACEHOLDER_VALUES = ['', 'CHANGE_ME_generate_a_secure_key_here']

if not ADMIN_API_KEY or ADMIN_API_KEY in PLACEHOLDER_VALUES:
    # Check if we're in debug/development mode
    is_debug = os.getenv('FLASK_DEBUG', '').lower() == 'true' or os.getenv('FLASK_ENV', '') == 'development'

    if is_debug:
        # Debug mode: log warning but allow startup
        logging.critical(
            "SECURITY WARNING: ADMIN_API_KEY is not set or uses a placeholder value. "
            "This is ONLY acceptable in debug/development mode. "
            "Set a secure key for production!"
        )
    else:
        # Production mode: refuse to start
        raise SystemExit(
            "FATAL: ADMIN_API_KEY is not set or uses a placeholder value. "
            "Set ADMIN_API_KEY to a secure random string in your environment. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent  # .../backend
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR / "templates"),
    static_folder=str(FRONTEND_DIR / "static"),
)


# =============================================================================
# SECURITY: CORS Configuration
# Only allow requests from whitelisted domains (update for production)
# =============================================================================
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000"
    ).split(",")
]

# =============================================================================
# SECURITY: Validate ALLOWED_ORIGINS at Startup
# =============================================================================
PLACEHOLDER_PATTERNS = ['your-', 'example', 'placeholder']
for origin in ALLOWED_ORIGINS:
    if any(pattern in origin.lower() for pattern in PLACEHOLDER_PATTERNS):
        logger.warning(
            "SECURITY WARNING: ALLOWED_ORIGINS contains a placeholder-like value: '%s'. "
            "This may indicate a misconfiguration. Please verify your CORS settings.",
            origin
        )

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
    # Content Security Policy - admin pages need relaxed rules for inline
    # scripts and blob: URLs (for JSON export downloads)
    is_admin = request.path.startswith('/admin')
    if is_admin:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self' blob:; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' " + ' '.join(ALLOWED_ORIGINS) + "; "
            f"frame-ancestors 'self' {frame_ancestors}"
        )
    else:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' " + ' '.join(ALLOWED_ORIGINS) + "; "
            f"frame-ancestors 'self' {frame_ancestors}"
        )

    # Cache-Control headers for API routes (including admin API)
    if request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'

    return response


# Rate limiting configuration
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# =============================================================================
# SECURITY: Reusable Admin Auth Decorator (Feature 30b)
# =============================================================================
def require_admin_key(f):
    """Decorator to require X-Admin-Key header for admin routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_key = os.environ.get("ADMIN_API_KEY")
        provided_key = request.headers.get("X-Admin-Key")

        if not admin_key:
            logger.warning("ADMIN_API_KEY not configured - admin API is disabled")
            return jsonify({"error": "Admin API not configured"}), 500

        if not provided_key or not secrets.compare_digest(provided_key, admin_key):
            logger.warning(
                "Unauthorized admin access attempt from %s on %s",
                request.remote_addr, request.path,
            )
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)
    return decorated_function


# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Constants
MAX_MESSAGE_LENGTH = 1000
VALID_STATUSES = {"open", "resolved", "escalated", "unknown_flagged"}
LABEL_NAME_RE = re.compile(r'^[a-zA-Z0-9-]+$')
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

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

# =============================================================================
# Portal DB: Initialize SQLite and register teardown (Feature 30a)
# =============================================================================
admin_db.init_db(app)

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
    """Enhanced health check with dependency awareness."""
    health_status = {
        "status": "ok",
        "dependencies": {}
    }
    status_code = 200

    # Check ChromaDB connection
    try:
        collection = rag_engine.collection
        if collection:
            doc_count = collection.count()
            health_status["dependencies"]["chromadb"] = {
                "status": "healthy",
                "document_count": doc_count
            }
        else:
            health_status["dependencies"]["chromadb"] = {
                "status": "degraded",
                "message": "Collection not initialized"
            }
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["chromadb"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
        status_code = 503

    # Check OpenAI client initialization
    try:
        openai_health = get_openai_health()

        health_status["dependencies"]["openai"] = openai_health

        if openai_health.get("status") != "healthy":
            health_status["status"] = "unhealthy"
            status_code = 503

    except Exception as e:
        health_status["dependencies"]["openai"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "unhealthy"
        status_code = 503

    # Check escalation method configuration
    try:
        escalation_key = "email" if ESCALATION_METHOD == "email" else "zendesk"
        if escalation_client.use_mock:
            health_status["dependencies"][escalation_key] = {
                "status": "mock_mode",
                "message": f"Using mock {escalation_key} client (no real calls)"
            }
        else:
            health_status["dependencies"][escalation_key] = {
                "status": "configured",
                "message": f"{escalation_key.title()} client configured"
            }

    except Exception as e:
        health_status["dependencies"]["escalation"] = {
            "status": "error",
            "error": str(e)
        }

    # Check shipping API
    try:
        shipping_client = get_shipping_client()
        if shipping_client.use_mock:
            health_status["dependencies"]["shipping"] = {
                "status": "mock_mode",
                "message": "Using mock shipping responses (no API key)"
            }
        else:
            health_status["dependencies"]["shipping"] = {
                "status": "configured",
                "message": "Shipping API configured"
            }
    except Exception as e:
        health_status["dependencies"]["shipping"] = {
            "status": "error",
            "error": str(e)
        }

    return jsonify(health_status), status_code

@app.route('/api/session', methods=['POST'])
@limiter.limit("10 per minute")
def create_session() -> Response:
    """Generate a cryptographically secure session ID."""
    # Generate secure random session ID (32 bytes = 256 bits of entropy)
    session_id = f"sess_{secrets.token_urlsafe(24)}"
    return jsonify({"session_id": session_id})

# State Machine for Ticket Flow
# ESCALATION_METHOD: "email" (default) sends SMTP email, "zendesk" creates Zendesk ticket
ESCALATION_METHOD = os.environ.get("ESCALATION_METHOD", "email").lower()

if ESCALATION_METHOD == "zendesk":
    escalation_client = ZendeskClient()
    logger.info("Escalation method: Zendesk ticket creation")
else:
    escalation_client = EmailClient()
    logger.info("Escalation method: SMTP email")
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


def _redact_pii_for_log(text: str) -> str:
    """Redact personally identifiable information from text for logging purposes."""
    if not text:
        return text
    # Replace email addresses with redaction marker
    redacted = re.sub(
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        '[EMAIL_REDACTED]',
        text
    )
    return redacted


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


def format_shipping_response(result: dict[str, Any], order_id: str) -> str:
    """Format shipping API result into user-friendly Dutch message."""
    status = result["status"]
    details = result.get("details", {})
    desc = details.get("status_description", "")

    # Build the main status message
    if status == "delivered":
        date = details.get("date", "")
        time = details.get("time", "")
        msg = f"✅ Je zending **#{order_id}** is afgeleverd"
        if date:
            msg += f" op {date}"
        if time:
            msg += f" om {time}"
        msg += "! 🎉"

    elif status == "in_transit":
        msg = f"🚚 Je zending **#{order_id}** is onderweg!"
        if desc:
            msg += f"\n\n📋 Status: {desc}"
        date = details.get("date", "")
        time = details.get("time", "")
        if date and time:
            msg += f"\n🕐 Laatste update: {date} om {time}"

    elif status == "at_depot":
        msg = f"📦 Je zending **#{order_id}** is bij het depot."
        if desc:
            msg += f"\n\n📋 Status: {desc}"

    else:
        msg = f"📦 Status zending **#{order_id}**: {desc or status}"

    # Add ETA if available
    eta_from = details.get("eta_from", "")
    eta_until = details.get("eta_until", "")
    if eta_from and eta_until:
        msg += f"\n\n⏰ Verwachte levering: tussen {eta_from} en {eta_until}"

    # Add Track & Trace link if available
    tracking_url = details.get("tracking_url", "")
    if tracking_url:
        msg += f"\n\n🔗 [Volg je zending hier]({tracking_url})"

    # Add note if present
    note = details.get("note", "")
    if note:
        msg += f"\n\n💬 Opmerking: {note}"

    return msg


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
        return jsonify({"response": "Hé, ik zie niks! 😊 Typ gerust je vraag.", "request_id": request_id})

    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "response": f"Oei, dat is een lange tekst! 😅 Kun je het iets korter houden (max {MAX_MESSAGE_LENGTH} tekens)?",
            "request_id": request_id
        })

    # Load State from Disk
    state_data = get_session_state(session_id)
    current_state = state_data.get('state', 'inactive')
    user_lang = state_data.get('language', 'en')
    chat_history: list[dict[str, str]] = state_data.get('chat_history', [])

    # ---------------------------------------------------------
    # STATE: AWAITING_NAME (with flexible intent detection)
    # ---------------------------------------------------------
    if current_state == 'awaiting_name':
        # Use LLM to understand what the user actually wants
        intent = rag_engine.detect_ticket_intent(user_message)
        logger.debug("Ticket intent detected: %s", intent)

        if intent == 'declining':
            # User doesn't want a ticket - cancel and return to chat
            state_data = {'state': 'inactive', 'chat_history': chat_history}
            save_session_state(session_id, state_data)

            if user_lang == 'nl':
                return jsonify({"response": "Geen probleem! 👍 Waarmee kan ik je verder helpen?", "request_id": request_id})
            return jsonify({"response": "No problem! 👍 How else can I help you?", "request_id": request_id})

        elif intent == 'new_question':
            # User is asking something else - cancel ticket flow and process as RAG
            state_data = {'state': 'inactive', 'chat_history': chat_history}
            save_session_state(session_id, state_data)
            # Fall through to RAG processing below (don't return here)

        else:  # 'giving_name'
            # User provided their name - extract and continue
            clean_name = rag_engine.extract_name(user_message)
            state_data['name'] = clean_name
            state_data['state'] = 'awaiting_email'
            save_session_state(session_id, state_data)

            if user_lang == 'nl':
                return jsonify({"response": f"Leuk je te ontmoeten, {clean_name}! 👋 Wat is je e-mailadres?", "request_id": request_id})
            return jsonify({"response": f"Nice to meet you, {clean_name}! 👋 What's your email address?", "request_id": request_id})

    # ---------------------------------------------------------
    # STATE: AWAITING_EMAIL (with decline detection)
    # ---------------------------------------------------------
    if current_state == 'awaiting_email':
        email = user_message.strip()

        # If it's not a valid email, check if user is declining
        if not is_valid_email(email):
            intent = rag_engine.detect_ticket_intent(user_message)
            logger.debug("Email state - intent detected: %s", intent)

            if intent == 'declining':
                # User changed their mind - cancel ticket
                state_data = {'state': 'inactive', 'chat_history': chat_history}
                save_session_state(session_id, state_data)

                if user_lang == 'nl':
                    return jsonify({"response": "Geen probleem! 👍 Waarmee kan ik je verder helpen?", "request_id": request_id})
                return jsonify({"response": "No problem! 👍 How else can I help you?", "request_id": request_id})

            elif intent == 'new_question':
                # User asking something else - cancel and process as RAG
                state_data = {'state': 'inactive', 'chat_history': chat_history}
                save_session_state(session_id, state_data)
                # Fall through to RAG processing below

            else:
                # Genuinely invalid email - ask again
                if user_lang == 'nl':
                    return jsonify({"response": "Hmm, dat lijkt niet helemaal te kloppen 🤔 Kun je je e-mailadres nog een keer checken?", "request_id": request_id})
                return jsonify({"response": "Hmm, that doesn't look quite right 🤔 Could you double-check your email address?", "request_id": request_id})

        else:
            # Valid email - proceed with ticket creation
            state_data['email'] = email
            name = state_data.get('name', 'Unknown')
            original_q = state_data.get('question', '')

            # Escalate (send email or create Zendesk ticket)
            if ESCALATION_METHOD == "zendesk":
                result = escalation_client.create_ticket(name, email, original_q, chat_history)
            else:
                result = escalation_client.send_email(name, email, original_q, chat_history)

            # Reset State and clear history after escalation
            state_data = {
                'state': 'inactive',
                'chat_history': []
            }
            save_session_state(session_id, state_data)

            if result:
                if ESCALATION_METHOD == "zendesk":
                    ticket_id = result.get('ticket', {}).get('id', '???')
                    if user_lang == 'nl':
                        return jsonify({"response": f"Top! Ik heb ticket #{ticket_id} voor je aangemaakt. Een collega neemt zo snel mogelijk contact op.", "request_id": request_id})
                    else:
                        return jsonify({"response": f"Great! I've created ticket #{ticket_id} for you. A colleague will be in touch shortly.", "request_id": request_id})
                else:
                    if user_lang == 'nl':
                        return jsonify({"response": "Top! Ik heb je bericht doorgestuurd naar een collega. We nemen zo snel mogelijk contact met je op via e-mail.", "request_id": request_id})
                    else:
                        return jsonify({"response": "Great! I've forwarded your message to a colleague. We'll get in touch via email as soon as possible.", "request_id": request_id})
            else:
                if user_lang == 'nl':
                    return jsonify({"response": "Sorry, er ging iets mis bij het versturen van je bericht. Neem alsjeblieft direct contact met ons op.", "request_id": request_id})
                else:
                    return jsonify({"response": "I'm sorry, something went wrong sending your message. Please contact us directly.", "request_id": request_id})


    # Check if user is responding to a pending order confirmation
    if state_data.get('awaiting_order_confirmation'):
        # Check for timeout (5 minutes)
        confirmation_time = state_data.get('confirmation_timestamp')
        if confirmation_time:
            ts = datetime.datetime.fromisoformat(confirmation_time)
            if datetime.datetime.now() - ts > datetime.timedelta(minutes=5):
                # Timeout - clear stale confirmation state
                state_data.pop('awaiting_order_confirmation', None)
                state_data.pop('pending_order_id', None)
                state_data.pop('confirmation_timestamp', None)
                save_session_state(session_id, state_data)
                # Fall through to normal processing (don't treat as confirmation)
            else:
                # Not timed out - process confirmation response
                order_id = state_data.get('pending_order_id')

                # User confirmed (yes/ja/correct/klopt/inderdaad)
                if re.search(r'\b(ja|yes|correct|klopt|inderdaad)\b', user_message.lower()):
                    client = get_shipping_client()
                    result = client.get_shipment_status(order_id)

                    # Clear confirmation state
                    state_data.pop('awaiting_order_confirmation', None)
                    state_data.pop('pending_order_id', None)
                    state_data.pop('confirmation_timestamp', None)
                    save_session_state(session_id, state_data)

                    if result["success"]:
                        response_text = format_shipping_response(result, order_id)
                    else:
                        response_text = f"❌ {result.get('error', 'Kon tracking info niet ophalen.')}"

                    return jsonify({"response": response_text, "request_id": request_id})

                # User declined (nee/no/nope/incorrect/verkeerd)
                elif re.search(r'\b(nee|no|nope|incorrect|verkeerd)\b', user_message.lower()):
                    state_data.pop('awaiting_order_confirmation', None)
                    state_data.pop('pending_order_id', None)
                    state_data.pop('confirmation_timestamp', None)
                    save_session_state(session_id, state_data)

                    response_text = "Oké, geen probleem! Wat is je correcte bestelnummer?"
                    return jsonify({"response": response_text, "request_id": request_id})

    # Detect potential order/zending number in message
    # Supports: order, bestelling, bestellingnummer, zending, zendingnummer
    order_match = re.search(r'(?:order|bestelling(?:nummer)?|zending(?:nummer)?)\s*#?\s*(\d+)', user_message.lower())

    if order_match:
        order_id = order_match.group(1)

        # Set confirmation state with timestamp
        state_data['awaiting_order_confirmation'] = True
        state_data['pending_order_id'] = order_id
        state_data['confirmation_timestamp'] = datetime.datetime.now().isoformat()
        save_session_state(session_id, state_data)

        # Ask for confirmation
        response_text = f"Wil je de status opvragen van zending **#{order_id}**? (Antwoord met 'ja' of 'nee')"
        return jsonify({"response": response_text, "request_id": request_id})

    # Feature 15: Detect language BEFORE RAG call so we can translate queries
    detected_lang = rag_engine.detect_language(user_message)
    state_data['language'] = detected_lang

    # Fallback to RAG (with conversation history for context)
    logger.debug("Querying RAG for: %s (language: %s)", user_message, detected_lang)
    response_text = rag_engine.get_answer(user_message, chat_history=chat_history, language=detected_lang)

    # Check for Human Contact Request - user explicitly wants to speak with someone
    if "__HUMAN_REQUESTED__" in response_text:
        state_data['state'] = 'awaiting_name'
        state_data['question'] = user_message

        if detected_lang == 'nl':
            response_text = (
                "Natuurlijk! Ik breng je graag in contact met een collega. "
                "Wat is je naam?"
            )
        else:
            response_text = (
                "Of course! I'd be happy to connect you with a colleague. "
                "What's your name?"
            )

        save_session_state(session_id, state_data)

    # Check for Unknown Signal - generate helpful response instead of immediate handoff
    elif "__UNKNOWN__" in response_text:
        # Generate a helpful response that doesn't immediately push to human handoff
        response_text = rag_engine.generate_helpful_unknown_response(user_message, detected_lang)

        # Stay in inactive state - user can ask for human help if they want
        # The system prompt already tells the bot to respond with __HUMAN_REQUESTED__
        # if the user explicitly asks for human contact
        save_session_state(session_id, state_data)

    # Update conversation history for context in future messages
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": response_text})
    # Keep only last 10 messages to avoid token bloat
    state_data['chat_history'] = chat_history[-10:]
    save_session_state(session_id, state_data)

    # LOGGING: Save conversation to file (with PII redaction)
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Simple logging format with request ID for tracing (PII redacted)
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "request_id": request_id,
            "user": _redact_pii_for_log(user_message),
            "bot": _redact_pii_for_log(response_text)
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
@require_admin_key
def ingest():
    """Endpoint to trigger re-ingestion of documents (requires admin API key)."""
    result = rag_engine.ingest_documents()
    logger.info("Document re-ingestion triggered successfully")
    return jsonify({"status": result})


# =============================================================================
# ADMIN: Chat Log Portal
# =============================================================================
@app.route('/admin')
def admin_portal():
    """Serve the admin chat-log portal page."""
    return render_template('portal.html')


@app.route('/portal/<path:filename>')
def serve_portal_static(filename):
    """Serve portal static files (JS, etc.) from the portal/ directory."""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), '..', 'portal'),
        filename
    )


@app.route('/admin/api/conversations', methods=['GET'])
@limiter.limit("30 per minute")
@require_admin_key
def admin_conversations():
    """Return all chat log files for the admin portal (requires ADMIN_API_KEY)."""
    log_dir = "logs"
    conversations = []

    if not os.path.isdir(log_dir):
        return jsonify({"conversations": []})

    for filename in os.listdir(log_dir):
        if not filename.startswith("chat_") or not filename.endswith(".json"):
            continue
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                entries = json.load(f)
            if not entries:
                continue
            # Derive session id from filename: chat_<session_id>.json
            session_id = filename[len("chat_"):-len(".json")]
            conversations.append({
                "id": session_id,
                "started": entries[0].get("timestamp", ""),
                "lastMessage": entries[-1].get("timestamp", ""),
                "messageCount": len(entries),
                "messages": [
                    {
                        "timestamp": e.get("timestamp", ""),
                        "user": e.get("user", ""),
                        "bot": e.get("bot", "")
                    }
                    for e in entries
                ]
            })
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning("Skipping corrupt log file %s: %s", filename, e)

    # Sort newest-first by last message timestamp
    conversations.sort(
        key=lambda c: c.get("lastMessage", ""), reverse=True
    )

    # Feature 30d: Overlay persistent metadata from SQLite database
    try:
        metadata_list = admin_db.get_all_metadata()
        metadata_map = {m["session_id"]: m for m in metadata_list}
    except Exception as e:
        logger.error("Failed to load portal metadata: %s", e)
        metadata_map = {}

    default_meta = {
        "status": "open",
        "rating": None,
        "language": None,
        "labels": [],
        "notes": [],
        "messageMetadata": {},
    }
    for conv in conversations:
        sid = conv.get("id")
        if sid and sid in metadata_map:
            meta = metadata_map[sid]
            conv["metadata"] = {
                "status": meta.get("status", "open"),
                "rating": meta.get("rating"),
                "language": meta.get("language"),
                "labels": meta.get("labels", []),
                "notes": meta.get("notes", []),
                "messageMetadata": meta.get("messageMetadata", {}),
            }
        else:
            conv["metadata"] = dict(default_meta)

    return jsonify({"conversations": conversations})


@app.route('/admin/api/conversations/<session_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_admin_key
def get_single_conversation(session_id):
    """
    GET /admin/api/conversations/<session_id>

    Fetch a single conversation with its messages and metadata.
    More efficient than fetching all conversations.

    Returns:
        200: Conversation object with messages and metadata
        400: Invalid session ID format
        404: Conversation not found
    """
    # Step 1: Sanitize and validate session ID
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    # Step 2: Load chat log file
    log_path = os.path.join("logs", f"chat_{safe_id}.json")
    if not os.path.exists(log_path):
        return jsonify({"error": "Conversation not found"}), 404

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to load conversation %s: %s", safe_id, e)
        return jsonify({"error": "Failed to load conversation"}), 500

    if not entries:
        return jsonify({"error": "Conversation is empty"}), 404

    # Step 3: Build conversation object
    conversation = {
        "id": safe_id,
        "started": entries[0].get("timestamp", ""),
        "lastMessage": entries[-1].get("timestamp", ""),
        "messageCount": len(entries),
        "messages": [
            {
                "timestamp": e.get("timestamp", ""),
                "user": e.get("user", ""),
                "bot": e.get("bot", "")
            }
            for e in entries
        ]
    }

    # Step 4: Overlay metadata from database
    try:
        metadata = admin_db.get_metadata(safe_id)
        if metadata:
            conversation["metadata"] = {
                "status": metadata.get("status", "open"),
                "rating": metadata.get("rating"),
                "language": metadata.get("language"),
                "labels": metadata.get("labels", []),
                "notes": metadata.get("notes", []),
            }
        else:
            # No metadata exists yet - use defaults
            conversation["metadata"] = {
                "status": "open",
                "rating": None,
                "language": None,
                "labels": [],
                "notes": [],
            }
    except Exception as e:
        logger.error("Failed to load metadata for %s: %s", safe_id, e)
        # Return conversation without metadata rather than failing entirely
        conversation["metadata"] = {
            "status": "open",
            "rating": None,
            "language": None,
            "labels": [],
            "notes": [],
        }

    return jsonify(conversation), 200


# =============================================================================
# ADMIN: Metadata CRUD API Routes (Feature 30c)
# =============================================================================


@app.route(
    "/admin/api/conversations/<session_id>/metadata", methods=["PUT"]
)
@limiter.limit("30 per minute")
@require_admin_key
def update_conversation_metadata(session_id):
    """Update conversation status, rating, or language."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate individual fields (only those present in the request body)
    if "status" in data and data["status"] is not None:
        if data["status"] not in VALID_STATUSES:
            return jsonify({
                "error": "Invalid status. Must be one of: "
                         + ", ".join(sorted(VALID_STATUSES)),
                "field": "status",
            }), 400

    if "rating" in data and data["rating"] is not None:
        if not isinstance(data["rating"], int) or data["rating"] < 1 or data["rating"] > 5:
            return jsonify({
                "error": "Rating must be null or an integer between 1 and 5",
                "field": "rating",
            }), 400

    # Build kwargs: only pass keys that are present in the request body
    # so that omitted keys stay unchanged, while explicit null clears the value
    kwargs = {}
    if "status" in data:
        kwargs["status"] = data["status"]
    if "rating" in data:
        kwargs["rating"] = data["rating"]
    if "language" in data:
        kwargs["language"] = data["language"]

    try:
        result = admin_db.upsert_metadata(safe_id, **kwargs)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Failed to update metadata for %s: %s", safe_id, e)
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>/labels", methods=["POST"]
)
@limiter.limit("30 per minute")
@require_admin_key
def add_conversation_label_route(session_id):
    """Add a label to a conversation."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    label_name = data.get("label_name", "").strip()
    if (not label_name or len(label_name) > 50
            or not LABEL_NAME_RE.match(label_name)):
        return jsonify({
            "error": "Invalid label name. "
                     "Must be 1-50 alphanumeric characters or hyphens.",
            "field": "label_name",
        }), 400

    try:
        success = admin_db.add_conversation_label(safe_id, label_name)
        if success:
            return jsonify({"success": True}), 200
        return jsonify({
            "error": "Label already exists on this conversation"
        }), 409
    except Exception as e:
        logger.error("Failed to add label for %s: %s", safe_id, e)
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>/labels/<label_name>",
    methods=["DELETE"],
)
@limiter.limit("30 per minute")
@require_admin_key
def remove_conversation_label_route(session_id, label_name):
    """Remove a label from a conversation."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    try:
        success = admin_db.remove_conversation_label(
            safe_id, label_name
        )
        if success:
            return jsonify({"success": True}), 200
        return jsonify({
            "error": "Label not found on this conversation"
        }), 404
    except Exception as e:
        logger.error(
            "Failed to remove label for %s: %s", safe_id, e
        )
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>/notes", methods=["POST"]
)
@limiter.limit("30 per minute")
@require_admin_key
def add_conversation_note(session_id):
    """Add a note to a conversation."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    text = data.get("text", "").strip()
    author = data.get("author", "admin").strip()

    if not author or len(author) > 100:
        return jsonify({
            "error": "Author must be 1-100 characters",
            "field": "author",
        }), 400

    if not text or len(text) > 2000:
        return jsonify({
            "error": "Note text must be 1-2000 characters",
            "field": "text",
        }), 400

    try:
        note_id = admin_db.add_note(safe_id, text, author)
        return jsonify({"note_id": note_id}), 201
    except Exception as e:
        logger.error("Failed to add note for %s: %s", safe_id, e)
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>/notes/<note_id>",
    methods=["DELETE"],
)
@limiter.limit("30 per minute")
@require_admin_key
def delete_conversation_note(session_id, note_id):
    """Delete a note from a conversation."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    try:
        success = admin_db.delete_note(note_id)
        if success:
            return jsonify({"success": True}), 200
        return jsonify({"error": "Note not found"}), 404
    except Exception as e:
        logger.error("Failed to delete note %s: %s", note_id, e)
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>"
    "/messages/<message_id>/labels",
    methods=["POST"],
)
@limiter.limit("30 per minute")
@require_admin_key
def add_message_label_route(session_id, message_id):
    """Add a label to a specific message."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400
    message_id = sanitize_session_id(message_id)
    if not message_id:
        return jsonify({"error": "Invalid message ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    label_name = data.get("label_name", "").strip()
    if (not label_name or len(label_name) > 50
            or not LABEL_NAME_RE.match(label_name)):
        return jsonify({
            "error": "Invalid label name",
            "field": "label_name",
        }), 400

    try:
        row_id = admin_db.add_message_label(
            safe_id, message_id, label_name
        )
        return jsonify({"id": row_id}), 200
    except Exception as e:
        logger.error("Failed to add message label: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>"
    "/messages/<message_id>/labels/<label_name>",
    methods=["DELETE"],
)
@limiter.limit("30 per minute")
@require_admin_key
def remove_message_label_route(session_id, message_id, label_name):
    """Remove a label from a specific message."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400
    message_id = sanitize_session_id(message_id)
    if not message_id:
        return jsonify({"error": "Invalid message ID"}), 400

    try:
        success = admin_db.remove_message_label(
            safe_id, message_id, label_name
        )
        if success:
            return jsonify({"success": True}), 200
        return jsonify({"error": "Message label not found"}), 404
    except Exception as e:
        logger.error("Failed to remove message label: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route(
    "/admin/api/conversations/<session_id>"
    "/messages/<message_id>/rating",
    methods=["PUT"],
)
@limiter.limit("30 per minute")
@require_admin_key
def set_message_rating_route(session_id, message_id):
    """Set rating for a specific message (1-5 or null)."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400
    message_id = sanitize_session_id(message_id)
    if not message_id:
        return jsonify({"error": "Invalid message ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    rating = data.get("rating")
    if rating is not None:
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({
                "error": "Rating must be null or integer 1-5",
                "field": "rating",
            }), 400

    try:
        admin_db.set_message_rating(safe_id, message_id, rating)
        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error("Failed to set message rating: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/admin/api/labels", methods=["GET"])
@limiter.limit("30 per minute")
@require_admin_key
def get_label_definitions_route():
    """Get all label definitions."""
    try:
        labels = admin_db.get_label_definitions()
        return jsonify(labels), 200
    except Exception as e:
        logger.error("Failed to get label definitions: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/admin/api/labels", methods=["POST"])
@limiter.limit("30 per minute")
@require_admin_key
def create_label_definition():
    """Create a new label definition."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = data.get("name", "").strip()
    color = data.get("color", "#94A3B8").strip()
    description = data.get("description", "").strip()

    if (not name or len(name) > 50
            or not LABEL_NAME_RE.match(name)):
        return jsonify({
            "error": "Invalid label name. "
                     "Must be 1-50 alphanumeric characters or hyphens.",
            "field": "name",
        }), 400

    if not HEX_COLOR_RE.match(color):
        return jsonify({
            "error": "Invalid color. "
                     "Must be a hex color code (e.g., #FF0000).",
            "field": "color",
        }), 400

    try:
        success = admin_db.add_label_definition(
            name, color, description
        )
        if success:
            return jsonify({"success": True, "name": name}), 201
        return jsonify({
            "error": "Label definition already exists"
        }), 409
    except Exception as e:
        logger.error("Failed to create label definition: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/admin/api/labels/<label_name>", methods=["DELETE"])
@limiter.limit("30 per minute")
@require_admin_key
def delete_label_definition_route(label_name):
    """Delete a label definition."""
    try:
        success = admin_db.delete_label_definition(label_name)
        if success:
            return jsonify({"success": True}), 200
        return jsonify({"error": "Label definition not found"}), 404
    except Exception as e:
        logger.error("Failed to delete label definition: %s", e)
        return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
