/* ARAVIX · CONTROL DECK — core chrome micro-interactions
   JS-ready marker · scroll reveal · mobile sidebar · login-cube
   parallax · breadcrumb shortening.
   Spatial engines (tilt / spotlight / stack) live in spatial.js. */

(function () {
  'use strict';

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Mark JS as available for entrance animations */
  document.documentElement.classList.add('js');

  /* ── Scroll reveal ──────────────────────────────────────────── */
  const rvs = document.querySelectorAll('.rv');
  if (rvs.length && 'IntersectionObserver' in window && !reduced) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if (en.isIntersecting) {
          en.target.classList.add('in');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -6% 0px' });
    rvs.forEach(el => io.observe(el));
  } else {
    rvs.forEach(el => el.classList.add('in'));
  }

  /* ── Mobile sidebar ─────────────────────────────────────────── */
  const menuBtn = document.getElementById('menu-btn');
  const sidebar = document.getElementById('sidebar');
  const scrim = document.getElementById('nav-scrim');

  function setMenu(open) {
    if (!sidebar || !menuBtn || !scrim) return;
    sidebar.classList.toggle('open', open);
    scrim.classList.toggle('show', open);
    menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuBtn.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    document.body.style.overflow = open ? 'hidden' : '';
  }

  if (menuBtn && sidebar && scrim) {
    menuBtn.addEventListener('click', () =>
      setMenu(!sidebar.classList.contains('open')));
    scrim.addEventListener('click', () => setMenu(false));
    // close when a nav link is chosen
    sidebar.querySelectorAll('a').forEach(a =>
      a.addEventListener('click', () => setMenu(false)));
    window.addEventListener('keydown', e => {
      if (e.key === 'Escape') setMenu(false);
    });
    // keep it in sync if the viewport grows back to desktop
    window.addEventListener('resize', () => {
      if (window.innerWidth > 960) setMenu(false);
    });
  }

  /* ── Login cube: gentle pointer parallax ────────────────────── */
  const scene = document.getElementById('cube-scene');
  if (scene && !reduced) {
    const wrap = scene.querySelector('.cube-wrap');
    let raf = null;
    scene.addEventListener('pointermove', e => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        const r = scene.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        if (wrap) {
          wrap.style.transform =
            'rotateX(' + (-py * 10).toFixed(2) + 'deg) rotateY(' + (px * 14).toFixed(2) + 'deg)';
          wrap.style.transition = 'transform 120ms linear';
        }
        raf = null;
      });
    });
    scene.addEventListener('pointerleave', () => {
      if (wrap) {
        wrap.style.transition = 'transform .6s cubic-bezier(.2,.7,.2,1)';
        wrap.style.transform = '';
      }
    });
  }

  /* ── Breadcrumb: shorten deep paths so they never wrap ──────── */
  const crumb = document.getElementById('page-crumb');
  if (crumb) {
    const parts = window.location.pathname.split('/').filter(Boolean);
    let label;
    if (parts.length >= 3) {
      label = parts[0] + ' / … / ' + parts[parts.length - 1];
    } else if (parts.length) {
      label = parts.join(' / ');
    } else {
      label = 'index';
    }
    crumb.textContent = label.replace(/-/g, ' ').toUpperCase();
    crumb.title = window.location.pathname.replace(/-/g, ' ');
  }
})();
