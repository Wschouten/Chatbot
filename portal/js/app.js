/**
 * Chat Log Portal - Application Controller
 *
 * Connects the StorageManager data layer (storage.js) to the portal DOM.
 * Manages views, authentication, filtering, conversation detail, export,
 * search, settings, and toast notifications.
 *
 * Depends on: storageManager (global, from storage.js)
 */

/* ================================================================
   SECTION 1 - UTILITY FUNCTIONS
   ================================================================ */

/**
 * Escape a string for safe insertion via innerHTML.
 * Prefer textContent where possible; this is for mixed trusted markup.
 *
 * @param {string} str - Raw user-supplied or data string.
 * @returns {string} HTML-entity-escaped string.
 */
function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

/**
 * Format an ISO date string to a human-readable date.
 * Example: "2 Feb 2025"
 *
 * @param {string} isoString
 * @returns {string}
 */
function formatDate(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  });
}

/**
 * Format an ISO date string to a time string.
 * Example: "14:32"
 *
 * @param {string} isoString
 * @returns {string}
 */
function formatTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Format an ISO date string to a readable date+time.
 * Example: "2 Feb 2025, 14:32"
 *
 * @param {string} isoString
 * @returns {string}
 */
function formatDateTime(isoString) {
  if (!isoString) return '';
  return formatDate(isoString) + ', ' + formatTime(isoString);
}

/**
 * Produce a relative time description.
 * Examples: "just now", "3 minutes ago", "2 hours ago", "yesterday", "5 days ago"
 *
 * @param {string} isoString
 * @returns {string}
 */
function timeAgo(isoString) {
  if (!isoString) return '';
  const now = Date.now();
  const then = new Date(isoString).getTime();
  if (isNaN(then)) return '';

  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return minutes === 1 ? '1 minute ago' : minutes + ' minutes ago';

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? '1 hour ago' : hours + ' hours ago';

  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 30) return days + ' days ago';

  const months = Math.floor(days / 30);
  if (months === 1) return '1 month ago';
  if (months < 12) return months + ' months ago';

  const years = Math.floor(months / 12);
  return years === 1 ? '1 year ago' : years + ' years ago';
}

/**
 * Return a CSS badge class for a conversation status.
 *
 * @param {string} status
 * @returns {string}
 */
function statusBadgeClass(status) {
  switch (status) {
    case 'resolved':       return 'badge-success';
    case 'escalated':      return 'badge-danger';
    case 'unknown_flagged': return 'badge-warning';
    case 'open':           return 'badge-info';
    default:               return 'badge-muted';
  }
}

/**
 * Return a human-readable label for a conversation status.
 *
 * @param {string} status
 * @returns {string}
 */
function statusLabel(status) {
  switch (status) {
    case 'resolved':       return 'Resolved';
    case 'escalated':      return 'Escalated';
    case 'unknown_flagged': return 'Unknown / Flagged';
    case 'open':           return 'Open';
    default:               return status || 'Unknown';
  }
}

/**
 * Return a status indicator CSS class for the conversation list dot.
 *
 * @param {string} status
 * @returns {string}
 */
function statusIndicatorClass(status) {
  switch (status) {
    case 'resolved':       return 'status-active';
    case 'escalated':      return 'status-closed';
    case 'unknown_flagged': return 'status-flagged';
    case 'open':           return 'status-active';
    default:               return '';
  }
}

/**
 * Create a debounced version of a function.
 *
 * @param {Function} fn
 * @param {number} ms - Delay in milliseconds.
 * @returns {Function}
 */
function debounce(fn, ms) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}

/**
 * Format a number with locale-appropriate thousands separators.
 *
 * @param {number} n
 * @returns {string}
 */
function formatNumber(n) {
  if (n === null || n === undefined) return '-';
  return Number(n).toLocaleString('en-US');
}


/* ================================================================
   SECTION 2 - PORTAL APP CLASS
   ================================================================ */

class PortalApp {

  constructor() {
    // --- State ---
    this.currentView = 'dashboard';
    this.currentFilters = {};
    this.currentConversationId = null;
    this.currentPage = 1;
    this._toastCounter = 0;

    // Label definitions cache (refreshed when needed)
    this._labelDefs = [];
  }

  /* ────────────────────────────────────────────────────────────────
     2.1  INITIALISATION
     ──────────────────────────────────────────────────────────────── */

  /**
   * Boot the portal: apply theme, check auth, bind all event listeners.
   * Called once from the HTML page after DOM is ready.
   */
  init() {
    this._applyTheme();
    this._refreshLabelDefs();

    const auth = storageManager.getAuth();
    if (auth.authenticated) {
      this._showPortal(auth.user);
    } else {
      this._showLogin();
    }

    this._bindGlobalEvents();
  }

  /**
   * Apply the saved (or system-detected) theme.
   */
  _applyTheme() {
    const settings = storageManager.getSettings();
    let theme = settings.theme;

    // If no saved preference, detect system preference
    if (!theme || theme === 'system') {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      theme = prefersDark ? 'dark' : 'light';
    }

    document.documentElement.setAttribute('data-theme', theme);
    this._updateDarkModeIcon(theme);
  }

  /**
   * Refresh the cached label definitions from storage.
   */
  _refreshLabelDefs() {
    this._labelDefs = storageManager.getLabelDefinitions();
  }

  /* ────────────────────────────────────────────────────────────────
     2.2  AUTH / LOGIN
     ──────────────────────────────────────────────────────────────── */

  /**
   * Show the login overlay and hide the portal.
   */
  _showLogin() {
    const overlay = document.getElementById('loginOverlay');
    const layout = document.getElementById('portalLayout');
    if (overlay) overlay.style.display = '';
    if (layout) layout.style.display = 'none';

    // Clear any previous error
    this._setLoginError('');

    // Clear fields
    const usernameInput = document.getElementById('loginUsername');
    const passwordInput = document.getElementById('loginPassword');
    if (usernameInput) usernameInput.value = '';
    if (passwordInput) passwordInput.value = '';
    if (usernameInput) usernameInput.focus();
  }

  /**
   * Show the portal and hide the login overlay.
   *
   * @param {{ username: string, role: string }} user
   */
  _showPortal(user) {
    const overlay = document.getElementById('loginOverlay');
    const layout = document.getElementById('portalLayout');
    if (overlay) overlay.style.display = 'none';
    if (layout) layout.style.display = '';

    // Populate header user info
    const avatarEl = document.getElementById('userAvatar');
    const nameEl = document.getElementById('userName');
    if (avatarEl) {
      avatarEl.textContent = (user.username || '?').charAt(0).toUpperCase();
    }
    if (nameEl) {
      nameEl.textContent = user.username || '';
    }

    // Apply default language filter from settings
    const settings = storageManager.getSettings();
    if (settings.defaultLanguageFilter && settings.defaultLanguageFilter !== 'all') {
      this.currentFilters.language = settings.defaultLanguageFilter;
    }

    // Navigate to default view
    this.navigateTo('dashboard');
  }

  /**
   * Handle login form submission.
   * Demo credentials: admin/admin, viewer/viewer, trainer/trainer.
   */
  handleLogin() {
    const usernameInput = document.getElementById('loginUsername');
    const passwordInput = document.getElementById('loginPassword');
    const username = (usernameInput ? usernameInput.value : '').trim();
    const password = passwordInput ? passwordInput.value : '';

    if (!username || !password) {
      this._setLoginError('Please enter both username and password.');
      return;
    }

    // Demo credential map
    const validUsers = {
      admin:   { password: 'admin',   role: 'admin' },
      viewer:  { password: 'viewer',  role: 'viewer' },
      trainer: { password: 'trainer', role: 'trainer' }
    };

    const entry = validUsers[username.toLowerCase()];
    if (!entry || entry.password !== password) {
      this._setLoginError('Invalid username or password.');
      return;
    }

    const user = { username: username.toLowerCase(), role: entry.role };
    storageManager.setAuth(user);
    this._showPortal(user);
    this.showToast('Welcome back, ' + user.username + '!', 'success');
  }

  /**
   * Log out: clear auth state, return to login screen.
   */
  handleLogout() {
    storageManager.clearAuth();
    this.currentView = 'dashboard';
    this.currentFilters = {};
    this.currentConversationId = null;
    this.currentPage = 1;
    this._showLogin();
    this.showToast('Logged out.', 'info');
  }

  /**
   * Display or hide the login error message.
   *
   * @param {string} message - Empty string hides the error.
   */
  _setLoginError(message) {
    const el = document.getElementById('loginError');
    if (!el) return;
    if (message) {
      el.textContent = message;
      el.classList.add('visible');
    } else {
      el.textContent = '';
      el.classList.remove('visible');
    }
  }

  /* ────────────────────────────────────────────────────────────────
     2.3  NAVIGATION
     ──────────────────────────────────────────────────────────────── */

  /**
   * Switch the active portal view.
   *
   * @param {string} view - One of: dashboard, conversations, search, export, settings.
   */
  navigateTo(view) {
    const validViews = ['dashboard', 'conversations', 'search', 'export', 'settings'];
    if (!validViews.includes(view)) return;

    this.currentView = view;

    // Update sidebar highlighting
    document.querySelectorAll('.sidebar-nav-item[data-view]').forEach(item => {
      if (item.getAttribute('data-view') === view) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Show/hide view panels
    document.querySelectorAll('.portal-view').forEach(panel => {
      if (panel.id === 'view-' + view) {
        panel.classList.add('active');
      } else {
        panel.classList.remove('active');
      }
    });

    // Close mobile sidebar if open
    this._closeSidebar();

    // Render the newly-visible view
    switch (view) {
      case 'dashboard':
        this.renderDashboard();
        break;
      case 'conversations':
        this.renderConversationList();
        break;
      case 'search':
        this._focusSearchInput();
        break;
      case 'export':
        this._renderExportConversationList();
        break;
      case 'settings':
        this._renderSettings();
        break;
    }
  }

  /**
   * Toggle the mobile sidebar open/closed.
   */
  _toggleSidebar() {
    const sidebar = document.getElementById('portalSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar) return;

    const isOpen = sidebar.classList.contains('open');
    if (isOpen) {
      this._closeSidebar();
    } else {
      sidebar.classList.add('open');
      if (backdrop) backdrop.classList.add('visible');
    }
  }

  /**
   * Close the mobile sidebar.
   */
  _closeSidebar() {
    const sidebar = document.getElementById('portalSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('visible');
  }

  /* ────────────────────────────────────────────────────────────────
     2.4  DASHBOARD
     ──────────────────────────────────────────────────────────────── */

  /**
   * Populate all dashboard stat cards from storageManager.getStats().
   */
  renderDashboard() {
    const stats = storageManager.getStats();

    this._setText('statTotal', formatNumber(stats.total));
    this._setText('statAvgMessages', stats.avgMessagesPerConv != null ? stats.avgMessagesPerConv.toFixed(1) : '-');
    this._setText('statEscalation', stats.escalationRate != null ? stats.escalationRate + '%' : '-');
    this._setText('statUnknown', stats.unknownRate != null ? stats.unknownRate + '%' : '-');
    this._setText('statAvgRating', stats.avgRating != null ? stats.avgRating.toFixed(1) + ' / 5' : 'N/A');
    this._setText('statThisWeek', formatNumber(stats.conversationsThisWeek));

    // Populate subtitle/extra-info spans where they exist
    const totalSub = document.querySelector('#statTotal + .stat-card-subtitle, [data-stat-sub="total"]');
    if (totalSub) {
      totalSub.textContent = stats.ratedCount + ' rated, ' + stats.unratedCount + ' unrated';
    }

    const escalationSub = document.querySelector('#statEscalation + .stat-card-subtitle, [data-stat-sub="escalation"]');
    if (escalationSub) {
      escalationSub.textContent = (stats.byStatus.escalated || 0) + ' of ' + stats.total + ' conversations';
    }

    const weekSub = document.querySelector('#statThisWeek + .stat-card-subtitle, [data-stat-sub="week"]');
    if (weekSub) {
      weekSub.textContent = stats.conversationsToday + ' today';
    }

    const busiestSub = document.querySelector('[data-stat-sub="busiest"]');
    if (busiestSub && stats.busiestHour !== null) {
      const hourLabel = stats.busiestHour.toString().padStart(2, '0') + ':00';
      busiestSub.textContent = 'Busiest hour: ' + hourLabel;
    }

    // Language distribution in subtitle
    const langSub = document.querySelector('[data-stat-sub="language"]');
    if (langSub && stats.byLanguage) {
      const parts = Object.entries(stats.byLanguage)
        .map(([lang, count]) => lang.toUpperCase() + ': ' + count)
        .join(', ');
      langSub.textContent = parts;
    }

    // Label distribution summary (top 5 labels) in a dashboard element if present
    const labelSummary = document.querySelector('[data-stat-sub="labels"]');
    if (labelSummary && stats.labelCounts) {
      const sorted = Object.entries(stats.labelCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
      if (sorted.length > 0) {
        labelSummary.textContent = 'Top: ' + sorted.map(([name, count]) => name + ' (' + count + ')').join(', ');
      } else {
        labelSummary.textContent = 'No labels applied';
      }
    }

    // Notes count
    const notesSub = document.querySelector('[data-stat-sub="notes"]');
    if (notesSub) {
      notesSub.textContent = stats.notesCount + ' notes across all conversations';
    }
  }

  /* ────────────────────────────────────────────────────────────────
     2.5  CONVERSATION LIST
     ──────────────────────────────────────────────────────────────── */

  /**
   * Render the filtered, paginated conversation list.
   */
  renderConversationList() {
    const filters = Object.assign({}, this.currentFilters, {
      page: this.currentPage,
      pageSize: storageManager.getSettings().pageSize || 20
    });

    const result = storageManager.getConversations(filters);
    const listEl = document.getElementById('conversationList');
    if (!listEl) return;

    // Build HTML
    if (result.conversations.length === 0) {
      listEl.innerHTML =
        '<div class="empty-state">' +
          '<div class="empty-state-icon">&#128172;</div>' +
          '<div class="empty-state-title">No conversations found</div>' +
          '<div class="empty-state-text">Try adjusting your filters or search query.</div>' +
        '</div>';
    } else {
      let html = '';
      for (const conv of result.conversations) {
        const firstUserMsg = conv.messages.find(m => m.role === 'user');
        const preview = firstUserMsg ? escapeHtml(firstUserMsg.content) : 'No user message';
        const isActive = conv.id === this.currentConversationId;
        const langBadge = conv.language === 'nl' ? 'NL' : 'EN';

        // Truncate preview for the list
        const truncated = preview.length > 80 ? preview.substring(0, 80) + '...' : preview;

        // Label chips (max 3 visible in list)
        let labelChips = '';
        const displayLabels = conv.labels.slice(0, 3);
        for (const label of displayLabels) {
          const def = this._getLabelDef(label);
          const bgColor = def ? def.color + '22' : '#6B728022';
          const textColor = def ? def.color : '#6B7280';
          labelChips +=
            '<span class="badge" style="background-color:' + escapeHtml(bgColor) +
            ';color:' + escapeHtml(textColor) +
            ';font-size:10px;padding:1px 6px;border-radius:8px;">' +
            escapeHtml(label) + '</span>';
        }
        if (conv.labels.length > 3) {
          labelChips += '<span class="badge badge-muted" style="font-size:10px;padding:1px 6px;">+' +
            (conv.labels.length - 3) + '</span>';
        }

        html +=
          '<div class="conversation-item' + (isActive ? ' active' : '') +
          '" data-id="' + escapeHtml(conv.id) + '">' +
            '<div class="conversation-item-header">' +
              '<span class="conversation-item-id">' + escapeHtml(conv.id.substring(0, 13)) + '</span>' +
              '<span class="conversation-item-date">' + escapeHtml(timeAgo(conv.startedAt)) + '</span>' +
            '</div>' +
            '<div class="conversation-item-preview">' + truncated + '</div>' +
            '<div class="conversation-item-footer">' +
              '<div class="conversation-item-meta">' +
                '<span class="status-indicator ' + statusIndicatorClass(conv.status) + '"></span>' +
                '<span class="badge ' + statusBadgeClass(conv.status) + '">' + escapeHtml(statusLabel(conv.status)) + '</span>' +
                '<span class="badge badge-muted">' + escapeHtml(langBadge) + '</span>' +
                '<span class="message-count-badge">&#128172; ' + conv.messageCount + '</span>' +
              '</div>' +
              '<div style="display:flex;gap:4px;flex-wrap:wrap;">' + labelChips + '</div>' +
            '</div>' +
          '</div>';
      }
      listEl.innerHTML = html;
    }

    // Pagination info
    this._setText('paginationInfo', 'Page ' + result.page + ' of ' + result.totalPages + ' (' + result.total + ' total)');

    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    if (prevBtn) prevBtn.disabled = result.page <= 1;
    if (nextBtn) nextBtn.disabled = result.page >= result.totalPages;

    // Update active filter chips
    this._updateFilterChips();

    // Update filter chip counts
    this._updateFilterCounts();
  }

  /**
   * Select a conversation from the list and render its detail panel.
   *
   * @param {string} id
   */
  selectConversation(id) {
    this.currentConversationId = id;

    // Highlight active list item
    document.querySelectorAll('.conversation-item').forEach(item => {
      if (item.getAttribute('data-id') === id) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    this.renderConversationDetail(id);
  }

  /* ────────────────────────────────────────────────────────────────
     2.6  FILTERS & PAGINATION
     ──────────────────────────────────────────────────────────────── */

  /**
   * Toggle a filter chip on or off.
   *
   * @param {string} filterType - e.g. "status", "language"
   * @param {string} filterValue - e.g. "resolved", "nl"
   */
  _toggleFilter(filterType, filterValue) {
    if (this.currentFilters[filterType] === filterValue) {
      // Deactivate: remove filter
      delete this.currentFilters[filterType];
    } else {
      this.currentFilters[filterType] = filterValue;
    }
    this.currentPage = 1;
    this.renderConversationList();
  }

  /**
   * Update filter chip visual state to reflect currentFilters.
   */
  _updateFilterChips() {
    document.querySelectorAll('.filter-chip[data-filter]').forEach(chip => {
      const rawFilter = chip.getAttribute('data-filter');
      // Expected format: "status:resolved" or "language:nl"
      const parts = rawFilter.split(':');
      if (parts.length !== 2) return;

      const [type, value] = parts;
      if (value === 'all') {
        // "All" chip is active when no filter of that type is set
        if (!this.currentFilters[type]) {
          chip.classList.add('active');
        } else {
          chip.classList.remove('active');
        }
      } else if (this.currentFilters[type] === value) {
        chip.classList.add('active');
      } else {
        chip.classList.remove('active');
      }
    });
  }

  /**
   * Update filter chip count badges with actual totals.
   */
  _updateFilterCounts() {
    const stats = storageManager.getStats();
    this._setText('filterAllCount', stats.total);
    this._setText('filterResolvedCount', stats.byStatus.resolved || 0);
    this._setText('filterEscalatedCount', stats.byStatus.escalated || 0);
    this._setText('filterUnknownCount', stats.byStatus.unknown_flagged || 0);
    this._setText('filterOpenCount', stats.byStatus.open || 0);
  }

  /**
   * Handle conversation search input (debounced).
   *
   * @param {string} query
   */
  _handleConversationSearch(query) {
    if (query.trim()) {
      this.currentFilters.search = query.trim();
    } else {
      delete this.currentFilters.search;
    }
    this.currentPage = 1;
    this.renderConversationList();
  }

  /**
   * Navigate to the previous page.
   */
  prevPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
      this.renderConversationList();
    }
  }

  /**
   * Navigate to the next page.
   */
  nextPage() {
    this.currentPage++;
    this.renderConversationList();
  }

  /* ────────────────────────────────────────────────────────────────
     2.7  CONVERSATION DETAIL
     ──────────────────────────────────────────────────────────────── */

  /**
   * Render the full conversation detail panel for a given conversation ID.
   *
   * @param {string} id
   */
  renderConversationDetail(id) {
    const conv = storageManager.getConversation(id);
    const detailPanel = document.getElementById('conversationDetail');
    const emptyState = document.getElementById('detailEmpty');
    if (!detailPanel) return;

    const parentPanel = document.getElementById('conversationDetailPanel');

    if (!conv) {
      if (emptyState) emptyState.style.display = '';
      detailPanel.style.display = 'none';
      if (parentPanel) parentPanel.classList.add('empty');
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    detailPanel.style.display = 'flex';
    if (parentPanel) parentPanel.classList.remove('empty');

    // Header
    this._setText('detailTitle', conv.id);
    this._setText('detailSubtitle', formatDateTime(conv.startedAt) + '  |  ' + conv.messageCount + ' messages  |  ' + conv.language.toUpperCase());

    // Status select
    const statusSelect = document.getElementById('detailStatusSelect');
    if (statusSelect) statusSelect.value = conv.status;

    // Status badge
    const statusBadge = document.getElementById('detailStatusBadge');
    if (statusBadge) {
      statusBadge.className = 'badge ' + statusBadgeClass(conv.status);
      statusBadge.textContent = statusLabel(conv.status);
    }

    // Message thread
    this._renderMessageThread(conv);

    // Labels
    this._renderLabels(conv);

    // Rating
    this._renderRating(conv);

    // Notes
    this._renderNotes(conv);
  }

  /**
   * Render the message bubbles for a conversation.
   *
   * @param {Object} conv - Full conversation object.
   */
  _renderMessageThread(conv) {
    const container = document.getElementById('messageThread');
    if (!container) return;

    let html = '';
    for (const msg of conv.messages) {
      const bubbleClass = msg.role === 'user' ? 'message-user' : 'message-bot';
      const roleLabel = msg.role === 'user' ? 'Customer' : 'Bot';

      // Build metadata section
      let metaHtml =
        '<div class="metadata-row"><span class="metadata-key">Message ID</span><span>' + escapeHtml(msg.id) + '</span></div>' +
        '<div class="metadata-row"><span class="metadata-key">Role</span><span>' + escapeHtml(roleLabel) + '</span></div>' +
        '<div class="metadata-row"><span class="metadata-key">Timestamp</span><span>' + escapeHtml(formatDateTime(msg.timestamp)) + '</span></div>';

      if (msg.requestId) {
        metaHtml += '<div class="metadata-row"><span class="metadata-key">Request ID</span><span>' + escapeHtml(msg.requestId) + '</span></div>';
      }

      if (msg.labels && msg.labels.length > 0) {
        metaHtml += '<div class="metadata-row"><span class="metadata-key">Labels</span><span>' + escapeHtml(msg.labels.join(', ')) + '</span></div>';
      }

      if (msg.rating !== null && msg.rating !== undefined) {
        metaHtml += '<div class="metadata-row"><span class="metadata-key">Rating</span><span>' + msg.rating + ' / 5</span></div>';
      }

      html +=
        '<div class="message-bubble ' + bubbleClass + '" data-message-id="' + escapeHtml(msg.id) + '">' +
          '<div class="message-content"></div>' +
          '<span class="message-timestamp">' + escapeHtml(formatTime(msg.timestamp)) + '</span>' +
          '<span class="message-metadata-toggle" data-msg-id="' + escapeHtml(msg.id) + '">details &#9662;</span>' +
          '<div class="message-metadata" id="meta-' + escapeHtml(msg.id) + '">' + metaHtml + '</div>' +
        '</div>';
    }

    container.innerHTML = html;

    // Set message content via textContent to prevent XSS
    container.querySelectorAll('.message-bubble').forEach((bubble, index) => {
      const contentEl = bubble.querySelector('.message-content');
      if (contentEl && conv.messages[index]) {
        contentEl.textContent = conv.messages[index].content;
      }
    });

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
  }

  /**
   * Toggle visibility of message metadata.
   *
   * @param {string} msgId
   */
  _toggleMessageMetadata(msgId) {
    const metaEl = document.getElementById('meta-' + msgId);
    if (!metaEl) return;
    metaEl.classList.toggle('expanded');

    // Update toggle text
    const toggle = document.querySelector('[data-msg-id="' + msgId + '"]');
    if (toggle) {
      const isExpanded = metaEl.classList.contains('expanded');
      toggle.innerHTML = isExpanded ? 'details &#9652;' : 'details &#9662;';
    }
  }

  /**
   * Render the labels section for a conversation.
   *
   * @param {Object} conv
   */
  _renderLabels(conv) {
    const container = document.getElementById('labelsContainer');
    if (!container) return;

    let html = '';
    for (const label of conv.labels) {
      const def = this._getLabelDef(label);
      const bgColor = def ? def.color + '22' : '#6B728022';
      const textColor = def ? def.color : '#6B7280';

      html +=
        '<span class="label-chip" style="background-color:' + escapeHtml(bgColor) +
        ';color:' + escapeHtml(textColor) + ';">' +
          escapeHtml(label) +
          '<span class="label-remove" data-conv-id="' + escapeHtml(conv.id) +
          '" data-label="' + escapeHtml(label) + '">&times;</span>' +
        '</span>';
    }

    container.innerHTML = html;

    // Build the "add label" dropdown menu
    this._renderAddLabelMenu(conv);
  }

  /**
   * Populate the add-label dropdown with labels not yet applied to the conversation.
   *
   * @param {Object} conv
   */
  _renderAddLabelMenu(conv) {
    const menu = document.getElementById('addLabelMenu');
    if (!menu) return;

    this._refreshLabelDefs();
    const available = this._labelDefs.filter(def => !conv.labels.includes(def.name));

    if (available.length === 0) {
      menu.innerHTML = '<div style="padding:10px 14px;font-size:12px;color:var(--portal-text-muted);">All labels applied</div>';
      return;
    }

    let html = '';
    for (const def of available) {
      html +=
        '<button class="add-label-menu-item" data-label="' + escapeHtml(def.name) + '">' +
          '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:' +
          escapeHtml(def.color) + ';margin-right:8px;"></span>' +
          escapeHtml(def.name) +
        '</button>';
    }
    menu.innerHTML = html;
  }

  /**
   * Add a label to the current conversation.
   *
   * @param {string} label
   */
  _addLabelToConversation(label) {
    if (!this.currentConversationId) return;
    const success = storageManager.addLabel(this.currentConversationId, null, label);
    if (success) {
      this.showToast('Label "' + label + '" added.', 'success');
      this.renderConversationDetail(this.currentConversationId);
      this.renderConversationList();
    } else {
      this.showToast('Failed to add label.', 'error');
    }
    this._closeAddLabelMenu();
  }

  /**
   * Remove a label from a conversation.
   *
   * @param {string} convId
   * @param {string} label
   */
  _removeLabelFromConversation(convId, label) {
    const success = storageManager.removeLabel(convId, null, label);
    if (success) {
      this.showToast('Label "' + label + '" removed.', 'info');
      this.renderConversationDetail(convId);
      this.renderConversationList();
    } else {
      this.showToast('Failed to remove label.', 'error');
    }
  }

  /**
   * Toggle the add-label dropdown visibility.
   */
  _toggleAddLabelMenu() {
    const menu = document.getElementById('addLabelMenu');
    if (!menu) return;
    menu.classList.toggle('open');
  }

  /**
   * Close the add-label dropdown.
   */
  _closeAddLabelMenu() {
    const menu = document.getElementById('addLabelMenu');
    if (menu) menu.classList.remove('open');
  }

  /**
   * Render the rating thumbs for the current conversation.
   *
   * @param {Object} conv
   */
  _renderRating(conv) {
    const upBtn = document.getElementById('ratingUp');
    const downBtn = document.getElementById('ratingDown');
    if (!upBtn || !downBtn) return;

    // rating 5 = thumbs up, rating 1 = thumbs down, null = neither
    upBtn.classList.remove('active', 'thumbs-up');
    downBtn.classList.remove('active', 'thumbs-down');

    if (conv.rating !== null && conv.rating !== undefined) {
      if (conv.rating >= 4) {
        upBtn.classList.add('active', 'thumbs-up');
      } else if (conv.rating <= 2) {
        downBtn.classList.add('active', 'thumbs-down');
      }
    }
  }

  /**
   * Handle a rating button click.
   *
   * @param {'up' | 'down'} direction
   */
  _handleRating(direction) {
    if (!this.currentConversationId) return;

    const conv = storageManager.getConversation(this.currentConversationId);
    if (!conv) return;

    let newRating;
    if (direction === 'up') {
      newRating = (conv.rating === 5) ? null : 5;
    } else {
      newRating = (conv.rating === 1) ? null : 1;
    }

    const success = storageManager.setRating(this.currentConversationId, null, newRating);
    if (success) {
      this.showToast(newRating !== null ? 'Rating updated.' : 'Rating cleared.', 'success');
      this.renderConversationDetail(this.currentConversationId);
    }
  }

  /**
   * Render the notes section for a conversation.
   *
   * @param {Object} conv
   */
  _renderNotes(conv) {
    const notesList = document.getElementById('notesList');
    if (!notesList) return;

    if (!conv.notes || conv.notes.length === 0) {
      notesList.innerHTML = '<div class="text-muted" style="font-size:12px;padding:4px 0;">No notes yet.</div>';
      return;
    }

    let html = '';
    for (const note of conv.notes) {
      html +=
        '<div class="note-item" style="padding:8px 12px;background-color:var(--portal-bg);border-radius:var(--portal-radius);margin-bottom:6px;">' +
          '<div class="note-content" style="font-size:13px;line-height:1.5;margin-bottom:4px;"></div>' +
          '<div style="display:flex;align-items:center;justify-content:space-between;">' +
            '<span style="font-size:11px;color:var(--portal-text-muted);">' +
              escapeHtml(note.author) + ' &middot; ' + escapeHtml(timeAgo(note.createdAt)) +
            '</span>' +
            '<button class="btn btn-ghost btn-sm note-delete-btn" data-note-id="' +
            escapeHtml(note.id) + '" data-conv-id="' + escapeHtml(conv.id) + '">&times;</button>' +
          '</div>' +
        '</div>';
    }

    notesList.innerHTML = html;

    // Set note content via textContent
    const noteItems = notesList.querySelectorAll('.note-item');
    noteItems.forEach((item, index) => {
      const contentEl = item.querySelector('.note-content');
      if (contentEl && conv.notes[index]) {
        contentEl.textContent = conv.notes[index].text;
      }
    });
  }

  /**
   * Handle adding a new note to the current conversation.
   */
  _handleAddNote() {
    if (!this.currentConversationId) return;

    const textarea = document.getElementById('notesTextarea');
    if (!textarea) return;

    const text = textarea.value.trim();
    if (!text) {
      this.showToast('Note cannot be empty.', 'warning');
      return;
    }

    const note = storageManager.addNote(this.currentConversationId, text);
    if (note) {
      textarea.value = '';
      this.showToast('Note added.', 'success');
      this.renderConversationDetail(this.currentConversationId);
    } else {
      this.showToast('Failed to add note.', 'error');
    }
  }

  /**
   * Delete a note from a conversation.
   *
   * @param {string} convId
   * @param {string} noteId
   */
  _handleDeleteNote(convId, noteId) {
    const success = storageManager.deleteNote(convId, noteId);
    if (success) {
      this.showToast('Note deleted.', 'info');
      this.renderConversationDetail(convId);
    } else {
      this.showToast('Failed to delete note.', 'error');
    }
  }

  /* ────────────────────────────────────────────────────────────────
     2.8  SEARCH VIEW
     ──────────────────────────────────────────────────────────────── */

  /**
   * Perform a global search and display results.
   *
   * @param {string} query
   */
  handleSearch(query) {
    const container = document.getElementById('searchResults');
    if (!container) return;

    if (!query || !query.trim()) {
      container.innerHTML =
        '<div class="empty-state">' +
          '<div class="empty-state-icon">&#128269;</div>' +
          '<div class="empty-state-title">Search conversations</div>' +
          '<div class="empty-state-text">Enter a search term to find matching messages, notes, and labels.</div>' +
        '</div>';
      return;
    }

    let results = storageManager.search(query.trim());

    // Apply additional search view filters
    const statusFilter = document.getElementById('searchStatusFilter');
    const langFilter = document.getElementById('searchLanguageFilter');
    const dateFrom = document.getElementById('searchDateFrom');
    const dateTo = document.getElementById('searchDateTo');

    if (statusFilter && statusFilter.value) {
      results = results.filter(r => r.conversation.status === statusFilter.value);
    }
    if (langFilter && langFilter.value) {
      results = results.filter(r => r.conversation.language === langFilter.value);
    }
    if (dateFrom && dateFrom.value) {
      const from = new Date(dateFrom.value).getTime();
      results = results.filter(r => new Date(r.conversation.startedAt).getTime() >= from);
    }
    if (dateTo && dateTo.value) {
      const to = new Date(dateTo.value).getTime() + 86400000; // end of day
      results = results.filter(r => new Date(r.conversation.startedAt).getTime() <= to);
    }

    if (results.length === 0) {
      container.innerHTML =
        '<div class="empty-state">' +
          '<div class="empty-state-icon">&#128533;</div>' +
          '<div class="empty-state-title">No results</div>' +
          '<div class="empty-state-text">No conversations match "' + escapeHtml(query.trim()) + '". Try a different term.</div>' +
        '</div>';
      return;
    }

    let html = '<div style="margin-bottom:12px;font-size:13px;color:var(--portal-text-muted);">' +
      results.length + ' conversation' + (results.length !== 1 ? 's' : '') + ' found</div>';

    for (const result of results) {
      const conv = result.conversation;

      html +=
        '<div class="search-result-card" data-id="' + escapeHtml(conv.id) +
        '" style="padding:14px 16px;background-color:var(--portal-surface);border:1px solid var(--portal-border);border-radius:var(--portal-radius-lg);margin-bottom:10px;cursor:pointer;transition:box-shadow 0.2s ease;">' +
          '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">' +
            '<span style="font-weight:600;font-size:13px;">' + escapeHtml(conv.id.substring(0, 13)) + '</span>' +
            '<div style="display:flex;gap:6px;">' +
              '<span class="badge ' + statusBadgeClass(conv.status) + '">' + escapeHtml(statusLabel(conv.status)) + '</span>' +
              '<span class="badge badge-muted">' + escapeHtml(conv.language.toUpperCase()) + '</span>' +
            '</div>' +
          '</div>' +
          '<div style="font-size:12px;color:var(--portal-text-muted);margin-bottom:8px;">' +
            escapeHtml(formatDateTime(conv.startedAt)) + ' &middot; ' + conv.messageCount + ' messages' +
          '</div>';

      // Render matching snippets
      for (const match of result.matches) {
        const roleIcon = match.role === 'user' ? '&#128100;' : match.role === 'bot' ? '&#129302;' : '&#128221;';
        html +=
          '<div style="padding:6px 10px;background-color:var(--portal-bg);border-radius:var(--portal-radius);margin-bottom:4px;font-size:12px;line-height:1.5;">' +
            '<span style="margin-right:6px;">' + roleIcon + '</span>' +
            '<span class="search-snippet"></span>' +
          '</div>';
      }

      html += '</div>';
    }

    container.innerHTML = html;

    // Set snippet content via textContent to prevent XSS
    const snippetEls = container.querySelectorAll('.search-snippet');
    let snippetIdx = 0;
    for (const result of results) {
      for (const match of result.matches) {
        if (snippetEls[snippetIdx]) {
          snippetEls[snippetIdx].textContent = match.snippet;
        }
        snippetIdx++;
      }
    }
  }

  /**
   * Focus the global search input.
   */
  _focusSearchInput() {
    const input = document.getElementById('globalSearch');
    if (input) {
      setTimeout(() => input.focus(), 100);
    }
  }

  /* ────────────────────────────────────────────────────────────────
     2.9  EXPORT VIEW
     ──────────────────────────────────────────────────────────────── */

  /**
   * Render the export view's conversation selector list.
   */
  _renderExportConversationList() {
    const container = document.getElementById('exportConversationList');
    if (!container) return;

    const result = storageManager.getConversations({ pageSize: 9999 });

    let html =
      '<label class="checkbox-option" style="padding:8px 0;border-bottom:1px solid var(--portal-border);font-weight:600;">' +
        '<input type="checkbox" id="exportSelectAllCb"> Select All (' + result.total + ' conversations)' +
      '</label>';

    for (const conv of result.conversations) {
      const firstUserMsg = conv.messages.find(m => m.role === 'user');
      const preview = firstUserMsg ? firstUserMsg.content.substring(0, 60) : 'No user message';

      html +=
        '<label class="checkbox-option" style="padding:6px 0;">' +
          '<input type="checkbox" class="export-conv-checkbox" value="' + escapeHtml(conv.id) + '">' +
          '<span style="flex:1;">' +
            '<span style="font-weight:500;font-size:12px;">' + escapeHtml(conv.id.substring(0, 13)) + '</span>' +
            '<span style="color:var(--portal-text-muted);font-size:11px;margin-left:8px;" class="export-preview"></span>' +
          '</span>' +
          '<span class="badge ' + statusBadgeClass(conv.status) + '" style="font-size:10px;">' + escapeHtml(statusLabel(conv.status)) + '</span>' +
        '</label>';
    }

    container.innerHTML = html;

    // Set preview text safely
    const previewEls = container.querySelectorAll('.export-preview');
    result.conversations.forEach((conv, idx) => {
      if (previewEls[idx]) {
        const firstUserMsg = conv.messages.find(m => m.role === 'user');
        previewEls[idx].textContent = firstUserMsg ? firstUserMsg.content.substring(0, 60) : 'No user message';
      }
    });

    // Bind select-all checkbox toggle
    const selectAllCb = document.getElementById('exportSelectAllCb');
    if (selectAllCb) {
      selectAllCb.addEventListener('change', () => {
        container.querySelectorAll('.export-conv-checkbox').forEach(cb => {
          cb.checked = selectAllCb.checked;
        });
      });
    }
  }

  /**
   * Handle export button click.
   */
  _handleExport() {
    const formatEl = document.querySelector('input[name="exportFormat"]:checked');
    const format = formatEl ? formatEl.value : 'json';

    const checkboxes = document.querySelectorAll('.export-conv-checkbox:checked');
    const ids = Array.from(checkboxes).map(cb => cb.value);

    if (ids.length === 0) {
      this.showToast('Please select at least one conversation to export.', 'warning');
      return;
    }

    storageManager.downloadExport(ids, format);
    this.showToast('Exported ' + ids.length + ' conversation' + (ids.length !== 1 ? 's' : '') + ' as ' + format.toUpperCase() + '.', 'success');
  }

  /* ────────────────────────────────────────────────────────────────
     2.10  EXPORT MODAL (Quick export from detail)
     ──────────────────────────────────────────────────────────────── */

  /**
   * Show the export modal for the current conversation.
   */
  _showExportModal() {
    const modal = document.getElementById('exportModal');
    if (modal) modal.classList.add('visible');
  }

  /**
   * Hide the export modal.
   */
  _hideExportModal() {
    const modal = document.getElementById('exportModal');
    if (modal) modal.classList.remove('visible');
  }

  /**
   * Handle the modal export confirmation.
   */
  _handleModalExport() {
    if (!this.currentConversationId) return;

    const formatEl = document.querySelector('#exportModal input[name="modalExportFormat"]:checked');
    const format = formatEl ? formatEl.value : 'json';

    storageManager.downloadExport([this.currentConversationId], format);
    this._hideExportModal();
    this.showToast('Conversation exported as ' + format.toUpperCase() + '.', 'success');
  }

  /* ────────────────────────────────────────────────────────────────
     2.11  SETTINGS VIEW
     ──────────────────────────────────────────────────────────────── */

  /**
   * Render settings form with current values.
   */
  _renderSettings() {
    const settings = storageManager.getSettings();

    const themeSelect = document.getElementById('settingTheme');
    const pageSizeInput = document.getElementById('settingPageSize');
    const langSelect = document.getElementById('settingLanguage');

    if (themeSelect) themeSelect.value = settings.theme || 'light';
    if (pageSizeInput) pageSizeInput.value = settings.pageSize || 20;
    if (langSelect) langSelect.value = settings.defaultLanguageFilter || 'all';

    // Storage usage display
    const usage = storageManager.getStorageUsage();
    const usageEl = document.getElementById('storageUsageDisplay') || document.querySelector('[data-setting="storage-usage"]');
    if (usageEl) {
      const percent = ((usage.used / usage.estimatedMax) * 100).toFixed(1);
      usageEl.textContent = usage.usedKB + ' / ~' + (usage.estimatedMax / 1024 / 1024).toFixed(0) + ' MB (' + percent + '%)';
    }
  }

  /**
   * Save a settings change.
   *
   * @param {string} key
   * @param {*} value
   */
  _updateSetting(key, value) {
    const update = {};
    update[key] = value;
    storageManager.updateSettings(update);

    if (key === 'theme') {
      document.documentElement.setAttribute('data-theme', value);
      this._updateDarkModeIcon(value);
      this.showToast('Theme changed to ' + value + '.', 'success');
    } else if (key === 'pageSize') {
      this.showToast('Page size updated to ' + value + '.', 'success');
    } else if (key === 'defaultLanguageFilter') {
      this.showToast('Default language filter updated.', 'success');
    }
  }

  /**
   * Update the dark mode toggle button icon.
   *
   * @param {string} theme
   */
  _updateDarkModeIcon(theme) {
    const btn = document.getElementById('darkModeToggle');
    if (!btn) return;
    // Sun for dark mode (to switch to light), moon for light mode (to switch to dark)
    btn.innerHTML = theme === 'dark' ? '&#9728;' : '&#9790;';
  }

  /**
   * Toggle dark mode via the header button.
   */
  _toggleDarkMode() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    this._updateSetting('theme', next);
  }

  /**
   * Handle the "Reset All Data" button.
   */
  _handleResetData() {
    const confirmed = window.confirm(
      'This will reset all conversations, labels, notes, and ratings to the default seed data. ' +
      'Your settings will also be reset. This cannot be undone.\n\nAre you sure?'
    );
    if (!confirmed) return;

    storageManager.resetAll();
    this.currentConversationId = null;
    this.currentPage = 1;
    this.currentFilters = {};
    this._refreshLabelDefs();
    this._applyTheme();
    this.showToast('All data has been reset to defaults.', 'info');
    this._renderSettings();
  }

  /* ────────────────────────────────────────────────────────────────
     2.12  TOAST NOTIFICATIONS
     ──────────────────────────────────────────────────────────────── */

  /**
   * Show a toast notification.
   *
   * @param {string} message
   * @param {'success' | 'error' | 'warning' | 'info'} [type='info']
   * @param {number} [duration=3000] - Auto-dismiss after this many ms.
   */
  showToast(message, type, duration) {
    type = type || 'info';
    duration = duration != null ? duration : 3000;

    const container = document.getElementById('toastContainer');
    if (!container) return;

    const id = 'toast-' + (++this._toastCounter);

    const iconMap = {
      success: '&#10004;',
      error: '&#10008;',
      warning: '&#9888;',
      info: '&#8505;'
    };

    const toast = document.createElement('div');
    toast.id = id;
    toast.className = 'toast-notification toast-' + type;
    toast.innerHTML =
      '<span class="toast-icon">' + (iconMap[type] || '') + '</span>' +
      '<span class="toast-message"></span>' +
      '<button class="toast-close" data-toast-id="' + id + '">&times;</button>';

    // Set message via textContent for safety
    const msgEl = toast.querySelector('.toast-message');
    if (msgEl) msgEl.textContent = message;

    container.appendChild(toast);

    // Auto-dismiss
    const dismissTimer = setTimeout(() => this._dismissToast(id), duration);

    // Close button
    const closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        clearTimeout(dismissTimer);
        this._dismissToast(id);
      });
    }
  }

  /**
   * Dismiss a toast by ID with exit animation.
   *
   * @param {string} toastId
   */
  _dismissToast(toastId) {
    const toast = document.getElementById(toastId);
    if (!toast) return;

    toast.classList.add('toast-exit');
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  /* ────────────────────────────────────────────────────────────────
     2.13  GLOBAL EVENT BINDINGS
     ──────────────────────────────────────────────────────────────── */

  /**
   * Bind all event listeners. Called once during init().
   */
  _bindGlobalEvents() {
    const self = this;

    // --- Login ---
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        self.handleLogin();
      });
    }

    // --- Logout ---
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => self.handleLogout());
    }

    // --- Sidebar toggle ---
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => self._toggleSidebar());
    }

    // --- Sidebar backdrop ---
    const backdrop = document.getElementById('sidebarBackdrop');
    if (backdrop) {
      backdrop.addEventListener('click', () => self._closeSidebar());
    }

    // --- Dark mode toggle ---
    const darkToggle = document.getElementById('darkModeToggle');
    if (darkToggle) {
      darkToggle.addEventListener('click', () => self._toggleDarkMode());
    }

    // --- Sidebar navigation ---
    document.querySelectorAll('.sidebar-nav-item[data-view]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const view = item.getAttribute('data-view');
        if (view) self.navigateTo(view);
      });
    });

    // --- Conversation list: search input (debounced) ---
    const convSearch = document.getElementById('conversationSearch');
    if (convSearch) {
      const debouncedSearch = debounce((val) => self._handleConversationSearch(val), 300);
      convSearch.addEventListener('input', (e) => debouncedSearch(e.target.value));
      convSearch.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          e.target.value = '';
          self._handleConversationSearch('');
        }
      });
    }

    // --- Filter chips ---
    document.querySelectorAll('.filter-chip[data-filter]').forEach(chip => {
      chip.addEventListener('click', () => {
        const rawFilter = chip.getAttribute('data-filter');
        const parts = rawFilter.split(':');
        if (parts.length !== 2) return;
        const [type, value] = parts;

        if (value === 'all') {
          // Clear this filter type
          delete self.currentFilters[type];
          self.currentPage = 1;
          self.renderConversationList();
        } else {
          self._toggleFilter(type, value);
        }
      });
    });

    // --- Pagination ---
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    if (prevBtn) prevBtn.addEventListener('click', () => self.prevPage());
    if (nextBtn) nextBtn.addEventListener('click', () => self.nextPage());

    // --- Conversation list: event delegation for clicking conversation items ---
    const listEl = document.getElementById('conversationList');
    if (listEl) {
      listEl.addEventListener('click', (e) => {
        const item = e.target.closest('.conversation-item');
        if (item) {
          const id = item.getAttribute('data-id');
          if (id) self.selectConversation(id);
        }
      });
    }

    // --- Conversation detail: event delegation ---
    const detailPanel = document.getElementById('conversationDetail');
    if (detailPanel) {
      detailPanel.addEventListener('click', (e) => {
        // Metadata toggle
        const metaToggle = e.target.closest('.message-metadata-toggle');
        if (metaToggle) {
          const msgId = metaToggle.getAttribute('data-msg-id');
          if (msgId) self._toggleMessageMetadata(msgId);
          return;
        }

        // Label remove
        const labelRemove = e.target.closest('.label-remove');
        if (labelRemove) {
          const convId = labelRemove.getAttribute('data-conv-id');
          const label = labelRemove.getAttribute('data-label');
          if (convId && label) self._removeLabelFromConversation(convId, label);
          return;
        }

        // Note delete
        const noteDelete = e.target.closest('.note-delete-btn');
        if (noteDelete) {
          const convId = noteDelete.getAttribute('data-conv-id');
          const noteId = noteDelete.getAttribute('data-note-id');
          if (convId && noteId) self._handleDeleteNote(convId, noteId);
          return;
        }
      });
    }

    // --- Add label button ---
    const addLabelBtn = document.getElementById('addLabelBtn');
    if (addLabelBtn) {
      addLabelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        self._toggleAddLabelMenu();
      });
    }

    // --- Add label menu: event delegation ---
    const addLabelMenu = document.getElementById('addLabelMenu');
    if (addLabelMenu) {
      addLabelMenu.addEventListener('click', (e) => {
        const menuItem = e.target.closest('.add-label-menu-item');
        if (menuItem) {
          const label = menuItem.getAttribute('data-label');
          if (label) self._addLabelToConversation(label);
        }
      });
    }

    // --- Rating buttons ---
    const ratingUp = document.getElementById('ratingUp');
    const ratingDown = document.getElementById('ratingDown');
    if (ratingUp) ratingUp.addEventListener('click', () => self._handleRating('up'));
    if (ratingDown) ratingDown.addEventListener('click', () => self._handleRating('down'));

    // --- Add note ---
    const addNoteBtn = document.getElementById('addNoteBtn');
    if (addNoteBtn) {
      addNoteBtn.addEventListener('click', () => self._handleAddNote());
    }

    // Enter key in notes textarea (Ctrl/Cmd + Enter to submit)
    const notesTextarea = document.getElementById('notesTextarea');
    if (notesTextarea) {
      notesTextarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          self._handleAddNote();
        }
      });
    }

    // --- Detail export button ---
    const detailExportBtn = document.getElementById('detailExportBtn');
    if (detailExportBtn) {
      detailExportBtn.addEventListener('click', () => self._showExportModal());
    }

    // --- Detail status select ---
    const detailStatusSelect = document.getElementById('detailStatusSelect');
    if (detailStatusSelect) {
      detailStatusSelect.addEventListener('change', (e) => {
        if (self.currentConversationId) {
          const success = storageManager.setStatus(self.currentConversationId, e.target.value);
          if (success) {
            self.showToast('Status updated to ' + statusLabel(e.target.value) + '.', 'success');
            self.renderConversationList();
          }
        }
      });
    }

    // --- Global search ---
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
      const debouncedGlobalSearch = debounce((val) => self.handleSearch(val), 300);
      globalSearch.addEventListener('input', (e) => debouncedGlobalSearch(e.target.value));
      globalSearch.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          self.handleSearch(e.target.value);
        }
        if (e.key === 'Escape') {
          e.target.value = '';
          self.handleSearch('');
        }
      });
    }

    // --- Search view filters (re-trigger search when changed) ---
    const searchFilterIds = ['searchDateFrom', 'searchDateTo', 'searchStatusFilter', 'searchLanguageFilter'];
    searchFilterIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', () => {
          const q = document.getElementById('globalSearch');
          if (q && q.value.trim()) self.handleSearch(q.value);
        });
      }
    });

    // --- Search results: event delegation ---
    const searchResults = document.getElementById('searchResults');
    if (searchResults) {
      searchResults.addEventListener('click', (e) => {
        const card = e.target.closest('.search-result-card');
        if (card) {
          const id = card.getAttribute('data-id');
          if (id) {
            self.currentConversationId = id;
            self.navigateTo('conversations');
            // Small delay to allow view render, then select
            setTimeout(() => self.selectConversation(id), 50);
          }
        }
      });
    }

    // --- Export button ---
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => self._handleExport());
    }

    // --- Export select all / select none buttons ---
    const exportSelectAllBtn = document.getElementById('exportSelectAll');
    if (exportSelectAllBtn) {
      exportSelectAllBtn.addEventListener('click', () => {
        document.querySelectorAll('.export-conv-checkbox').forEach(cb => cb.checked = true);
      });
    }
    const exportSelectNoneBtn = document.getElementById('exportSelectNone');
    if (exportSelectNoneBtn) {
      exportSelectNoneBtn.addEventListener('click', () => {
        document.querySelectorAll('.export-conv-checkbox').forEach(cb => cb.checked = false);
      });
    }

    // --- Export modal ---
    const modalClose = document.getElementById('modalClose');
    if (modalClose) {
      modalClose.addEventListener('click', () => self._hideExportModal());
    }

    const modalExportBtn = document.getElementById('modalExportBtn');
    if (modalExportBtn) {
      modalExportBtn.addEventListener('click', () => self._handleModalExport());
    }

    const modalCancel = document.getElementById('exportModalCancel');
    if (modalCancel) {
      modalCancel.addEventListener('click', () => self._hideExportModal());
    }

    const exportModal = document.getElementById('exportModal');
    if (exportModal) {
      exportModal.addEventListener('click', (e) => {
        // Close on backdrop click (not on modal content)
        if (e.target === exportModal) {
          self._hideExportModal();
        }
      });
    }

    // --- Settings ---
    const themeSelect = document.getElementById('settingTheme');
    if (themeSelect) {
      themeSelect.addEventListener('change', (e) => {
        self._updateSetting('theme', e.target.value);
      });
    }

    const pageSizeInput = document.getElementById('settingPageSize');
    if (pageSizeInput) {
      pageSizeInput.addEventListener('change', (e) => {
        const val = parseInt(e.target.value, 10);
        if (val > 0 && val <= 100) {
          self._updateSetting('pageSize', val);
        }
      });
    }

    const langSelect = document.getElementById('settingLanguage');
    if (langSelect) {
      langSelect.addEventListener('change', (e) => {
        self._updateSetting('defaultLanguageFilter', e.target.value);
      });
    }

    const resetBtn = document.getElementById('resetDataBtn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => self._handleResetData());
    }

    // --- Global keyboard shortcuts ---
    document.addEventListener('keydown', (e) => {
      // Escape closes modals and dropdowns
      if (e.key === 'Escape') {
        self._hideExportModal();
        self._closeAddLabelMenu();
      }
    });

    // --- Close add-label menu when clicking outside ---
    document.addEventListener('click', (e) => {
      const menu = document.getElementById('addLabelMenu');
      const btn = document.getElementById('addLabelBtn');
      if (menu && menu.classList.contains('open')) {
        if (!menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
          self._closeAddLabelMenu();
        }
      }
    });
  }

  /* ────────────────────────────────────────────────────────────────
     2.14  HELPERS
     ──────────────────────────────────────────────────────────────── */

  /**
   * Safely set the textContent of an element by ID.
   *
   * @param {string} id
   * @param {string} text
   */
  _setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text != null ? String(text) : '';
  }

  /**
   * Look up a label definition by name.
   *
   * @param {string} name
   * @returns {{ name: string, color: string, description: string } | null}
   */
  _getLabelDef(name) {
    return this._labelDefs.find(d => d.name === name) || null;
  }
}


/* ================================================================
   SECTION 3 - BOOTSTRAP
   ================================================================ */

/**
 * Global PortalApp instance. Initialised on DOMContentLoaded.
 */
let portalApp = null;

document.addEventListener('DOMContentLoaded', () => {
  portalApp = new PortalApp();
  portalApp.init();
});
