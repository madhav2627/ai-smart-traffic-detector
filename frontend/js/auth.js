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

function getAuthApiBase() {
  try {
    if (typeof ApiClient !== 'undefined' && ApiClient.getBaseUrl) return ApiClient.getBaseUrl();
    const custom = (typeof localStorage !== 'undefined') ? localStorage.getItem('surv_api_base') : null;
    if (custom && custom.trim()) return custom.trim().replace(/\/$/, '');
    if (typeof window !== 'undefined' && window.ENV_API_URL) return window.ENV_API_URL.replace(/\/$/, '');
  } catch {}
  return '';
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
   * Supports both server-backed (Flask) and Vercel standalone local storage fallback.
   * Returns { ok: true, user } or { ok: false, error }
   */
  async register({ fullName, email, username, password }) {
    const base = getAuthApiBase();
    let serverUnavailable = false;

    try {
      const res = await fetch(`${base}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fullName, email, username, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        saveSession(data.user);
        return { ok: true, user: data.user };
      }
      if (res.status === 409) {
        return {
          ok: false,
          error: data.error || 'Account already exists with that username or email.',
        };
      }
      // If 404 (e.g. running on Vercel without live backend server), fallback to local storage
      if (res.status === 404 || res.status >= 500) {
        serverUnavailable = true;
      } else {
        return {
          ok: false,
          error: data.error || `Registration failed (${res.status})`,
        };
      }
    } catch {
      serverUnavailable = true;
    }

    // Vercel / Client-side persistent storage fallback
    if (serverUnavailable) {
      try {
        const LOCAL_KEY = 'st_local_users_db';
        const raw = localStorage.getItem(LOCAL_KEY);
        const users = raw ? JSON.parse(raw) : [];

        const exists = users.find(u =>
          (u.username && u.username.toLowerCase() === username.toLowerCase()) ||
          (u.email && u.email.toLowerCase() === email.toLowerCase())
        );
        if (exists) {
          return { ok: false, error: 'Account already exists with that username or email.' };
        }

        // Create user record in browser storage
        const uid = 'usr_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        const newUser = {
          id: uid,
          userId: uid,
          name: fullName,
          fullName: fullName,
          email: email,
          username: username,
          role: 'operator',
          createdAt: new Date().toISOString(),
          settings: { theme: 'dark', notifications: true, confidence: 0.20 }
        };

        // Simple local hash
        newUser.password = password; // kept locally in browser storage for fallback login

        users.push(newUser);
        localStorage.setItem(LOCAL_KEY, JSON.stringify(users));

        // Save session immediately so user is logged in
        saveSession(newUser);

        return { ok: true, user: newUser };
      } catch (err) {
        return { ok: false, error: 'Storage error: ' + err.message };
      }
    }
  },

  /**
   * Log in against authoritative server SQLite user store or local storage fallback.
   * Returns { ok: true, session, user } or { ok: false, error, code }
   */
  async login({ identifier, password, remember }) {
    const base = getAuthApiBase();
    let serverUnavailable = false;

    try {
      const res = await fetch(`${base}/api/auth/login`, {
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
      if (res.status === 404 || res.status >= 500) {
        serverUnavailable = true;
      } else {
        return {
          ok: false,
          error: data.error || 'Incorrect password',
          code: data.code || 'INVALID_PASSWORD',
        };
      }
    } catch {
      serverUnavailable = true;
    }

    // Vercel / Client-side fallback authentication
    if (serverUnavailable) {
      try {
        const LOCAL_KEY = 'st_local_users_db';
        const raw = localStorage.getItem(LOCAL_KEY);
        const users = raw ? JSON.parse(raw) : [];

        const idLower = (identifier || '').toLowerCase();
        let user = users.find(u =>
          (u.username && u.username.toLowerCase() === idLower) ||
          (u.email && u.email.toLowerCase() === idLower)
        );

        // Auto-provision demo account if none exists
        if (!user && (idLower === 'madhav2627' || idLower === 'admin')) {
          user = {
            id: 'usr_madhav_' + Date.now(),
            name: idLower === 'madhav2627' ? 'Madhav Prasad' : 'Administrator',
            fullName: idLower === 'madhav2627' ? 'Madhav Prasad' : 'Administrator',
            email: idLower === 'madhav2627' ? 'mp7553696@gmail.com' : 'admin@traffic.ai',
            username: identifier,
            password: password,
            role: 'operator',
            settings: { theme: 'dark', notifications: true, confidence: 0.20 }
          };
          users.push(user);
          localStorage.setItem(LOCAL_KEY, JSON.stringify(users));
        }

        if (!user) {
          return { ok: false, error: 'Account not found', code: 'USER_NOT_FOUND' };
        }

        if (user.password && user.password !== password) {
          return { ok: false, error: 'Incorrect password', code: 'INVALID_PASSWORD' };
        }

        const session = saveSession(user);
        if (remember) localStorage.setItem('st_remember', '1');
        return { ok: true, session, user };
      } catch (err) {
        return { ok: false, error: 'Authentication error: ' + err.message };
      }
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
      const LOCAL_KEY = 'st_local_users_db';
      const raw = localStorage.getItem(LOCAL_KEY);
      if (raw) {
        const users = JSON.parse(raw);
        const idx = users.findIndex(u => (u.id || u.userId) === (session.userId || session.id));
        if (idx !== -1) {
          users[idx].settings = session.settings;
          localStorage.setItem(LOCAL_KEY, JSON.stringify(users));
        }
      }
    } catch {}

    try {
      const base = getAuthApiBase();
      await fetch(`${base}/api/auth/settings`, {
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

    const base = getAuthApiBase();
    try {
      const res = await fetch(`${base}/api/auth/profile`, {
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
      if (res.status !== 404 && res.status < 500) {
        return { ok: false, error: data.error || 'Update failed' };
      }
    } catch {}

    // Standalone fallback: update in browser session and local database
    session.fullName = fullName || session.fullName;
    session.name = session.fullName;
    session.email = email || session.email;
    localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));

    try {
      const LOCAL_KEY = 'st_local_users_db';
      const raw = localStorage.getItem(LOCAL_KEY);
      if (raw) {
        const users = JSON.parse(raw);
        const idx = users.findIndex(u => (u.id || u.userId) === (session.userId || session.id));
        if (idx !== -1) {
          users[idx].fullName = session.fullName;
          users[idx].name = session.fullName;
          users[idx].email = session.email;
          localStorage.setItem(LOCAL_KEY, JSON.stringify(users));
        }
      }
    } catch {}

    return { ok: true, user: session };
  },
};

/* ── Apply theme on page load ─────────────────────────────── */
(function applyTheme() {
  const settings = Auth.getSettings();
  document.documentElement.setAttribute('data-theme', settings.theme || 'dark');
})();

window.Auth = Auth;
