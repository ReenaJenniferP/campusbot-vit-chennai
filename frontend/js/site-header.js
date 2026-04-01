function getSiteHeader(activePage = "") {
  return `
    <header class="site-header">
      <a class="brand-link" href="index.html">
        <span class="brand-wrap">
          <span class="brand-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2 3 6v2h18V6l-9-4Zm-7 8v8H3v2h18v-2h-2v-8h-2v8h-2v-8h-2v8h-2v-8H9v8H7v-8H5Z"/>
            </svg>
          </span>
          <span class="brand-text">Campus<span>Bot</span></span>
        </span>
      </a>

      <nav class="nav-links">
        <a href="index.html" class="${activePage === "home" ? "active" : ""}">Home</a>
        <a href="about.html" class="${activePage === "about" ? "active" : ""}">About</a>
        <a href="chat.html" class="${activePage === "chat" ? "active" : ""}">Chat</a>
        <a href="dashboard.html" class="${activePage === "dashboard" ? "active" : ""}">Dashboard</a>
      </nav>
    </header>
  `;
}

function renderSiteHeader(activePage) {
  const target = document.getElementById("siteHeader");
  if (target) {
    target.innerHTML = getSiteHeader(activePage);
  }
}