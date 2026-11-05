/* wt-fade.js —— 双缓冲交叉淡化（场景背景 / 立绘）
 *
 * 以前换背景是「先压到 0.25、等 260ms 再换图」，中间会黑一下；
 * 立绘则是先藏起来、180ms 后再显示，同样有一瞬间空场。
 * 双缓冲 = 新旧两张同时在场：新的淡入、旧的留在底下，看起来是「化过去」而不是「闪一下」。
 *
 * 对外（WA2.fade）：
 *   enabled()                过渡开不开（prefs.xfade === false 就关，默认开）
 *   ms()                     时长（prefs.xfadeMs，夹在 200~300ms，默认 240）
 *   set(on, ms)              改设置（写进 prefs，跟着设置文件持久化）
 *   crossBg(url, ok, fail)   场景背景：图先预载，载完再淡
 *   crossSprite(url, ok, fail) 立绘：新图叠一层淡入，淡完再把主图换掉
 *   describe()               当前设置的快照（调试面板用）
 *
 * 关掉过渡时两个函数都退化成「立刻换」，不再有任何动画。
 * 这个文件不碰 DOM 也能加载（自测里用 Node 跑）：所有 getElementById 都在函数里。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = function (id) {
    return (typeof document !== "undefined" && document.getElementById) ? document.getElementById(id) : null;
  };

  var DEF_MS = 240;
  var MIN_MS = 200;
  var MAX_MS = 300;

  var seqBg = 0;     /* 每次新背景过渡 +1：旧的收尾回调据此作废 */
  var seqSpr = 0;    /* 立绘单独一套序号 */
  var front = 0;     /* 0 = #bgLayer 在前（不透明），1 = #bgLayer2 在前 */

  function prefs() {
    return (window.App && window.App.getPrefs) ? (window.App.getPrefs() || {}) : {};
  }

  function enabled() {
    var P = prefs();
    return P.xfade !== false;          /* 只有显式 false 才关：老设置文件里没有这个键 */
  }

  function ms() {
    var v = Number(prefs().xfadeMs);
    if (!isFinite(v) || v <= 0) return DEF_MS;
    return Math.max(MIN_MS, Math.min(MAX_MS, Math.round(v)));
  }

  function set(on, msVal) {
    try {
      if (window.App && window.App.setPref) {
        window.App.setPref("xfade", !!on);
        if (msVal !== undefined && msVal !== null) {
          var v = Number(msVal);
          if (isFinite(v) && v > 0) {
            window.App.setPref("xfadeMs", Math.max(MIN_MS, Math.min(MAX_MS, Math.round(v))));
          }
        }
      }
    } catch (e) {}
  }

  function describe() {
    return { enabled: enabled(), ms: ms(), front: front };
  }

  /* ---------- 背景 ---------- */

  /** #bgLayer 永远保持「当前这张图」：过渡结束后把图搬回去，别的代码读它不会读到旧值 */
  function settle(url) {
    var a = $("bgLayer"), b = $("bgLayer2");
    if (!a || !url) return;
    if (b) {
      b.style.transition = "none";
      b.style.opacity = "0";
      b.style.backgroundImage = "none";
    }
    a.style.transition = "none";
    a.style.backgroundImage = 'url("' + url + '")';
    a.style.opacity = "1";
    front = 0;
  }

  function paintBg(a, b, url, my) {
    var on = enabled() && !!b;
    var t = ms();
    a.style.backgroundColor = "";            /* 有图了就把缺图时的兜底底色清掉 */

    if (!on) {
      if (b) {
        b.style.transition = "none";
        b.style.opacity = "0";
        b.style.backgroundImage = "none";
      }
      a.style.transition = "none";
      a.style.backgroundImage = 'url("' + url + '")';
      a.style.opacity = "1";
      front = 0;
      return;
    }

    var from = front === 0 ? a : b;
    var to = front === 0 ? b : a;
    /* 目标层：先换图、压到 0，强制一次重排，再放开过渡。
       不加这一步，浏览器会把「0 → 1」合并成一帧，看着还是硬切。 */
    to.style.transition = "none";
    to.style.opacity = "0";
    to.style.backgroundImage = 'url("' + url + '")';
    to.style.backgroundColor = "";
    void to.offsetWidth;
    to.style.transition = "opacity " + t + "ms linear";
    from.style.transition = "opacity " + t + "ms linear";
    to.style.opacity = "1";
    from.style.opacity = "0";
    front = 1 - front;

    setTimeout(function () {
      if (my !== seqBg) return;              /* 期间又换了一张：这次收尾作废 */
      settle(url);
    }, t + 40);
  }

  function crossBg(url, ok, fail) {
    var a = $("bgLayer"), b = $("bgLayer2");
    if (!a || !url) { if (fail) fail(); return false; }
    var my = ++seqBg;
    if (typeof Image === "undefined") { paintBg(a, b, url, my); if (ok) ok(); return true; }
    var probe = new Image();
    probe.onload = function () {
      if (my !== seqBg) return;
      paintBg(a, b, url, my);
      if (ok) ok();
    };
    probe.onerror = function () { if (my === seqBg && fail) fail(); };
    probe.src = url;
    return true;
  }

  /* ---------- 立绘 ---------- */

  function ghost(wrap) {
    var g = document.getElementById("spriteGhost");
    if (!g) {
      g = document.createElement("img");
      g.id = "spriteGhost";
      g.className = "spriteGhost";
      g.alt = "";
      wrap.appendChild(g);
    }
    return g;
  }

  /* 叠层淡完之后把主图换掉：本来就是同一张图，看不出切换 */
  function applySprite(cur, url) {
    if (cur.classList && cur.classList.contains("show")) {
      cur.src = url;
      return;
    }
    /* 主图本来就藏着（刚进对话 / 刚切角色）：直接显示，别和叠层抢那 0.6s */
    cur.style.transition = "none";
    cur.src = url;
    if (cur.classList) cur.classList.add("show");
    void cur.offsetWidth;
    cur.style.transition = "";
  }

  function crossSprite(url, ok, fail) {
    var cur = $("sprite"), wrap = $("spriteWrap");
    if (!cur || !url) { if (fail) fail(); return false; }
    var my = ++seqSpr;
    if (typeof Image === "undefined") {
      applySprite(cur, url);
      if (ok) ok();
      return true;
    }
    var probe = new Image();
    probe.onload = function () {
      if (my !== seqSpr) return;
      if (!enabled() || !wrap) {                 /* 关过渡 / 没有容器：立刻换 */
        applySprite(cur, url);
        if (ok) ok();
        return;
      }
      var t = ms();
      var g = ghost(wrap);
      g.src = url;
      g.style.transition = "none";
      g.style.opacity = "0";
      void g.offsetWidth;
      g.style.transition = "opacity " + t + "ms linear";
      g.style.opacity = "1";
      setTimeout(function () {
        if (my !== seqSpr) return;
        applySprite(cur, url);
        g.style.transition = "none";
        g.style.opacity = "0";
        if (ok) ok();
      }, t + 40);
    };
    probe.onerror = function () { if (my === seqSpr && fail) fail(); };
    probe.src = url;
    return true;
  }

  var api = {
    enabled: enabled,
    ms: ms,
    set: set,
    crossBg: crossBg,
    crossSprite: crossSprite,
    settle: settle,
    describe: describe,
    DEF_MS: DEF_MS,
    MIN_MS: MIN_MS,
    MAX_MS: MAX_MS
  };

  WA2.fade = api;
  window.__fade = api;
  if (WA2.register) WA2.register("fade", api);
})();
