/**
 * SURVILLENCE TRAFFIC — Online Server-Backed Authentication
 * ========================================================
 * Authentic server-side authentication for Vercel deployment.
 * Communicates directly with server /api/auth/* routes.
 * Permanent unique user IDs and strict user isolation.
 * No hardcoded accounts. No browser-only fake registration.
 */

const AUTH_SESSION_KEY = 'st_session';

/* ── Session Storage (Client cache of active server session) ── */
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
  getSession,

  getUserId() {
    const s = getSession();
    return s ? (s.userId || s.id) : null;
  },

  getCurrentUser() {
    return getSession();
  },

  isAuthenticated() {
    const s = getSession();
    return s !== null && !!(s.userId || s.id);
  },

  requireAuth() {
    if (!Auth.isAuthenticated()) {
      window.location.href = '/login.html';
      return false;
    }
    return true;
  },

  redirectIfAuth(dest = '/pages/dashboard.html') {
    if (Auth.isAuthenticated()) {
      window.location.href = dest;
      return true;
    }
    return false;
  },

  /**
   * Register a new user with the server database.
   */
  async register({ fullName, email, username, password }) {
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fullName, email, username, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        saveSession(data.user);
        return { ok: true, user: data.user };
      }
      return {
        ok: false,
        error: data.error || (res.status === 409 ? 'An account with this username or email already exists.' : `Registration failed (${res.status})`),
      };
    } catch (err) {
      return { ok: false, error: 'Could not connect to authentication service. Please verify internet connectivity.' };
    }
  },

  /**
   * Log in against authoritative server user store.
   */
  async login({ identifier, password, remember }) {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        const session = saveSession(data.user);
        if (remember) localStorage.setItem('st_remember', '1');
        return { ok: true, session, user: data.user };
      }
      return {
        ok: false,
        error: data.error || (res.status === 404 ? 'Account not found' : 'Incorrect password'),
        code: data.code || (res.status === 404 ? 'USER_NOT_FOUND' : 'INVALID_PASSWORD'),
      };
    } catch (err) {
      return { ok: false, error: 'Could not connect to authentication service. Please verify internet connectivity.' };
    }
  },

  /**
   * Revalidate current session against the server.
   */
  async verifySession() {
    const session = getSession();
    if (!session || !session.userId) return false;
    try {
      const res = await fetch('/api/auth/me', {
        headers: { 'X-User-Id': session.userId }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated && data.user) {
          saveSession(data.user);
          return true;
        }
      }
      clearSession();
      return false;
    } catch {
      return true; // Keep cached session on transient offline
    }
  },

  /** Logout and redirect to login */
  logout() {
    clearSession();
    window.location.href = '/login.html';
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
    } catch {}
  },

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
      if (res.ok && data.ok) {
        session.fullName = data.user.fullName || data.user.name;
        session.name = session.fullName;
        session.email = data.user.email;
        localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
        return { ok: true, user: data.user };
      }
      return { ok: false, error: data.error || 'Update failed' };
    } catch {
      return { ok: false, error: 'Failed to update profile.' };
    }
  },
};

/* ── Apply theme on page load ─────────────────────────────── */
(function applyTheme() {
  const settings = Auth.getSettings();
  document.documentElement.setAttribute('data-theme', settings.theme || 'dark');
})();

window.Auth = Auth;
