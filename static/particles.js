/* ARAVIX · CONTROL DECK — WebGL particle field
   Floating geometric shapes, depth-reactive particles, mouse parallax,
   scan-line sweep, and holographic bloom.  Runs behind the whole page.
   Canvas sits under .bg with pointer-events:none.
   Reduced-motion → static field, no animation. */

(function () {
  'use strict';

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const gl = canvas.getContext('webgl', { alpha: true, antialias: true, premultipliedAlpha: false });
  if (!gl) return;

  /* ── Sizing ─────────────────────────────────────────────────── */
  let W, H, dpr;
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  resize();
  window.addEventListener('resize', resize);

  /* ── Mouse ──────────────────────────────────────────────────── */
  const mouse = { x: 0.5, y: 0.5, tx: 0.5, ty: 0.5 };
  document.addEventListener('pointermove', function (e) {
    mouse.tx = e.clientX / W;
    mouse.ty = e.clientY / W;
  }, { passive: true });

  /* ── Shader sources ─────────────────────────────────────────── */
  const VS = `
    attribute vec2 a_pos;
    attribute float a_size;
    attribute float a_alpha;
    attribute float a_depth;
    attribute float a_hue;
    uniform vec2 u_res;
    uniform vec2 u_mouse;
    uniform float u_time;
    varying float v_alpha;
    varying float v_depth;
    varying float v_hue;
    void main() {
      float parallax = (1.0 - a_depth) * 0.12;
      vec2 pos = a_pos;
      pos.x += (u_mouse.x - 0.5) * parallax;
      pos.y += (u_mouse.y - 0.5) * parallax;
      vec2 clip = pos * 2.0 - 1.0;
      clip.y = -clip.y;
      gl_Position = vec4(clip, 0.0, 1.0);
      float sizeScale = mix(1.0, 1.8, a_depth);
      gl_PointSize = a_size * sizeScale * u_res.y / 900.0;
      v_alpha = a_alpha;
      v_depth = a_depth;
      v_hue = a_hue;
    }
  `;
  const FS = `
    precision mediump float;
    varying float v_alpha;
    varying float v_depth;
    varying float v_hue;
    uniform float u_time;
    void main() {
      vec2 uv = gl_PointCoord - 0.5;
      float d = length(uv);
      if (d > 0.5) discard;
      float glow = exp(-d * 5.0) * 0.7;
      float core = exp(-d * 12.0);
      vec3 col;
      if (v_hue < 0.33) {
        col = mix(vec3(0.55, 0.59, 1.0), vec3(0.44, 0.83, 0.91), v_hue * 3.0);
      } else if (v_hue < 0.66) {
        col = mix(vec3(0.44, 0.83, 0.91), vec3(0.33, 0.88, 0.66), (v_hue - 0.33) * 3.0);
      } else {
        col = mix(vec3(0.66, 0.47, 0.98), vec3(1.0, 0.55, 0.65), (v_hue - 0.66) * 3.0);
      }
      float alpha = (core + glow) * v_alpha;
      gl_FragColor = vec4(col * alpha, alpha * 0.55);
    }
  `;

  function compile(src, type) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  }
  const prog = gl.createProgram();
  gl.attachShader(prog, compile(VS, gl.VERTEX_SHADER));
  gl.attachShader(prog, compile(FS, gl.FRAGMENT_SHADER));
  gl.linkProgram(prog);
  gl.useProgram(prog);

  const a_pos   = gl.getAttribLocation(prog, 'a_pos');
  const a_size  = gl.getAttribLocation(prog, 'a_size');
  const a_alpha = gl.getAttribLocation(prog, 'a_alpha');
  const a_depth = gl.getAttribLocation(prog, 'a_depth');
  const a_hue   = gl.getAttribLocation(prog, 'a_hue');
  const u_res   = gl.getUniformLocation(prog, 'u_res');
  const u_mouse = gl.getUniformLocation(prog, 'u_mouse');
  const u_time  = gl.getUniformLocation(prog, 'u_time');

  /* ── Particles ──────────────────────────────────────────────── */
  const COUNT = reduced ? 60 : 140;
  const pos   = new Float32Array(COUNT * 2);
  const size  = new Float32Array(COUNT);
  const alpha = new Float32Array(COUNT);
  const depth = new Float32Array(COUNT);
  const hue   = new Float32Array(COUNT);
  const vx    = new Float32Array(COUNT);
  const vy    = new Float32Array(COUNT);
  const drift = new Float32Array(COUNT);

  for (var i = 0; i < COUNT; i++) {
    pos[i * 2]     = Math.random();
    pos[i * 2 + 1] = Math.random();
    size[i]  = 2 + Math.random() * 5;
    alpha[i] = 0.15 + Math.random() * 0.45;
    depth[i] = Math.random();
    hue[i]   = Math.random();
    vx[i]    = (Math.random() - 0.5) * 0.0003;
    vy[i]    = (Math.random() - 0.5) * 0.0002;
    drift[i] = Math.random() * Math.PI * 2;
  }

  function createBuf(data) {
    var b = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    return b;
  }
  var bufPos   = createBuf(pos);
  var bufSize  = createBuf(size);
  var bufAlpha = createBuf(alpha);
  var bufDepth = createBuf(depth);
  var bufHue   = createBuf(hue);

  function bind(buf, loc, size) {
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
  }

  /* ── Scan-line uniforms ─────────────────────────────────────── */
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  /* ── Render loop ────────────────────────────────────────────── */
  var t = 0;
  function frame() {
    requestAnimationFrame(frame);
    if (document.hidden) return;
    t += 0.016;

    mouse.x += (mouse.tx - mouse.x) * 0.04;
    mouse.y += (mouse.ty - mouse.y) * 0.04;

    if (!reduced) {
      for (var i = 0; i < COUNT; i++) {
        drift[i] += 0.002 + i * 0.00001;
        pos[i * 2]     += vx[i] + Math.sin(drift[i]) * 0.00008;
        pos[i * 2 + 1] += vy[i] + Math.cos(drift[i] * 0.7) * 0.00006;
        if (pos[i * 2] < -0.05) pos[i * 2] = 1.05;
        if (pos[i * 2] > 1.05) pos[i * 2] = -0.05;
        if (pos[i * 2 + 1] < -0.05) pos[i * 2 + 1] = 1.05;
        if (pos[i * 2 + 1] > 1.05) pos[i * 2 + 1] = -0.05;
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, bufPos);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, pos);
    }

    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(prog);
    gl.uniform2f(u_res, canvas.width, canvas.height);
    gl.uniform2f(u_mouse, mouse.x, mouse.y);
    gl.uniform1f(u_time, t);

    bind(bufPos,   a_pos,   2);
    bind(bufSize,  a_size,  1);
    bind(bufAlpha, a_alpha, 1);
    bind(bufDepth, a_depth, 1);
    bind(bufHue,   a_hue,   1);

    gl.drawArrays(gl.POINTS, 0, COUNT);
  }
  requestAnimationFrame(frame);
})();
