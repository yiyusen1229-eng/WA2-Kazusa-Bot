/* ============================================================
   顶部菜单栏（做成窗口标题栏，和游戏一致）
   ------------------------------------------------------------
   · 无边框窗口 -> 菜单栏就是最顶上那条
   · 菜单项: 画面设置 / 环境设置 / 系统 / 帮助
   · 画面设置 -> 全屏模式 / 窗口模式 ▸ 1280x720(推荐) 1024x576 800x450
   · 字号是独立通道：无论选什么分辨率，文字大小都不变
   ============================================================ */
(function () {
  var RES = [
    { w: 1280, h: 720, label: "1280x720（推荐）" },
    { w: 1024, h: 576, label: "1024x576" },
    { w: 800, h: 450, label: "800x450" }
  ];

  // 字体固定比例（不随分辨率变化）
  var FIXED_TEXT_SCALE = 0.625;

  function getRes() {
    try {
      var r = JSON.parse(localStorage.getItem("app_renderRes") || "null");
      if (r && r.w && r.h) {
        for (var i = 0; i < RES.length; i++) {
          if (RES[i].w === r.w && RES[i].h === r.h) return RES[i];
        }
      }
    } catch (e) {}
    return RES[0];
  }

  function applyRes(r) {
    localStorage.setItem("app_renderRes", JSON.stringify(r));
    // 字号独立：永远保持固定比例，分辨率不影响文字大小
    window.TEXT_SCALE = FIXED_TEXT_SCALE;
    try {
      localStorage.setItem("app_textScale", String(FIXED_TEXT_SCALE));
    } catch (e) {}
    if (typeof window.__applyTextScale === "function") {
      window.__applyTextScale();
    }
    updateChecks();
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function closeAll() {
    var items = document.querySelectorAll("#menuBar .mbItem");
    for (var i = 0; i < items.length; i++) items[i].classList.remove("open");
    var subs = document.querySelectorAll("#menuBar .has-sub");
    for (var j = 0; j < subs.length; j++) subs[j].classList.remove("open");
    document.body.classList.remove("mbOpen");
  }

  function makeMenu(title, rows) {
    var item = el("div", "mbItem", title);
    var menu = el("div", "mbMenu");
    rows.forEach(function (r) {
      if (r === "-") { menu.appendChild(el("div", "mi-sep")); return; }
      var row = el("div", "mi-row", r.label);
      if (r.sub) {
        row.classList.add("has-sub");
        var sub = el("div", "mbSub");
        r.sub.forEach(function (s) {
          var sr = el("div", "mi-row", s.label);
          sr.dataset.res = s.w + "x" + s.h;
          sr.addEventListener("click", function (ev) {
            ev.stopPropagation();
            if (s.act) {
              localStorage.setItem("app_voiceLang", s.act);
              window.voiceLang = s.act;
              closeAll();
              return;
            }
            applyRes({ w: s.w, h: s.h });
            closeAll();
          });
          sub.appendChild(sr);
        });
        row.appendChild(sub);
        row.addEventListener("mouseenter", function () { row.classList.add("open"); });
        row.addEventListener("mouseleave", function () { row.classList.remove("open"); });
      } else {
        row.addEventListener("click", function (ev) {
          ev.stopPropagation();
          if (r.action) r.action();
          closeAll();
        });
      }
      menu.appendChild(row);
    });
    item.appendChild(menu);
    item.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var wasOpen = item.classList.contains("open");
      closeAll();
      if (!wasOpen) {
        item.classList.add("open");
        document.body.classList.add("mbOpen");
      }
    });
    return item;
  }

  function updateChecks() {
    var cur = getRes();
    var rows = document.querySelectorAll("#menuBar .mi-row[data-res]");
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (r.dataset.res === cur.w + "x" + cur.h) r.classList.add("checked");
      else r.classList.remove("checked");
    }
  }

  function toggleFullscreen() {
    /* 不要用浏览器的 document.documentElement.requestFullscreen()：
       在无边框 WebView2 上会把窗口铺成一层“点不动”的透明层（实测会把整个桌面挡住）。
       改走 pywebview 自己的全屏开关（后端 /api/window?action=togglefull）。 */
    try {
      if (window.__dbg) window.__dbg("FULL", "togglefull");
      fetch("/api/window?action=togglefull", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) { if (window.__dbg) window.__dbg("FULL", JSON.stringify(d).slice(0, 40)); })
        .catch(function () {});
    } catch (e) {}
  }

  // 窗口控制（无边框窗口需要自己实现）
  function winCtrl(act) {
    try { if (window.__dbg) window.__dbg("WIN", act); } catch (e) {}
    /* 双通道：先走 pywebview 桥接（不经过 HTTP），同时发一条 HTTP 兜底。
       哪条通就用哪条，避免一条链路坏掉就完全动不了窗口。 */
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.win) {
        window.pywebview.api.win(act);
        try { if (window.__dbg) window.__dbg("BRIDGE", act); } catch (e) {}
      }
    } catch (e) {}
    try {
      fetch("/api/window?act=" + act, { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) { try { if (window.__dbg) window.__dbg("HTTP", JSON.stringify(d).slice(0, 40)); } catch (e) {} })
        .catch(function (err) { try { if (window.__dbg) window.__dbg("HTTP!", String(err).slice(0, 40)); } catch (e) {} });
    } catch (e) {}
  }

  function build() {
    if (document.getElementById("menuBar")) return;
    var bar = el("div", "");
    bar.id = "menuBar";

    bar.appendChild(makeMenu("画面设置", [
      { label: "全屏模式", action: toggleFullscreen },
      { label: "窗口模式", sub: RES }
    ]));
    bar.appendChild(makeMenu("环境设置", [
      { label: "配音语言", sub: [
          { label: "日文（贴近原版声线）", w: 0, h: 0, act: "ja" },
          { label: "中文", w: 0, h: 0, act: "zh" },
        ] },
      { label: "背景音乐音量" },
      { label: "界面音效" }
    ]));
    bar.appendChild(makeMenu("系统", [
      { label: "系统设置", action: function () {
          if (window.__openOptions) window.__openOptions();
      } },
      { label: "返回标题", action: function () { location.reload(); } }
    ]));

    var spacer = el("div", "mbSpacer");
    bar.appendChild(spacer);

    bar.appendChild(makeMenu("帮助", [
      { label: "导出运行日志（诊断卡死）", action: function () {
          fetch("/api/log/dump", { cache: "no-store" })
            .then((r) => r.json())
            .then((d) => { alert("已写入日志：\\n" + (d.log || "")); })
            .catch(() => alert("日志导出失败"));
        } },
      { label: "关于本程序" }
    ]));

    // 版本号(从页面角标取文字)
    var stampSrc = document.getElementById("__BUILDSTAMP");
    if (stampSrc) {
      var st = (stampSrc.textContent || "").trim();
      if (st) {
        var mb = el("div", "mbBuild", st);
        mb.title = st;
        bar.appendChild(mb);
      }
    }

    // 窗口按钮
    var minBtn = el("div", "mbWinBtn", "—");
    minBtn.title = "最小化";
    minBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      winCtrl("min");
    });
    bar.appendChild(minBtn);

    var maxBtn = el("div", "mbWinBtn", "□");
    maxBtn.title = "最大化";
    function syncMaxBtn(maxed) {
      window.__maxed = !!maxed;
      maxBtn.textContent = maxed ? "❐" : "□";
      maxBtn.title = maxed ? "向下还原" : "最大化";
    }
    function toggleMax() {
      fetch("/api/window?act=togglemax", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) { syncMaxBtn(d && d.maxed); })
        .catch(function () {});
    }
    maxBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      toggleMax();
    });
    bar.appendChild(maxBtn);

    // 打开时同步一次当前状态，并跟随窗口尺寸变化刷新
    fetch("/api/window?act=state", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) { syncMaxBtn(d && d.maxed); })
      .catch(function () {});
    window.addEventListener("resize", function () {
      fetch("/api/window?act=state", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) { syncMaxBtn(d && d.maxed); })
        .catch(function () {});
    });

    var closeBtn = el("div", "mbWinBtn mbClose", "✕");
    closeBtn.title = "关闭";
    closeBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      winCtrl("close");
    });
    bar.appendChild(closeBtn);

    document.body.appendChild(bar);

    function api() {
      return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
    }

    /* ---------- 拖动窗口 ----------
       坐标换算全部交给后端：按下时只喊一声 "开始拖"，后端用 GetCursorPos + SetWindowPos
       自己盯光标挪窗口（同一套物理像素坐标，不会有 CSS/物理像素错位，也不会排队追不上）。 */
    bar.addEventListener("mousedown", function (ev) {
      if (ev.button !== 0) return;
      if (ev.target.closest(".mbItem") || ev.target.closest(".mbWinBtn")) return;
      ev.preventDefault();
      document.body.classList.add("mbDragging");
      var a = api();
      if (a && a.drag_begin) {
        a.drag_begin().catch(function () {});
      } else {
        fetch("/api/window?act=dragbegin", { cache: "no-store" }).catch(function () {});
      }
    });

    document.addEventListener("mouseup", function () {
      document.body.classList.remove("mbDragging");
    });

    bar.addEventListener("dblclick", function (ev) {
      if (ev.target.closest(".mbItem") || ev.target.closest(".mbWinBtn")) return;
      ev.preventDefault();
      toggleMax();
    });

    document.addEventListener("click", closeAll);
  /* fullscreenchange 监听已移除：不再使用浏览器全屏 API */

    updateChecks();
    applyRes(getRes());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();

  // ---------- 标题栏自动隐藏 ----------
  (function autoHideBar() {
    var bar = null;
    var tries = 0;
    function wait() {
      bar = document.getElementById("menuBar");
      if (!bar && tries++ < 50) { setTimeout(wait, 100); return; }
      if (!bar) return;
      init();
    }
    function init() {

    // 顶部热区: 鼠标碰到最上面 3px 就弹出
    var hot = document.createElement("div");
    hot.id = "mbHotZone";
    document.body.appendChild(hot);

    var hideTimer = null;
    function show() {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
      bar.classList.remove("mbHidden");
    }
    function hideSoon() {
      if (hideTimer) clearTimeout(hideTimer);
      hideTimer = setTimeout(function () {
        // 菜单展开时不收
        if (bar.querySelector(".mbItem.open")) return;
        bar.classList.add("mbHidden");
      }, 700);
    }

    document.addEventListener("mousemove", function (e) {
      var h = bar.offsetHeight || 22;
      if (e.clientY <= h + 6) show();
      else hideSoon();
    });
    hot.addEventListener("mouseenter", show);
    bar.addEventListener("mouseenter", show);
    hot.addEventListener("mouseleave", hideSoon);

    // 菜单展开期间保持可见
    bar.addEventListener("click", function () {
      if (bar.querySelector(".mbItem.open")) show();
    });

    // 键盘操作时也亮出来
    document.addEventListener("keydown", function (e) {
      if (e.key === "Alt") show();
    });
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", wait);
    } else {
      wait();
    }
  })();

