/**
 * SURVILLENCE TRAFFIC — Shared Shell (Sidebar + Topbar)
 * Call renderShell(pageTitle) inside DOMContentLoaded on every protected page.
 * Includes:
 *  - Premium sidebar navigation
 *  - Topbar with global processing indicator
 *  - User avatar + logout
 *  - Mobile responsiveness
 */
function renderShell(pageTitle = 'Dashboard') {
  const sidebarHTML = `
    <div id="sidebar-overlay" class="sidebar-overlay"></div>
    <nav id="sidebar" class="sidebar" aria-label="Main navigation">
      <div class="sidebar-logo">
        <div class="sidebar-logo-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M15 10l4.553-2.069A1 1 0 0121 8.866V19a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h3.5"/>
            <circle cx="9" cy="9" r="3"/>
          </svg>
        </div>
        <div class="sidebar-logo-text">SURVILLENCE<span>Traffic Intelligence</span></div>
        <button id="sidebar-close-btn" class="sidebar-close-btn" aria-label="Close navigation menu">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <nav class="sidebar-nav" aria-label="Sections">
        <div class="sidebar-section-label">Overview</div>
        <a class="nav-item" href="/pages/dashboard.html" id="nav-dashboard">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
          Dashboard
        </a>
        <a class="nav-item" href="/pages/surveillance.html" id="nav-surveillance">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 10l4.553-2.069A1 1 0 0121 8.866V19a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h3.5"/><circle cx="9" cy="9" r="3"/></svg>
          Surveillance
        </a>
        <a class="nav-item" href="/pages/cameras.html" id="nav-cameras">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
          CCTV Connectivity
        </a>

        <div class="sidebar-section-label" style="margin-top:var(--space-4)">Analytics</div>
        <a class="nav-item" href="/pages/analytics.html" id="nav-analytics">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          Vehicle Analytics
        </a>
        <a class="nav-item" href="/pages/traffic-ai.html" id="nav-traffic-ai">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          Traffic AI
        </a>

        <div class="sidebar-section-label" style="margin-top:var(--space-4)">Records</div>
        <a class="nav-item" href="/pages/history.html" id="nav-history">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          History
        </a>
        <a class="nav-item" href="/pages/reports.html" id="nav-reports">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          Reports
        </a>
        <a class="nav-item" href="/pages/settings.html" id="nav-settings">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
          Settings
        </a>
      </nav>

      <div class="sidebar-footer">
        <div class="sidebar-user">
          <div class="sidebar-avatar" data-user-initials>--</div>
          <div class="sidebar-user-info">
            <div class="sidebar-user-name" data-user-name>User</div>
            <div class="sidebar-user-role" data-user-email>Operator</div>
          </div>
          <button class="btn btn-ghost btn-icon btn-sm" data-logout title="Sign out" aria-label="Sign out">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </div>
    </nav>

    <header class="topbar" role="banner">
      <div class="topbar-left">
        <button type="button" id="sidebar-toggle" class="topbar-btn sidebar-toggle-btn" aria-label="Toggle navigation menu">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>

        <div class="topbar-breadcrumb">
          <span class="topbar-brand">SURVILLENCE TRAFFIC</span>
          <span class="topbar-sep">/</span>
          <h1 class="topbar-page">${pageTitle}</h1>
        </div>
      </div>

      <!-- Global Processing Indicator -->
      <div id="global-proc-indicator" class="global-proc-indicator" style="display:none">
        <div class="gpi-pulse-ring"></div>
        <div class="gpi-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </div>
        <div class="gpi-info">
          <div class="gpi-label">AI ANALYSIS</div>
          <div class="gpi-filename">Processing...</div>
        </div>
        <div class="gpi-status-wrap">
          <span class="gpi-status">Detecting vehicles...</span>
        </div>
        <a href="/pages/surveillance.html" class="gpi-view-link" title="View progress">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </a>
      </div>

      <div class="topbar-actions">
        <div class="server-status-dot" id="server-status-dot" title="Server status"></div>
        <div class="topbar-avatar" data-user-initials style="cursor:pointer" title="Account">--</div>
      </div>
    </header>
  `;

  // Insert sidebar and topbar directly into document.body without wrapper div
  document.body.insertAdjacentHTML('afterbegin', sidebarHTML);

  // Active nav highlight
  const currentPath = window.location.pathname.split('/').pop();
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    const aPath = a.getAttribute('href').split('/').pop();
    if (aPath === currentPath) a.classList.add('active');
  });

  // Mobile drawer handlers (click + touchstart support)
  const toggleBtn = document.getElementById('sidebar-toggle');
  const closeBtn  = document.getElementById('sidebar-close-btn');
  const sidebar   = document.getElementById('sidebar');
  const overlay   = document.getElementById('sidebar-overlay');

  function openDrawer(e) {
    if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
    const sb = document.getElementById('sidebar');
    const ov = document.getElementById('sidebar-overlay');
    if (sb) sb.classList.add('mobile-open');
    if (ov) ov.classList.add('visible');
    document.body.classList.add('drawer-open');
  }

  function closeDrawer(e) {
    if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
    const sb = document.getElementById('sidebar');
    const ov = document.getElementById('sidebar-overlay');
    if (sb) sb.classList.remove('mobile-open');
    if (ov) ov.classList.remove('visible');
    document.body.classList.remove('drawer-open');
  }

  function toggleDrawer(e) {
    if (e) {
      if (typeof e.preventDefault === 'function') e.preventDefault();
      if (typeof e.stopPropagation === 'function') e.stopPropagation();
    }
    const sb = document.getElementById('sidebar');
    if (sb && sb.classList.contains('mobile-open')) {
      closeDrawer(e);
    } else {
      openDrawer(e);
    }
  }

  if (toggleBtn) {
    toggleBtn.onclick = toggleDrawer;
  }
  if (closeBtn) {
    closeBtn.onclick = closeDrawer;
  }
  if (overlay) {
    overlay.onclick = closeDrawer;
  }
  document.querySelectorAll('.nav-item').forEach(el => el.addEventListener('click', () => {
    if (window.innerWidth <= 900) closeDrawer();
  }));
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
  });

  initShell();

  // Server status check (non-blocking)
  setTimeout(() => {
    const dot = document.getElementById('server-status-dot');
    if (dot) checkServerStatus(dot);
  }, 1000);
}

window.renderShell = renderShell;
