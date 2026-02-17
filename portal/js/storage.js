/**
 * Chat Log Portal - localStorage Data Layer
 *
 * localStorage Key Schema:
 * ─────────────────────────────────────────────────────────────────
 * portal_version       - string  - Schema version for migrations ("1.0")
 * portal_auth          - object  - Current auth state
 * portal_conversations - array   - All conversation objects with messages
 * portal_labels_meta   - array   - Available label definitions
 * portal_settings      - object  - Portal user preferences
 * ─────────────────────────────────────────────────────────────────
 *
 * Size budget (localStorage ~5-10 MB):
 *   ~25 conversations x ~10 messages x ~500 bytes = ~125 KB
 *   Labels/notes metadata: ~5 KB
 *   Auth + settings: ~1 KB
 *   Total seed footprint: ~130 KB (well within limits)
 *   At scale: ~2000 conversations before approaching 5 MB
 */

/* ================================================================
   SECTION 1 - DATA STRUCTURES / SCHEMAS
   ================================================================

   portal_auth:
   {
     "authenticated": boolean,
     "user": {
       "username": string,
       "role": "admin" | "viewer" | "trainer"
     },
     "loginTime": ISO string | null
   }

   portal_conversations[]:
   {
     "id": string (uuid-like, e.g. "conv_a1b2c3d4"),
     "sessionId": string (matches log filename pattern),
     "startedAt": ISO string,
     "endedAt": ISO string,
     "language": "nl" | "en",
     "messageCount": number,
     "status": "resolved" | "escalated" | "unknown_flagged" | "open",
     "labels": string[],          // conversation-level labels
     "rating": number | null,     // 1-5 overall quality rating
     "notes": [                   // internal notes
       { "id": string, "text": string, "author": string, "createdAt": ISO }
     ],
     "messages": [
       {
         "id": string (e.g. "msg_0"),
         "timestamp": ISO string,
         "requestId": string | null (8-char from logs),
         "role": "user" | "bot",
         "content": string,
         "labels": string[],       // message-level labels
         "rating": number | null   // per-message quality 1-5
       }
     ]
   }

   portal_labels_meta[]:
   {
     "name": string,
     "color": string (hex),
     "description": string
   }

   portal_settings:
   {
     "theme": "light" | "dark",
     "pageSize": number,
     "defaultLanguageFilter": "all" | "nl" | "en"
   }

   ================================================================ */


// ================================================================
// SECTION 2 - STORAGE MANAGER CLASS
// ================================================================

const STORAGE_VERSION = '1.0';
const KEYS = {
  VERSION: 'portal_version',
  AUTH: 'portal_auth',
  CONVERSATIONS: 'portal_conversations',
  LABELS: 'portal_labels_meta',
  SETTINGS: 'portal_settings'
};

class StorageManager {
  constructor() {
    this._init();
  }

  // ── Initialization & Migration ─────────────────────────────────

  _init() {
    const version = localStorage.getItem(KEYS.VERSION);

    if (!version) {
      // First run - seed everything
      this._seedAll();
    } else if (version !== STORAGE_VERSION) {
      // Future: run migrations here
      this._migrate(version);
    }
  }

  _seedAll() {
    // Start with empty conversations — real data comes from API sync
    this._write(KEYS.CONVERSATIONS, []);
    // Labels are now synced from backend API, not seeded locally
    this._write(KEYS.LABELS, []);
    this._write(KEYS.SETTINGS, {
      theme: 'light',
      pageSize: 20,
      defaultLanguageFilter: 'all'
    });
    this._write(KEYS.AUTH, {
      authenticated: false,
      user: null,
      loginTime: null,
      apiKey: null
    });
    localStorage.setItem(KEYS.VERSION, STORAGE_VERSION);
  }

  _migrate(fromVersion) {
    // Placeholder for future schema migrations
    // Example: if (fromVersion === '1.0') { ... migrate to 1.1 ... }
    localStorage.setItem(KEYS.VERSION, STORAGE_VERSION);
  }

  // ── Low-level read/write with error handling ───────────────────

  _read(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      console.error(`StorageManager: failed to read ${key}`, e);
      return null;
    }
  }

  _write(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (e) {
      if (e.name === 'QuotaExceededError' || e.code === 22) {
        console.error('StorageManager: localStorage quota exceeded');
        return false;
      }
      console.error(`StorageManager: failed to write ${key}`, e);
      return false;
    }
  }

  // ── Authenticated API Helper (Feature 30e) ────────────────────

  /**
   * Make an authenticated API call to the backend.
   * Auto-logouts on 401.
   *
   * @param {string} method - HTTP method
   * @param {string} path   - API path (e.g. '/admin/api/labels')
   * @param {object} [body] - Request body for POST/PUT
   * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
   */
  async _apiCall(method, path, body = null) {
    const auth = this.getAuth();
    const adminKey = auth.apiKey;
    if (!adminKey) {
      return { ok: false, error: 'Not authenticated' };
    }

    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Key': adminKey
        }
      };

      if (body !== null) {
        options.body = JSON.stringify(body);
      }

      const response = await fetch(path, options);

      if (response.status === 401) {
        this.clearAuth();
        window.location.reload();
        return { ok: false, error: 'Unauthorized' };
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        return { ok: false, error: errorData.error || `Request failed (${response.status})` };
      }

      const data = await response.json();
      return { ok: true, data };

    } catch (err) {
      console.error('API call failed:', err);
      return { ok: false, error: err.message };
    }
  }

  // ── Auth ───────────────────────────────────────────────────────

  getAuth() {
    return this._read(KEYS.AUTH) || { authenticated: false, user: null, loginTime: null, apiKey: null };
  }

  setAuth(user, apiKey) {
    return this._write(KEYS.AUTH, {
      authenticated: true,
      user: { username: user.username, role: user.role || 'viewer' },
      loginTime: new Date().toISOString(),
      apiKey: apiKey || null
    });
  }

  clearAuth() {
    return this._write(KEYS.AUTH, { authenticated: false, user: null, loginTime: null, apiKey: null });
  }

  // ── API Sync ────────────────────────────────────────────────────

  /**
   * Validate an admin API key against the backend.
   * @param {string} apiKey
   * @returns {Promise<boolean>}
   */
  async validateApiKey(apiKey) {
    try {
      const resp = await fetch('/admin/api/conversations', {
        method: 'GET',
        headers: { 'X-Admin-Key': apiKey }
      });
      return resp.ok;
    } catch (e) {
      console.error('StorageManager: API key validation failed', e);
      return false;
    }
  }

  /**
   * Detect language from message content (simple heuristic).
   * @param {string} text
   * @returns {string} 'nl' or 'en'
   */
  _detectLanguage(text) {
    const nlWords = ['hallo', 'bedankt', 'bestelling', 'levering', 'graag', 'vraag', 'welkom', 'producten', 'tuin', 'kunt', 'helpen', 'goed', 'onze', 'webshop'];
    const lower = text.toLowerCase();
    let nlScore = 0;
    for (const w of nlWords) {
      if (lower.includes(w)) nlScore++;
    }
    return nlScore >= 2 ? 'nl' : 'en';
  }

  /**
   * Transform an API conversation object to the localStorage format.
   * @param {Object} apiConv - From /admin/api/conversations
   * @returns {Object} Portal-formatted conversation
   */
  _transformApiConversation(apiConv) {
    // Build messages in portal format
    const messages = [];
    let allText = '';
    let msgIdx = 0;

    for (const entry of (apiConv.messages || [])) {
      // Each API entry has both user and bot in one object
      if (entry.user) {
        messages.push({
          id: `msg_${msgIdx++}`,
          timestamp: entry.timestamp || '',
          requestId: null,
          role: 'user',
          content: entry.user,
          labels: [],
          rating: null
        });
        allText += ' ' + entry.user;
      }
      if (entry.bot) {
        messages.push({
          id: `msg_${msgIdx++}`,
          timestamp: entry.timestamp || '',
          requestId: null,
          role: 'bot',
          content: entry.bot,
          labels: [],
          rating: null
        });
        allText += ' ' + entry.bot;
      }
    }

    const detectedLang = this._detectLanguage(allText);

    // Feature 30e: Read persistent metadata from API response (added by 30d)
    const meta = apiConv.metadata || {};

    // Overlay message-level metadata from DB onto messages
    const msgMeta = meta.messageMetadata || {};
    for (const msg of messages) {
      const mm = msgMeta[msg.id];
      if (mm) {
        msg.labels = mm.labels || [];
        msg.rating = mm.rating != null ? mm.rating : null;
      }
    }

    return {
      id: apiConv.id,
      sessionId: apiConv.id,
      startedAt: apiConv.started || '',
      endedAt: apiConv.lastMessage || '',
      language: meta.language || detectedLang,
      messageCount: messages.length,
      status: meta.status || 'open',
      labels: meta.labels || [],
      rating: meta.rating != null ? meta.rating : null,
      notes: (meta.notes || []).map(n => ({
        id: n.id,
        text: n.text,
        author: n.author,
        createdAt: n.created_at
      })),
      messages: messages
    };
  }

  /**
   * Fetch real conversations from the backend API and merge
   * with existing localStorage data (preserving labels, notes, etc.).
   *
   * @param {string} [apiKey] - If not given, uses stored key
   * @returns {Promise<{ synced: number, errors: string[] }>}
   */
  /**
   * Fetch conversations from the backend API.
   * Metadata (labels, notes, status, rating) is now included in the API
   * response (Feature 30d), so no localStorage merge is needed.
   *
   * @param {string} [apiKey] - If not given, uses stored key
   * @returns {Promise<{ synced: number, errors: string[] }>}
   */
  async syncFromApi(apiKey) {
    const key = apiKey || this.getAuth().apiKey;
    if (!key) {
      return { synced: 0, errors: ['No API key available'] };
    }

    try {
      const result = await this._apiCall('GET', '/admin/api/conversations');

      if (!result.ok) {
        return { synced: 0, errors: [result.error] };
      }

      const apiConversations = result.data.conversations || [];

      // Transform API conversations (metadata is read from response)
      const conversations = apiConversations.map(c => this._transformApiConversation(c));

      // Sort newest first
      conversations.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));

      this._write(KEYS.CONVERSATIONS, conversations);
      console.log(`StorageManager: synced ${conversations.length} conversations from API`);
      return { synced: conversations.length, errors: [] };

    } catch (e) {
      console.error('StorageManager: syncFromApi failed', e);
      return { synced: 0, errors: [e.message] };
    }
  }

  /**
   * Refresh a single conversation from the backend API.
   * More efficient than syncFromApi() which re-fetches everything.
   *
   * @param {string} sessionId - The conversation session ID
   * @returns {Promise<boolean>} - True if successful, false if failed
   */
  async _refreshConversation(sessionId) {
    try {
      const result = await this._apiCall('GET', `/admin/api/conversations/${sessionId}`);

      if (!result.ok) {
        console.warn('Failed to refresh conversation:', result.error);
        return false;
      }

      // Transform the API response to portal format
      const transformed = this._transformApiConversation(result.data);

      // Update only this conversation in localStorage
      const convs = this._read(KEYS.CONVERSATIONS) || [];
      const idx = convs.findIndex(c => c.id === sessionId);

      if (idx !== -1) {
        // Replace existing conversation
        convs[idx] = transformed;
      } else {
        // New conversation - add to beginning
        convs.unshift(transformed);
      }

      this._write(KEYS.CONVERSATIONS, convs);
      console.log(`StorageManager: refreshed conversation ${sessionId}`);
      return true;

    } catch (e) {
      console.error('StorageManager: _refreshConversation failed', e);
      return false;
    }
  }

  // ── Conversations (Read) ───────────────────────────────────────

  /**
   * Get conversations with optional filtering, sorting, and pagination.
   *
   * @param {Object} filters
   * @param {string}   [filters.status]     - Filter by status
   * @param {string}   [filters.language]   - Filter by language ("nl"|"en")
   * @param {string}   [filters.label]      - Filter by label (conversation-level)
   * @param {string}   [filters.dateFrom]   - ISO date string lower bound
   * @param {string}   [filters.dateTo]     - ISO date string upper bound
   * @param {boolean}  [filters.hasNotes]   - Only conversations with notes
   * @param {boolean}  [filters.unrated]    - Only unrated conversations
   * @param {string}   [filters.search]     - Full-text search query
   * @param {string}   [filters.sortBy]     - "date"|"messages"|"rating" (default: "date")
   * @param {string}   [filters.sortDir]    - "asc"|"desc" (default: "desc")
   * @param {number}   [filters.page]       - Page number (1-based)
   * @param {number}   [filters.pageSize]   - Items per page
   * @returns {{ conversations: Array, total: number, page: number, pageSize: number, totalPages: number }}
   */
  getConversations(filters = {}) {
    let convs = this._read(KEYS.CONVERSATIONS) || [];

    // Apply filters
    if (filters.status) {
      convs = convs.filter(c => c.status === filters.status);
    }
    if (filters.language) {
      convs = convs.filter(c => c.language === filters.language);
    }
    if (filters.label) {
      convs = convs.filter(c => c.labels.includes(filters.label));
    }
    if (filters.dateFrom) {
      const from = new Date(filters.dateFrom).getTime();
      convs = convs.filter(c => new Date(c.startedAt).getTime() >= from);
    }
    if (filters.dateTo) {
      const to = new Date(filters.dateTo).getTime();
      convs = convs.filter(c => new Date(c.startedAt).getTime() <= to);
    }
    if (filters.hasNotes) {
      convs = convs.filter(c => c.notes && c.notes.length > 0);
    }
    if (filters.unrated) {
      convs = convs.filter(c => c.rating === null || c.rating === undefined);
    }
    if (filters.search) {
      const q = filters.search.toLowerCase();
      convs = convs.filter(c =>
        c.messages.some(m => m.content.toLowerCase().includes(q)) ||
        c.labels.some(l => l.toLowerCase().includes(q)) ||
        (c.notes && c.notes.some(n => n.text.toLowerCase().includes(q)))
      );
    }

    // Sorting
    const sortBy = filters.sortBy || 'date';
    const sortDir = filters.sortDir || 'desc';
    const dirMul = sortDir === 'asc' ? 1 : -1;

    convs.sort((a, b) => {
      switch (sortBy) {
        case 'messages':
          return (a.messageCount - b.messageCount) * dirMul;
        case 'rating':
          return ((a.rating || 0) - (b.rating || 0)) * dirMul;
        case 'date':
        default:
          return (new Date(a.startedAt) - new Date(b.startedAt)) * dirMul;
      }
    });

    // Pagination
    const total = convs.length;
    const pageSize = filters.pageSize || this.getSettings().pageSize || 20;
    const page = filters.page || 1;
    const totalPages = Math.ceil(total / pageSize);
    const start = (page - 1) * pageSize;
    const paged = convs.slice(start, start + pageSize);

    return { conversations: paged, total, page, pageSize, totalPages };
  }

  /**
   * Get a single conversation by ID.
   * @param {string} id
   * @returns {Object|null}
   */
  getConversation(id) {
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    return convs.find(c => c.id === id) || null;
  }

  // ── Labels ─────────────────────────────────────────────────────

  /**
   * Add a label to a conversation or specific message via API.
   * @param {string} conversationId
   * @param {string|null} messageId - null for conversation-level label
   * @param {string} label
   * @returns {Promise<boolean>}
   */
  async addLabel(conversationId, messageId, label) {
    let result;
    if (messageId) {
      result = await this._apiCall(
        'POST',
        `/admin/api/conversations/${conversationId}/messages/${messageId}/labels`,
        { label_name: label }
      );
    } else {
      result = await this._apiCall(
        'POST',
        `/admin/api/conversations/${conversationId}/labels`,
        { label_name: label }
      );
    }

    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  /**
   * Remove a label from a conversation or specific message via API.
   * @param {string} conversationId
   * @param {string|null} messageId - null for conversation-level label
   * @param {string} label
   * @returns {Promise<boolean>}
   */
  async removeLabel(conversationId, messageId, label) {
    let result;
    if (messageId) {
      result = await this._apiCall(
        'DELETE',
        `/admin/api/conversations/${conversationId}/messages/${messageId}/labels/${encodeURIComponent(label)}`
      );
    } else {
      result = await this._apiCall(
        'DELETE',
        `/admin/api/conversations/${conversationId}/labels/${encodeURIComponent(label)}`
      );
    }

    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  /**
   * Get all available label definitions (from cache).
   * @returns {Array}
   */
  getLabelDefinitions() {
    return this._read(KEYS.LABELS) || [];
  }

  /**
   * Fetch label definitions from the backend API and cache locally.
   * @returns {Promise<Array>}
   */
  async syncLabelDefinitions() {
    const result = await this._apiCall('GET', '/admin/api/labels');
    if (!result.ok) throw new Error(result.error);
    this._write(KEYS.LABELS, result.data);
    return result.data;
  }

  /**
   * Add a new label definition via API.
   * @param {string} name
   * @param {string} color - hex color
   * @param {string} description
   * @returns {Promise<boolean>}
   */
  async addLabelDefinition(name, color, description) {
    const result = await this._apiCall(
      'POST', '/admin/api/labels',
      { name, color, description }
    );
    if (!result.ok) throw new Error(result.error);
    await this.syncLabelDefinitions();
    return true;
  }

  // ── Ratings ────────────────────────────────────────────────────

  /**
   * Set quality rating on a conversation or specific message via API.
   * @param {string} conversationId
   * @param {string|null} messageId - null for conversation-level rating
   * @param {number|null} rating - 1 to 5, or null to clear
   * @returns {Promise<boolean>}
   */
  async setRating(conversationId, messageId, rating) {
    if (rating !== null && (rating < 1 || rating > 5)) {
      throw new Error('Rating must be 1-5 or null');
    }

    let result;
    if (messageId) {
      result = await this._apiCall(
        'PUT',
        `/admin/api/conversations/${conversationId}/messages/${messageId}/rating`,
        { rating }
      );
    } else {
      result = await this._apiCall(
        'PUT',
        `/admin/api/conversations/${conversationId}/metadata`,
        { rating }
      );
    }

    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  // ── Notes ──────────────────────────────────────────────────────

  /**
   * Add an internal note to a conversation via API.
   * @param {string} conversationId
   * @param {string} text
   * @returns {Promise<Object>} The created note
   */
  async addNote(conversationId, text) {
    const auth = this.getAuth();
    const author = auth.user ? auth.user.username : 'admin';

    const result = await this._apiCall(
      'POST',
      `/admin/api/conversations/${conversationId}/notes`,
      { text, author }
    );

    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return { id: result.data.note_id, text, author, createdAt: new Date().toISOString() };
  }

  /**
   * Delete a note from a conversation via API.
   * @param {string} conversationId
   * @param {string} noteId
   * @returns {Promise<boolean>}
   */
  async deleteNote(conversationId, noteId) {
    const result = await this._apiCall(
      'DELETE',
      `/admin/api/conversations/${conversationId}/notes/${noteId}`
    );

    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  // ── Status ─────────────────────────────────────────────────────

  /**
   * Update conversation status via API.
   * @param {string} conversationId
   * @param {string} status - "resolved"|"escalated"|"unknown_flagged"|"open"
   * @returns {Promise<boolean>}
   */
  async setStatus(conversationId, status) {
    const valid = ['resolved', 'escalated', 'unknown_flagged', 'open'];
    if (!valid.includes(status)) {
      throw new Error('Invalid status: ' + status);
    }

    const result = await this._apiCall(
      'PUT',
      `/admin/api/conversations/${conversationId}/metadata`,
      { status }
    );

    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  // ── Dashboard Stats ────────────────────────────────────────────

  /**
   * Compute dashboard statistics from current data.
   * @returns {Object}
   */
  getStats() {
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    const total = convs.length;

    if (total === 0) {
      return {
        total: 0, byStatus: {}, byLanguage: {},
        avgMessagesPerConv: 0, avgRating: null,
        ratedCount: 0, unratedCount: 0,
        escalationRate: 0, unknownRate: 0,
        labelCounts: {}, notesCount: 0,
        conversationsToday: 0, conversationsThisWeek: 0,
        busiestHour: null, avgResponseMessages: 0
      };
    }

    // By status
    const byStatus = {};
    convs.forEach(c => {
      byStatus[c.status] = (byStatus[c.status] || 0) + 1;
    });

    // By language
    const byLanguage = {};
    convs.forEach(c => {
      byLanguage[c.language] = (byLanguage[c.language] || 0) + 1;
    });

    // Average messages
    const totalMessages = convs.reduce((sum, c) => sum + c.messageCount, 0);
    const avgMessagesPerConv = Math.round((totalMessages / total) * 10) / 10;

    // Average rating (only rated conversations)
    const rated = convs.filter(c => c.rating !== null && c.rating !== undefined);
    const avgRating = rated.length > 0
      ? Math.round((rated.reduce((sum, c) => sum + c.rating, 0) / rated.length) * 10) / 10
      : null;

    // Escalation and unknown rates
    const escalationRate = Math.round(((byStatus.escalated || 0) / total) * 1000) / 10;
    const unknownRate = Math.round(((byStatus.unknown_flagged || 0) / total) * 1000) / 10;

    // Label distribution
    const labelCounts = {};
    convs.forEach(c => {
      c.labels.forEach(l => {
        labelCounts[l] = (labelCounts[l] || 0) + 1;
      });
    });

    // Notes count
    const notesCount = convs.reduce((sum, c) => sum + (c.notes ? c.notes.length : 0), 0);

    // Time-based stats
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const weekStart = new Date(todayStart);
    weekStart.setDate(weekStart.getDate() - 7);

    const conversationsToday = convs.filter(c => new Date(c.startedAt) >= todayStart).length;
    const conversationsThisWeek = convs.filter(c => new Date(c.startedAt) >= weekStart).length;

    // Busiest hour
    const hourCounts = new Array(24).fill(0);
    convs.forEach(c => {
      const hour = new Date(c.startedAt).getHours();
      hourCounts[hour]++;
    });
    const busiestHour = hourCounts.indexOf(Math.max(...hourCounts));

    return {
      total,
      byStatus,
      byLanguage,
      avgMessagesPerConv,
      avgRating,
      ratedCount: rated.length,
      unratedCount: total - rated.length,
      escalationRate,
      unknownRate,
      labelCounts,
      notesCount,
      conversationsToday,
      conversationsThisWeek,
      busiestHour,
      avgResponseMessages: avgMessagesPerConv
    };
  }

  // ── Search ─────────────────────────────────────────────────────

  /**
   * Full-text search across conversations.
   * Returns matching conversations with highlighted context.
   *
   * @param {string} query
   * @returns {Array<{ conversation: Object, matches: Array<{ messageId: string, snippet: string }> }>}
   */
  search(query) {
    if (!query || query.trim().length === 0) return [];

    const q = query.toLowerCase().trim();
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    const results = [];

    for (const conv of convs) {
      const matches = [];

      for (const msg of conv.messages) {
        const idx = msg.content.toLowerCase().indexOf(q);
        if (idx !== -1) {
          // Extract a snippet around the match
          const start = Math.max(0, idx - 40);
          const end = Math.min(msg.content.length, idx + q.length + 40);
          let snippet = '';
          if (start > 0) snippet += '...';
          snippet += msg.content.substring(start, end);
          if (end < msg.content.length) snippet += '...';

          matches.push({ messageId: msg.id, role: msg.role, snippet });
        }
      }

      // Also search notes
      if (conv.notes) {
        for (const note of conv.notes) {
          if (note.text.toLowerCase().includes(q)) {
            matches.push({ messageId: null, role: 'note', snippet: note.text.substring(0, 80) });
          }
        }
      }

      if (matches.length > 0) {
        results.push({
          conversation: {
            id: conv.id,
            startedAt: conv.startedAt,
            language: conv.language,
            status: conv.status,
            messageCount: conv.messageCount,
            labels: conv.labels
          },
          matches
        });
      }
    }

    return results;
  }

  // ── Export ──────────────────────────────────────────────────────

  /**
   * Export conversations in JSON or CSV format.
   * @param {string[]} ids - Conversation IDs to export (empty = all)
   * @param {string} format - "json" or "csv"
   * @returns {string} The formatted export data
   */
  exportConversations(ids = [], format = 'json') {
    let convs = this._read(KEYS.CONVERSATIONS) || [];

    if (ids.length > 0) {
      convs = convs.filter(c => ids.includes(c.id));
    }

    if (format === 'csv') {
      return this._toCSV(convs);
    }

    // JSON export - full data
    return JSON.stringify(convs, null, 2);
  }

  _toCSV(conversations) {
    const rows = [];
    rows.push([
      'conversation_id', 'session_id', 'started_at', 'ended_at',
      'language', 'status', 'message_count', 'rating', 'labels',
      'message_id', 'message_timestamp', 'role', 'content', 'message_labels', 'message_rating'
    ].join(','));

    for (const conv of conversations) {
      for (const msg of conv.messages) {
        rows.push([
          this._csvEscape(conv.id),
          this._csvEscape(conv.sessionId),
          this._csvEscape(conv.startedAt),
          this._csvEscape(conv.endedAt),
          conv.language,
          conv.status,
          conv.messageCount,
          conv.rating !== null ? conv.rating : '',
          this._csvEscape(conv.labels.join('; ')),
          this._csvEscape(msg.id),
          this._csvEscape(msg.timestamp),
          msg.role,
          this._csvEscape(msg.content),
          this._csvEscape(msg.labels.join('; ')),
          msg.rating !== null ? msg.rating : ''
        ].join(','));
      }
    }

    return rows.join('\n');
  }

  _csvEscape(val) {
    if (val === null || val === undefined) return '';
    const str = String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  /**
   * Trigger a browser download of exported data.
   * @param {string[]} ids
   * @param {string} format - "json" or "csv"
   */
  downloadExport(ids = [], format = 'json') {
    const data = this.exportConversations(ids, format);
    const mimeType = format === 'csv' ? 'text/csv' : 'application/json';
    const ext = format === 'csv' ? 'csv' : 'json';
    const filename = `chat-export-${new Date().toISOString().slice(0, 10)}.${ext}`;

    const blob = new Blob([data], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Settings ───────────────────────────────────────────────────

  getSettings() {
    return this._read(KEYS.SETTINGS) || { theme: 'light', pageSize: 20, defaultLanguageFilter: 'all' };
  }

  updateSettings(partial) {
    const current = this.getSettings();
    return this._write(KEYS.SETTINGS, { ...current, ...partial });
  }

  // ── Data Integrity & Maintenance ───────────────────────────────

  /**
   * Get current localStorage usage in bytes.
   * @returns {{ used: number, usedKB: string, estimatedMax: number }}
   */
  getStorageUsage() {
    let used = 0;
    for (const key of Object.values(KEYS)) {
      const val = localStorage.getItem(key);
      if (val) {
        used += key.length + val.length;
      }
    }
    // Each char is 2 bytes in JS (UTF-16)
    const usedBytes = used * 2;
    return {
      used: usedBytes,
      usedKB: (usedBytes / 1024).toFixed(1) + ' KB',
      estimatedMax: 5 * 1024 * 1024 // 5 MB conservative estimate
    };
  }

  /**
   * Reset all portal data and re-seed.
   */
  resetAll() {
    for (const key of Object.values(KEYS)) {
      localStorage.removeItem(key);
    }
    this._seedAll();
  }

  /**
   * Clear only conversations (keep auth, settings, labels).
   */
  clearConversations() {
    this._write(KEYS.CONVERSATIONS, []);
  }

  /**
   * Import conversations from JSON (merge or replace).
   * @param {string} jsonString
   * @param {boolean} replace - true to replace all, false to merge
   * @returns {{ imported: number, errors: string[] }}
   */
  importConversations(jsonString, replace = false) {
    const errors = [];
    let imported = 0;

    try {
      const data = JSON.parse(jsonString);
      if (!Array.isArray(data)) {
        return { imported: 0, errors: ['Invalid format: expected an array of conversations'] };
      }

      // Validate each conversation has required fields
      const valid = [];
      for (let i = 0; i < data.length; i++) {
        const c = data[i];
        if (!c.id || !c.messages || !Array.isArray(c.messages)) {
          errors.push(`Conversation at index ${i}: missing required fields (id, messages)`);
          continue;
        }
        valid.push(c);
      }

      if (replace) {
        this._write(KEYS.CONVERSATIONS, valid);
        imported = valid.length;
      } else {
        const existing = this._read(KEYS.CONVERSATIONS) || [];
        const existingIds = new Set(existing.map(c => c.id));
        for (const c of valid) {
          if (!existingIds.has(c.id)) {
            existing.push(c);
            imported++;
          } else {
            errors.push(`Conversation ${c.id}: already exists (skipped)`);
          }
        }
        this._write(KEYS.CONVERSATIONS, existing);
      }
    } catch (e) {
      errors.push('JSON parse error: ' + e.message);
    }

    return { imported, errors };
  }
}


// ================================================================
// SECTION 3 - SINGLETON EXPORT
// ================================================================

// Create a single global instance
const storageManager = new StorageManager();
