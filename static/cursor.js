/* ARAVIX · CONTROL DECK — cursor + magnetic interactions
   Custom cursor trail, magnetic button pull, scroll-triggered
   entrance orchestrator, and smooth parallax for depth layers.
   Reduced-motion → no cursor trail, instant reveals. */

(function () {
  'use strict';

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) return;

  /* ── Custom cursor ring + trail ──────────────────────────────── */
  var ring = document.createElement('div');
  ring.className = 'cursor-ring';
  var trail = document.createElement('div');
  trail.className = 'cursor-trail';
  document.body.appendChild(trail);
  document.body.appendChild(ring);

  var cx = -100, cy = -100, tx = -100, ty = -100;
  var raf = null;

  function updateCursor() {
    cx += (tx - cx) * 0.12;
    cy += (ty - cy) * 0.12;
    ring.style.transform = 'translate(' + (tx - 18) + 'px,' + (ty - 18) + 'px)';
    trail.style.transform = 'translate(' + (cx - 4) + 'px,' + (cy - 4) + 'px)';
    raf = null;
  }

  document.addEventListener('pointermove', function (e) {
    tx = e.clientX;
    ty = e.clientY;
    if (!raf) raf = requestAnimationFrame(updateCursor);
  }, { passive: true });

  /* grow cursor on interactive targets */
  document.addEventListener('pointerover', function (e) {
    var t = e.target;
    if (t.closest('a, button, .toggle, .settings-card, .server-card, .st-card, .btn')) {
      ring.classList.add('cursor-hover');
      trail.classList.add('cursor-hover');
    }
  }, true);
  document.addEventListener('pointerout', function (e) {
    var t = e.target;
    if (t.closest('a, button, .toggle, .settings-card, .server-card, .st-card, .btn')) {
      ring.classList.remove('cursor-hover');
      trail.classList.remove('cursor-hover');
    }
  }, true);

  /* hide on touch devices */
  if ('ontouchstart' in window) {
    ring.style.display = 'none';
    trail.style.display = 'none';
  }

  /* ── Magnetic buttons ────────────────────────────────────────── */
  var magnetics = document.querySelectorAll('.btn-discord, .btn-primary, .brand-tile');
  magnetics.forEach(function (el) {
    var str = 0.3;
    if (el.classList.contains('brand-tile')) str = 0.15;
    el.addEventListener('pointermove', function (e) {
      var r = el.getBoundingClientRect();
      var dx = (e.clientX - r.left - r.width / 2) * str;
      var dy = (e.clientY - r.top - r.height / 2) * str;
      el.style.transition = 'transform 150ms cubic-bezier(.2,.7,.2,1)';
      el.style.transform = 'translate(' + dx.toFixed(2) + 'px,' + dy.toFixed(2) + 'px)';
    });
    el.addEventListener('pointerleave', function () {
      el.style.transition = 'transform .5s cubic-bezier(.2,.7,.2,1)';
      el.style.transform = '';
    });
  });

  /* ── Scroll-driven entrance orchestrator ────────────────────────
     Elements with .reveal-in get a staggered slide-up when they
     enter the viewport.  The hero section uses a class toggle on
     the <body> for the initial load sequence. */
  document.documentElement.classList.add('js');

  /* hero load sequence */
  var hero = document.querySelector('.login-hero');
  if (hero) {
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        document.body.classList.add('hero-loaded');
      });
    });
  }

  /* section scroll reveals */
  var reveals = document.querySelectorAll('.reveal-in');
  if (reveals.length && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('revealed');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.06, rootMargin: '0px 0px -8% 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add('revealed'); });
  }

  /* ── Parallax depth layers ──────────────────────────────────────
     .parallax-layer elements get their Y offset driven by scroll
     position multiplied by their data-speed attribute. */
  var layers = document.querySelectorAll('.parallax-layer');
  if (layers.length) {
    var ticking = false;
    window.addEventListener('scroll', function () {
      if (!ticking) {
        ticking = requestAnimationFrame(function () {
          ticking = false;
          var scrollY = window.pageYOffset;
          layers.forEach(function (l) {
            var speed = parseFloat(l.dataset.speed) || 0.1;
            l.style.transform = 'translateY(' + (scrollY * speed).toFixed(1) + 'px)';
          });
        });
      }
    }, { passive: true });
  }

  /* ── Scan-line sweep on the hero ─────────────────────────────── */
  var scanLine = document.querySelector('.hero-scan-line');
  if (scanLine) {
    var scanT = 0;
    function scanFrame() {
      scanT += 0.008;
      var y = (Math.sin(scanT) * 0.5 + 0.5) * 100;
      scanLine.style.top = y + '%';
      requestAnimationFrame(scanFrame);
    }
    requestAnimationFrame(scanFrame);
  }

  /* ── Animated counter for numbers ────────────────────────────── */
  var counters = document.querySelectorAll('[data-count]');
  if (counters.length && 'IntersectionObserver' in window) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        var target = parseInt(el.dataset.count, 10);
        if (isNaN(target)) return;
        var dur = 1200;
        var start = performance.now();
        function tick(now) {
          var p = Math.min((now - start) / dur, 1);
          var ease = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(target * ease);
          if (p < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        cio.unobserve(el);
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { cio.observe(el); });
  }

  /* ── Tilt depth on hover for .hover-tilt elements ────────────── */
  var tiltEls = document.querySelectorAll('.hover-tilt');
  tiltEls.forEach(function (el) {
    el.addEventListener('pointermove', function (e) {
      var r = el.getBoundingClientRect();
      var px = (e.clientX - r.left) / r.width - 0.5;
      var py = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = 'perspective(600px) rotateX(' + (-py * 8).toFixed(2) + 'deg) rotateY(' + (px * 8).toFixed(2) + 'deg) scale(1.01)';
    });
    el.addEventListener('pointerleave', function () {
      el.style.transition = 'transform .5s cubic-bezier(.2,.7,.2,1)';
      el.style.transform = '';
      setTimeout(function () { el.style.transition = ''; }, 500);
    });
  });

})();
