(() => {
  const root = document.querySelector('[data-app-layout]');
  const sidebar = document.getElementById('app-sidebar');
  const menuButton = document.querySelector('[data-nav-toggle]');
  const overlay = document.querySelector('[data-nav-overlay]');
  const themeButton = document.querySelector('[data-theme-toggle]');
  let returnFocus = null;

  const setNav = (open) => {
    if (!root || !sidebar || !menuButton) return;
    root.classList.toggle('nav-open', open);
    menuButton.setAttribute('aria-expanded', String(open));
    sidebar.setAttribute('aria-hidden', String(!open && window.matchMedia('(max-width: 900px)').matches));
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) {
      returnFocus = document.activeElement;
      sidebar.querySelector('a, button')?.focus();
    } else if (returnFocus instanceof HTMLElement) {
      returnFocus.focus();
      returnFocus = null;
    }
  };

  menuButton?.addEventListener('click', () => setNav(!root.classList.contains('nav-open')));
  overlay?.addEventListener('click', () => setNav(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && root?.classList.contains('nav-open')) setNav(false);
  });
  window.addEventListener('resize', () => {
    if (window.innerWidth > 900 && root?.classList.contains('nav-open')) setNav(false);
    sidebar?.setAttribute('aria-hidden', String(window.innerWidth <= 900));
  });

  const syncTheme = () => {
    if (!themeButton) return;
    const dark = document.documentElement.classList.contains('dark');
    themeButton.setAttribute('aria-pressed', String(dark));
    themeButton.setAttribute('aria-label', dark ? 'Use light theme' : 'Use dark theme');
    const glyph = themeButton.querySelector('.theme-glyph');
    if (glyph) {
      glyph.textContent = dark ? '☀' : '☾';
      glyph.setAttribute('aria-hidden', 'true');
    }
  };
  themeButton?.addEventListener('click', () => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const rect = themeButton.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    const applyTheme = () => {
      const dark = document.documentElement.classList.toggle('dark');
      localStorage.setItem('ldp-theme', dark ? 'dark' : 'light');
      syncTheme();
    };

    if (document.startViewTransition && !reduceMotion) {
      const transition = document.startViewTransition(applyTheme);
      transition.ready.then(() => {
        document.documentElement.animate(
          { clipPath: [`circle(0 at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 520, easing: 'cubic-bezier(.22,.75,.2,1)', pseudoElement: '::view-transition-new(root)' }
        );
      }).catch(() => {});
    } else {
      document.documentElement.classList.add('theme-changing');
      applyTheme();
      window.setTimeout(() => document.documentElement.classList.remove('theme-changing'), reduceMotion ? 0 : 320);
    }
  });
  syncTheme();

  const path = window.location.pathname;
  document.querySelectorAll('.app-nav-link[href]').forEach((link) => {
    const target = new URL(link.href, window.location.origin).pathname;
    const active = target === '/dashboard/' ? path === target : path.startsWith(target);
    if (active) {
      link.classList.add('is-active');
      link.setAttribute('aria-current', 'page');
    }
  });
})();
