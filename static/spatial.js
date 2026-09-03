/* ARAVIX · CONTROL DECK — spatial engines (React Bits ports)
   SpotlightCard tracking · TiltedCard spring tilt · Stack deck.
   CSS lives in style.css (Spatial UI section); chrome-only
   micro-interactions live in app.js. Loaded after app.js on every
   page because only these engines touch .server-card, .settings-card
   and #login-stack. */

(function () {
  'use strict';

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── SpotlightCard — one delegated tracker ────────────────────
     A single rAF-throttled pointermove keeps --mx/--my fresh for
     every card that renders a cursor-following glow — .server-card
     (.tilt-glare) and .settings-card (::after spotlight) — instead
     of separate per-card listeners per mechanism. */

  if ('PointerEvent' in window) {
    let raf = null;
    document.addEventListener('pointermove', e => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = null;
        const el = e.target && e.target.closest
          ? e.target.closest('.server-card, .settings-card')
          : null;
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100).toFixed(1) + '%');
        el.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100).toFixed(1) + '%');
      });
    }, { passive: true });
  }

  /* ── TiltedCard — spring tilt (server cards) ──────────────────
     Pointer targets feed a small spring loop (exponential easing)
     instead of instant jumps, so the card rotates and settles with
     weight. The glare vars --mx/--my are owned by the spotlight
     tracker above; this engine only drives rotation. */

  const tiltables = document.querySelectorAll('.tilt, .server-card');
  if (!reduced && tiltables.length) {
    const AMP_X = 9;   // rotateX amplitude (deg)
    const AMP_Y = 11;  // rotateY amplitude (deg)
    const SPRING = 0.16;

    tiltables.forEach(el => {
      const s = { cx: 0, cy: 0, tx: 0, ty: 0, raf: 0, hover: false };

      function frame() {
        s.cx += (s.tx - s.cx) * SPRING;
        s.cy += (s.ty - s.cy) * SPRING;
        el.style.transition = 'none';
        el.style.transform =
          'perspective(900px) rotateX(' + s.cx.toFixed(2) + 'deg) rotateY(' +
          s.cy.toFixed(2) + 'deg) translateY(-4px)';
        const converged =
          Math.abs(s.cx - s.tx) < 0.03 && Math.abs(s.cy - s.ty) < 0.03;
        if (!converged) { s.raf = requestAnimationFrame(frame); return; }
        s.raf = 0;
        if (s.hover) return;              // hold the tilt while the cursor stays
        el.style.transition =
          'transform .45s cubic-bezier(.2,.7,.2,1), box-shadow .3s ease, border-color .3s';
        el.style.transform = '';
        el.style.setProperty('--rx', '0deg');
        el.style.setProperty('--ry', '0deg');
      }

      el.addEventListener('pointermove', e => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;   // 0..1
        const py = (e.clientY - r.top) / r.height;   // 0..1
        s.tx = (0.5 - py) * AMP_X;
        s.ty = (px - 0.5) * AMP_Y;
        if (!s.raf) s.raf = requestAnimationFrame(frame);
      });
      el.addEventListener('pointerenter', () => {
        s.hover = true;
        if (!s.raf) s.raf = requestAnimationFrame(frame);
      });
      el.addEventListener('pointerleave', () => {
        s.hover = false;
        s.tx = 0;
        s.ty = 0;
        if (!s.raf) s.raf = requestAnimationFrame(frame);
      });
    });
  }

  /* ── Stack — React Bits Stack port (login module deck) ─────────
     Cards live bottom→top in the DOM; the front card is the last
     child. Deeper cards fan behind it. Dragging the front card past
     a threshold (or clicking it) sends it to the back; autoplay
     rotates the deck unless hovered or reduced-motion. */

  const stackZone = document.getElementById('login-stack');
  if (stackZone) {
    const cards = Array.from(stackZone.querySelectorAll('.st-card'));
    if (cards.length > 1) {
      let hovering = false;
      let timer = null;
      let drag = null;

      function render() {
        const n = cards.length;
        const staticMode = reduced || stackZone.classList.contains('st-static');
        cards.forEach((card, i) => {
          const depth = n - 1 - i;                    // 0 = front
          card.style.zIndex = String(i + 1);
          if (staticMode) {
            const rot = depth === 0 ? 0 : (depth % 2 ? -3.4 : 3.4) * depth;
            card.style.transform =
              'translate(' + (depth % 2 ? 9 : -9) * depth + 'px,' + depth * 10 + 'px)' +
              ' rotate(' + rot + 'deg)';
            card.style.opacity = '';
            card.style.cursor = depth === 0 ? 'pointer' : 'default';
            return;
          }
          card.style.cursor = depth === 0 ? 'grab' : 'default';
          const rot = depth === 0 ? 0 : (depth % 2 ? 1 : -1) * depth * 2.2;
          const ty = depth * 9;
          const tx = (depth % 2 ? 1 : -1) * depth * 7;
          card.style.transform =
            'translate(' + tx + 'px,' + ty + 'px) rotate(' + rot + 'deg)';
          card.style.opacity = String(Math.max(1 - depth * 0.16, 0.45));
        });
      }

      function sendToBack(card) {
        const i = cards.indexOf(card);
        if (i < 0) return;
        // keep the array in sync with the DOM — both run bottom→top,
        // front card last. Rotating sends the front card to the bottom.
        cards.splice(i, 1);
        cards.unshift(card);
        stackZone.insertBefore(card, stackZone.firstChild);
        render();
      }

      function schedule() {
        if (timer) clearTimeout(timer);
        timer = setTimeout(tick, 3600);
      }

      function tick() {
        timer = null;
        // decide at fire time: hover, drag, hidden tabs and reduced
        // motion all pause, but the next wake simply re-arms.
        if (!reduced && !hovering && !drag && !document.hidden) {
          sendToBack(cards[cards.length - 1]);
        }
        schedule();
      }

      function topCard() { return cards[cards.length - 1]; }

      let gestureMoved = false;
      cards.forEach(c => c.addEventListener('click', () => {
        if (drag || gestureMoved) return;
        if (c === topCard()) sendToBack(c);
      }));

      if (reduced) {
        stackZone.classList.add('st-static');
        render();
      } else {
        stackZone.addEventListener('pointerdown', e => {
          gestureMoved = false;
          if (drag || e.button !== 0) return;
          const card = topCard();
          if (card !== e.target.closest('.st-card')) return;
          drag = {
            card: card,
            x: e.clientX,
            y: e.clientY,
            dx: 0,
            dy: 0
          };
          card.classList.add('is-drag');
          card.style.transition = 'none';
          if (card.setPointerCapture) { try { card.setPointerCapture(e.pointerId); } catch (_) {} }
          schedule();
        });

        stackZone.addEventListener('pointermove', e => {
          if (!drag) return;
          drag.dx = e.clientX - drag.x;
          drag.dy = e.clientY - drag.y;
          if (Math.abs(drag.dx) > 5 || Math.abs(drag.dy) > 5) gestureMoved = true;
          drag.card.style.transform =
            'translate(' + drag.dx + 'px,' + drag.dy + 'px) rotate(' + (drag.dx * 0.08).toFixed(1) + 'deg)';
        });

        function endDrag() {
          if (!drag) return;
          const card = drag.card;
          const d = drag;
          drag = null;
          card.classList.remove('is-drag');
          card.style.transition = '';
          if (Math.abs(d.dx) > 80 || Math.abs(d.dy) > 70) sendToBack(card);
          else render();
          schedule();
        }
        stackZone.addEventListener('pointerup', endDrag);
        stackZone.addEventListener('pointercancel', endDrag);
      }

      stackZone.addEventListener('mouseenter', () => { hovering = true; if (timer) { clearTimeout(timer); timer = null; } });
      stackZone.addEventListener('mouseleave', () => { hovering = false; schedule(); });

      render();
      schedule();
    }
  }
})();
