document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('toggleChat');
    const closeBtn = document.getElementById('closeChat');
    const chatWidget = document.getElementById('chatWidget');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatBody = document.getElementById('chatBody');
    const chatInputArea = document.getElementById('chatInputArea');
    const consentOverlay = document.getElementById('consentOverlay');
    const acceptConsentBtn = document.getElementById('acceptConsent');
    const declineConsentBtn = document.getElementById('declineConsent');

    let isOpen = false;
    let sessionId = null;
    let hasConsent = false;

    // =============================================================================
    // GDPR: Check for existing consent
    // =============================================================================
    const CONSENT_KEY = 'chatbot_gdpr_consent';
    const SESSION_KEY = 'chatbot_session_id';

    function checkConsent() {
        const consent = localStorage.getItem(CONSENT_KEY);
        if (consent === 'accepted') {
            hasConsent = true;
            sessionId = localStorage.getItem(SESSION_KEY);
            hideConsentOverlay();
            // If no session ID, fetch a new one
            if (!sessionId) {
                fetchSecureSessionId();
            }
        } else if (consent === 'declined') {
            hasConsent = false;
            hideConsentOverlay();
            disableChat();
        }
        // If no consent recorded, overlay will show when chat opens
    }

    function hideConsentOverlay() {
        if (consentOverlay) {
            consentOverlay.style.display = 'none';
        }
    }

    function showConsentOverlay() {
        if (consentOverlay) {
            consentOverlay.style.display = 'flex';
        }
    }

    function disableChat() {
        if (chatInputArea) {
            chatInputArea.style.display = 'none';
        }
        appendMessage(
            "Je hebt geen toestemming gegeven voor gegevensverwerking. " +
            "Neem contact op via telefoon of e-mail.\n\n" +
            "You declined data processing consent. " +
            "Please contact us by phone or email.",
            'bot'
        );
    }

    // =============================================================================
    // SECURITY: Fetch cryptographically secure session ID from server
    // =============================================================================
    async function fetchSecureSessionId() {
        try {
            const response = await fetch('/api/session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (data.session_id) {
                sessionId = data.session_id;
                localStorage.setItem(SESSION_KEY, sessionId);
            }
        } catch (error) {
            console.error('Failed to fetch session ID:', error);
            // Fallback (less secure, but functional)
            sessionId = 'fallback_' + Date.now();
        }
    }

    // =============================================================================
    // Consent button handlers
    // =============================================================================
    if (acceptConsentBtn) {
        acceptConsentBtn.addEventListener('click', async () => {
            localStorage.setItem(CONSENT_KEY, 'accepted');
            hasConsent = true;
            hideConsentOverlay();
            await fetchSecureSessionId();
            userInput.focus();
        });
    }

    if (declineConsentBtn) {
        declineConsentBtn.addEventListener('click', () => {
            localStorage.setItem(CONSENT_KEY, 'declined');
            hasConsent = false;
            hideConsentOverlay();
            disableChat();
        });
    }

    // =============================================================================
    // Toggle Chat
    // =============================================================================
    function toggleChat() {
        isOpen = !isOpen;
        if (isOpen) {
            chatWidget.classList.add('active');
            // Check consent status when opening
            const consent = localStorage.getItem(CONSENT_KEY);
            if (!consent) {
                showConsentOverlay();
            } else if (consent === 'accepted') {
                userInput.focus();
            }
        } else {
            chatWidget.classList.remove('active');
        }
    }

    toggleBtn.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);

    // =============================================================================
    // Send Message Logic
    // =============================================================================
    function sendMessage() {
        // Check consent before sending
        if (!hasConsent) {
            appendMessage(
                "Geef eerst toestemming voor gegevensverwerking.\n" +
                "Please accept the privacy notice first.",
                'bot'
            );
            return;
        }

        const text = userInput.value.trim();
        if (!text) return;

        // Add User Message
        appendMessage(text, 'user');
        userInput.value = '';

        // Show Typing Indicator
        const loadingId = showTyping();

        // Call API
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: text,
                session_id: sessionId
            })
        })
            .then(response => response.json())
            .then(data => {
                removeTyping(loadingId);
                if (data.response) {
                    appendMessage(data.response, 'bot');
                } else {
                    appendMessage("I apologize, but I encountered an error. Please try again.", 'bot');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                removeTyping(loadingId);
                appendMessage(`Connection Error: ${error.message || error}. Please try refreshing the page.`, 'bot');
            });
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // =============================================================================
    // Helper: Append Message (XSS-safe with innerText)
    // =============================================================================
    function appendMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');
        msgDiv.innerText = text; // innerText is safer than innerHTML
        chatBody.appendChild(msgDiv);
        scrollToBottom();
    }

    // Helper: Typing Indicator
    function showTyping() {
        const id = 'typing-' + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.classList.add('typing');
        typingDiv.id = id;
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        chatBody.appendChild(typingDiv);
        scrollToBottom();
        return id;
    }

    function removeTyping(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    // =============================================================================
    // Initialize: Check consent on page load
    // =============================================================================
    checkConsent();
});
