// 系统设置界面（重建中：目前只有顶栏和底栏）
(function () {
  function byId(id) { return document.getElementById(id); }

  // 单个模块出错不影响整个界面打开
  function safe(fn) {
    try { fn(); } catch (err) {
      if (window.console && console.error) console.error("[opt]", err);
    }
  }

  function open() {
    var s = byId("optScreen");
    if (!s) return;
    safe(bindTabs);
    safe(bindPager);
    safe(bindContent);
    safe(bindContent2);
    safe(bindModelFields);
    safe(bindExit);
    safe(refreshTabs);
    s.classList.add("show");
    window.__optOpen = true;
    // 界面显示后让统一文字渲染器补扫一遍（隐藏时它不会处理）
    if (window.__uiTextScan) {
      window.__uiTextScan(s);
      window.__uiTextScan(byId("optContent3"));
    }
  }

  function close() {
    var s = byId("optScreen");
    if (!s) return;
    s.classList.remove("show");
    window.__optOpen = false;
  }


  // ---------- 三个 OPTION 标签：悬停 / 选中 ----------
  var current = 1;

  function setTab(n, state) {
    var img = document.querySelector("#optT" + n + " img");
    if (!img) return;
    img.src = "assets/ui/opt/tab" + n + "_" + state + ".png";
  }

  function refreshTabs() {
    for (var i = 1; i <= 3; i++) setTab(i, i === current ? "on" : "off");
    // 内容区目前只做了 OPTION 1，其余两页留空
    var c1 = document.getElementById("optContent");
    var c2 = document.getElementById("optContent2");
    var c3 = document.getElementById("optContent3");
    if (c1) c1.style.display = (current === 1) ? "block" : "none";
    if (c2) c2.style.display = (current === 2) ? "block" : "none";
    if (c3) c3.style.display = (current === 3) ? "block" : "none";
    if (current === 3 && window.__uiTextScan && c3) window.__uiTextScan(c3);
  }

  var tabsBound = false;
  function bindTabs() {
    if (tabsBound) return;
    tabsBound = true;
    for (var i = 1; i <= 3; i++) {
      (function (n) {
        var el = byId("optT" + n);
        if (!el) return;
        el.addEventListener("mouseenter", function () {
          if (n !== current) setTab(n, "hover");
        });
        el.addEventListener("mouseleave", function () {
          if (n !== current) setTab(n, "off");
        });
        el.addEventListener("click", function (e) {
          e.stopPropagation();
          current = n;
          refreshTabs();
        });
      })(i);
    }
  }

  window.__optTab = function (n) { current = n; refreshTabs(); };


  var pagerBound = false;
  function bindPager() {
    if (pagerBound) return;
    pagerBound = true;
    [["optPrev", "l"], ["optNext", "r"]].forEach(function (pair) {
      var el = byId(pair[0]);
      if (!el) return;
      var img = el.querySelector("img");
      if (!img) return;
      var base = "assets/ui/opt/pager_" + pair[1] + "1.png";
      var hover = "assets/ui/opt/pager_" + pair[1] + "2.png";
      img.src = base;
      el.addEventListener("mouseenter", function () { img.src = hover; });
      el.addEventListener("mouseleave", function () { img.src = base; });
      el.addEventListener("click", function (e) {
        e.stopPropagation();
        if (typeof window.__optTab !== "function") return;
        var n = current + (pair[1] === "l" ? -1 : 1);   /* 标签编号是 1~3 */
        n = Math.max(1, Math.min(3, n));
        window.__optTab(n);
      });
    });
  }

  // ---------- OPTION 1 内容区：按控件贴图 ----------
  var CT = {
    W: 1024, H: 464,
    W_STAGE: 645.27, H_STAGE: 292.45,
    widgets: [
      [458, 14, 252, 36, 1], [714, 14, 252, 36, 1],
      [458, 78, 124, 36, 2], [586, 78, 124, 36, 2],
      [714, 78, 124, 36, 2], [842, 78, 124, 36, 2],
      [458, 118, 252, 36, 3], [714, 118, 252, 36, 3],
      [482, 158, 52, 36, 0], [890, 158, 52, 36, 0],
      [458, 222, 252, 36, 4], [714, 222, 252, 36, 4],
      [482, 262, 52, 36, 0], [890, 262, 52, 36, 0],
      [388, 272, 80, 26, 5], [388, 302, 80, 26, 5],
      [482, 302, 52, 36, 0], [890, 302, 52, 36, 0],
      [482, 342, 52, 36, 0], [890, 342, 52, 36, 0],
      [482, 382, 52, 36, 0], [890, 382, 52, 36, 0]
    ],
    sliders: [
      { x: 543, y: 158, n: 21, pitch: 16, h: 26 },
      { x: 543, y: 262, n: 21, pitch: 16, h: 26 },
      { x: 543, y: 302, n: 21, pitch: 16, h: 26 },
      { x: 543, y: 342, n: 21, pitch: 16, h: 26 },
      { x: 543, y: 382, n: 21, pitch: 16, h: 26 }
    ],
    sel: { 0: 1, 5: 1, 11: 1, 14: 1 },
    slideVal: [11, 0, 0, 0, 0]
  };

  function bindContent() {
    if (window.__ctBound) return;
    window.__ctBound = true;

    var box = byId("optContent");
    if (!box) return;

    var sx = CT.W_STAGE / CT.W;
    var sy = CT.H_STAGE / CT.H;

    // 底图必须显式显示（CSS 里 .optLayer 默认 display:none）
    var baseLayer = box.querySelector(".ctBase");
    if (baseLayer) baseLayer.classList.add("on");
    var DIR = "assets/ui/opt/ct/";
    var W2 = function (i) { return (i < 10 ? "0" + i : "" + i); };

    // 每个控件一张 img，按状态切图
    var imgs = [];
    CT.widgets.forEach(function (w, idx) {
      var img = document.createElement("img");
      img.className = "ctImg";
      img.style.left = (w[0] * sx) + "px";
      img.style.top = (w[1] * sy) + "px";
      img.style.width = (w[2] * sx) + "px";
      img.style.height = (w[3] * sy) + "px";
      box.appendChild(img);
      imgs[idx] = img;
    });

    function paint(idx) {
      var img = imgs[idx];
      if (CT.sel[idx]) {
        img.src = DIR + "w" + W2(idx) + "_sel.png";
        img.classList.add("on");
      } else if (img.dataset.hover) {
        img.src = DIR + "w" + W2(idx) + "_hover.png";
        img.classList.add("on");
      } else {
        img.classList.remove("on");
      }
    }

    function clickWidget(idx) {
      var g = CT.widgets[idx][4];
      if (g === 0) return;                       // 箭头不参与选中
      if (CT.sel[idx]) { delete CT.sel[idx]; paint(idx); return; }
      for (var k in CT.sel) {
        if (+k !== idx && CT.widgets[+k][4] === g) { delete CT.sel[k]; paint(+k); }
      }
      CT.sel[idx] = 1;
      paint(idx);
    }

    // 热区
    CT.widgets.forEach(function (w, idx) {
      var d = document.createElement("div");
      d.className = "ctHot";
      d.style.left = (w[0] * sx) + "px";
      d.style.top = (w[1] * sy) + "px";
      d.style.width = (w[2] * sx) + "px";
      d.style.height = (w[3] * sy) + "px";
      d.addEventListener("mouseenter", function () {
        imgs[idx].dataset.hover = "1";
        paint(idx);
      });
      d.addEventListener("mouseleave", function () {
        delete imgs[idx].dataset.hover;
        paint(idx);
      });
      d.addEventListener("click", function (e) {
        e.stopPropagation();
        clickWidget(idx);
      });
      box.appendChild(d);
    });

    // 滑块：整条轨道图 + 宽度裁剪决定亮几格；悬停时整条变黄
    var SL_TRACK_PX = 21 * 16;                      // 素材里整条轨道宽 336
    function makeBar(cls, src) {
      var d = document.createElement("div");
      d.className = "ctBar " + cls;
      d.style.left = (543 * sx) + "px";
      d.style.height = (26 * sy) + "px";
      var im = document.createElement("img");
      im.src = src;
      im.style.width = (SL_TRACK_PX * sx) + "px";
      im.style.height = (26 * sy) + "px";
      d.appendChild(im);
      box.appendChild(d);
      return d;
    }

    var hoverBars = [], fillBars = [];
    CT.sliders.forEach(function (s2, si) {
      var hy = makeBar("ctHoverBar", "assets/ui/opt/ct/sl_track_hover.png");
      hy.style.top = (s2.y * sy) + "px";
      hy.style.width = (SL_TRACK_PX * sx) + "px";
      hoverBars[si] = hy;

      var fb = makeBar("ctFillBar", "assets/ui/opt/ct/sl_track_sel.png");
      fb.style.top = (s2.y * sy) + "px";
      fillBars[si] = fb;

      // 热区
      var d = document.createElement("div");
      d.className = "ctHot";
      d.style.left = (s2.x * sx) + "px";
      d.style.top = (s2.y * sy) + "px";
      d.style.width = (s2.n * s2.pitch * sx) + "px";
      d.style.height = (s2.h * sy) + "px";
      d.addEventListener("mouseenter", function () { hy.classList.add("on"); });
      d.addEventListener("mouseleave", function () { hy.classList.remove("on"); });
      d.addEventListener("click", function (e) {
        e.stopPropagation();
        var r = box.getBoundingClientRect();
        var ax = (e.clientX - r.left) / r.width * CT.W;
        var n = Math.floor((ax - s2.x) / s2.pitch) + 1;
        CT.slideVal[si] = Math.max(1, Math.min(s2.n, n));
        drawFill(si);
      });
      box.appendChild(d);
    });

    function drawFill(si) {
      var fb = fillBars[si];
      var n = CT.slideVal[si];
      if (!n) { fb.classList.remove("on"); return; }
      fb.style.width = (n * 16 * sx) + "px";
      fb.classList.add("on");
    }

    // 初始状态
    for (var k2 in CT.sel) paint(+k2);
    for (var si2 = 0; si2 < CT.sliders.length; si2++) drawFill(si2);
  }

// ---------- OPTION 2 内容区（03101 常态 / 03210 悬停 / 03211 选中）----------
  var CT2 = {
    W: 1024, H: 464,
    W_STAGE: 645.27, H_STAGE: 292.45,
    dir: "assets/ui/opt/ct2/",
    widgets: [[458,14,252,36,1],[714,14,252,36,1],[458,54,164,36,2],[630,54,164,36,2],[802,54,164,36,2],[482,118,52,36,0],[890,118,52,36,0],[390,119,80,14,3],[390,137,80,14,3],[482,158,52,36,0],[890,158,52,36,0],[390,159,80,14,4],[390,177,80,14,4],[482,198,52,36,0],[890,198,52,36,0],[946,198,52,36,0],[390,199,80,14,5],[390,217,80,14,5],[482,238,52,36,0],[890,238,52,36,0],[946,238,52,36,0],[390,239,80,14,6],[390,257,80,14,6],[458,302,252,36,7],[714,302,252,36,7],[458,342,252,36,8],[714,342,252,36,8]],
    sliders: [{x:543,y:119,n:21,pitch:16,h:26},{x:543,y:159,n:21,pitch:16,h:26},{x:543,y:199,n:21,pitch:16,h:26},{x:543,y:239,n:21,pitch:16,h:26}],
    sel: { 0: 1, 2: 1, 7: 1, 11: 1, 16: 1, 21: 1, 24: 1, 26: 1 },
    slideVal: [13, 13, 13, 21]
  };

  function bindContent2() {
    if (window.__ct2Bound) return;
    window.__ct2Bound = true;

    var box = byId("optContent2");
    if (!box) return;

    var sx = CT2.W_STAGE / CT2.W;
    var sy = CT2.H_STAGE / CT2.H;

    var baseLayer = box.querySelector(".ctBase");
    if (baseLayer) baseLayer.classList.add("on");

    var W2 = function (i) { return (i < 10 ? "0" + i : "" + i); };
    var imgs = [];
    CT2.widgets.forEach(function (w, idx) {
      var img = document.createElement("img");
      img.className = "ctImg";
      img.style.left = (w[0] * sx) + "px";
      img.style.top = (w[1] * sy) + "px";
      img.style.width = (w[2] * sx) + "px";
      img.style.height = (w[3] * sy) + "px";
      box.appendChild(img);
      imgs[idx] = img;
    });

    function paint(idx) {
      var img = imgs[idx];
      if (CT2.sel[idx]) {
        img.src = CT2.dir + "w" + W2(idx) + "_sel.png";
        img.classList.add("on");
      } else if (img.dataset.hover) {
        img.src = CT2.dir + "w" + W2(idx) + "_hover.png";
        img.classList.add("on");
      } else {
        img.classList.remove("on");
      }
    }

    function clickWidget(idx) {
      var g = CT2.widgets[idx][4];
      if (g === 0) return;
      if (CT2.sel[idx]) { delete CT2.sel[idx]; paint(idx); return; }
      for (var k in CT2.sel) {
        if (+k !== idx && CT2.widgets[+k][4] === g) { delete CT2.sel[k]; paint(+k); }
      }
      CT2.sel[idx] = 1;
      paint(idx);
    }

    CT2.widgets.forEach(function (w, idx) {
      var d = document.createElement("div");
      d.className = "ctHot";
      d.style.left = (w[0] * sx) + "px";
      d.style.top = (w[1] * sy) + "px";
      d.style.width = (w[2] * sx) + "px";
      d.style.height = (w[3] * sy) + "px";
      d.addEventListener("mouseenter", function () {
        imgs[idx].dataset.hover = "1"; paint(idx);
      });
      d.addEventListener("mouseleave", function () {
        delete imgs[idx].dataset.hover; paint(idx);
      });
      d.addEventListener("click", function (e) {
        e.stopPropagation();
        clickWidget(idx);
      });
      box.appendChild(d);
    });

    // 滑块：轨道图 + 宽度裁剪
    var TRACK = 21 * 16;
    var hoverBars = [], fillBars = [];
    CT2.sliders.forEach(function (s2, si) {
      var hy = document.createElement("div");
      hy.className = "ctBar ctHoverBar";
      hy.style.left = (s2.x * sx) + "px";
      hy.style.top = (s2.y * sy) + "px";
      hy.style.width = (TRACK * sx) + "px";
      hy.style.height = (s2.h * sy) + "px";
      var hi = document.createElement("img");
      hi.src = CT2.dir + "sl" + si + "_hover.png";
      hi.style.width = (TRACK * sx) + "px";
      hi.style.height = (s2.h * sy) + "px";
      hy.appendChild(hi);
      box.appendChild(hy);
      hoverBars[si] = hy;

      var fb = document.createElement("div");
      fb.className = "ctBar ctFillBar";
      fb.style.left = (s2.x * sx) + "px";
      fb.style.top = (s2.y * sy) + "px";
      fb.style.height = (s2.h * sy) + "px";
      var fi = document.createElement("img");
      fi.src = CT2.dir + "sl" + si + "_sel.png";
      fi.style.width = (TRACK * sx) + "px";
      fi.style.height = (s2.h * sy) + "px";
      fb.appendChild(fi);
      box.appendChild(fb);
      fillBars[si] = fb;

      var d = document.createElement("div");
      d.className = "ctHot";
      d.style.left = (s2.x * sx) + "px";
      d.style.top = (s2.y * sy) + "px";
      d.style.width = (s2.n * s2.pitch * sx) + "px";
      d.style.height = (s2.h * sy) + "px";
      d.addEventListener("mouseenter", function () { hy.classList.add("on"); });
      d.addEventListener("mouseleave", function () { hy.classList.remove("on"); });
      d.addEventListener("click", function (e) {
        e.stopPropagation();
        var r = box.getBoundingClientRect();
        var ax = (e.clientX - r.left) / r.width * CT2.W;
        var n = Math.floor((ax - s2.x) / s2.pitch) + 1;
        CT2.slideVal[si] = Math.max(1, Math.min(s2.n, n));
        drawFill2(si);
      });
      box.appendChild(d);
    });

    function drawFill2(si) {
      var fb = fillBars[si];
      var n = CT2.slideVal[si];
      if (!n) { fb.classList.remove("on"); return; }
      fb.style.width = (n * 16 * sx) + "px";
      fb.classList.add("on");
    }

    for (var k2 in CT2.sel) paint(+k2);
    for (var si2 = 0; si2 < CT2.sliders.length; si2++) drawFill2(si2);
  }

// ---------- OPTION 3：三个模型板块 ----------
  var MODEL_SECTIONS = ["chat", "voice", "mt"];
  var MODEL_FIELDS = ["endpoint", "key", "model"];
  var TEXT_VER = "1031opt3";

  function txtUrl(t) {
    return "/api/text?text=" + encodeURIComponent(t) + "&plain=1&v=" + TEXT_VER + "&max_width=4000";
  }

  function modelApi(cb, body) {
    var xhr = new XMLHttpRequest();
    xhr.open(body ? "POST" : "GET", "/api/modelcfg", true);
    if (body) xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onload = function () {
      var d = null;
      try { d = JSON.parse(xhr.responseText); } catch (err) {}
      cb(d);
    };
    xhr.onerror = function () { cb(null); };
    xhr.send(body ? JSON.stringify(body) : null);
  }

  function setConnLabel(btn, text) {
    var old = btn.querySelector("img");
    if (old) old.remove();
    if (!text) return;
    var im = new Image();
    im.src = txtUrl(text);
    btn.appendChild(im);
  }

  var modelBound = false;
  function bindModelFields() {
    if (modelBound) return;
    modelBound = true;

    var box = byId("optContent3");
    if (!box) return;

    // 显示一个值：优先字模图；若渲染成多行则退回单行文本
    function showValue(wrap, text) {
      var img = wrap.querySelector(".o3val");
      var sp = wrap.querySelector(".o3plain");
      if (!img) {
        img = document.createElement("img");
        img.className = "o3val";
        wrap.insertBefore(img, sp || null);
      }
      if (!sp) {
        sp = document.createElement("span");
        sp.className = "o3plain";
        sp.setAttribute("data-no-uitext", "1");
        wrap.appendChild(sp);
      }
      img.classList.remove("show");
      sp.classList.remove("show");
      img.removeAttribute("src");
      if (!text) { sp.textContent = ""; return; }

      img.onload = function () {
        var ratio = (img.naturalWidth > 0)
          ? img.naturalHeight / img.naturalWidth : 1;
        if (ratio > 0.30) {           // 高/宽偏大 → 图是多行
          img.classList.remove("show");
          sp.textContent = text;
          sp.classList.add("show");
        } else {
          img.classList.add("show");
          sp.textContent = "";
          sp.classList.remove("show");
        }
      };
      img.onerror = function () {
        img.classList.remove("show");
        sp.textContent = text;
        sp.classList.add("show");
      };
      img.src = txtUrl(text);
    }

    // ---------- 字段：提交时把 input 移出 DOM ----------
    function maskKey(v) {
      if (!v) return "";
      return new Array(Math.min(v.length, 24) + 1).join("•");
    }

    function fieldOf(k) {
      return box.querySelector('.o3field[data-k="' + k + '"]');
    }

    function commitField(wrap) {
      var inp = wrap._inp || wrap.querySelector(".o3input");
      if (!inp) return;
      wrap._inp = inp;
      var v = inp.value;
      var isKey = (inp.dataset.k || "").indexOf(".key") >= 0;
      var show = isKey ? maskKey(v) : v;
      var img = wrap.querySelector(".o3val");

      if (!v) {
        wrap.classList.remove("committed");
        if (!inp.parentNode) wrap.appendChild(inp);
        var sp0 = wrap.querySelector(".o3plain");
        if (sp0) { sp0.textContent = ""; sp0.classList.remove("show"); }
        var im0 = wrap.querySelector(".o3val");
        if (im0) { im0.classList.remove("show"); im0.removeAttribute("src"); }
        return;
      }
      wrap.classList.add("committed");
      // 把 input 从 DOM 拿掉，再用单行文本显示
      if (inp.parentNode) inp.parentNode.removeChild(inp);
      showValue(wrap, show);
    }

    function beginEdit(wrap) {
      var inp = wrap._inp;
      if (!inp) return;
      wrap.classList.remove("committed");
      var sp = wrap.querySelector(".o3plain");
      if (sp) sp.textContent = "";
      if (!inp.parentNode) wrap.appendChild(inp);
      inp.style.display = "";
      setTimeout(function () { inp.focus(); }, 0);
    }

    Array.prototype.forEach.call(box.querySelectorAll(".o3field"), function (wrap) {
      var inp = wrap.querySelector(".o3input");
      if (!inp) return;
      wrap._inp = inp;
      wrap.dataset.k = inp.dataset.k || "";

      inp.addEventListener("focus", function () { wrap.classList.remove("committed"); });
      inp.addEventListener("blur", function () { commitField(wrap); });
      inp.addEventListener("keydown", function (e) {
        e.stopPropagation();
        if (e.key === "Enter") inp.blur();
      });
      wrap.addEventListener("click", function () {
        if (wrap.classList.contains("committed")) beginEdit(wrap);
      });
    });

    // ---------- 模型名：只显示 ----------
    function setModelName(sec, name) {
      var wrap = fieldOf(sec + ".model");
      if (!wrap) return;
      if (wrap._inp && wrap._inp.parentNode) wrap._inp.parentNode.removeChild(wrap._inp);
      wrap.classList.add("committed");
      showValue(wrap, name || "");
    }

    // 本地端点隐藏密钥行
    function syncKeyRow(sec, endpoint) {
      var wrap = fieldOf(sec + ".key");
      if (!wrap) return;
      var row = wrap.closest(".o3row");
      if (!row) return;
      var ep = (endpoint || "").toLowerCase();
      var local = ep.indexOf("127.0.0.1") >= 0 || ep.indexOf("localhost") >= 0
                  || ep.indexOf("0.0.0.0") >= 0 || ep.indexOf("::1") >= 0;
      row.style.display = local ? "none" : "";
    }

    // 清空某个板块：恢复成刚打开时的空白状态（密钥输入框重新出现）
    function resetSection(sec) {
      MODEL_FIELDS.forEach(function (f) {
        var wrap = fieldOf(sec + "." + f);
        if (!wrap) return;
        var inp = wrap._inp || wrap.querySelector(".o3input");
        if (inp) {
          inp.value = "";
          if (!inp.parentNode) wrap.appendChild(inp);
          inp.style.display = "";
        }
        wrap.classList.remove("committed");
        var sp = wrap.querySelector(".o3plain");
        if (sp) { sp.textContent = ""; sp.classList.remove("show"); }
        var im = wrap.querySelector(".o3val");
        if (im) { im.classList.remove("show"); im.removeAttribute("src"); }
      });
      // 密钥行恢复显示
      var kwrap = fieldOf(sec + ".key");
      if (kwrap) {
        var row = kwrap.closest(".o3row");
        if (row) row.style.display = "";
      }
      // 按钮回到未连接
      var b = btns[sec];
      if (b) { b.classList.remove("on"); b.classList.remove("fail"); setConnLabel(b, "连接"); }
      // 后端也清空，下次打开是空白
      modelApi(function () {}, { section: sec, endpoint: "", key: "", model: "", probe: false });
    }

    // ---------- 连接按钮 ----------
    var btns = {};
    MODEL_SECTIONS.forEach(function (sec, i) {
      var b = document.createElement("button");
      b.className = "o3conn";
      b.dataset.sec = sec;
      setConnLabel(b, "连接");
      var secEl = box.querySelector(".o3sec" + (i + 1));
      if (secEl) secEl.appendChild(b);
      btns[sec] = b;

      var sw = document.createElement("button");
      sw.className = "o3switch";
      setConnLabel(sw, "切换模型");
      if (secEl) secEl.appendChild(sw);
      sw.addEventListener("click", function (e) {
        e.stopPropagation();
        if (b.classList.contains("on")) {
          // 已连接：先断开，再重置
          modelApi(function () { resetSection(sec); }, { section: sec, disconnect: true });
        } else {
          resetSection(sec);
        }
      });

      b.addEventListener("click", function (e) {
        e.stopPropagation();

        if (b.classList.contains("on")) {
          modelApi(function (d) {
            b.classList.remove("on");
            b.classList.remove("fail");
            setConnLabel(b, "连接");
            if (d && d.cfg && d.cfg[sec]) syncKeyRow(sec, d.cfg[sec].endpoint);
          }, { section: sec, disconnect: true });
          return;
        }

        var payload = { section: sec, probe: true };
        MODEL_FIELDS.forEach(function (f) {
          var w = fieldOf(sec + "." + f);
          var inp = w ? (w._inp || w.querySelector(".o3input")) : null;
          payload[f] = inp ? inp.value.trim() : "";
        });

        // 端点是空的：明确提示，别让它默默失败
        if (!payload.endpoint) {
          setConnLabel(b, "请填端点");
          setTimeout(function () { setConnLabel(b, "连接"); }, 1800);
          var w0 = fieldOf(sec + ".endpoint");
          if (w0) {
            w0.classList.remove("committed");
            var i0 = w0._inp || w0.querySelector(".o3input");
            if (i0) {
              if (!i0.parentNode) w0.appendChild(i0);
              i0.style.display = "";
              i0.focus();
            }
          }
          return;
        }

        setConnLabel(b, "连接中");
        b.disabled = true;
        modelApi(function (d) {
          b.disabled = false;
          if (d && d.ok) {
            b.classList.add("on");
            b.classList.remove("fail");
            setConnLabel(b, "已连接");
            var got = d.cfg && d.cfg[sec];
            if (got) {
              setModelName(sec, got.model);
              syncKeyRow(sec, got.endpoint);
            }
          } else {
            b.classList.remove("on");
            b.classList.add("fail");
            setConnLabel(b, "连接失败");
            setTimeout(function () {
              b.classList.remove("fail");
              setConnLabel(b, "连接");
            }, 2000);
          }
        }, payload);
      });
    });

    // ---------- 打开时回填 ----------
    modelApi(function (d) {
      if (!d) return;
      MODEL_SECTIONS.forEach(function (sec) {
        var got = d[sec];
        if (!got) return;
        MODEL_FIELDS.forEach(function (f) {
          if (f === "model") return;
          var wrap = fieldOf(sec + "." + f);
          if (!wrap) return;
          var inp = wrap._inp || wrap.querySelector(".o3input");
          if (!inp) return;
          wrap._inp = inp;
          inp.value = got[f] || "";
          commitField(wrap);
        });
        setModelName(sec, got.model);
        syncKeyRow(sec, got.endpoint);
        var b = btns[sec];
        if (b) {
          if (got.connected) {
            b.classList.add("on");
            setConnLabel(b, "已连接");
          } else {
            setConnLabel(b, "连接");
          }
        }
      });
    });
  }

  // ---------- 右下角 EXIT：三态 ----------
  var exitBound = false;
  function bindExit() {
    if (exitBound) return;
    exitBound = true;
    /* EXIT: shared .uiExit (sys_09100 3 states, CSS-driven) */
    var el = document.querySelector("#optScreen .uiExit");
    if (!el) return;
    el.addEventListener("click", function (e) {
      e.stopPropagation();
      close();
    });
  }
  window.__openOptions = function () { open(); return false; };
  window.__closeOptions = close;

  document.addEventListener("DOMContentLoaded", function () {
    var s = byId("optScreen");
    if (!s) return;
    // 点空白处关闭（后续加内容时改成只关弹层）
    s.addEventListener("click", function (e) {
      if (e.target === s) close();
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && window.__optOpen) close();
  });
})();
