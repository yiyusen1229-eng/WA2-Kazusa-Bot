/* optWidgets.js —— 从 opt.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.optWidgets；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

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

      // 每个控件一张 img，按状态切图（被删掉的行是 null，直接跳过）
      var imgs = [];
      CT.widgets.forEach(function (w, idx) {
        if (!w) { imgs[idx] = null; return; }
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
        if (!img) { return; }   /* 控件被删但 sel 还有残留 key，直接跳过 */
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

      /* 「窗口透明度（普通场景）」那一行的左右箭头（12/13）；其余三行按用户要求先不接 */
      var CT_ARROWS = { 12: -1, 13: 1 };

      function clickWidget(idx) {
        if (!CT.widgets[idx]) return;              // 被删掉的行
        var g = CT.widgets[idx][4];
        var d = CT_ARROWS[idx];
        if (d) {
          var s = CT.sliders[0];
          CT.slideVal[0] = Math.max(1, Math.min(s.n, (CT.slideVal[0] || s.n) + d));
          drawFill(0);
          applyCt1();
          return;
        }
        if (g === 0) return;                       // 其它箭头：暂不接
        if (CT.sel[idx]) return;                   // 单选组：不允许再点一下变成"全都不选"
        for (var k in CT.sel) {
          var wk = CT.widgets[+k];
          if (+k !== idx && wk && wk[4] === g) { delete CT.sel[k]; paint(+k); }
        }
        CT.sel[idx] = 1;
        paint(idx);
        applyCt1();
        /* 窗口 / 全屏：点了就真的切窗口 */
        if (idx === 0 || idx === 1) {
          try { if (window.__setWinMode) window.__setWinMode(idx === 1 ? "full" : "window"); } catch (e) {}
        }
      }

      // 热区（被删掉的行不建热区）
      CT.widgets.forEach(function (w, idx) {
        if (!w) return;
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
          if (si === 0) applyCt1();     /* 只有「普通场景窗口透明度」接了功能 */
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

      /* 全量重画（启动时按 prefs 还原后调用） */
      window.__ct1RepaintAll = function () {
        for (var i = 0; i < imgs.length; i++) paint(i);
        for (var si = 0; si < CT.sliders.length; si++) drawFill(si);
      };

      // 初始状态
      for (var k2 in CT.sel) paint(+k2);
      for (var si2 = 0; si2 < CT.sliders.length; si2++) drawFill(si2);
    }

  // ---------- OPTION 2 内容区（03101 常态 / 03210 悬停 / 03211 选中）----------
  /* 控件分组（原始 27 个控件见 assets/ui/opt/ct2/widgets.js.txt）：
       1 = 是/否确认（0 确认 / 1 不确认）
       2 = 滑鼠右键功能（2 隐藏窗口 / 3 设置菜单 / 4 存档）
       0 = 箭头与试听（5/6、9/10、13/14、18/19 四组左右箭头，15/20 试听）
       3~6 = 四条音量的 音量ON / 音量OFF（7/8、11/12、16/17、21/22）
       7 = 翻页时中断语音（23/24）—— 用户要求删除，已不再创建
       8 = 原版的空行（25/26）—— 从未使用 */
    CT2 = {
      W: 1024, H: 464,
      W_STAGE: 645.27, H_STAGE: 292.45,
      dir: "assets/ui/opt/ct2/",
      widgets: [[458,14,252,36,1],[714,14,252,36,1],[458,54,164,36,2],[630,54,164,36,2],[802,54,164,36,2],[482,118,52,36,0],[890,118,52,36,0],[390,119,80,14,3],[390,137,80,14,3],[482,158,52,36,0],[890,158,52,36,0],[390,159,80,14,4],[390,177,80,14,4],[482,198,52,36,0],[890,198,52,36,0],[946,198,52,36,0],[390,199,80,14,5],[390,217,80,14,5],[482,238,52,36,0],[890,238,52,36,0],[946,238,52,36,0],[390,239,80,14,6],[390,257,80,14,6]],
      sliders: [{x:543,y:119,n:21,pitch:16,h:26},{x:543,y:159,n:21,pitch:16,h:26},{x:543,y:199,n:21,pitch:16,h:26},{x:543,y:239,n:21,pitch:16,h:26}],
      sel: { 0: 1, 2: 1, 7: 1, 11: 1, 16: 1, 21: 1 },
      slideVal: [13, 13, 13, 21]
    };

    function bindContent2() {
    if (window.__ct2Bound) return;
      window.__ct2Bound = true;
      ;

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

      function paint2(idx) {
        var img = imgs[idx];
        if (!img) { return; }   /* 控件被删但 sel 还有残留 key，直接跳过 */
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

      /* 全量重画（启动时按 prefs 还原后调用；paint 只重画 sel 里的控件，不够用） */
      window.__ct2RepaintAll = function () {
        for (var i = 0; i < imgs.length; i++) paint2(i);
        for (var si = 0; si < CT2.sliders.length; si++) drawFill2(si);
      };

      /* 箭头 / 音量 ON-OFF 的索引表（控件已固定在 0~22，删掉 23/24 后不会位移） */
      var ARROWS = { 5: [0, -1], 6: [0, 1], 9: [1, -1], 10: [1, 1],
                     13: [2, -1], 14: [2, 1], 18: [3, -1], 19: [3, 1] };
      var PILLS = { 7: [0, 1], 8: [0, 0], 11: [1, 1], 12: [1, 0],
                    16: [2, 1], 17: [2, 0], 21: [3, 1], 22: [3, 0] };
      var PILL_IDX = [[7, 8], [11, 12], [16, 17], [21, 22]];

      /* 「音量ON / 音量OFF」跟着滑块走：0% 显示 OFF，其余显示 ON */
      function syncPill(si) {
        var pair = PILL_IDX[si];
        if (!pair) return;
        var on = (CT2.slideVal[si] || 1) > 1;
        var want = on ? pair[0] : pair[1], other = on ? pair[1] : pair[0];
        if (!CT2.sel[want]) {
          delete CT2.sel[other];
          CT2.sel[want] = 1;
          paint2(want); paint2(other);
        }
      }

      function clickWidget2(idx) {
        var g = CT2.widgets[idx][4];
        /* 左右箭头：一格 = 5% */
        var ar = ARROWS[idx];
        if (ar) {
          var s = CT2.sliders[ar[0]];
          CT2.slideVal[ar[0]] = Math.max(1, Math.min(s.n, (CT2.slideVal[ar[0]] || 1) + ar[1]));
          drawFill2(ar[0]);
          syncPill(ar[0]);
          applyCt2();
          return;
        }
        /* 音量 ON / OFF：ON = 满格，OFF = 静音 */
        var pf = PILLS[idx];
        if (pf) {
          CT2.slideVal[pf[0]] = pf[1] ? CT2.sliders[pf[0]].n : 1;
          drawFill2(pf[0]);
          syncPill(pf[0]);
          applyCt2();
          return;
        }
        if (g === 0) return;                     /* 试听按钮：暂未接 */
        if (CT2.sel[idx]) { delete CT2.sel[idx]; paint2(idx); applyCt2(); return; }
        for (var k in CT2.sel) {
          var wk = CT2.widgets[+k];
          if (+k !== idx && wk && wk[4] === g) { delete CT2.sel[k]; paint2(+k); }
        }
        CT2.sel[idx] = 1;
        paint2(idx);
        /* 选中分支原来漏了 applyCt2 —— 于是「是/否确认」「右键功能」只在界面上变，实际不生效 */
        applyCt2();
      }

      CT2.widgets.forEach(function (w, idx) {
        var d = document.createElement("div");
        d.className = "ctHot";
        d.style.left = (w[0] * sx) + "px";
        d.style.top = (w[1] * sy) + "px";
        d.style.width = (w[2] * sx) + "px";
        d.style.height = (w[3] * sy) + "px";
        d.addEventListener("mouseenter", function () {
          imgs[idx].dataset.hover = "1"; paint2(idx);
        });
        d.addEventListener("mouseleave", function () {
          delete imgs[idx].dataset.hover; paint2(idx);
        });
        d.addEventListener("click", function (e) {
          e.stopPropagation();
          clickWidget2(idx);
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
          syncPill(si);
          applyCt2();
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

      for (var k3 in CT2.sel) { if (+k3 >= CT2.widgets.length) delete CT2.sel[k3]; }
      for (var k2 in CT2.sel) paint2(+k2);
      for (var si2 = 0; si2 < CT2.sliders.length; si2++) { drawFill2(si2); syncPill(si2); }
    }

  // ---------- OPTION 3：三个模型板块 ----------
    window.MODEL_SECTIONS = ["chat", "voice", "mt"];
    window.MODEL_FIELDS = ["endpoint", "key", "model"];
    window.TEXT_VER = "1031opt3";
  var _exp = {};
  var _names = ["bindContent", "bindContent2", "clickWidget", "drawFill", "drawFill2", "makeBar", "paint", "syncPill"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.optWidgets = _exp;
  WA2.register("optWidgets", _exp);
  /* __export_all__ */
  ["bindContent", "bindContent2", "clickWidget", "drawFill", "drawFill2", "makeBar", "paint", "syncPill", "ARROWS", "CT_ARROWS", "DIR", "PILLS", "PILL_IDX", "SL_TRACK_PX", "TRACK", "W2", "WA2", "_exp", "_names", "ar", "ax", "baseLayer", "box", "d", "fb", "fi", "g", "hi", "hoverBars", "hy", "im", "img", "imgs", "n", "on", "pair", "pf", "r", "s", "sx", "sy", "want", "wk"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
