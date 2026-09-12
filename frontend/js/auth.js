/**
 * SURVILLENCE TRAFFIC — Unified Server-Backed Authentication
 * Communicates with the local SQLite user database on the backend via relative API routes.
 * Identical behavior on http://localhost:5000 and LAN IP http://192.168.x.x:5000.
 */

const AUTH_SESSION_KEY = 'st_session';

/* ── Session Helpers ──────────────────────────────────────── */

function getSession() {
  try {
    const raw = localStorage.getItem(AUTH_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(user) {
  const uid = user.id || user.userId;
  const session = {
    id: uid,
    userId: uid,
    fullName: user.fullName || user.name || user.username,
    name: user.fullName || user.name || user.username,
    email: user.email || '',
    username: user.username || '',
    role: user.role || 'operator',
    settings: user.settings || { theme: 'dark', notifications: true, confidence: 0.20 },
    loginTime: Date.now(),
  };
  localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
  return session;
}

function clearSession() {
  localStorage.removeItem(AUTH_SESSION_KEY);
}

/* ── Public Auth API ───────────────────────────────────────── */
const Auth = {
  /** Returns current session or null */
  getSession,

  /** Returns permanent unique user ID or null */
  getUserId() {
    const s = getSession();
    return s ? (s.userId || s.id) : null;
  },

  /** Returns current authenticated user object or null */
  getCurrentUser() {
    return getSession();
  },

  /** Returns true if a user is logged in */
  isAuthenticated() {
    const s = getSession();
    return s !== null && !!(s.userId || s.id);
  },

  /** Redirect to login if not authenticated */
  requireAuth() {
    if (!Auth.isAuthenticated()) {
      const isFile = window.location.protocol === 'file:';
      const isInPages = window.location.pathname.includes('/pages/') || window.location.pathname.includes('\\pages\\');
      window.location.href = isFile ? (isInPages ? '../login.html' : 'login.html') : '/login.html';
      return false;
    }
    return true;
  },

  /** Redirect to dashboard if already authenticated */
  redirectIfAuth(dest = '/pages/dashboard.html') {
    if (Auth.isAuthenticated()) {
      if (window.location.protocol === 'file:' && dest.startsWith('/')) {
        const isInPages = window.location.pathname.includes('/pages/') || window.location.pathname.includes('\\pages\\');
        dest = isInPages ? dest.replace(/^\/pages\//, '') : dest.replace(/^\//, '');
      }
      window.location.href = dest;
      return true;
    }
    return false;
  },

  /**
   * Register a new user with the server database.
   * Uses same-origin relative fetch so it works on localhost and LAN.
   * Returns { ok: true, user } or { ok: false, error }
   */
  async register({ fullName, email, username, password }) {
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fullName, email, username, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        return {
          ok: false,
          error: data.error || (res.status === 409 ? 'Account already exists.' : `Registration failed (${res.status})`),
        };
      }
      return { ok: true, user: data.user };
    } catch (err) {
      return {
        ok: false,
        error: 'Unable to reach backend server. Please verify START.bat is running on port 5000.',
      };
    }
  },

  /**
   * Log in against authoritative server SQLite user store.
   * Returns { ok: true, session, user } or { ok: false, error, code }
   */
  async login({ identifier, password, remember }) {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        return {
          ok: false,
          error: data.error || (res.status === 404 ? 'Account not found' : 'Incorrect password'),
          code: data.code || (res.status === 404 ? 'USER_NOT_FOUND' : 'INVALID_PASSWORD'),
        };
      }

      const session = saveSession(data.user);
      if (remember) {
        localStorage.setItem('st_remember', '1');
      }
      return { ok: true, session, user: data.user };
    } catch (err) {
      return {
        ok: false,
        error: 'Unable to reach backend server. Please verify START.bat is running on port 5000.',
      };
    }
  },

  /** Logout and redirect to login */
  logout() {
    clearSession();
    const isFile = window.location.protocol === 'file:';
    const isInPages = window.location.pathname.includes('/pages/') || window.location.pathname.includes('\\pages\\');
    window.location.href = isFile ? (isInPages ? '../login.html' : 'login.html') : '/login.html';
  },

  /** Update settings for current user */
  async updateSettings(settings) {
    const session = getSession();
    if (!session) return;
    session.settings = { ...(session.settings || {}), ...settings };
    localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));

    try {
      await fetch('/api/auth/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': session.userId || session.id,
        },
        body: JSON.stringify(session.settings),
      });
    } catch {
      // Offline fallback: settings already updated in session
    }
  },

  /** Get current user's settings */
  getSettings() {
    const session = getSession();
    return session?.settings || { theme: 'dark', notifications: true, confidence: 0.20 };
  },

  /** Update profile fields (fullName, email) */
  async updateProfile({ fullName, email }) {
    const session = getSession();
    if (!session) return { ok: false, error: 'Not authenticated' };

    try {
      const res = await fetch('/api/auth/profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': session.userId || session.id,
        },
        body: JSON.stringify({ fullName, email }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        return { ok: false, error: data.error || 'Update failed' };
      }
      session.fullName = data.user.fullName || data.user.name;
      session.name = session.fullName;
      session.email = data.user.email;
      localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
      return { ok: true, user: data.user };
    } catch (err) {
      return { ok: false, error: 'Network error updating profile' };
    }
  },
};

/* ── Apply theme on page load ─────────────────────────────── */
(function applyTheme() {
  const settings = Auth.getSettings();
  document.documentElement.setAttribute('data-theme', settings.theme || 'dark');
})();

window.Auth = Auth;
