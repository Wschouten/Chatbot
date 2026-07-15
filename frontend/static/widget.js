/**
 * GroundCoverGroup Chatbot Widget - Embeddable Script
 *
 * Usage on Shopify or any website:
 * <script src="https://your-domain.com/widget.js"
 *         data-api-url="https://your-domain.com"
 *         data-brand="GroundCoverGroup"
 *         data-position="bottom-right"
 *         data-primary-color="#2C5E2E">
 * </script>
 */
(function() {
    'use strict';

    // Prevent multiple initializations
    if (window.GroundCoverGroupChatbot) return;
    window.GroundCoverGroupChatbot = { initialized: true };

    // =============================================================================
    // Configuration from script tag data attributes
    // =============================================================================
    // Single-tenant: only the API origin varies per deploy (data-api-url on the
    // <script> tag). Everything else is fixed. Trailing slashes stripped so we
    // never build "https://host//api/chat".
    const scriptTag = document.currentScript || document.querySelector('script[data-api-url]');
    const CONFIG = {
        apiUrl: (scriptTag?.getAttribute('data-api-url') || '').replace(/\/+$/, ''),
        brand: 'GroundCoverGroup',
        position: 'bottom-right',
        primaryColor: '#2C5E2E',
        welcomeMessage: 'Hallo! Hoe kan ik je helpen?',
        privacyUrl: '/privacy'
    };

    // Validate API URL
    if (!CONFIG.apiUrl) {
        console.error('GroundCoverGroup Chatbot: data-api-url is required');
        return;
    }

    function _escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // =============================================================================
    // CSS Styles (injected into page)
    // =============================================================================
    const styles = `
        #gc-chatbot-container {
            --gc-primary: ${CONFIG.primaryColor};
            --gc-cream: #f5f0dc;
            --gc-text: #2d2d2d;
            --gc-white: #FFFFFF;
            --gc-gray: #888888;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            box-sizing: border-box;
        }
        #gc-chatbot-container *, #gc-chatbot-container *::before, #gc-chatbot-container *::after {
            box-sizing: border-box;
        }
        #gc-toggle-btn {
            position: fixed !important;
            ${CONFIG.position.includes('left') ? 'left: 20px !important;' : 'right: 20px !important;'}
            bottom: 20px !important;
            background-color: var(--gc-primary) !important;
            border: none !important;
            border-radius: 50% !important;
            width: 60px !important;
            height: 60px !important;
            min-height: unset !important;
            padding: 0 !important;
            margin: 0 !important;
            box-sizing: border-box !important;
            cursor: pointer !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            line-height: 1 !important;
            transition: transform 0.2s, box-shadow 0.2s !important;
            z-index: 2147483646 !important;
        }
        #gc-toggle-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(0,0,0,0.2);
        }
        #gc-chat-widget {
            position: fixed;
            ${CONFIG.position.includes('left') ? 'left: 20px;' : 'right: 20px;'}
            bottom: 90px;
            width: 380px;
            height: 520px;
            max-height: calc(100vh - 120px);
            max-width: calc(100vw - 40px);
            background-color: var(--gc-cream);
            border-radius: 16px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.18);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 2147483647;
            border: none;
            opacity: 0;
            pointer-events: none;
            transform: translateY(20px);
            transition: opacity 0.3s ease, transform 0.3s ease;
        }
        #gc-chat-widget.gc-active {
            opacity: 1;
            pointer-events: all;
            transform: translateY(0);
        }
        .gc-chat-header {
            padding: 16px 20px 14px;
            flex-shrink: 0;
            border-bottom: 1px solid rgba(0,0,0,0.08);
            /* Above the consent overlay so the × close button stays clickable. */
            position: relative;
            z-index: 101;
            /* ponytail: !important defeats Shopify theme flex/color overrides
               (stylesheet !important beats theme rules but not inline styles;
               themes don't inline-style our elements). Was JS setProperty. */
            display: flex !important;
            flex-direction: row !important;
            justify-content: space-between !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            gap: 0 !important;
            background-color: var(--gc-cream) !important;
            color: var(--gc-text) !important;
        }
        .gc-header-info {
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            line-height: 1.2 !important;
            color: var(--gc-text) !important;
        }
        .gc-header-info span:last-child {
            /* Keep the brand text on one line. */
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            font-size: 15px !important;
            color: var(--gc-text) !important;
        }
        .gc-status-dot {
            width: 8px;
            height: 8px;
            background-color: #4CAF50;
            border-radius: 50%;
        }
        .gc-close-btn {
            cursor: pointer;
            transition: color 0.2s;
            /* ponytail: !important defeats Shopify theme <button> styles. Was JS setProperty. */
            background: none !important;
            border: none !important;
            color: #999999 !important;
            font-size: 22px !important;
            padding: 0 !important;
            margin-left: auto !important;
            line-height: 1 !important;
            width: auto !important;
            height: auto !important;
            min-height: unset !important;
            flex-shrink: 0 !important;
        }
        .gc-close-btn:hover {
            color: var(--gc-text);
        }
        .gc-chat-body {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            background-color: var(--gc-cream);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .gc-chat-body::-webkit-scrollbar { width: 6px; }
        .gc-chat-body::-webkit-scrollbar-track { background: rgba(0,0,0,0.05); border-radius: 3px; }
        .gc-chat-body::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.15); border-radius: 3px; }
        .gc-message {
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
            line-height: 1.6;
            word-wrap: break-word;
        }
        .gc-bot-message {
            background-color: var(--gc-white);
            color: var(--gc-text);
            align-self: flex-start;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        }
        .gc-user-message {
            background-color: var(--gc-primary);
            color: var(--gc-white);
            align-self: flex-end;
            border-radius: 12px;
            border-bottom-right-radius: 4px;
        }
        .gc-input-area {
            padding: 12px 16px 14px;
            border-top: 1px solid rgba(0,0,0,0.08);
            display: flex;
            gap: 8px;
            background-color: var(--gc-white);
            flex-shrink: 0;
            align-items: center;
        }
        .gc-input-area input {
            flex: 1;
            padding: 10px 14px;
            border: 1px solid #e8e0cc;
            border-radius: 8px;
            outline: none;
            font-family: inherit;
            font-size: 16px; /* >=16px stops iOS Safari auto-zoom on focus */
            background-color: var(--gc-white);
            color: var(--gc-text);
        }
        .gc-input-area input:focus {
            border-color: var(--gc-primary);
        }
        .gc-send-btn {
            background-color: var(--gc-primary);
            color: var(--gc-white);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: opacity 0.2s;
            /* ponytail: !important defeats Shopify theme <button> styles. Was JS setProperty. */
            border: none !important;
            width: 38px !important;
            height: 38px !important;
            min-width: unset !important;
            max-width: unset !important;
            min-height: unset !important;
            max-height: unset !important;
            padding: 0 !important;
            box-sizing: border-box !important;
            border-radius: 8px !important;
            line-height: 1 !important;
            flex-shrink: 0 !important;
        }
        .gc-send-btn:hover {
            opacity: 0.85;
        }
        .gc-typing {
            display: flex;
            gap: 4px;
            padding: 12px 14px;
            background-color: var(--gc-white);
            border-radius: 12px;
            align-self: flex-start;
            width: fit-content;
            box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        }
        .gc-typing span {
            width: 6px;
            height: 6px;
            background-color: #999;
            border-radius: 50%;
            animation: gc-bounce 1.4s infinite ease-in-out both;
        }
        .gc-typing span:nth-child(1) { animation-delay: -0.32s; }
        .gc-typing span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes gc-bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        .gc-consent-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(245, 240, 220, 0.98);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 100;
            padding: 20px;
        }
        .gc-consent-overlay.gc-hidden {
            display: none;
        }
        .gc-consent-content {
            text-align: center;
            max-width: 300px;
        }
        .gc-consent-content h3 {
            color: var(--gc-primary);
            margin: 0 0 12px 0;
            font-size: 18px;
        }
        .gc-consent-content p {
            color: var(--gc-text);
            font-size: 13px;
            line-height: 1.6;
            margin: 0 0 8px 0;
        }
        .gc-consent-content .gc-subtitle {
            color: var(--gc-gray);
            font-size: 12px;
            margin-bottom: 16px;
        }
        .gc-consent-content a {
            color: var(--gc-primary);
        }
        .gc-consent-buttons {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .gc-consent-btn {
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            border: none;
        }
        .gc-consent-accept {
            background-color: var(--gc-primary);
            color: var(--gc-white);
        }
        .gc-consent-decline {
            background-color: transparent;
            color: var(--gc-gray);
            border: 1px solid #ccc;
        }
    `;

    // =============================================================================
    // HTML Structure
    // =============================================================================
    const html = `
        <div id="gc-chatbot-container">
            <button id="gc-toggle-btn" aria-label="Open chat">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
            <div id="gc-chat-widget">
                <div class="gc-chat-header">
                    <div class="gc-header-info">
                        <span class="gc-status-dot"></span>
                        <span>${_escHtml(CONFIG.brand)} Support</span>
                    </div>
                    <button class="gc-close-btn" aria-label="Close chat">&times;</button>
                </div>
                <div class="gc-consent-overlay" id="gc-consent">
                    <div class="gc-consent-content">
                        <h3>Privacy Notice</h3>
                        <p>Om je te helpen slaan we je chatberichten tijdelijk op. Je gegevens worden verwerkt conform onze <a href="${_escHtml(CONFIG.privacyUrl)}" target="_blank">privacyverklaring</a>.</p>
                        <p class="gc-subtitle">To help you, we temporarily store your chat messages according to our <a href="${_escHtml(CONFIG.privacyUrl)}" target="_blank">privacy policy</a>.</p>
                        <div class="gc-consent-buttons">
                            <button class="gc-consent-btn gc-consent-accept" id="gc-accept">Akkoord / Accept</button>
                            <button class="gc-consent-btn gc-consent-decline" id="gc-decline">Weigeren / Decline</button>
                        </div>
                    </div>
                </div>
                <div class="gc-chat-body" id="gc-body"></div>
                <div class="gc-input-area" id="gc-input-area">
                    <input type="text" id="gc-input" placeholder="Stel je vraag... / Ask your question..." autocomplete="off">
                    <button class="gc-send-btn" id="gc-send" aria-label="Send message">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M22 2L11 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;

    // =============================================================================
    // Inject styles and HTML into page
    // =============================================================================
    function init() {
        // Inject CSS
        const styleEl = document.createElement('style');
        styleEl.id = 'gc-chatbot-styles';
        styleEl.textContent = styles;
        document.head.appendChild(styleEl);

        // Inject HTML
        const container = document.createElement('div');
        container.innerHTML = html;
        document.body.appendChild(container.firstElementChild);

        // Initialize chat functionality
        initChat();
    }

    // =============================================================================
    // Chat Functionality
    // =============================================================================
    function initChat() {
        const toggleBtn = document.getElementById('gc-toggle-btn');
        const widget = document.getElementById('gc-chat-widget');
        const closeBtn = widget.querySelector('.gc-close-btn');
        const chatBody = document.getElementById('gc-body');
        const inputArea = document.getElementById('gc-input-area');
        const input = document.getElementById('gc-input');
        const sendBtn = document.getElementById('gc-send');
        const consentOverlay = document.getElementById('gc-consent');
        const acceptBtn = document.getElementById('gc-accept');
        const declineBtn = document.getElementById('gc-decline');

        let isOpen = false;
        let sessionId = null;
        let hasConsent = false;
        let isSending = false;
        let typingCounter = 0;

        const CONSENT_KEY = 'gc_chatbot_consent';
        const SESSION_KEY = 'gc_chatbot_session';

        // Check existing consent
        function checkConsent() {
            if (localStorage.getItem(CONSENT_KEY) === 'accepted') {
                hasConsent = true;
                sessionId = sessionStorage.getItem(SESSION_KEY);
                consentOverlay.classList.add('gc-hidden');
                if (!sessionId) fetchSession();
            } else if (sessionStorage.getItem(CONSENT_KEY) === 'declined') {
                // Decline is per-tab (sessionStorage): reloading the page re-offers consent.
                hasConsent = false;
                consentOverlay.classList.add('gc-hidden');
                disableChat();
            }
        }

        function disableChat() {
            inputArea.style.display = 'none';
            appendMessage("Je hebt geen toestemming gegeven. Neem contact op via telefoon of e-mail.\n\nYou declined consent. Please contact us by phone or email.", 'bot');
        }

        // Fetch secure session ID
        async function fetchSession() {
            try {
                const response = await fetch(CONFIG.apiUrl + '/api/session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.session_id) {
                    sessionId = data.session_id;
                    sessionStorage.setItem(SESSION_KEY, sessionId);
                }
            } catch (error) {
                console.error('GroundCoverGroup Chatbot: Failed to get session', error);
                sessionId = 'fallback_' + Date.now();
            }
        }

        // Toggle chat
        function toggleChat() {
            isOpen = !isOpen;
            if (isOpen) {
                widget.classList.add('gc-active');
                if (localStorage.getItem(CONSENT_KEY) === 'accepted') {
                    input.focus();
                } else if (sessionStorage.getItem(CONSENT_KEY) !== 'declined') {
                    consentOverlay.classList.remove('gc-hidden');
                }
                // Declined this tab: stay disabled; a reload re-offers consent.
            } else {
                widget.classList.remove('gc-active');
            }
        }

        // Safe markdown renderer for bot messages.
        // Escapes HTML first (XSS prevention), then applies safe transformations.
        function renderBotMessage(text) {
            return _escHtml(text)
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
                    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
                .replace(/\n/g, '<br>');
        }

        // Append message. Bot messages use safe markdown rendering;
        // user messages use textContent (no HTML ever).
        function appendMessage(text, sender) {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'gc-message ' + (sender === 'user' ? 'gc-user-message' : 'gc-bot-message');
            if (sender === 'bot') {
                msgDiv.innerHTML = renderBotMessage(text);
            } else {
                msgDiv.textContent = text;
            }
            chatBody.appendChild(msgDiv);
            chatBody.scrollTop = chatBody.scrollHeight;
        }

        // Typing indicator
        function showTyping() {
            const id = 'gc-typing-' + (++typingCounter);
            const div = document.createElement('div');
            div.className = 'gc-typing';
            div.id = id;
            div.innerHTML = '<span></span><span></span><span></span>';
            chatBody.appendChild(div);
            chatBody.scrollTop = chatBody.scrollHeight;
            return id;
        }

        function removeTyping(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }

        // Send message
        async function sendMessage() {
            if (isSending) return; // send lock: one in-flight request at a time
            if (!hasConsent) {
                appendMessage("Geef eerst toestemming. / Please accept privacy notice first.", 'bot');
                return;
            }

            const text = input.value.trim();
            if (!text) return;

            // Guarantee a server session before the first send (never POST session_id: null).
            if (!sessionId) await fetchSession();

            isSending = true;
            sendBtn.disabled = true;
            appendMessage(text, 'user');
            input.value = '';

            const typingId = showTyping();

            try {
                const response = await fetch(CONFIG.apiUrl + '/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: sessionId })
                });
                removeTyping(typingId);
                if (response.status === 429) {
                    appendMessage('Je stuurt te snel berichten. Wacht even en probeer opnieuw.\n\nYou are sending messages too quickly. Please wait a moment and try again.', 'bot');
                    return;
                }
                if (!response.ok) {
                    throw new Error('Server returned an error.');
                }
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Server returned an unexpected response.');
                }
                const data = await response.json();
                appendMessage(data.response || 'Sorry, an error occurred. Please try again.', 'bot');
            } catch (error) {
                removeTyping(typingId);
                appendMessage('Connection error. Please check your internet and try again.', 'bot');
            } finally {
                isSending = false;
                sendBtn.disabled = false;
            }
        }

        // Event listeners
        toggleBtn.addEventListener('click', toggleChat);
        closeBtn.addEventListener('click', toggleChat);
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        acceptBtn.addEventListener('click', async () => {
            localStorage.setItem(CONSENT_KEY, 'accepted');
            hasConsent = true;
            consentOverlay.classList.add('gc-hidden');
            await fetchSession();
            input.focus();
        });

        declineBtn.addEventListener('click', () => {
            sessionStorage.setItem(CONSENT_KEY, 'declined'); // per-tab; reload re-offers consent
            hasConsent = false;
            consentOverlay.classList.add('gc-hidden');
            disableChat();
        });

        // Initialize
        checkConsent();

        // Add welcome message with small gray English subtitle
        if (chatBody.children.length === 0) {
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'gc-message gc-bot-message';
            welcomeDiv.innerHTML = renderBotMessage(CONFIG.welcomeMessage) +
                '<br><small style="color:#666;font-size:12px;">(I also speak English!)</small>';
            chatBody.appendChild(welcomeDiv);
        }
    }

    // =============================================================================
    // Start when DOM is ready
    // =============================================================================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
