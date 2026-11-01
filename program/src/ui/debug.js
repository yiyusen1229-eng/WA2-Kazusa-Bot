/* 调试面板：把「音效触发 / 界面打开 / 滚轮」记成时间线显示在屏幕上
 *
 * 用法：默认显示在左上角；Ctrl+Shift+D 开关。
 * 它只观察、不改变行为（包一层 window.playSE / __openScreen，再挂在 document 上听滚轮）。
 */
(function () {
  var MAX = 18;
  var buf = [];

  var box = document.createElement("div");
  box.id = "dbgPanel";
  box.style.cssText = [
    "position:fixed", "left:6px", "top:6px", "z-index:99999",
    "max-width:520px", "padding:4px 6px", "border-radius:3px",
    "background:rgba(0,0,0,.72)", "color:#8f8", "font:10px/1.45 monospace",
    "white-space:pre", "pointer-events:none", "display:block",
    "text-shadow:0 0 2px #000"
  ].join(";");
  document.body.appendChild(box);

  function stamp() {
    var d = new Date();
    return ("0" + d.getMinutes()).slice(-2) + ":" + ("0" + d.getSeconds()).slice(-2) +
           "." + ("00" + d.getMilliseconds()).slice(-3);
  }

  function log(tag, msg) {
    buf.push(stamp() + " " + tag + " " + msg);
    if (buf.length > MAX) buf.shift();
    box.textContent = buf.join("\n");
  }
  window.__dbg = log;
  window.__dbgBuf = buf;

  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey && e.shiftKey && (e.key === "D" || e.key === "d")) {
      box.style.display = box.style.display === "none" ? "block" : "none";
    }
  });

  /* ---- 音效 ---- */
  function wrapSE() {
    if (!window.playSE || window.playSE.__wrapped) return false;
    var orig = window.playSE;
    window.playSE = function (kind) {
      log("SE  ", kind);
      try { return orig.apply(this, arguments); } catch (e) { log("SE! ", e.message); }
    };
    window.playSE.__wrapped = true;
    return true;
  }

  /* ---- 界面打开：采样 opacity，看有没有渐变 ---- */
  function wrapOpen() {
    if (!window.__openScreen || window.__openScreen.__wrapped) return false;
    var orig = window.__openScreen;
    window.__openScreen = function (name, mode) {
      log("OPEN", name + (mode ? "/" + mode : ""));
      var r = orig.apply(this, arguments);
      try {
        var el = document.getElementById(name === "save" ? "saveScreen" : name + "Screen");
        if (el) {
          var vals = [], t0 = performance.now();
          var iv = setInterval(function () {
            vals.push(parseFloat(getComputedStyle(el).opacity).toFixed(2));
            if (performance.now() - t0 > 300) {
              clearInterval(iv);
              var u = {}; vals.forEach(function (v) { u[v] = 1; });
              log("OPAC", Object.keys(u).join(">") + " (" + Object.keys(u).length + "值)");
            }
          }, 20);
        }
      } catch (e) {}
      return r;
    };
    window.__openScreen.__wrapped = true;
    return true;
  }

  /* ---- 滚轮：document 捕获阶段，元素被重建也不受影响 ---- */
  var BACKLOG = "#historyBox,#blogList,.historyBox,.backlog,.hlineBox";
  var acc = 0;
  var lastWheelSE = 0;

  document.addEventListener("wheel", function (e) {
    var t = e.target;
    var inBack = t && t.closest && t.closest(BACKLOG);
    log("WHEEL", (inBack ? "回想 " : "其它 ") + Math.round(e.deltaY));
    if (!inBack) return;
    acc += Math.abs(e.deltaY);
    if (acc >= 60) {
      acc = 0;
      /* 高速滚动时限流：260ms 内只响一次，低速正常触发 */
      var now = performance.now();
      if (now - lastWheelSE < 420) return;
      lastWheelSE = now;
      log("PAGE", "滚轮触发");
      try { if (window.playSE) window.playSE("page"); } catch (err) {}
    }
  }, true);

  /* ---- 兜底：脚本可能比 game.js 早执行，轮询几次把它包上 ---- */
  var tries = 0;
  var timer = setInterval(function () {
    var a = wrapSE(), b = wrapOpen();
    if ((a && b) || ++tries > 40) clearInterval(timer);
  }, 250);

  log("BOOT", "面板已启动（Ctrl+Shift+D 开关）");
})();

/* 把 JS 运行时报错也记进面板（有异常时动画会整段不执行，这条能看到原因） */
window.addEventListener("error", function (e) {
  try {
    var msg = (e && e.message) ? e.message : "unknown";
    var src = (e && e.filename ? e.filename.split("/").pop() : "") + ":" + (e && e.lineno || 0);
    log("ERR ", src + " " + msg.slice(0, 60));
  } catch (err) {}
});
window.addEventListener("unhandledrejection", function (e) {
  try { log("REJ ", String(e.reason).slice(0, 60)); } catch (err) {}
});

/* ---------- WAAPI 测试：打开存档界面时自动跑一次 ----------
   目的：区分「动画没执行」和「执行了但渲染层没画出来」。
   transform 若在跑却采不到变化 → 说明是渲染层问题；若 playState 就不是 running → 是执行问题。 */
(function () {
  var done = false;

  function sample(el, prop, n, gap, cb) {
    var vals = [], i = 0;
    var iv = setInterval(function () {
      vals.push(getComputedStyle(el)[prop]);
      if (++i >= n) { clearInterval(iv); cb(vals); }
    }, gap);
  }

  function run(el) {
    if (done) return;
    done = true;
    __dbg("WAAPI", "开始测试 #" + el.id);

    var a1 = null, a2 = null;
    try {
      a1 = el.animate([{ transform: "scale(1)" }, { transform: "scale(0.5)" }],
                      { duration: 1200, fill: "both", easing: "linear" });
      __dbg("T  anim=" + (a1 ? "ok" : "null") + " state=" + (a1 ? a1.playState : "-") +
          " n=" + el.getAnimations().length);
    } catch (e) { __dbg("T!  " + e.message.slice(0, 40)); }

    try {
      a2 = el.animate([{ opacity: 1 }, { opacity: 0.4 }], { duration: 1200, fill: "both" });
    } catch (e) { __dbg("O!  " + e.message.slice(0, 40)); }

    sample(el, "transform", 8, 150, function (tv) {
      var u = {}; tv.forEach(function (v) { u[v] = 1; });
      __dbg("T  transform 值种类=" + Object.keys(u).length);
      __dbg("T  首=" + tv[0].slice(0, 22));
      __dbg("T  末=" + tv[tv.length - 1].slice(0, 22));
      __dbg("T  currentTime=" + (a1 ? Math.round(a1.currentTime) : "-") +
          " state=" + (a1 ? a1.playState : "-"));

      sample(el, "opacity", 8, 150, function (ov) {
        var u2 = {}; ov.forEach(function (v) { u2[v] = 1; });
        __dbg("O  opacity 值种类=" + Object.keys(u2).length +
            "  (" + ov[0] + " -> " + ov[ov.length - 1] + ")");
        __dbg("结论", Object.keys(u).length > 1 ? "T 可用 -> 换页动画走 WAAPI"
              : (Object.keys(u2).length > 1 ? "T 被吞 / O 正常 -> 渲染层问题，需 canvas"
                 : "两者都不动 -> 动画没执行"));
        try { a1 && a1.cancel(); } catch (e) {}
        try { a2 && a2.cancel(); } catch (e) {}
      });
    });
  }

  var timer = setInterval(function () {
    var el = document.getElementById("saveScreen");
    if (el && el.classList.contains("show")) { clearInterval(timer); setTimeout(function(){ run(el); }, 400); }
  }, 300);
})();
