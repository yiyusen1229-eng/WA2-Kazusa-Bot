/* wt-choices.js —— 选择分支：让 AI 按当前对话给几个分歧选项，点一条就当玩家发言发出去。
 *
 * 结构：点「选择分支」→ POST /api/choice → 每条画成 .choiceRow
 *       （.choiceBg 三段拉伸的条 + .choiceSnowL/R 两端雪花 + .choiceTag 白牌 +
 *         .choiceNum 烤好的数字字模 + .choiceTxt 文字）
 * 几何：见 choice.css 顶部注释（读数来自原版整帧截图，系数 800/2730）。
 * 交互：悬停换高亮贴图 + 字变金；点击整层淡出 420ms 后发送；数字键 1~5 选择，Esc 关闭。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  var state = { open: false, busy: false, options: [], error: "", count: 2 };
  var FADE_MS = 420;
  var ROW_TOP = 176;      /* 首条上沿（舞台 px，原版实测） */
  var ROW_PITCH = 29;     /* 行距 */

  function prefsCount() {
    var n = 2;
    try {
      var p = (WA2.prefs && WA2.prefs.getPrefs) ? WA2.prefs.getPrefs() : null;
      if (p && p.choiceCount) n = parseInt(p.choiceCount, 10) || 2;
    } catch (e) {}
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

  function numHTML(i) {
    var s = String(i + 1), h = "";
    for (var k = 0; k < s.length; k++) {
      h += '<img src="assets/ui/save/d' + s.charAt(k) + '.png" alt="">';
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
      b.style.top = (ROW_TOP + i * ROW_PITCH) + "px";
      b.innerHTML = '<span class="choiceBg"></span>' +
                    '<span class="choiceSnowL"></span><span class="choiceSnowR"></span>' +
                    '<span class="choiceTag"></span>' + numHTML(i) +
                    '<span class="choiceTxt"></span>';
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

  function hide() {
    var el = $("choiceScreen");
    state.open = false;
    if (!el) return;
    el.classList.remove("show", "fading");
  }

  function pick(i) {
    var txt = state.options[i];
    if (!txt) return;
    se("click");
    state.open = false;
    var el = $("choiceScreen");
    if (el) el.classList.add("fading");        /* 整层淡出，和演出过渡同一个时长 */
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
    return fetch("/api/choice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count: state.count, messages: historyMsgs() })
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        state.busy = false;
        if (!d || !d.ok || !(d.options || []).length) {
          state.error = (d && d.error) || "没有生成选项";
          hide();
          try { if (window.__toast) window.__toast("选择分支失败：" + state.error, 2400); } catch (e) {}
          return state;
        }
        render(d.options);
        return state;
      })
      .catch(function (e) {
        state.busy = false;
        state.error = String(e);
        hide();
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
  window.showChoices = open;          /* 旧名，别的模块还在用 */
  window.__openChoices = open;
})();
