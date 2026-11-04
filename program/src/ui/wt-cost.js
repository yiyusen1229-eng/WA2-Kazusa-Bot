/* cost.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.cost；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  function costNum(el, str) {
    if (!el) return;
    if (el.dataset.v === str && el.children.length) return;
    el.dataset.v = str;
    var html = "";
    for (var i = 0; i < str.length; i++) {
      var ch = str.charAt(i);
      var key = (ch === ".") ? "cost_dot" : ("cost_d" + ch);
      html += '<img src="assets/ui/text/' + key + '.png" alt="' + ch + '">';
    }
    el.innerHTML = html;
    /* 字模图缺失时退回文字，至少能看到数字 */
    var imgs = el.querySelectorAll("img");
    for (var j = 0; j < imgs.length; j++) {
      (function (img, c) {
        img.addEventListener("error", function () {
          if (!el.dataset.plain) {
            el.dataset.plain = "1";
            el.style.fontSize = "11px";
            el.style.color = "#cfe9f5";
            el.style.lineHeight = "12px";
            el.textContent = str;
          }
        });
      })(imgs[j], str);
    }
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
    /* 每次渲染前重新确认元素（拆分后元素可能比脚本晚出现） */
    try { bindCostEls(); } catch (e) {}
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

  /* 绑定四个数字容器；元素还没出来就下次调用时再绑（拆分后这类时序更脆弱） */
  function bindCostEls() {
    if (COST_EL.totT && COST_EL.totC && COST_EL.nowT && COST_EL.nowC) return true;
    COST_EL.nowT = document.getElementById("costNowT");
    COST_EL.nowC = document.getElementById("costNowC");
    COST_EL.totT = document.getElementById("costTotalT");
    COST_EL.totC = document.getElementById("costTotalC");
    return !!(COST_EL.totT && COST_EL.totC);
  }

  function refresh() {
    bindCostEls();
    try { window.__refreshCost(); } catch (e) {}
  }

  window.__renderCost = renderCost;
  window.__bindCost = bindCostEls;
  window.__refreshCostNow = refresh;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      refresh();
      setInterval(refresh, 20000);
    });
  } else {
    refresh();
    setInterval(refresh, 20000);
  }

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
    window.__charName = n;
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
  if (WA2.cost) WA2.cost.render = renderCost;
  /* __export_all__ */
  ["costNum", "moneyStr", "renderCost", "WA2", "_exp", "_names", "ch", "css", "el", "html", "key"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
