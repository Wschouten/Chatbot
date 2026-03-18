"""GroundCoverGroup Chatbot - Flask Application."""
import logging
import os
import re
import json
import datetime
import secrets
import sys
import uuid
from functools import wraps
from typing import Any

from flask import Flask, render_template, request, jsonify, Response, g, send_from_directory, redirect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv

from rag_engine import RagEngine, get_openai_health, RAG_DEPENDENCIES_LOADED
from shipping_api import get_shipment_status, get_shipping_client
from zendesk_client import ZendeskClient
from email_client import EmailClient
from brand_config import get_brand_config
from data_retention import run_data_retention_cleanup
import requests
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
# GLOBAL ERROR HANDLER: Always return JSON for API errors
# =============================================================================
@app.errorhandler(400)
def handle_400(e):
    """Return JSON instead of HTML for bad requests."""
    return jsonify({"response": "Ongeldig verzoek."}), 400


@app.errorhandler(404)
def handle_404(e):
    """Return JSON instead of HTML for not-found errors."""
    return jsonify({"response": "Pagina niet gevonden."}), 404


@app.errorhandler(405)
def handle_405(e):
    """Return JSON instead of HTML for method-not-allowed errors."""
    return jsonify({"response": "Methode niet toegestaan."}), 405


@app.errorhandler(500)
def handle_500(e):
    """Return JSON instead of HTML for internal server errors."""
    logger.error("Internal Server Error: %s", e)
    return jsonify({"response": "Er ging iets mis op de server. Probeer het later opnieuw."}), 500


@app.errorhandler(429)
def handle_429(e):
    """Return JSON for rate-limit errors."""
    return jsonify({"response": "Te veel verzoeken. Probeer het over een paar minuten opnieuw."}), 429


@app.errorhandler(Exception)
def handle_generic_error(e):
    """Catch-all: return JSON for any unhandled exception."""
    code = getattr(e, 'code', 500)
    logger.error("Unhandled error (%s): %s", type(e).__name__, e)
    return jsonify({"response": "Er ging iets mis. Probeer het later opnieuw."}), code


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
PRE_PURCHASE_RE = re.compile(
    r'\b(als ik (?:\w+\s+){0,5}bestel'
    r'|als ik (een )?bestelling (zou )?plaatsen'
    r'|wanneer kan ik (het )?verwachten als'
    r'|indien ik bestel'
    r'|if i (place an? )?order'
    r'|if i (buy|purchase|order)'
    r'|when (would|will) (it|the order) (be )?delivered if)\b',
    re.IGNORECASE
)
TRACKING_INTENT_RE = re.compile(
    r'\b(waar is|waar blijft|status van|wanneer komt|wanneer wordt|hoe laat komt'
    r'|hoe laat komen|wanneer komen jullie|komen brengen|zouden.*brengen'
    r'|vandaag.*lever|vandaag.*bezorg|vandaag.*brengen'
    r'|hoe laat.*lever|hoe laat.*bezorg'
    r'|mijn (pakketje|pakket|bestelling|zending|order|bezorging|levering)'
    r'|mij (pakketje|pakket|bestelling|zending|order|bezorging|levering)'
    r'|onze (pakketje|pakket|bestelling|zending|order|bezorging|levering)'
    r'|uw (pakketje|pakket|bestelling|zending|order|bezorging|levering)'
    r'|jullie (pakketje|pakket|bestelling|zending|order|bezorging|levering)'
    r'|wanneer kunnen'
    r'|binnenkrijgen|binnen\s+krijgen'
    r'|bezorgd worden|wanneer bezorgd|wordt bezorgd'
    r'|track|where is my|my order|my package|my delivery|when will i receive|shipped)\b',
    re.IGNORECASE
)
POSTCODE_RE = re.compile(r'\b(\d{4}\s?[A-Za-z]{2})\b')
CLOSING_RE = re.compile(
    r'^\s*(?:dankjewel|dankje|bedankt|dank u wel|dank je wel|prima|top|goed zo|'
    r'ok(?:é|e)?|helemaal goed|dat hoeft niet|laat maar|niet nodig|'
    r'thanks?|thank you|no\s+thanks?|no\s+need|that\'?s\s+(?:all|fine|ok)|'
    r'great|perfect|alright|got it)\b[!.,]?\s*$',
    re.IGNORECASE
)
# Detects when user says they haven't ordered yet
NO_ORDER_YET_RE = re.compile(
    r'\b(nog geen bestell|heb nog geen|nog niet besteld|heb nog niet besteld'
    r'|nog geen order|geen bestelling gedaan'
    r"|haven'?t ordered|have not ordered|haven'?t placed|no order yet"
    r'|not ordered yet|not placed yet)\b',
    re.IGNORECASE,
)
# Detects when user says they don't have / can't provide the requested number
HAS_SHIPMENT_NUMBER_RE = re.compile(
    r'\b(ik heb een? (zendingnummer|zendingsnummer|trackingnummer|tracking\s*nummer|track.*trace)'
    r"|i have (a |my )?(tracking|shipment|trace)\s*(number|code|link)"
    r'|heb het zendingnummer|heb het trackingnummer)\b',
    re.IGNORECASE,
)
NO_SHIPMENT_NUMBER_RE = re.compile(
    r'\b(geen|heb\s+geen|heb\s+het\s+niet|weet\s+het\s+niet|niet\s+bij\s+de\s+hand'
    r"|don'?t\s+have|do\s+not\s+have|haven'?t\s+got|not\s+got|no\s+shipment"
    r'|no\s+tracking|geen\s+zendingnummer|geen\s+trackingnummer)\b',
    re.IGNORECASE,
)
HUMAN_ESCALATION_RE = re.compile(
    # Dutch: medewerker/collega spreken|praten
    r'(medewerker|collega)\s+(spreken|praten)'
    r'|(spreken|praten)\s+met\s+een?\s+(medewerker|collega|mens|persoon)'
    r'|wil\s+een?\s+(medewerker|collega|mens)'
    r'|mag\s+ik\s+een?\s+(medewerker|collega|mens|persoon)'
    r'|menselijke\s+hulp|doorverbinden\s+met'
    # English: speak/talk to a human/agent/person
    r'|speak\s+(to|with)\s+(a\s+)?(human|person|agent|representative|someone)'
    r'|talk\s+(to|with)\s+(a\s+)?(human|person|agent|representative|someone)'
    r'|human\s+(agent|support|representative)|real\s+person|live\s+(agent|chat|support)',
    re.IGNORECASE
)
FRUSTRATION_RE = re.compile(
    r'\b(ik baal\b|behoorlijk balen|heel erg balen'
    r'|dit is belachelijk|absoluut belachelijk|volkomen belachelijk'
    r'|ik ben niet blij|niet blij (mee|hierover|over)'
    r'|vreselijk|vreselijk slecht'
    r'|onacceptabel|totaal onacceptabel'
    r'|schande|een schande'
    r'|klacht\b|klachten\b|klacht indienen'
    r'|teleurgesteld|erg teleurgesteld|heel teleurgesteld'
    r'|ik ben het zat|ben er klaar mee'
    r'|jullie luisteren niet|niemand helpt'
    # English
    r'|this is ridiculous|this is unacceptable|absolutely unacceptable'
    r'|i am not happy|not satisfied|very disappointed'
    r'|terrible service|awful service|horrible service'
    r'|complaint\b|file a complaint)\b',
    re.IGNORECASE,
)
PRIOR_CONTACT_FAILED_RE = re.compile(
    # Dutch
    r'(mijn\s+(vorige|eerdere)\s+(mail|e-?mail|bericht))'
    r'|(al\s+meerdere\s+keren?\s+(gemaild|gebeld|geprobeerd|contact\s+opgenomen))'
    r'|(geen\s+(reactie|antwoord|respons)\s+(gehad|gekregen|ontvangen))'
    r'|(al\s+(dagen|weken)\s+(gewacht|geen\s+antwoord))'
    r'|(niemand\s+reageert|niemand\s+antwoordt)'
    # English
    r'|(my\s+(previous|earlier|last)\s+(email|message))'
    r'|(emailed?\s+(multiple|several|many)\s+times?)'
    r'|(no\s+(response|reply|answer)\s+(at all|from you))'
    r'|(been\s+waiting\s+(for\s+)?(days|weeks))',
    re.IGNORECASE,
)


# Initialize RAG Engine
rag_engine = RagEngine()

logger.info("Initializing RAG Engine...")

# SAFETY CHECK: Prevent running locally (Zombie processes)
in_container = os.path.exists('/.dockerenv') or os.getenv('RAILWAY_ENVIRONMENT') is not None
if not in_container:
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
    sessions_dir="data/sessions",
    logs_dir="data/logs",
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


@app.route('/privacy')
def privacy_redirect():
    """Redirect to the external privacy policy page."""
    return redirect('https://www.boomschors.nl/policies/privacy-policy', code=301)


@app.route('/health')
def health():
    """Enhanced health check with dependency awareness."""
    health_status = {
        "status": "ok",
        "dependencies": {}
    }
    health_status["rag_available"] = bool(
        RAG_DEPENDENCIES_LOADED and rag_engine.collection
    )
    health_status["python_version"] = sys.version.split()[0]
    health_status["environment"] = "docker" if os.path.exists("/.dockerenv") else "local"
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
SESSION_DIR = "data/sessions"
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


_DEAD_END_PATTERN = re.compile(
    r'neem\s+contact\s+op'
    r'|klantenservice@'
    r'|bel\s+ons'
    r'|stuur\s+(een\s+)?e?-?mail'
    r'|contact\s+us'
    r'|send\s+(an?\s+)?email'
    r'|call\s+us',
    re.IGNORECASE,
)
DEAD_END_LOOP_THRESHOLD = 3


def _detect_dead_end_loop(chat_history: list[dict]) -> bool:
    """Return True when the bot has redirected to customer service 3 or more times."""
    count = sum(
        1
        for turn in chat_history
        if turn.get("role") == "assistant"
        and _DEAD_END_PATTERN.search(turn.get("content", ""))
    )
    return count >= DEAD_END_LOOP_THRESHOLD


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


def _log_chat_message(session_id: str, request_id: str, user_message: str, response_text: str) -> None:
    """Log a chat message exchange to the conversation log file."""
    try:
        log_dir = "data/logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "request_id": request_id,
            "user": _redact_pii_for_log(user_message),
            "bot": _redact_pii_for_log(response_text)
        }

        safe_id = sanitize_session_id(session_id)
        log_file = os.path.join(log_dir, f"chat_{safe_id}.json")

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


@app.route('/api/chat', methods=['POST'])
@limiter.limit("30 per minute")
def chat() -> Response:
    """Handle chat messages from the frontend."""
    request_id = g.request_id
    try:
        return _handle_chat(request_id)
    except Exception as e:
        logger.error("[%s] Unhandled chat error: %s", request_id, e, exc_info=True)
        return jsonify({"response": "Er ging iets mis. Probeer het later opnieuw.", "request_id": request_id}), 200


def _handle_chat(request_id: str) -> Response:
    """Inner chat handler (extracted so the outer function can catch all errors)."""
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

            resp = "Geen probleem! 👍 Waarmee kan ik je verder helpen?" if user_lang == 'nl' else "No problem! 👍 How else can I help you?"
            _log_chat_message(session_id, request_id, user_message, resp)
            return jsonify({"response": resp, "request_id": request_id})

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

            resp = f"Leuk je te ontmoeten, {clean_name}! 👋 Wat is je e-mailadres?" if user_lang == 'nl' else f"Nice to meet you, {clean_name}! 👋 What's your email address?"
            _log_chat_message(session_id, request_id, user_message, resp)
            return jsonify({"response": resp, "request_id": request_id})

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

                resp = "Geen probleem! 👍 Waarmee kan ik je verder helpen?" if user_lang == 'nl' else "No problem! 👍 How else can I help you?"
                _log_chat_message(session_id, request_id, user_message, resp)
                return jsonify({"response": resp, "request_id": request_id})

            elif intent == 'new_question':
                # User asking something else - cancel and process as RAG
                state_data = {'state': 'inactive', 'chat_history': chat_history}
                save_session_state(session_id, state_data)
                # Fall through to RAG processing below

            else:
                # Genuinely invalid email - ask again
                resp = "Hmm, dat lijkt niet helemaal te kloppen 🤔 Kun je je e-mailadres nog een keer checken?" if user_lang == 'nl' else "Hmm, that doesn't look quite right 🤔 Could you double-check your email address?"
                _log_chat_message(session_id, request_id, user_message, resp)
                return jsonify({"response": resp, "request_id": request_id})

        else:
            # Valid email - proceed with ticket creation
            state_data['email'] = email
            name = state_data.get('name', 'Unknown')
            original_q = state_data.get('question', '')

            # Escalate (send email or create Zendesk ticket)
            try:
                if ESCALATION_METHOD == "zendesk":
                    result = escalation_client.create_ticket(name, email, original_q, chat_history)
                else:
                    result = escalation_client.send_email_async(name, email, original_q, chat_history)
            except Exception as exc:
                logger.error("Escalation failed with unhandled error: %s", exc)
                result = None

            # Reset State and clear history after escalation
            state_data = {
                'state': 'inactive',
                'chat_history': []
            }
            save_session_state(session_id, state_data)

            if result:
                if ESCALATION_METHOD == "zendesk":
                    ticket_id = result.get('ticket', {}).get('id', '???')
                    resp = f"Top! Ik heb ticket #{ticket_id} voor je aangemaakt. Een collega neemt zo snel mogelijk contact op." if user_lang == 'nl' else f"Great! I've created ticket #{ticket_id} for you. A colleague will be in touch shortly."
                else:
                    resp = "Top! Ik heb je bericht doorgestuurd naar een collega. We nemen zo snel mogelijk contact met je op via e-mail." if user_lang == 'nl' else "Great! I've forwarded your message to a colleague. We'll get in touch via email as soon as possible."
            else:
                resp = "Sorry, er ging iets mis bij het versturen van je bericht. Neem alsjeblieft direct contact met ons op." if user_lang == 'nl' else "I'm sorry, something went wrong sending your message. Please contact us directly."
            _log_chat_message(session_id, request_id, user_message, resp)
            return jsonify({"response": resp, "request_id": request_id})


    # -------------------------------------------------------------------------
    # Shipping tracking state machine (two-step: shipment number → postcode)
    # -------------------------------------------------------------------------

    def _tracking_timeout(ts_str: str) -> bool:
        """Return True if the tracking state timestamp is older than 5 minutes."""
        try:
            ts = datetime.datetime.fromisoformat(ts_str)
            return datetime.datetime.now() - ts > datetime.timedelta(minutes=5)
        except (ValueError, TypeError):
            return True

    def _call_zapier_wismo(order_number: str, email: str) -> dict:
        """POST order_number + email to Zapier WISMO webhook.
        Returns: {"outcome": "ok"} | {"outcome": "not_found"} | {"outcome": "error"}
        """
        webhook_url = os.getenv('ZAPIER_WEBHOOK_URL_WISMO', '').strip()
        if not webhook_url:
            logger.warning("ZAPIER_WEBHOOK_URL_WISMO not configured")
            return {"outcome": "error"}
        payload = {"order_number": order_number, "email": email}
        try:
            resp = requests.post(webhook_url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or data.get("Status") or "").lower().strip()
            if status in ("verified", "success"):
                return {"outcome": "ok"}
            if status in ("not_found", "error", "notfound", "not found"):
                return {"outcome": "not_found"}
            logger.warning("Zapier WISMO: unexpected status %r", status)
            return {"outcome": "error"}
        except requests.exceptions.Timeout:
            logger.error("Zapier WISMO timeout for order %s", order_number)
            return {"outcome": "error"}
        except requests.exceptions.RequestException as exc:
            logger.error("Zapier WISMO request failed: %s", exc)
            return {"outcome": "error"}

    def _clear_tracking_state() -> None:
        for key in ('awaiting_order_number', 'pending_order_id', 'tracking_timestamp'):
            state_data.pop(key, None)
        save_session_state(session_id, state_data)

    def _reset_to_awaiting_order_number() -> None:
        """Reset to step 1 of tracking flow so the user can re-enter the shipment number."""
        for key in ('pending_order_id',):
            state_data.pop(key, None)
        state_data['awaiting_order_number'] = True
        state_data['tracking_timestamp'] = datetime.datetime.now().isoformat()
        save_session_state(session_id, state_data)

    def _clear_shopify_verification_state() -> None:
        """Clear all Shopify order verification state keys from the session."""
        for key in ('awaiting_shopify_order_number', 'awaiting_shopify_postcode',
                    'pending_shopify_order_number',
                    'shopify_verification_timestamp'):
            state_data.pop(key, None)
        save_session_state(session_id, state_data)


    # WISMO step 1 of 2: waiting for Shopify order number
    if state_data.get('awaiting_shopify_order_number'):
        if _tracking_timeout(state_data.get('shopify_verification_timestamp', '')):
            _clear_shopify_verification_state()
            # Fall through to normal processing
        else:
            user_lang = state_data.get('language', 'nl')
            order_num_match = re.search(r'#?(\d+)', user_message.strip())
            if order_num_match:
                order_number = order_num_match.group(1)
                state_data.pop('awaiting_shopify_order_number', None)
                state_data['pending_shopify_order_number'] = order_number
                state_data['awaiting_shopify_postcode'] = True
                state_data['shopify_verification_timestamp'] = datetime.datetime.now().isoformat()
                save_session_state(session_id, state_data)
                if user_lang == 'en':
                    response_text = (
                        "Thanks. What is the **postcode** of the delivery address?"
                    )
                else:
                    response_text = (
                        "Bedankt. Wat is de **postcode** van het afleveradres?"
                    )
            elif NO_ORDER_YET_RE.search(user_message):
                _clear_shopify_verification_state()
                save_session_state(session_id, state_data)
                if user_lang == 'en':
                    response_text = (
                        "No problem! Orders are typically delivered within a few working days. "
                        "For the exact delivery time to your area, please check the webshop at checkout "
                        "or contact us at klantenservice@groundcovergroup.nl."
                    )
                else:
                    response_text = (
                        "Geen probleem! Bestellingen worden doorgaans binnen enkele werkdagen geleverd. "
                        "Voor de exacte levertijd naar jouw regio, check de webshop bij het afrekenen "
                        "of neem contact op via klantenservice@groundcovergroup.nl."
                    )
            else:
                if user_lang == 'en':
                    response_text = (
                        "I didn't find an order number in your message. "
                        "Please enter your **Shopify order number** (e.g. **#12345**)."
                    )
                else:
                    response_text = (
                        "Ik zie geen bestelnummer in je bericht. "
                        "Vul je **bestelnummer** in (bijv. **#12345**)."
                    )
            _log_chat_message(session_id, request_id, user_message, response_text)
            return jsonify({"response": response_text, "request_id": request_id})

    # WISMO step 2 of 2: order number stored, waiting for postcode
    if state_data.get('awaiting_shopify_postcode'):
        if _tracking_timeout(state_data.get('shopify_verification_timestamp', '')):
            _clear_shopify_verification_state()
            # Fall through to normal processing
        else:
            user_lang = state_data.get('language', 'nl')
            postcode_match = POSTCODE_RE.search(user_message.strip())
            if postcode_match:
                _clear_shopify_verification_state()
                state_data['awaiting_order_number'] = True
                state_data['tracking_timestamp'] = datetime.datetime.now().isoformat()
                save_session_state(session_id, state_data)
                if user_lang == 'en':
                    response_text = (
                        "✅ Thank you, I found your order! "
                        "To retrieve the exact delivery time from our carrier, "
                        "I need your **shipment tracking number**. "
                        "(You should have received this separately by email.) "
                        "What is your **shipment number**?"
                    )
                else:
                    response_text = (
                        "✅ Bedankt, ik heb je bestelling gevonden! "
                        "Om de exacte levertijd bij de vervoerder op te halen, "
                        "heb ik je **zendingnummer** nodig. "
                        "(Dit heb je apart per e-mail ontvangen.) "
                        "Wat is je **zendingnummer**?"
                    )
            else:
                if user_lang == 'en':
                    response_text = (
                        "That doesn't look like a valid postcode. "
                        "Please enter a Dutch postcode (e.g. **1234 AB**)."
                    )
                else:
                    response_text = (
                        "Dat lijkt geen geldige postcode. "
                        "Vul een Nederlandse postcode in (bijv. **1234 AB**)."
                    )
            _log_chat_message(session_id, request_id, user_message, response_text)
            return jsonify({"response": response_text, "request_id": request_id})

    # Step 1 of 2: we asked for the shipment number, waiting for user to provide it
    if state_data.get('awaiting_order_number'):
        if _tracking_timeout(state_data.get('tracking_timestamp', '')):
            _clear_tracking_state()
            # Fall through to normal processing
        else:
            user_lang = state_data.get('language', 'nl')
            number_match = re.search(r'\b(\d{6,})\b', user_message)
            if number_match:
                order_id = number_match.group(1)
                _clear_tracking_state()  # clean up before API call

                client = get_shipping_client()
                result = client.get_shipment_status(order_id)

                if result["success"]:
                    response_text = format_shipping_response(result, order_id)
                elif result["status"] == "not_found":
                    if user_lang == 'en':
                        response_text = (
                            f"❌ Shipment **#{order_id}** was not found. "
                            "Please check the shipment number and try again."
                        )
                    else:
                        response_text = (
                            f"❌ Zendingnummer **#{order_id}** is niet gevonden. "
                            "Controleer het zendingnummer en probeer het opnieuw."
                        )
                    _reset_to_awaiting_order_number()
                elif result["status"] == "no_status":
                    if user_lang == 'en':
                        response_text = (
                            f"📦 Your shipment **#{order_id}** is registered but "
                            "no status updates are available yet."
                        )
                    else:
                        response_text = (
                            f"📦 Je zending **#{order_id}** is aangemeld maar "
                            "er zijn nog geen statusupdates beschikbaar."
                        )
                else:  # API error
                    if user_lang == 'en':
                        response_text = (
                            "I'm unable to retrieve your shipment status right now. "
                            "Please try again later or contact our customer service."
                        )
                    else:
                        response_text = (
                            "Het is momenteel niet mogelijk om je zendingstatus op te halen. "
                            "Probeer het later opnieuw of neem contact op met onze klantenservice."
                        )
            else:
                # Check if user is expressing they don't have the shipment number
                if NO_SHIPMENT_NUMBER_RE.search(user_message):
                    _clear_tracking_state()
                    if user_lang == 'en':
                        response_text = (
                            "No problem! Your shipment number can be found in the shipping "
                            "confirmation email you received. If you don't have it, feel free "
                            "to contact our customer service and they can help you further."
                        )
                    else:
                        response_text = (
                            "Geen probleem! Je zendingnummer staat in de verzendbevestigingsmail "
                            "die je hebt ontvangen. Als je die niet hebt, kun je contact opnemen "
                            "met onze klantenservice — zij kunnen je verder helpen."
                        )
                else:
                    # No 6+ digit number found in message — re-prompt once more
                    if user_lang == 'en':
                        response_text = (
                            "I didn't find a shipment number in your message. "
                            "Please enter your **shipment number** (digits only, e.g. **1234567890**). "
                            "If you don't have it, just let me know."
                        )
                    else:
                        response_text = (
                            "Ik zie geen zendingnummer in je bericht. "
                            "Vul je **zendingnummer** in (alleen cijfers, bijv. **1234567890**). "
                            "Als je die niet hebt, laat het me weten."
                        )
            _log_chat_message(session_id, request_id, user_message, response_text)
            return jsonify({"response": response_text, "request_id": request_id})

    # Detect order number mentioned directly in the message
    # Supports: order, bestelling, bestellingnummer, zending, zendingnummer
    # Even when the user already mentions their order number we still require
    # the Exact 200 pre-verification step before revealing shipment information.
    order_match = re.search(r'(?:order|bestelling(?:nummer)?|zending(?:nummer)?)\s*#?\s*(\d+)', user_message.lower())

    if order_match:
        detected_lang = state_data.get('language') or rag_engine.detect_language(user_message)
        state_data['language'] = detected_lang
        state_data['pending_shopify_order_number'] = order_match.group(1)
        state_data['awaiting_shopify_postcode'] = True
        state_data['shopify_verification_timestamp'] = datetime.datetime.now().isoformat()
        save_session_state(session_id, state_data)

        if detected_lang == 'en':
            response_text = (
                "I can look that up! What is the **postcode** of the delivery address?"
            )
        else:
            response_text = (
                "Dat kan ik voor je opzoeken! Wat is de **postcode** van het afleveradres?"
            )
        _log_chat_message(session_id, request_id, user_message, response_text)
        return jsonify({"response": response_text, "request_id": request_id})

    # Detect tracking intent without an order number (e.g. "Waar is mijn pakket?")
    # Skip WISMO for pre-purchase / hypothetical questions — let RAG answer instead
    if not PRE_PURCHASE_RE.search(user_message) and (
        TRACKING_INTENT_RE.search(user_message) or HAS_SHIPMENT_NUMBER_RE.search(user_message)
    ):
        detected_lang = state_data.get('language') or rag_engine.detect_language(user_message)
        state_data['language'] = detected_lang
        state_data['awaiting_order_number'] = True
        state_data['tracking_timestamp'] = datetime.datetime.now().isoformat()
        save_session_state(session_id, state_data)

        if detected_lang == 'en':
            response_text = (
                "I can look that up! Please enter your **shipment number** "
                "(digits only, e.g. **1234567890**). "
                "You can find it in the shipping confirmation email."
            )
        else:
            response_text = (
                "Dat kan ik voor je opzoeken! Geef je **zendingnummer** door "
                "(alleen cijfers, bijv. **1234567890**). "
                "Je vindt dit in de verzendbevestigingsmail."
            )
        _log_chat_message(session_id, request_id, user_message, response_text)
        return jsonify({"response": response_text, "request_id": request_id})

    # Detect explicit human escalation request (pre-RAG, deterministic)
    if HUMAN_ESCALATION_RE.search(user_message):
        detected_lang = state_data.get('language') or rag_engine.detect_language(user_message)
        state_data['state'] = 'awaiting_name'
        state_data['question'] = user_message
        state_data['language'] = detected_lang
        save_session_state(session_id, state_data)

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
        _log_chat_message(session_id, request_id, user_message, response_text)
        return jsonify({"response": response_text, "request_id": request_id})

    # FRUSTRATION GATE: auto-escalate on detected distress or dead-end loop
    user_turns_so_far = sum(1 for t in chat_history if t.get("role") == "user")

    if current_state not in ('awaiting_name', 'awaiting_email') and user_turns_so_far >= 1:
        frustration_hit = FRUSTRATION_RE.search(user_message)
        prior_contact_hit = PRIOR_CONTACT_FAILED_RE.search(user_message)
        loop_hit = _detect_dead_end_loop(chat_history)

        if frustration_hit or prior_contact_hit or loop_hit:
            detected_lang = state_data.get('language') or rag_engine.detect_language(user_message)
            state_data['state'] = 'awaiting_name'
            state_data['question'] = user_message
            state_data['language'] = detected_lang
            state_data['escalation_reason'] = (
                'frustration' if (frustration_hit or prior_contact_hit) else 'loop'
            )
            save_session_state(session_id, state_data)

            if detected_lang == 'nl':
                response_text = (
                    "Dat klinkt echt frustrerend, en dat begrijp ik goed. "
                    "Dit verdient persoonlijke aandacht van een collega. "
                    "Mag ik je naam, zodat ik je direct kan doorverbinden?"
                )
            else:
                response_text = (
                    "I can hear that this has been really frustrating, and I'm sorry. "
                    "This deserves personal attention from one of our colleagues. "
                    "May I have your name so I can connect you right away?"
                )
            _log_chat_message(session_id, request_id, user_message, response_text)
            logger.info(
                "[%s] Frustration escalation triggered (frustration=%s, prior_contact=%s, loop=%s)",
                request_id, bool(frustration_hit), bool(prior_contact_hit), loop_hit,
            )
            return jsonify({"response": response_text, "request_id": request_id})

    # Closing/farewell detection — skip RAG, reply with short canned response
    if CLOSING_RE.match(user_message.strip()):
        consecutive_closings = state_data.get('consecutive_closings', 0) + 1
        state_data['consecutive_closings'] = consecutive_closings
        user_lang = state_data.get('language', 'nl')
        save_session_state(session_id, state_data)
        if consecutive_closings >= 2:
            response_text = "Goed, succes! 👋" if user_lang == 'nl' else "Great, good luck! 👋"
        else:
            response_text = (
                "Graag gedaan! Mocht je later nog vragen hebben, dan help ik je graag."
                if user_lang == 'nl' else
                "You're welcome! Feel free to ask if you have more questions."
            )
        _log_chat_message(session_id, request_id, user_message, response_text)
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": response_text})
        state_data['chat_history'] = chat_history[-10:]
        save_session_state(session_id, state_data)
        return jsonify({"response": response_text, "request_id": request_id})

    # Reset closing counter on a real message
    state_data.pop('consecutive_closings', None)

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
        response_text = rag_engine.generate_helpful_unknown_response(user_message, detected_lang, chat_history)

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

    # Log and return
    _log_chat_message(session_id, request_id, user_message, response_text)
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
    log_dir = "data/logs"
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
    log_path = os.path.join("data", "logs", f"chat_{safe_id}.json")
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
