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
        .then(function (d) {
          if (window.__dbg) window.__dbg("FULL", JSON.stringify(d).slice(0, 40));
          /* OPTION 1 的「窗口模式 / 全屏模式」高亮要跟着变 */
          if (d && typeof d.fullscreen === "boolean" && window.__ct1SetWinModeUI) {
            window.__ct1SetWinModeUI(d.fullscreen);
          }
        })
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


  /* ================= 顶部菜单：场景 / 服装 ================= */
  var _sceneMeta = null;
  function sceneMeta() {
    if (_sceneMeta) return _sceneMeta;
    var keys = [];
    try { keys = Object.keys(CG_URL); } catch (e) {}
    if (!keys.length) return null;
    var map = {}, ids = {}, places = [], times = {};
    keys.forEach(function (id) {
      var p = id.split("（")[0];
      var m = id.match(/（(白天|黄昏|晚上|黑夜|深夜)）/);
      var t = m ? m[1] : "默认";
      if (!ids[p]) { ids[p] = []; places.push(p); }
      ids[p].push({ id: id, time: t });
      map[id] = { place: p, time: t };
    });
    places.sort(function (a, b) { return a.localeCompare(b, "zh"); });
    places.forEach(function (p) {
      var ts = [];
      ids[p].forEach(function (x) { if (ts.indexOf(x.time) < 0) ts.push(x.time); });
      times[p] = ts;
    });
    _sceneMeta = { map: map, ids: ids, places: places, times: times };
    return _sceneMeta;
  }

  function sceneState(meta) {
    var cur = (typeof currentBg === "string") ? currentBg : "";
    var p = "", t = "";
    if (cur && meta.map[cur]) { p = meta.map[cur].place; t = meta.map[cur].time; }
    if (!p || !meta.ids[p]) {
      p = meta.ids["教室"] ? "教室" : meta.places[0];
      t = (meta.times[p] || [""])[0];
    }
    if (!t || (meta.times[p] || []).indexOf(t) < 0) t = (meta.times[p] || [""])[0];
    return { place: p, time: t };
  }

  function applySceneById(id) {
    try { currentBg = null; setBg(id); sessionSave(); } catch (e) {}
    window.__nextScene = "";
  }

  function applyOutfitByName(name) {
    try {
      currentOutfit = name;
      setSpriteByScene(currentBg || "classroom", window.__lastEmo || "", true, name);
      sessionSave();
    } catch (e) {}
    window.__nextOutfit = "";
  }

  function menuSub(title, items, current, onPick) {
    var row = el("div", "mi-row has-sub", title);
    var sub = el("div", "mbSub");
    items.forEach(function (v) {
      var r = el("div", "mi-row", v);
      if (v === current) r.classList.add("checked");
      r.addEventListener("click", function (ev) {
        ev.stopPropagation();
        onPick(v);
        closeAll();
      });
      sub.appendChild(r);
    });
    row.appendChild(sub);
    row.addEventListener("mouseenter", function () { row.classList.add("open"); });
    row.addEventListener("mouseleave", function () { row.classList.remove("open"); });
    return row;
  }

  function menuToggle(title, on, menu, fn) {
    var row = el("div", "mi-row", title + "：" + (on ? "开" : "关"));
    if (on) row.classList.add("checked");
    row.addEventListener("click", function (ev) {
      ev.stopPropagation();
      fn(!on);
      refreshSceneMenu(menu);
    });
    return row;
  }

  function refreshSceneMenu(menu) {
    menu.innerHTML = "";
    var meta = sceneMeta();
    if (!meta) {
      menu.appendChild(el("div", "mi-row", "场景数据加载中…"));
      return;
    }
    var st = sceneState(meta);
    menu.appendChild(menuSub("场景地点", meta.places, st.place, function (p) {
      var ts = meta.times[p] || [];
      var t = ts.indexOf(st.time) >= 0 ? st.time : (ts[0] || "");
      var ids = meta.ids[p] || [];
      var hit = null;
      for (var i = 0; i < ids.length; i++) if (ids[i].time === t) { hit = ids[i]; break; }
      if (!hit) hit = ids[0];
      if (hit) applySceneById(hit.id);
    }));
    menu.appendChild(menuSub("场景时段", meta.times[st.place] || [], st.time, function (t) {
      var ids = meta.ids[st.place] || [];
      var hit = null;
      for (var i = 0; i < ids.length; i++) if (ids[i].time === t) { hit = ids[i]; break; }
      if (!hit) hit = ids[0];
      if (hit) applySceneById(hit.id);
    }));
    menu.appendChild(el("div", "mi-sep"));

    var outfits = [];
    try { outfits = Object.keys(SPRITE_INDEX).sort(function (a, b) { return a.localeCompare(b, "zh"); }); } catch (e) {}
    var curOut = (typeof currentOutfit === "string") ? currentOutfit : "";
    menu.appendChild(menuSub("服装", outfits, curOut, function (n) { applyOutfitByName(n); }));
    var _pm = "auto";
    try { _pm = localStorage.getItem("app_period") || "auto"; } catch (e) {}
    var _plabels = [["自动", "auto"], ["IC（高中）", "ic"], ["CC（大学/出道）", "cc"], ["CODA（成年）", "coda"]];
    var _plabel = "自动";
    for (var _pi = 0; _pi < _plabels.length; _pi++) {
      if (_plabels[_pi][1] === _pm) _plabel = _plabels[_pi][0];
    }
    menu.appendChild(menuSub("时期", _plabels.map(function (x) { return x[0]; }), _plabel, function (lab) {
      var val = "auto";
      for (var _pj = 0; _pj < _plabels.length; _pj++) if (_plabels[_pj][0] === lab) val = _plabels[_pj][1];
      try { localStorage.setItem("app_period", val); } catch (e) {}
      closeAll();
    }));
    menu.appendChild(el("div", "mi-sep"));

    menu.appendChild(menuToggle("锁定场景", !!window.__lockScene, menu, function (v) {
      window.__lockScene = v;
      try { if (window.App && window.App.setPref) window.App.setPref("lockScene", v); } catch (e) {}
      try { localStorage.setItem("lockScene", v ? "1" : "0"); } catch (e) {}
    }));
    menu.appendChild(menuToggle("锁定服装", !!window.__lockOutfit, menu, function (v) {
      window.__lockOutfit = v;
      try { if (window.App && window.App.setPref) window.App.setPref("lockOutfit", v); } catch (e) {}
      try { localStorage.setItem("lockOutfit", v ? "1" : "0"); } catch (e) {}
    }));
  }

  function makeSceneMenu() {
    var item = el("div", "mbItem", "场景 / 服装");
    var menu = el("div", "mbMenu");
    item.appendChild(menu);
    item.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var wasOpen = item.classList.contains("open");
      closeAll();
      if (!wasOpen) {
        refreshSceneMenu(menu);
        item.classList.add("open");
        document.body.classList.add("mbOpen");
      }
    });
    return item;
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
        ] }
    ]));
    bar.appendChild(makeSceneMenu());
    bar.appendChild(makeMenu("系统", [
      { label: "系统设置", action: function () {
          if (window.__openOptions) window.__openOptions();
      } },
      { label: "返回标题", action: function () { location.reload(); } }
    ]));

    /* 调试面板开关：不放子菜单，点一下直接开/关左上角那块绿字 */
    var dbgBtn = el("div", "mbItem", "调试");
    dbgBtn.title = "显示 / 隐藏左上角调试面板";
    dbgBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      closeAll();
      var p = document.getElementById("dbgPanel");
      if (p) p.style.display = (p.style.display === "none") ? "block" : "none";
    });
    bar.appendChild(dbgBtn);

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

