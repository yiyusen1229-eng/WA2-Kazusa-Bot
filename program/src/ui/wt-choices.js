/* wt-choices.js —— 选择分支（galgame 那种选项条）
 *
 * 流程：点「选择分支」→ POST /api/choice（带上最近对话 + prefs 里设的选项数量）
 *      → 渲染 2~5 条选项（bar.png 三态：常态 / 悬停高亮+金字 / 按下）
 *      → 悬停播 se_select；点一条 → 整层淡出 → 把选项当成玩家说的话发出去
 *
 * 素材：assets/ui/choice/bar.png（sys_00200）、assets/ui/save/d1..d9.png（烤好的数字字模）、
 *      assets/snowflake_right.png（两端雪花）。样式在 choice.css。
 *
 * 探针：window.__openChoices() 直接弹；window.WA2.choices.state 看状态。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  var state = { open: false, busy: false, options: [], error: "", count: 2 };
  var FADE_MS = 420;

  function prefsCount() {
    var n = 2;
    try {
      var p = (WA2.prefs && WA2.prefs.getPrefs) ? WA2.prefs.getPrefs() : null;
      if (p && p.choiceCount) n = parseInt(p.choiceCount, 10) || 2;
    } catch (e) {}
    if (!n) {
      try {
        var raw = localStorage.getItem("app_prefs");
        if (raw) n = parseInt(JSON.parse(raw).choiceCount, 10) || 2;
      } catch (e) {}
    }
    return Math.max(2, Math.min(5, n));
  }

  function historyMsgs() {
    var h = window.__history || [];
    var out = [];
    for (var i = 0; i < h.length; i++) {
      if (!h[i] || !h[i].content) continue;
      out.push({ role: h[i].role, content: String(h[i].content).slice(0, 400) });
    }
    return out.slice(-8);
  }

  function se(name) {
    try { if (typeof window.playSE === "function") window.playSE(name); } catch (e) {}
  }

  function layer() {
    var el = $("choiceScreen");
    if (!el) {
      el = document.createElement("div");
      el.id = "choiceScreen";
      var list = document.createElement("div");
      list.id = "choiceList";
      el.appendChild(list);
      document.body.appendChild(el);
    }
    return el;
  }

  function numGlyphs(i) {
    /* 用烤好的数字字模：1~9 取 dN.png；「.」用 CSS 点 */
    var n = String(i + 1);
    var h = "";
    for (var k = 0; k < n.length; k++) {
      h += '<img src="assets/ui/save/d' + n.charAt(k) + '.png" alt="">';
    }
    return '<span class="choiceNum">' + h + '<i class="dot"></i></span>';
  }

  function render(options) {
    var el = layer();
    var list = $("choiceList");
    list.innerHTML = "";
    options.forEach(function (txt, i) {
      var b = document.createElement("button");
      b.className = "choiceRow";
      b.setAttribute("data-i", String(i));
      b.innerHTML = '<span class="choiceBg"></span><span class="choiceTop"></span>' +
                    '<span class="choiceSnow"></span><span class="choiceTag"></span>' +
                    numGlyphs(i) + '<span class="choiceTxt"></span>';
      b.querySelector(".choiceTxt").textContent = txt;
      b.addEventListener("mouseenter", function () { b.classList.add("hover"); se("hover"); });
      b.addEventListener("mouseleave", function () { b.classList.remove("hover"); });
      b.addEventListener("click", function (e) { e.stopPropagation(); pick(i); });
      list.appendChild(b);
    });
    el.classList.remove("fading");
    el.classList.add("show");
    state.open = true;
    state.options = options.slice();
  }

  function hide(instant) {
    var el = $("choiceScreen");
    state.open = false;
    if (!el) return;
    if (instant) {
      el.classList.remove("show", "fading");
      return;
    }
    el.classList.add("fading");
    setTimeout(function () { el.classList.remove("show", "fading"); }, FADE_MS);
  }

  function pick(i) {
    var txt = state.options[i];
    if (!txt) return;
    se("click");
    state.open = false;
    var el = $("choiceScreen");
    if (el) el.classList.add("fading");
    setTimeout(function () {
      if (el) el.classList.remove("show", "fading");
      try {
        var inp = $("input");
        if (inp) {
          inp.value = txt;
          inp.dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (typeof window.send === "function") window.send();
        else if (WA2.chat && WA2.chat.send) WA2.chat.send();
      } catch (e) {}
    }, FADE_MS);
  }

  function open() {
    if (state.busy || state.open) return Promise.resolve(state);
    var el = layer();
    var list = $("choiceList");
    state.busy = true;
    state.error = "";
    state.count = prefsCount();
    list.innerHTML = '<div class="choiceLoading">……</div>';
    el.classList.add("show");
    var body = { count: state.count, messages: historyMsgs() };
    return fetch("/api/choice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        state.busy = false;
        if (!d || !d.ok || !(d.options || []).length) {
          state.error = (d && d.error) || "没有生成选项";
          hide(true);
          try { if (window.__toast) window.__toast("选择分支失败：" + state.error, 2400); } catch (e) {}
          return state;
        }
        render(d.options);
        return state;
      })
      .catch(function (e) {
        state.busy = false;
        state.error = String(e);
        hide(true);
        try { if (window.__toast) window.__toast("选择分支失败：" + state.error, 2400); } catch (e) {}
        return state;
      });
  }

  document.addEventListener("keydown", function (e) {
    if (!state.open) return;
    var k = parseInt(e.key, 10);
    if (k >= 1 && k <= state.options.length) { e.preventDefault(); pick(k - 1); }
    else if (e.key === "Escape") { e.preventDefault(); hide(); }
  });

  document.addEventListener("DOMContentLoaded", function () {
    var btn = $("choiceBtn");
    if (btn) btn.addEventListener("click", function (e) { e.preventDefault(); open(); });
  });

  WA2.choices = { state: state, open: open, openChoices: open, showChoices: open,
                  pick: pick, hide: hide, prefsCount: prefsCount };
  WA2.register("choices", WA2.choices);
  window.openChoices = open;
  window.showChoices = open;          /* 旧名字，别的模块还在用 */
  window.__openChoices = open;
})();
