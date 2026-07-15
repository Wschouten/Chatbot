/**
 * Chat Log Portal - Data Layer
 *
 * Conversations and label definitions are held IN MEMORY only — the backend
 * (SQLite metadata + chat-log files) is the single source of truth, and
 * syncFromApi()/syncLabelDefinitions() refetch everything on load. Keeping them
 * out of localStorage kills three bugs for free: quota exhaustion, stale caches,
 * and customer conversations left readable after logout.
 *
 * Only two small things persist in localStorage:
 *   portal_auth     - UI hint {authenticated, user:{username}, loginTime}.
 *                     Real auth is the HttpOnly `admin_session` cookie.
 *   portal_settings - user preferences {theme, pageSize, defaultLanguageFilter}.
 */

const KEYS = {
  AUTH: 'portal_auth',
  SETTINGS: 'portal_settings'
};

const DEFAULT_SETTINGS = { theme: 'light', pageSize: 20, defaultLanguageFilter: 'all' };

class StorageManager {
  constructor() {
    // In-memory caches (source of truth is the backend API).
    this._conversations = [];
    this._labels = [];

    // Seed localStorage prefs on first run.
    if (!this._read(KEYS.SETTINGS)) this._write(KEYS.SETTINGS, { ...DEFAULT_SETTINGS });
    if (!this._read(KEYS.AUTH)) this._write(KEYS.AUTH, { authenticated: false, user: null, loginTime: null });
  }

  // ── Low-level localStorage read/write (auth + settings only) ────

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
      console.error(`StorageManager: failed to write ${key}`, e);
      return false;
    }
  }

  // ── Authenticated API helper ────────────────────────────────────

  /**
   * Make an authenticated API call. Auth rides the HttpOnly `admin_session`
   * cookie (credentials: 'include'); no key is ever read from JS. Auto-logout on 401.
   *
   * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
   */
  async _apiCall(method, path, body = null) {
    try {
      const options = {
        method,
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
      };
      if (body !== null) options.body = JSON.stringify(body);

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

  // ── Auth (UI hint; server cookie is the real gate) ──────────────

  getAuth() {
    return this._read(KEYS.AUTH) || { authenticated: false, user: null, loginTime: null };
  }

  setAuth(user) {
    return this._write(KEYS.AUTH, {
      authenticated: true,
      user: { username: user.username },
      loginTime: new Date().toISOString()
    });
  }

  clearAuth() {
    return this._write(KEYS.AUTH, { authenticated: false, user: null, loginTime: null });
  }

  /**
   * Log in against the backend; it sets an HttpOnly session cookie.
   * @returns {Promise<{ok: boolean, user?: object, error?: string}>}
   */
  async login(username, password) {
    try {
      const resp = await fetch('/admin/api/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (!resp.ok) return { ok: false, error: `Login failed (${resp.status})` };
      const data = await resp.json();
      return { ok: true, user: data.user };
    } catch (e) {
      console.error('StorageManager: login failed', e);
      return { ok: false, error: e.message };
    }
  }

  /** Ask the backend to clear the session cookie. Safe if no session exists. */
  async logoutServer() {
    try {
      await fetch('/admin/api/logout', { method: 'POST', credentials: 'include' });
    } catch (e) {
      console.warn('StorageManager: logout request failed', e);
    }
  }

  /** Does the browser already hold a valid session cookie? */
  async hasValidSession() {
    try {
      const resp = await fetch('/admin/api/session', { method: 'GET', credentials: 'include' });
      return resp.ok;
    } catch (e) {
      return false;
    }
  }

  // ── API Sync ────────────────────────────────────────────────────

  /**
   * Transform an API conversation (from /admin/api/conversations) to portal format.
   * Metadata (language/status/labels/rating/notes/messageMetadata) comes from the
   * API response; language falls back to 'nl' (Dutch company) when absent.
   */
  _transformApiConversation(apiConv) {
    const messages = [];
    let msgIdx = 0;

    for (const entry of (apiConv.messages || [])) {
      if (entry.user) {
        messages.push({ id: `msg_${msgIdx++}`, timestamp: entry.timestamp || '', requestId: null, role: 'user', content: entry.user, labels: [], rating: null });
      }
      if (entry.bot) {
        messages.push({ id: `msg_${msgIdx++}`, timestamp: entry.timestamp || '', requestId: null, role: 'bot', content: entry.bot, labels: [], rating: null });
      }
    }

    const meta = apiConv.metadata || {};

    // Overlay message-level metadata from DB onto messages.
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
      language: meta.language || 'nl',
      messageCount: messages.length,
      status: meta.status || 'open',
      labels: meta.labels || [],
      rating: meta.rating != null ? meta.rating : null,
      notes: (meta.notes || []).map(n => ({ id: n.id, text: n.text, author: n.author, createdAt: n.created_at })),
      messages
    };
  }

  /**
   * Fetch all conversations from the backend into the in-memory cache.
   * @returns {Promise<{ synced: number, errors: string[] }>}
   */
  async syncFromApi() {
    try {
      const result = await this._apiCall('GET', '/admin/api/conversations');
      if (!result.ok) return { synced: 0, errors: [result.error] };

      const conversations = (result.data.conversations || []).map(c => this._transformApiConversation(c));
      conversations.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));

      this._conversations = conversations;
      return { synced: conversations.length, errors: [] };
    } catch (e) {
      console.error('StorageManager: syncFromApi failed', e);
      return { synced: 0, errors: [e.message] };
    }
  }

  /**
   * Refresh a single conversation from the backend (after a mutation).
   * @returns {Promise<boolean>}
   */
  async _refreshConversation(sessionId) {
    try {
      const result = await this._apiCall('GET', `/admin/api/conversations/${sessionId}`);
      if (!result.ok) {
        console.warn('Failed to refresh conversation:', result.error);
        return false;
      }
      const transformed = this._transformApiConversation(result.data);
      const idx = this._conversations.findIndex(c => c.id === sessionId);
      if (idx !== -1) {
        this._conversations[idx] = transformed;
      } else {
        this._conversations.unshift(transformed);
      }
      return true;
    } catch (e) {
      console.error('StorageManager: _refreshConversation failed', e);
      return false;
    }
  }

  // ── Conversations (Read) ────────────────────────────────────────

  /**
   * Get conversations, newest first, with optional filtering and pagination.
   *
   * @param {Object} filters
   * @param {string}  [filters.status]   - status filter
   * @param {string}  [filters.language] - "nl" | "en"
   * @param {string}  [filters.search]   - full-text query (messages/labels/notes)
   * @param {number}  [filters.page]     - 1-based page
   * @param {number}  [filters.pageSize] - items per page
   */
  getConversations(filters = {}) {
    let convs = this._conversations.slice();

    if (filters.status) convs = convs.filter(c => c.status === filters.status);
    if (filters.language) convs = convs.filter(c => c.language === filters.language);
    if (filters.search) {
      const q = filters.search.toLowerCase();
      convs = convs.filter(c =>
        c.messages.some(m => m.content.toLowerCase().includes(q)) ||
        c.labels.some(l => l.toLowerCase().includes(q)) ||
        (c.notes && c.notes.some(n => n.text.toLowerCase().includes(q)))
      );
    }

    convs.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));

    const total = convs.length;
    const pageSize = filters.pageSize || this.getSettings().pageSize || 20;
    const page = filters.page || 1;
    const totalPages = Math.ceil(total / pageSize);
    const start = (page - 1) * pageSize;
    const paged = convs.slice(start, start + pageSize);

    return { conversations: paged, total, page, pageSize, totalPages };
  }

  getConversation(id) {
    return this._conversations.find(c => c.id === id) || null;
  }

  // ── Labels ──────────────────────────────────────────────────────

  /** Add a label to a conversation (messageId null) or a message. */
  async addLabel(conversationId, messageId, label) {
    const path = messageId
      ? `/admin/api/conversations/${conversationId}/messages/${messageId}/labels`
      : `/admin/api/conversations/${conversationId}/labels`;
    const result = await this._apiCall('POST', path, { label_name: label });
    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  /** Remove a label from a conversation (messageId null) or a message. */
  async removeLabel(conversationId, messageId, label) {
    const path = messageId
      ? `/admin/api/conversations/${conversationId}/messages/${messageId}/labels/${encodeURIComponent(label)}`
      : `/admin/api/conversations/${conversationId}/labels/${encodeURIComponent(label)}`;
    const result = await this._apiCall('DELETE', path);
    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  getLabelDefinitions() {
    return this._labels;
  }

  /** Fetch label definitions from the backend into the in-memory cache. */
  async syncLabelDefinitions() {
    const result = await this._apiCall('GET', '/admin/api/labels');
    if (!result.ok) throw new Error(result.error);
    this._labels = result.data;
    return result.data;
  }

  // ── Ratings ─────────────────────────────────────────────────────

  /** Set a 1-5 rating (or null to clear) on a conversation or message. */
  async setRating(conversationId, messageId, rating) {
    if (rating !== null && (rating < 1 || rating > 5)) {
      throw new Error('Rating must be 1-5 or null');
    }
    const path = messageId
      ? `/admin/api/conversations/${conversationId}/messages/${messageId}/rating`
      : `/admin/api/conversations/${conversationId}/metadata`;
    const result = await this._apiCall('PUT', path, { rating });
    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  // ── Notes ───────────────────────────────────────────────────────

  async addNote(conversationId, text) {
    const auth = this.getAuth();
    const author = auth.user ? auth.user.username : 'admin';
    const result = await this._apiCall('POST', `/admin/api/conversations/${conversationId}/notes`, { text, author });
    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return { id: result.data.note_id, text, author, createdAt: new Date().toISOString() };
  }

  async deleteNote(conversationId, noteId) {
    const result = await this._apiCall('DELETE', `/admin/api/conversations/${conversationId}/notes/${noteId}`);
    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  // ── Status ──────────────────────────────────────────────────────

  async setStatus(conversationId, status) {
    const valid = ['resolved', 'escalated', 'unknown_flagged', 'open'];
    if (!valid.includes(status)) throw new Error('Invalid status: ' + status);
    const result = await this._apiCall('PUT', `/admin/api/conversations/${conversationId}/metadata`, { status });
    if (!result.ok) throw new Error(result.error);
    await this._refreshConversation(conversationId);
    return true;
  }

  // ── Dashboard Stats ─────────────────────────────────────────────

  /** Compute the dashboard statistics actually shown in the UI. */
  getStats() {
    const convs = this._conversations;
    const total = convs.length;

    if (total === 0) {
      return {
        total: 0, byStatus: {}, avgMessagesPerConv: 0, avgRating: null,
        ratedCount: 0, unratedCount: 0, escalationRate: 0, unknownRate: 0,
        conversationsToday: 0, conversationsThisWeek: 0
      };
    }

    const byStatus = {};
    convs.forEach(c => { byStatus[c.status] = (byStatus[c.status] || 0) + 1; });

    const totalMessages = convs.reduce((sum, c) => sum + c.messageCount, 0);
    const avgMessagesPerConv = Math.round((totalMessages / total) * 10) / 10;

    const rated = convs.filter(c => c.rating !== null && c.rating !== undefined);
    const avgRating = rated.length > 0
      ? Math.round((rated.reduce((sum, c) => sum + c.rating, 0) / rated.length) * 10) / 10
      : null;

    const escalationRate = Math.round(((byStatus.escalated || 0) / total) * 1000) / 10;
    const unknownRate = Math.round(((byStatus.unknown_flagged || 0) / total) * 1000) / 10;

    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const weekStart = new Date(todayStart);
    weekStart.setDate(weekStart.getDate() - 7);

    const conversationsToday = convs.filter(c => new Date(c.startedAt) >= todayStart).length;
    const conversationsThisWeek = convs.filter(c => new Date(c.startedAt) >= weekStart).length;

    return {
      total, byStatus, avgMessagesPerConv, avgRating,
      ratedCount: rated.length, unratedCount: total - rated.length,
      escalationRate, unknownRate, conversationsToday, conversationsThisWeek
    };
  }

  // ── Search (search view: returns snippets) ──────────────────────

  /**
   * Full-text search across conversations, returning matching snippets.
   * @returns {Array<{ conversation: Object, matches: Array<{ messageId, role, snippet }> }>}
   */
  search(query) {
    if (!query || query.trim().length === 0) return [];

    const q = query.toLowerCase().trim();
    const results = [];

    for (const conv of this._conversations) {
      const matches = [];

      for (const msg of conv.messages) {
        const idx = msg.content.toLowerCase().indexOf(q);
        if (idx !== -1) {
          const start = Math.max(0, idx - 40);
          const end = Math.min(msg.content.length, idx + q.length + 40);
          let snippet = '';
          if (start > 0) snippet += '...';
          snippet += msg.content.substring(start, end);
          if (end < msg.content.length) snippet += '...';
          matches.push({ messageId: msg.id, role: msg.role, snippet });
        }
      }

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
            id: conv.id, startedAt: conv.startedAt, language: conv.language,
            status: conv.status, messageCount: conv.messageCount, labels: conv.labels
          },
          matches
        });
      }
    }

    return results;
  }

  // ── Export ──────────────────────────────────────────────────────

  /** Export conversations by id (empty = all) as JSON or CSV. */
  exportConversations(ids = [], format = 'json') {
    let convs = this._conversations;
    if (ids.length > 0) convs = convs.filter(c => ids.includes(c.id));
    return format === 'csv' ? this._toCSV(convs) : JSON.stringify(convs, null, 2);
  }

  _toCSV(conversations) {
    const MAX_EXPORT_ROWS = 5000;
    if (conversations.length > MAX_EXPORT_ROWS) {
      console.warn(`CSV export limited to ${MAX_EXPORT_ROWS} rows (${conversations.length} total)`);
      conversations = conversations.slice(0, MAX_EXPORT_ROWS);
    }
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

  /** Trigger a browser download of exported data. */
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

  // ── Settings (localStorage) ─────────────────────────────────────

  getSettings() {
    return this._read(KEYS.SETTINGS) || { ...DEFAULT_SETTINGS };
  }

  updateSettings(partial) {
    return this._write(KEYS.SETTINGS, { ...this.getSettings(), ...partial });
  }

  /** Drop the in-memory caches (the reset button then re-syncs from the backend). */
  resetAll() {
    this._conversations = [];
    this._labels = [];
    this._write(KEYS.SETTINGS, { ...DEFAULT_SETTINGS });
  }
}


// Single global instance.
const storageManager = new StorageManager();
