/* ════════════════════════════════════════════════════════════════
   Effects Lab — React Bits components ported to vanilla JS.
   MorphSlider (real WebGL displacement engine via ogl CDN) ·
   AnimatedList · Dock · AnimatedContent. Each feature degrades to
   a readable static state if a dependency fails to load.
   ════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const CDN = {
    // deep, versioned URL — avoids esm.sh's shim hop, which flakes
    ogl: 'https://esm.sh/ogl@1.0.11/es2022/ogl.mjs'
  };

  /* easing curves (ported from GSAP's common eases) */
  const EASES = {
    'power2.inOut': t => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    'power2.out': t => 1 - Math.pow(1 - t, 2),
    'power3.out': t => 1 - Math.pow(1 - t, 3),
    'power3.in': t => t * t * t
  };

  let oglLib = null;

  async function loadOgl() {
    if (oglLib) return oglLib;
    oglLib = await import(/* webpackIgnore: true */ CDN.ogl).catch(() => null);
    return oglLib;
  }

  /* Wall-clock stepper with an interval watchdog: even if rAF is
     throttled (background tabs, sleepy compositors) the tween still
     completes. Progress = eased elapsed time, matching the gsap
     curves used by the original component. */
  function tweenTo(target, prop, from, to, duration, easeName, onComplete) {
    const durMs = Math.max(duration, 0.05) * 1000;
    const easeFn = EASES[easeName] || EASES['power2.inOut'];
    const start = performance.now();
    let latest = start;
    let done = false;
    let raf = 0;
    let interval = null;

    const finish = () => {
      if (done) return;
      done = true;
      cancelAnimationFrame(raf);
      clearInterval(interval);
      if (onComplete) onComplete();
    };

    const step = now => {
      latest = now;
      const t = Math.min((now - start) / durMs, 1);
      target[prop] = from + (to - from) * easeFn(t);
      if (t < 1) raf = requestAnimationFrame(step);
      else finish();
    };

    raf = requestAnimationFrame(step);
    // watchdog — step manually if rAF is being throttled
    interval = setInterval(() => {
      if (!done && performance.now() - latest > 90) step(performance.now());
      else if (done) clearInterval(interval);
    }, 40);
  }

  /* ── Generated local slide art (SVG data URIs: always load, no CORS) ── */
  function artUri(stops, accent) {
    const circles = accent
      .map((c, i) => `<circle cx="${15 + i * 26}" cy="${40 + (i % 2) * 34}" r="${46 - i * 6}" fill="${c}"/>`)
      .join('');
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">` +
      `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
      `<stop offset="0" stop-color="${stops[0]}"/><stop offset="1" stop-color="${stops[1]}"/></linearGradient>` +
      `<radialGradient id="h" cx=".5" cy=".35" r=".8"><stop offset="0" stop-color="rgba(255,255,255,.16)"/><stop offset="1" stop-color="rgba(255,255,255,0)"/></radialGradient></defs>` +
      `<rect width="1600" height="900" fill="url(#g)"/>` +
      `<rect width="1600" height="900" fill="url(#h)"/>` +
      circles +
      `<rect width="1600" height="900" fill="none" stroke="rgba(255,255,255,.05)" stroke-width="2"/>` +
      `</svg>`;
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  const MORPH_ITEMS = [
    { caption: 'Moderation', image: artUri(['#3a3f8f', '#181b42'], ['rgba(255,255,255,.10)', 'rgba(170,176,255,.14)', 'rgba(255,255,255,.06)']) },
    { caption: 'Games & Fun', image: artUri(['#0e4a52', '#0a232e'], ['rgba(111,211,232,.18)', 'rgba(255,255,255,.08)', 'rgba(53,224,168,.12)']) },
    { caption: 'Tickets & Music', image: artUri(['#4a2a5e', '#1d1230'], ['rgba(255,139,167,.14)', 'rgba(168,120,255,.18)', 'rgba(255,255,255,.07)']) },
    { caption: 'Economy', image: artUri(['#3f4a20', '#141d0d'], ['rgba(53,224,168,.16)', 'rgba(255,196,107,.12)', 'rgba(255,255,255,.06)']) }
  ];

  /* ══════════════════════════ MorphSlider ══════════════════════════
     Port of the React Bits MorphSlider (ogl engine, MIT). */
  const VERT = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}`;

  const FRAG = `
precision highp float;

uniform sampler2D tCurrent;
uniform sampler2D tNext;
uniform vec2 uResolution;
uniform vec2 uCurrentSize;
uniform vec2 uNextSize;
uniform float uProgress;
uniform float uDir;
uniform int uMode;
uniform float uIntensity;
uniform float uScale;
uniform float uAberration;
uniform float uDrift;
uniform float uTime;
uniform float uReduce;
uniform vec2 uPointer;
uniform vec3 uOverlay;

varying vec2 vUv;

const float PI = 3.14159265359;

float hash11(float p) {
  p = fract(p * 0.1031);
  p *= p + 33.33;
  p *= p + p;
  return fract(p);
}

float hash21(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.0;
    a *= 0.5;
  }
  return v;
}

mat2 rot(float a) {
  float s = sin(a);
  float c = cos(a);
  return mat2(c, -s, s, c);
}

vec2 coverUV(vec2 uv, vec2 res, vec2 img) {
  float rA = res.x / max(res.y, 1.0);
  float iA = img.x / max(img.y, 1.0);
  vec2 s = vec2(1.0);
  float ratio = rA / max(iA, 0.0001);
  if (ratio > 1.0) {
    s.y = 1.0 / ratio;
  } else {
    s.x = ratio;
  }
  return (uv - 0.5) * s + 0.5;
}

void main() {
  float p = clamp(uProgress, 0.0, 1.0);
  float env = sin(p * PI);

  vec2 uv = vUv;

  uv += vec2(sin(uTime * 0.25 + uv.y * 4.0), cos(uTime * 0.22 + uv.x * 4.0)) * uDrift * 0.008;
  uv = (uv - 0.5) * (1.0 - uDrift * 0.02 * sin(uTime * 0.4)) + 0.5;

  vec2 uvC = uv;
  vec2 uvN = uv;
  float m = smoothstep(0.0, 1.0, p);

  if (uReduce < 0.5) {
    if (uMode == 3) {
      vec2 c = uv - 0.5;
      float r = length(c);
      float ang = env * uIntensity * 3.5 * (1.0 - r);
      uvC = rot(ang) * c + 0.5;
      uvN = rot(-ang) * c + 0.5;
      m = smoothstep(0.0, 1.0, p);
    } else if (uMode == 1) {
      float d = distance(uv, uPointer);
      float ring = p * 1.6;
      float wave = sin((d - ring) * 30.0) * env;
      vec2 dir = normalize(uv - uPointer + 1e-4);
      vec2 disp = dir * wave * uIntensity * 0.25;
      uvC = uv + disp;
      uvN = uv + disp * 0.6;
      m = 1.0 - smoothstep(ring - 0.03, ring + 0.03, d);
    } else if (uMode == 2) {
      float slices = 14.0;
      float row = floor(uv.y * slices);
      float rnd = hash11(row);
      vec2 disp = vec2((rnd - 0.5) * env * uIntensity * 0.6, 0.0);
      uvC = uv + disp;
      uvN = uv + disp;
      float localX = uDir > 0.0 ? uv.x : 1.0 - uv.x;
      float th = p * 1.5 - 0.25 + (rnd - 0.5) * 0.25;
      m = 1.0 - smoothstep(th - 0.06, th + 0.06, localX);
    } else {
      float nn = fbm(uv * uScale + uTime * 0.03);
      float warp = fbm(uv * uScale * 1.7 - uTime * 0.02);
      vec2 g = vec2(nn, warp) - 0.5;
      uvC = uv + g * uIntensity * 0.5 * p;
      uvN = uv - g * uIntensity * 0.5 * (1.0 - p);
      m = smoothstep(nn - 0.15, nn + 0.15, p);
    }
  }

  vec2 sC = coverUV(uvC, uResolution, uCurrentSize);
  vec2 sN = coverUV(uvN, uResolution, uNextSize);

  float ca = uReduce < 0.5 ? uAberration * env * 0.03 : 0.0;

  vec3 colC = vec3(
    texture2D(tCurrent, sC + vec2(ca, 0.0)).r,
    texture2D(tCurrent, sC).g,
    texture2D(tCurrent, sC - vec2(ca, 0.0)).b
  );
  vec3 colN = vec3(
    texture2D(tNext, sN + vec2(ca, 0.0)).r,
    texture2D(tNext, sN).g,
    texture2D(tNext, sN - vec2(ca, 0.0)).b
  );

  vec3 col = mix(colC, colN, m);

  float vig = smoothstep(1.25, 0.25, length(uv - 0.5));
  col = mix(col, uOverlay, (1.0 - vig) * 0.28);

  gl_FragColor = vec4(col, 1.0);
}`;

  const MODES = { melt: 0, ripple: 1, shear: 2, swirl: 3 };

  function makeFallbackTexture(gl, Texture) {
    const size = 4;
    const data = new Uint8Array(size * size * 4);
    for (let i = 0; i < size * size; i++) {
      data[i * 4] = 20; data[i * 4 + 1] = 20; data[i * 4 + 2] = 26; data[i * 4 + 3] = 255;
    }
    return new Texture(gl, { image: data, width: size, height: size, generateMipmaps: false });
  }

  function hexToRgb(hex) {
    let h = String(hex || '#000000').replace('#', '');
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    const n = parseInt(h, 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }

  class MorphEngine {
    constructor(container, items, opts, onIndexChange, ogl) {
      const { Renderer, Triangle, Program, Mesh, Texture } = ogl;
      this.container = container;
      this.items = items;
      this.opts = opts;
      this.onIndexChange = onIndexChange;
      this.current = opts.startIndex || 0;
      this.shownIndex = this.current;
      this.animating = false;
      this.dragging = false;
      this.dragDir = 0;
      this.destroyed = false;

      this.renderer = new Renderer({
        alpha: false,
        antialias: true,
        dpr: Math.min(window.devicePixelRatio || 1, 2)
      });
      this.gl = this.renderer.gl;
      this.gl.clearColor(0.05, 0.05, 0.06, 1);
      this.canvas = this.gl.canvas;
      this.canvas.className = 'morph-slider-canvas';
      container.appendChild(this.canvas);

      this.geometry = new Triangle(this.gl);
      this.textures = items.map(() => makeFallbackTexture(this.gl, Texture));
      this.sizes = items.map(() => [1, 1]);

      this.program = new Program(this.gl, {
        vertex: VERT,
        fragment: FRAG,
        uniforms: {
          tCurrent: { value: this.textures[this.current] },
          tNext: { value: this.textures[this.current] },
          uResolution: { value: [1, 1] },
          uCurrentSize: { value: this.sizes[this.current] },
          uNextSize: { value: this.sizes[this.current] },
          uProgress: { value: 0 },
          uDir: { value: 1 },
          uMode: { value: MODES[opts.transition] ?? 0 },
          uIntensity: { value: opts.intensity },
          uScale: { value: opts.scale },
          uAberration: { value: opts.aberration },
          uDrift: { value: opts.drift },
          uTime: { value: 0 },
          uReduce: { value: reducedMotion ? 1 : 0 },
          uPointer: { value: [0.5, 0.5] },
          uOverlay: { value: hexToRgb(opts.overlayColor) }
        }
      });
      this.mesh = new Mesh(this.gl, { geometry: this.geometry, program: this.program });

      this.ro = new ResizeObserver(() => this.resize());
      this.ro.observe(container);
      this.resize();

      this.loadTextures();
      this.raf = requestAnimationFrame(this.loop.bind(this));
    }

    loadTextures() {
      this.items.forEach((item, i) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.src = item.image;
        img.onload = () => {
          if (this.destroyed) return;
          const texture = new (this.textures[i].constructor)(this.gl, { generateMipmaps: false });
          texture.image = img;
          this.textures[i] = texture;
          this.sizes[i] = [img.naturalWidth || 1, img.naturalHeight || 1];
          if (i === this.current) {
            this.program.uniforms.tCurrent.value = texture;
            this.program.uniforms.uCurrentSize.value = this.sizes[i];
          }
        };
      });
    }

    resize() {
      const rect = this.container.getBoundingClientRect();
      const w = Math.max(rect.width, 1);
      const h = Math.max(rect.height, 1);
      this.renderer.setSize(w, h);
      this.program.uniforms.uResolution.value = [this.canvas.width, this.canvas.height];
    }

    syncOptions() {
      const o = this.opts;
      this.program.uniforms.uMode.value = MODES[o.transition] ?? 0;
      this.program.uniforms.uIntensity.value = o.intensity;
      this.program.uniforms.uScale.value = o.scale;
      this.program.uniforms.uAberration.value = o.aberration;
      this.program.uniforms.uDrift.value = o.drift;
      this.program.uniforms.uOverlay.value = hexToRgb(o.overlayColor);
    }

    loop(t) {
      if (this.destroyed) return;
      this.program.uniforms.uTime.value = t * 0.001;
      if (!this.dragging && !this.animating) this.syncOptions();
      this.renderer.render({ scene: this.mesh });
      this.raf = requestAnimationFrame(this.loop.bind(this));
    }

    wrap(i) {
      const n = this.items.length;
      return ((i % n) + n) % n;
    }

    prepareNext(dir) {
      const target = this.wrap(this.current + dir);
      this.program.uniforms.tCurrent.value = this.textures[this.current];
      this.program.uniforms.uCurrentSize.value = this.sizes[this.current];
      this.program.uniforms.tNext.value = this.textures[target];
      this.program.uniforms.uNextSize.value = this.sizes[target];
      this.program.uniforms.uDir.value = dir;
      return target;
    }

    goTo(dir) {
      if (this.animating || this.dragging || this.items.length < 2) return;
      const o = this.opts;
      if (!o.loop) {
        const raw = this.current + dir;
        if (raw < 0 || raw > this.items.length - 1) return;
      }
      this.syncOptions();
      const target = this.prepareNext(dir);
      this.animating = true;
      this.announce(target);
      const duration = reducedMotion ? Math.min(o.duration, 0.4) : o.duration;
      tweenTo(this.program.uniforms.uProgress, 'value', 0, 1, duration, o.ease || 'power2.inOut', () => this.commit(target));
    }

    jumpTo(index) {
      if (this.animating || this.dragging || index === this.current) return;
      const n = this.items.length;
      let delta = index - this.current;
      if (!this.opts.loop) {
        if (index < 0 || index > n - 1) return;
        this.goTo(delta > 0 ? 1 : -1);
        return;
      }
      if (Math.abs(delta) > n / 2) delta = delta > 0 ? delta - n : delta + n;
      this.goTo(delta > 0 ? 1 : -1);
    }

    announce(index) {
      if (index === this.shownIndex) return;
      this.shownIndex = index;
      if (this.onIndexChange) this.onIndexChange(index);
    }

    commit(target) {
      this.current = target;
      this.program.uniforms.tCurrent.value = this.textures[target];
      this.program.uniforms.uCurrentSize.value = this.sizes[target];
      this.program.uniforms.uProgress.value = 0;
      this.animating = false;
      this.announce(target);
    }

    next() { this.goTo(1); }
    prev() { this.goTo(-1); }

    setPointer(x, y) { this.program.uniforms.uPointer.value = [x, y]; }

    beginDrag() {
      if (this.animating || this.items.length < 2) return false;
      this.dragging = true;
      this.dragDir = 0;
      this.syncOptions();
      return true;
    }

    drag(ndx) {
      if (!this.dragging) return;
      const o = this.opts;
      const dir = ndx < 0 ? 1 : -1;
      if (!o.loop) {
        const raw = this.current + dir;
        if (raw < 0 || raw > this.items.length - 1) {
          this.program.uniforms.uProgress.value = 0;
          return;
        }
      }
      if (dir !== this.dragDir) {
        this.dragDir = dir;
        this.prepareNext(dir);
      }
      const progress = Math.min(Math.abs(ndx), 1);
      this.program.uniforms.uProgress.value = progress;
      this.announce(progress > 0.5 ? this.wrap(this.current + dir) : this.current);
    }

    endDrag() {
      if (!this.dragging) return;
      this.dragging = false;
      const p = this.program.uniforms.uProgress.value;
      if (this.dragDir === 0) return;
      const target = this.wrap(this.current + this.dragDir);
      if (p > 0.4) {
        this.announce(target);
        this.animating = true;
        tweenTo(this.program.uniforms.uProgress, 'value', p, 1, reducedMotion ? 0.25 : 0.5, 'power2.out', () => this.commit(target));
      } else {
        this.announce(this.current);
        this.animating = true;
        tweenTo(this.program.uniforms.uProgress, 'value', p, 0, reducedMotion ? 0.25 : 0.5, 'power2.out', () => {
          this.animating = false;
        });
      }
    }

    destroy() {
      this.destroyed = true;
      cancelAnimationFrame(this.raf);
      this.ro.disconnect();
      if (this.canvas && this.canvas.parentNode) this.canvas.parentNode.removeChild(this.canvas);
    }
  }

  function createMorphSlider(root, opts) {
    root.classList.add('morph-slider');
    root.innerHTML =
      '<div class="morph-slider-stage" role="group" aria-roledescription="carousel" aria-label="Image morph slider" tabindex="0"></div>' +
      '<div class="morph-slider-caption" aria-live="polite"></div>' +
      '<div class="morph-slider-controls">' +
      '<button type="button" class="morph-slider-btn" aria-label="Previous slide"><svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<button type="button" class="morph-slider-btn" aria-label="Next slide"><svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '</div>' +
      '<div class="morph-slider-indicators" role="tablist" aria-label="Slides"></div>';

    const stage = root.querySelector('.morph-slider-stage');
    const captionEl = root.querySelector('.morph-slider-caption');
    const dotsEl = root.querySelector('.morph-slider-indicators');
    const items = opts.items || MORPH_ITEMS;

    const all = opts;
    const capDelay = (opts.duration * 0.66).toFixed(3) + 's';
    const dotDelay = (opts.duration * 0.45).toFixed(3) + 's';
    root.style.setProperty('--ms-swap', capDelay);
    root.style.setProperty('--ms-dot', dotDelay);

    items.forEach((item, i) => {
      const span = document.createElement('span');
      span.className = 'morph-slider-caption-text';
      span.textContent = item.caption || '';
      captionEl.appendChild(span);
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'morph-slider-dot';
      dot.setAttribute('role', 'tab');
      dot.setAttribute('aria-label', 'Go to slide ' + (i + 1));
      dot.addEventListener('click', () => engine && engine.jumpTo(i));
      dotsEl.appendChild(dot);
    });

    const syncUI = index => {
      captionEl.querySelectorAll('.morph-slider-caption-text').forEach((s, i) => {
        const on = i === index;
        s.classList.toggle('is-active', on);
        s.setAttribute('aria-hidden', on ? 'false' : 'true');
      });
      dotsEl.querySelectorAll('.morph-slider-dot').forEach((d, i) => {
        d.classList.toggle('is-active', i === index);
        d.setAttribute('aria-selected', i === index ? 'true' : 'false');
      });
    };

    let engine = null;
    let hovering = false;
    let autoplayTimer = null;

    function scheduleAutoplay() {
      if (autoplayTimer) clearTimeout(autoplayTimer);
      if (!all.autoplay || hovering || !engine) return;
      autoplayTimer = setTimeout(() => {
        engine.next();
        scheduleAutoplay();
      }, Math.max(all.autoplayDelay, 1) * 1000);
    }

    const prevBtn = root.querySelectorAll('.morph-slider-btn')[0];
    const nextBtn = root.querySelectorAll('.morph-slider-btn')[1];
    prevBtn.addEventListener('click', () => engine && engine.prev());
    nextBtn.addEventListener('click', () => engine && engine.next());

    root.addEventListener('mouseenter', () => { hovering = true; scheduleAutoplay(); });
    root.addEventListener('mouseleave', () => { hovering = false; scheduleAutoplay(); });

    // pointer drag
    let startX = 0, width = 1, active = false;
    stage.addEventListener('pointerdown', e => {
      const rect = root.getBoundingClientRect();
      width = rect.width || 1;
      startX = e.clientX;
      if (engine) {
        engine.setPointer((e.clientX - rect.left) / rect.width, 1 - (e.clientY - rect.top) / rect.height);
        active = engine.beginDrag();
        if (active && stage.setPointerCapture) { try { stage.setPointerCapture(e.pointerId); } catch (_) {} }
      }
    });
    stage.addEventListener('pointermove', e => { if (active && engine) engine.drag((e.clientX - startX) / width); });
    const endDrag = () => { if (active) { active = false; if (engine) engine.endDrag(); } };
    stage.addEventListener('pointerup', endDrag);
    stage.addEventListener('pointercancel', endDrag);

    stage.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { e.preventDefault(); if (engine) engine.next(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); if (engine) engine.prev(); }
    });

    const fallback = () => {
      root.classList.add('is-static');
      root.style.backgroundImage = 'url(' + items[all.startIndex || 0].image + ')';
      prevBtn.disabled = nextBtn.disabled = true;
      dotsEl.style.display = 'none';
    };

    // ogl loads from a CDN — retry a couple of times (backoff) before
    // settling for the static fallback, so one flaky fetch doesn't kill
    // the WebGL experience for the whole visit.
    let attempts = 0;
    function boot() {
      loadOgl().then(l => {
        if (!root.isConnected) return;
        // esm.sh namespaces expose the classes directly (Renderer, …)
        if (!l || !l.Renderer) {
          if (attempts < 2) { attempts++; oglLib = null; setTimeout(boot, 700 * attempts); return; }
          return fallback();
        }
        try {
          engine = new MorphEngine(stage, items, all, index => syncUI(index), l);
          syncUI(all.startIndex || 0);
          scheduleAutoplay();
        } catch (err) {
          console.error('MorphSlider init failed:', err);
          fallback();
        }
      });
    }
    boot();

    return {
      setOption(k, v) { all[k] = v; if (engine) engine.syncOptions(); }
    };
  }

  /* ══════════════════════════ AnimatedList ═══════════════════════ */
  function createAnimatedList(root, items, onSelect) {
    const scroll = root.querySelector('.al-scroll');
    const status = root.querySelector('.lab-status');
    if (!scroll) return;
    let selected = -1;

    scroll.querySelectorAll('.al-item').forEach(item => {
      const idx = Number(item.dataset.index);
      item.querySelector('.al-pop').style.animationDelay = Math.min(idx * 45, 400) + 'ms';
      item.addEventListener('click', () => {
        setSelected(idx, true);
      });
      item.addEventListener('mouseenter', () => setSelected(idx, false));
    });

    function setSelected(idx, notify) {
      selected = idx;
      scroll.querySelectorAll('.al-item').forEach(el => el.classList.toggle('selected', Number(el.dataset.index) === idx));
      const item = items[idx];
      if (status && item) status.innerHTML = 'Selected: <b>$' + item.name + '</b> — ' + item.desc;
      if (notify && onSelect) onSelect(item, idx);
      if (scroll.contains(document.activeElement)) scrollItemIntoView(idx);
    }

    function scrollItemIntoView(idx) {
      const el = scroll.querySelector('[data-index="' + idx + '"]');
      if (!el) return;
      const margin = 60;
      const st = scroll.scrollTop, ch = scroll.clientHeight;
      const top = el.offsetTop, bottom = top + el.offsetHeight;
      if (top < st + margin) scroll.scrollTo({ top: top - margin, behavior: 'smooth' });
      else if (bottom > st + ch - margin) scroll.scrollTo({ top: bottom - ch + margin, behavior: 'smooth' });
    }

    // gradients
    const topG = root.querySelector('.al-gradient.top');
    const bottomG = root.querySelector('.al-gradient.bottom');
    function syncGradients() {
      const { scrollTop, scrollHeight, clientHeight } = scroll;
      if (topG) topG.style.opacity = Math.min(scrollTop / 50, 1);
      if (bottomG) bottomG.style.opacity = scrollHeight <= clientHeight ? 0 : Math.min((scrollHeight - scrollTop - clientHeight) / 50, 1);
    }
    scroll.addEventListener('scroll', syncGradients, { passive: true });
    syncGradients();

    // keyboard (arrows only while the list itself is focused)
    scroll.tabIndex = 0;
    scroll.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(Math.min(selected + 1, items.length - 1), false); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(Math.max(selected - 1, 0), false); }
      else if (e.key === 'Enter') {
        if (selected >= 0) { e.preventDefault(); setSelected(selected, true); }
      }
    });

    setSelected(-1, false);
    // ensure the intro line reads nicely before any pick
    if (status) status.textContent = 'Use ↑ ↓ + Enter, or click a command…';
    if (items.length) setSelected(-1, false);
    return { select: i => setSelected(i, true) };
  }

  /* ══════════════════════════ Dock ══════════════════════════ */
  function createDock(root, items, baseSize, magnification, distance) {
    const panel = root.querySelector('.dock-panel');
    if (!panel) return;
    panel.innerHTML = '';
    items.forEach(item => {
      const a = document.createElement('a');
      a.className = 'dock-item';
      a.href = item.href || '#';
      a.setAttribute('aria-label', item.label);
      a.innerHTML = '<span class="dock-label">' + item.label + '</span>' + item.icon;
      panel.appendChild(a);
    });
    const els = panel.querySelectorAll('.dock-item');

    if (reducedMotion || !window.matchMedia('(pointer: fine)').matches) return;

    let raf = null;
    function magnify(pageX) {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        els.forEach(el => {
          const r = el.getBoundingClientRect();
          const cx = r.left + r.width / 2;
          const d = Math.abs(pageX - cx);
          const t = d <= distance ? baseSize + (magnification - baseSize) * (1 - d / distance) : baseSize;
          el.style.width = Math.round(t) + 'px';
          el.style.height = Math.round(t) + 'px';
        });
        raf = null;
      });
    }
    function reset() {
      els.forEach(el => {
        el.style.width = baseSize + 'px';
        el.style.height = baseSize + 'px';
      });
    }
    root.addEventListener('pointermove', e => magnify(e.pageX));
    root.addEventListener('pointerleave', reset);
    window.addEventListener('blur', reset);
  }

  /* ══════════════════════════ AnimatedContent ═══════════════════════
     Scroll-triggered reveal port: IntersectionObserver + native CSS
     transitions (same data-driven API as the gsap original — direction,
     distance, scale, delay — but immune to rAF throttling). */
  function initReveal() {
    const els = Array.from(document.querySelectorAll('[data-lab-reveal]'));
    if (!els.length || reducedMotion) return;

    els.forEach(el => {
      const horizontal = el.dataset.dir === 'horizontal';
      const reverse = el.dataset.reverse === 'true';
      const distance = Number(el.dataset.distance || 90);
      const scale = Number(el.dataset.scale || 1);
      const duration = Number(el.dataset.duration || 0.8);
      const delay = Number(el.dataset.delay || 0);
      const offset = (reverse ? -1 : 1) * distance;
      const tx = horizontal ? offset : 0;
      const ty = horizontal ? 0 : offset;

      el.style.opacity = '0';
      el.style.transform = 'translate3d(' + tx + 'px,' + ty + 'px,0) scale(' + scale + ')';
      el.style.transition = 'transform ' + duration + 's cubic-bezier(.2,.6,.2,1), opacity ' + duration + 's ease';
      el.style.transitionDelay = delay + 's';
      el.classList.add('lab-reveal');
    });

    if (!('IntersectionObserver' in window)) {
      els.forEach(el => {
        el.style.opacity = '1';
        el.style.transform = 'none';
      });
      return;
    }

    const io = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        el.style.opacity = '1';
        el.style.transform = 'translate3d(0,0,0) scale(1)';
        el.style.transitionDelay = '0s';
        io.unobserve(el);
      });
    }, { threshold: 0.12 });
    els.forEach(el => io.observe(el));
  }

  /* ── Boot ───────────────────────────────────────────────────── */
  function init() {
    const root = document.getElementById('lab-root');
    if (!root) return;

    const morphEl = document.getElementById('lab-morph');
    if (morphEl) {
      const slider = createMorphSlider(morphEl, {
        items: MORPH_ITEMS,
        startIndex: 0,
        transition: 'melt',
        duration: 1.1,
        ease: 'power2.inOut',
        intensity: 0.55,
        scale: 2.4,
        aberration: 0.35,
        drift: 0.4,
        autoplay: true,
        autoplayDelay: 4,
        loop: true,
        overlayColor: '#000000'
      });
      const chips = document.querySelectorAll('.lab-chip[data-mode]');
      chips.forEach(chip => {
        chip.addEventListener('click', () => {
          chips.forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
          if (slider) slider.setOption('transition', chip.dataset.mode);
        });
      });
    }

    const listEl = document.getElementById('lab-list');
    if (listEl) {
      const items = Array.from(listEl.querySelectorAll('.al-item')).map(el => ({
        name: el.dataset.name,
        desc: el.dataset.desc
      }));
      createAnimatedList(listEl, items);
    }

    const dockEl = document.getElementById('lab-dock');
    if (dockEl) {
      createDock(dockEl, DOCK_ITEMS, 50, 74, 200);
    }

    initReveal();
  }

  const DOCK_ITEMS = [
    { label: 'Home', href: '/', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></svg>' },
    { label: 'Dashboard', href: '/dashboard', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>' },
    { label: 'Effects Lab', href: '/showcase', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z"/><path d="M19 15l.9 2.6L22.5 18.5l-2.6.9L19 22l-.9-2.6-2.6-.9 2.6-.9z"/></svg>' },
    { label: 'Sign out', href: '/logout', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>' }
  ];

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
