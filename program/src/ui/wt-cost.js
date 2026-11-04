/* cost.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.cost；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  function costNum(el, str) {
    if (!el) return;
    if (el.dataset.v === str) return;
    el.dataset.v = str;
    var html = "";
    for (var i = 0; i < str.length; i++) {
      var ch = str.charAt(i);
      var key = (ch === ".") ? "cost_dot" : ("cost_d" + ch);
      html += '<img src="assets/ui/text/' + key + '.png" alt="">';
    }
    el.innerHTML = html;
  }

  /* 金额转成"纯数字串"（币种符号已经是一张固定的 ¥ 图） */
  function moneyStr(v) {
    v = Number(v) || 0;
    if (v === 0) return "0";
    if (v < 0.01) return v.toFixed(6);
    if (v < 1) return v.toFixed(4);
    return v.toFixed(3);
  }

  function renderCost(u) {
    if (!u) return;
    if (u.tokens !== undefined) {
      costNum(COST_EL.nowT, String(Math.round(u.tokens)));
      costNum(COST_EL.nowC, moneyStr(u.cost));
    }
    costNum(COST_EL.totT, String(Math.round(u.cumTokens || 0)));
    costNum(COST_EL.totC, moneyStr(u.cumCost));
  }
  /* 只刷新累计（程序启动时、以及后台总结之后） */
  window.__refreshCost = function () {
    try {
      fetch("/api/usage", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok) renderCost({ cumTokens: d.tokens, cumCost: d.cost });
        })
        .catch(function () {});
    } catch (e) {}
  };

  document.addEventListener("DOMContentLoaded", function () {
    COST_EL.nowT = document.getElementById("costNowT");
    COST_EL.nowC = document.getElementById("costNowC");
    COST_EL.totT = document.getElementById("costTotalT");
    COST_EL.totC = document.getElementById("costTotalC");
    window.__refreshCost();
    setInterval(function () { window.__refreshCost(); }, 20000);
  });

  /* 隐藏窗口后，左键点一下画面就恢复 ——
     此时 UI 全是 pointer-events:none，点事件落在底层元素上，所以监听在 document 捕获阶段。
     右键不走这里（交给上面的 contextmenu，避免"恢复界面"和"右键功能"同时触发）。 */
  document.addEventListener("click", function (e) {
    if (!document.body.classList.contains("uiHidden")) return;
    document.body.classList.remove("uiHidden");
    e.preventDefault();
    e.stopPropagation();   /* 只负责"叫回界面"，不要顺带翻页 */
  }, true);

  /* 隐藏界面：只留背景与立绘
     注意选择器必须对得上真实 ID：#menubar / .dialogBox / #quickBar 这三个在 DOM 里根本不存在
     （菜单栏是 #menuBar，对话框是 #msgWrap），所以之前「隐藏窗口」只隐藏了底部工具栏。 */
  (function () {
    var css = document.createElement("style");
    css.textContent =
      "body.uiHidden #msgWrap,body.uiHidden #inputBar,body.uiHidden #toolbar," +
      "body.uiHidden #menuBar,body.uiHidden #glowBottom,body.uiHidden #historyPanel," +
      "body.uiHidden #thinkBox,body.uiHidden #choiceScreen,body.uiHidden #costBar," +
      "body.uiHidden .uiScreen," +
      "body.uiHidden #dbgPanel{" +
      "opacity:0!important;pointer-events:none!important}";
    document.head.appendChild(css);
  })();

  /* ---------- 角色名：存在 char/name.txt，特别模式里改的就是它 ---------- */
  window.__setCharName = function (n) {
    if (!n) return;
    CHAR_NAME = n;
    var el = document.getElementById("namePlate");
    if (el && typeof gdiRenderName === "function") gdiRenderName(n, el);
    // 输入框占位符等跟着名字变（uitext.js 监听）
    try {
      document.dispatchEvent(new CustomEvent("wa2:charname", { detail: n }));
    } catch (e) {}
  };
  fetch("/api/special/name", { cache: "no-store" })
    .then(function (r) { return r.json(); })
    .then(function (d) { if (d && d.ok && d.name) window.__setCharName(d.name); })
    .catch(function () {});


  /* ---------- 启动默认全屏 ---------- */
  var _exp = {};
  var _names = ["costNum", "moneyStr", "renderCost"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.cost = _exp;
  WA2.register("cost", _exp);
  /* __export_all__ */
  ["costNum", "moneyStr", "renderCost", "WA2", "_exp", "_names", "ch", "css", "el", "html", "key"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
