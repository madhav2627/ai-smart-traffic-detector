/**
 * SURVILLENCE TRAFFIC — API Client
 * Handles all communication with the local Flask backend.
 * Uses window.location.origin so it works on localhost AND LAN IPs.
 */

// Dynamic API endpoint resolution supporting:
// 1. Same-origin relative path (local Flask server / LAN IP)
// 2. Custom remote inference server (when frontend is deployed on Vercel)
function getApiBase() {
  try {
    const custom = (typeof localStorage !== 'undefined') ? localStorage.getItem('surv_api_base') : null;
    if (custom && custom.trim()) return custom.trim().replace(/\/$/, '');
    if (typeof window !== 'undefined' && window.ENV_API_URL) return window.ENV_API_URL.replace(/\/$/, '');
  } catch {}
  return '';
}

const ApiClient = {
  getBaseUrl() {
    return getApiBase();
  },

  setBaseUrl(url) {
    try {
      if (url && url.trim()) {
        localStorage.setItem('surv_api_base', url.trim().replace(/\/$/, ''));
      } else {
        localStorage.removeItem('surv_api_base');
      }
    } catch {}
  },

  /* ── Internal fetch helper ────────────────────────────────── */
  async _fetch(path, opts = {}) {
    try {
      const uid = (typeof Auth !== 'undefined' && Auth.getUserId) ? Auth.getUserId() : null;
      const headers = { ...(opts.headers || {}) };
      if (uid) {
        headers['X-User-Id'] = uid;
      }
      const base = getApiBase();
      const res = await fetch(`${base}${path}`, { ...opts, headers });
      if (!res.ok) {
        let msg = `Server error ${res.status}`;
        try { const j = await res.json(); msg = j.error || msg; } catch {}
        throw new Error(msg);
      }
      return res;
    } catch (err) {
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        throw new Error('Cannot connect to local server. Make sure START.bat is running.');
      }
      throw err;
    }
  },

  async _json(path, opts = {}) {
    const res = await ApiClient._fetch(path, opts);
    return res.json();
  },

  /* ── User Helper ─────────────────────────────────────────── */
  _getUserParams() {
    const uid = (typeof Auth !== 'undefined' && Auth.getUserId) ? Auth.getUserId() : null;
    const params = new URLSearchParams();
    if (uid) params.set('user_id', uid);
    return params;
  },

  /* ── Health / Status ──────────────────────────────────────── */
  async health() {
    return ApiClient._json('/health');
  },

  /* ── Analysis ─────────────────────────────────────────────── */
  /**
   * Upload a video file and start analysis.
   * Throws with code ALREADY_PROCESSING if user has an active job.
   */
  async analyze(file) {
    const form = new FormData();
    form.append('video', file);
    const uid = (typeof Auth !== 'undefined' && Auth.getUserId) ? Auth.getUserId() : null;
    if (uid) form.append('user_id', uid);
    return ApiClient._json('/api/analyze', { method: 'POST', body: form });
  },

  /**
   * Get an EventSource for SSE progress stream.
   */
  progressStream(sessionId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return new EventSource(`${API_BASE}/api/progress/${sessionId}${qs}`);
  },

  /**
   * Fetch any currently active processing job for this user.
   */
  async getActiveJob() {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/active-job${qs}`);
  },

  /**
   * Fetch the most recently completed job (within TTL) for this user.
   * Used for the global completion notification.
   */
  async getCompletedJob() {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/completed-job${qs}`);
  },

  /**
   * Dismiss the completion notification for a session.
   */
  async dismissCompletedJob(sessionId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/completed-job/${sessionId}/dismiss${qs}`, { method: 'POST' });
  },

  /**
   * Fetch the result/report for a session.
   */
  async getResult(sessionId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/result/${sessionId}${qs}`);
  },

  /**
   * Get the URL of the processed video for a session.
   */
  videoUrl(sessionId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return `${API_BASE}/api/video/${sessionId}${qs}`;
  },

  /* ── History ─────────────────────────────────────────────── */
  async getHistory() {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/history${qs}`);
  },

  async deleteHistory(sessionId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/history/${sessionId}${qs}`, { method: 'DELETE' });
  },

  /* ── Storage ─────────────────────────────────────────────── */
  async storageStats() {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/storage/stats${qs}`);
  },

  async cleanupStorage() {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/storage/cleanup${qs}`, { method: 'POST' });
  },

  /* ── CCTV / Camera Management ────────────────────────────── */
  async getCameras() {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/cameras${qs}`);
  },

  async getCamera(cameraId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/cameras/${cameraId}${qs}`);
  },

  async createCamera(data) {
    return ApiClient._json('/api/cameras', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async updateCamera(cameraId, data) {
    return ApiClient._json(`/api/cameras/${cameraId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async deleteCamera(cameraId) {
    return ApiClient._json(`/api/cameras/${cameraId}`, { method: 'DELETE' });
  },

  async testCameraRaw(data) {
    return ApiClient._json('/api/cameras/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async testCamera(cameraId) {
    return ApiClient._json(`/api/cameras/${cameraId}/test`, { method: 'POST' });
  },

  async getCameraStats(cameraId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return ApiClient._json(`/api/cameras/${cameraId}/stats${qs}`);
  },

  cameraStreamUrl(cameraId) {
    const q = ApiClient._getUserParams().toString();
    const qs = q ? `?${q}` : '';
    return `${getApiBase()}/api/cameras/${cameraId}/stream${qs}`;
  },
};

/* ── Toast Notification System ───────────────────────────── */
const Toast = {
  _container: null,

  _getContainer() {
    if (!Toast._container) {
      Toast._container = document.createElement('div');
      Toast._container.id = 'toast-container';
      document.body.appendChild(Toast._container);
    }
    return Toast._container;
  },

  show(type, title, message = '', duration = 4500) {
    const icons = {
      success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
      error:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
      warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
      info:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    };

    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        ${message ? `<div class="toast-msg">${message}</div>` : ''}
      </div>
      <button class="toast-close" aria-label="Dismiss">×</button>
    `;

    el.querySelector('.toast-close').addEventListener('click', () => {
      el.classList.add('toast-exit');
      setTimeout(() => el.remove(), 300);
    });

    Toast._getContainer().appendChild(el);

    // Animate in
    requestAnimationFrame(() => el.classList.add('toast-visible'));

    if (duration > 0) {
      setTimeout(() => {
        el.classList.add('toast-exit');
        setTimeout(() => el.remove(), 300);
      }, duration);
    }

    return el;
  },

  success(title, msg, dur) { return Toast.show('success', title, msg, dur); },
  error(title, msg, dur)   { return Toast.show('error',   title, msg, dur); },
  warning(title, msg, dur) { return Toast.show('warning', title, msg, dur); },
  info(title, msg, dur)    { return Toast.show('info',    title, msg, dur); },
};

/* ── Utility: format bytes ────────────────────────────────── */
function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return `${bytes.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/* ── Utility: format seconds ──────────────────────────────── */
function formatDuration(seconds) {
  if (!seconds || isNaN(seconds)) return 'N/A';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/* ── Utility: format date ─────────────────────────────────── */
function formatDate(iso) {
  if (!iso) return 'N/A';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

/* ── Utility: relative time ───────────────────────────────── */
function timeAgo(iso) {
  if (!iso) return '';
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60)   return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/* ── Sidebar / shell shared init ─────────────────────────── */
function initShell() {
  const session = Auth.getSession();
  if (!session) return;

  // User display
  const nameEls = document.querySelectorAll('[data-user-name]');
  const initEls = document.querySelectorAll('[data-user-initials]');
  const emailEls = document.querySelectorAll('[data-user-email]');

  nameEls.forEach(el => { el.textContent = session.fullName || session.username || 'User'; });
  emailEls.forEach(el => { el.textContent = session.email || ''; });
  initEls.forEach(el => {
    const parts = (session.fullName || session.username || '?').split(' ');
    el.textContent = parts.map(p => p[0]).join('').toUpperCase().slice(0, 2);
  });

  // Active nav highlight
  const path = window.location.pathname.split('/').pop();
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    const aPath = a.getAttribute('href').split('/').pop();
    if (aPath === path) a.classList.add('active');
  });

  // Note: mobile sidebar drawer handlers are managed exclusively in shell.js renderShell()

  // Logout buttons
  document.querySelectorAll('[data-logout]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      Auth.logout();
    });
  });

  // Theme
  const settings = Auth.getSettings();
  document.documentElement.setAttribute('data-theme', settings.theme || 'dark');

  // Start global processing monitor
  initGlobalProcessingMonitor();
}

/* ── Global Processing Monitor ───────────────────────────── */
let _gpmInterval = null;
let _lastNotifiedSession = null;

function initGlobalProcessingMonitor() {
  if (_gpmInterval) clearInterval(_gpmInterval);
  _pollProcessingStatus();
  _gpmInterval = setInterval(_pollProcessingStatus, 5000);
}

async function _pollProcessingStatus() {
  try {
    const activeRes = await ApiClient.getActiveJob();
    const indicatorEl = document.getElementById('global-proc-indicator');

    if (activeRes && activeRes.job) {
      const job = activeRes.job;
      if (indicatorEl) {
        indicatorEl.style.display = 'flex';
        const nameEl = indicatorEl.querySelector('.gpi-filename');
        const statusEl = indicatorEl.querySelector('.gpi-status');
        if (nameEl) nameEl.textContent = job.filename || 'Processing...';
        if (statusEl) statusEl.textContent = 'Detecting & tracking vehicles...';
      }
      return; // Active job found, skip completed check
    }

    // No active job — hide indicator
    if (indicatorEl) indicatorEl.style.display = 'none';

    // Check for recently completed job we haven't notified about
    const completedRes = await ApiClient.getCompletedJob();
    if (completedRes && completedRes.job) {
      const job = completedRes.job;
      if (job.sessionId !== _lastNotifiedSession) {
        _lastNotifiedSession = job.sessionId;
        _showCompletionNotification(job);
      }
    }
  } catch {
    // Server might be offline; silently skip
  }
}

function _showCompletionNotification(job) {
  const filename = job.filename || 'video';
  const sessionId = job.sessionId;

  const el = Toast.show('success', '✓ Analysis Complete', filename, 0);
  if (!el) return;

  // Add "View Results" link
  const link = document.createElement('a');
  link.href = `/pages/surveillance.html?session=${sessionId}`;
  link.className = 'toast-action-link';
  link.textContent = 'View Results →';
  el.querySelector('.toast-body').appendChild(link);

  // Auto-dismiss after 12 seconds
  setTimeout(() => {
    el.classList.add('toast-exit');
    setTimeout(() => el.remove(), 300);
  }, 12000);

  // Dismiss from server when user clicks view or X
  el.querySelector('.toast-close').addEventListener('click', () => {
    ApiClient.dismissCompletedJob(sessionId).catch(() => {});
  });
  link.addEventListener('click', () => {
    ApiClient.dismissCompletedJob(sessionId).catch(() => {});
  });
}

/* ── Server status check ─────────────────────────────────── */
async function checkServerStatus(indicator) {
  if (!indicator) return false;
  try {
    await ApiClient.health();
    indicator.classList.remove('offline', 'warning');
    indicator.classList.add('online');
    return true;
  } catch {
    indicator.classList.add('offline');
    indicator.classList.remove('online');
    return false;
  }
}

window.ApiClient   = ApiClient;
window.Toast       = Toast;
window.formatBytes = formatBytes;
window.formatDuration = formatDuration;
window.formatDate  = formatDate;
window.timeAgo     = timeAgo;
window.initShell   = initShell;
window.checkServerStatus = checkServerStatus;
