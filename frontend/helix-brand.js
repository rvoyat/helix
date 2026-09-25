/* ═══════════════════════════════════════════════════════════════════
   HELIX Brand — logo, particles, theme
   ═══════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── Logo SVG (heart + ECG) ──────────────────────────────────────── */
  function logoSVG(w, h) {
    w = w || 36; h = h || 32;
    return `<svg class="logo-icon" viewBox="0 0 48 44" width="${w}" height="${h}"
      xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="hx-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#A100FF" stop-opacity="0.20"/>
          <stop offset="100%" stop-color="#00C9FF" stop-opacity="0.20"/>
        </linearGradient>
        <linearGradient id="hx-stroke" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#A100FF"/>
          <stop offset="100%" stop-color="#00C9FF"/>
        </linearGradient>
      </defs>
      <!-- Heart -->
      <path d="M24 40 C24 40 3 26 3 13.5
               C3 7.5 7.5 3.5 12.5 3.5
               C16.5 3.5 20 6 24 11
               C28 6 31.5 3.5 35.5 3.5
               C40.5 3.5 45 7.5 45 13.5
               C45 26 24 40 24 40Z"
        fill="url(#hx-fill)" stroke="url(#hx-stroke)" stroke-width="1.6"/>
      <!-- ECG waveform -->
      <polyline
        points="3,22 11,22 14,22 16,9 18.5,32 20.5,4 22.5,35 24.5,22 30,22 45,22"
        fill="none" stroke="url(#hx-stroke)"
        stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
  }

  /* ── Replace .logo contents with new brand mark ─────────────────── */
  function initLogo() {
    document.querySelectorAll('.logo').forEach(function (el) {
      var isLogin = el.classList.contains('logo-login') ||
                    el.closest('header') && document.querySelector('main .login-wrapper');
      var svgSize = isLogin ? [42, 38] : [36, 32];
      el.innerHTML =
        logoSVG(svgSize[0], svgSize[1]) +
        '<div class="logo-text-block">' +
          '<span class="logo-mark-new">HELIX</span>' +
          '<span class="logo-sub-brand">Accenture Health</span>' +
        '</div>';
    });
  }

  /* ── Particle canvas ─────────────────────────────────────────────── */
  function initParticles() {
    var canvas = document.createElement('canvas');
    canvas.id = 'helix-canvas';
    document.body.insertBefore(canvas, document.body.firstChild);
    var ctx = canvas.getContext('2d');
    var W, H, particles;
    var COUNT = 55;

    function isLight() {
      return document.documentElement.classList.contains('light');
    }

    function resize() {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
    }

    function Particle(spread) {
      this.reset(spread);
    }

    Particle.prototype.reset = function (spread) {
      this.x   = Math.random() * W;
      this.y   = spread ? Math.random() * H : H + 20 + Math.random() * 80;
      this.vy  = -(0.2 + Math.random() * 0.6);
      this.r   = 0.7 + Math.random() * 1.9;
      this.maxA = isLight()
        ? 0.06 + Math.random() * 0.14
        : 0.18 + Math.random() * 0.40;
      this.alpha = 0;
      this.purple = Math.random() < 0.55;
    };

    Particle.prototype.tick = function () {
      this.y += this.vy;
      var prog = 1 - (this.y / H);
      this.alpha = this.maxA *
        Math.min(prog * 5, 1) *
        Math.min((1 - prog) * 5, 1);
      if (this.y < -12) this.reset(false);
    };

    Particle.prototype.draw = function () {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, 6.2832);
      ctx.fillStyle = this.purple
        ? 'rgba(161,0,255,' + this.alpha + ')'
        : 'rgba(0,201,255,'  + this.alpha + ')';
      ctx.fill();
    };

    function setup() {
      resize();
      particles = [];
      for (var i = 0; i < COUNT; i++) {
        particles.push(new Particle(true));
      }
    }

    function loop() {
      ctx.clearRect(0, 0, W, H);
      for (var i = 0; i < particles.length; i++) {
        particles[i].tick();
        particles[i].draw();
      }
      requestAnimationFrame(loop);
    }

    window.addEventListener('resize', function () {
      resize();
      for (var i = 0; i < particles.length; i++) {
        particles[i].reset(true);
      }
    });

    setup();
    loop();
  }

  /* ── Theme ───────────────────────────────────────────────────────── */
  var THEME_KEY = 'helix_theme';

  function applyTheme(theme) {
    if (theme === 'light') {
      document.documentElement.classList.add('light');
    } else {
      document.documentElement.classList.remove('light');
    }
    document.querySelectorAll('.theme-toggle').forEach(function (btn) {
      btn.textContent = theme === 'light' ? '🌙' : '☀️';
      btn.title = theme === 'light' ? 'Tema scuro' : 'Tema chiaro';
    });
  }

  function initTheme() {
    var saved = localStorage.getItem(THEME_KEY) || 'dark';
    applyTheme(saved);
  }

  function toggleTheme() {
    var current = document.documentElement.classList.contains('light') ? 'light' : 'dark';
    var next = current === 'light' ? 'dark' : 'light';
    applyTheme(next);
    localStorage.setItem(THEME_KEY, next);
    // Persist to backend silently
    var token = localStorage.getItem('helix_token');
    if (token) {
      var base = (typeof API_BASE !== 'undefined') ? API_BASE : 'http://localhost:8092';
      fetch(base + '/auth/me', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ theme: next })
      }).catch(function () {});
    }
  }

  /* Called after auth check — sync theme from server profile */
  window.helixApplyUserTheme = function (user) {
    if (user && user.theme) {
      localStorage.setItem(THEME_KEY, user.theme);
      applyTheme(user.theme);
    }
  };

  /* ── Inject theme toggle button ──────────────────────────────────── */
  function injectThemeToggle() {
    var btn = document.createElement('button');
    btn.className = 'theme-toggle';
    btn.onclick = toggleTheme;

    // Try header-right first (app pages)
    var right = document.querySelector('.header-right');
    if (right) {
      right.insertBefore(btn, right.firstChild);
      return;
    }
    // Login page: append to header
    var hdr = document.querySelector('header');
    if (hdr) {
      btn.style.marginLeft = 'auto';
      hdr.appendChild(btn);
    }
  }

  /* ── DOMContentLoaded boot ───────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();    // apply before render to avoid flicker
    initLogo();
    initParticles();
    injectThemeToggle();
    applyTheme(localStorage.getItem(THEME_KEY) || 'dark'); // update button icon
  });

})();
