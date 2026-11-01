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

  document.addEventListener("wheel", function (e) {
    var t = e.target;
    var inBack = t && t.closest && t.closest(BACKLOG);
    log("WHEEL", (inBack ? "回想 " : "其它 ") + Math.round(e.deltaY));
    if (!inBack) return;
    acc += Math.abs(e.deltaY);
    if (acc >= 60) {
      acc = 0;
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
