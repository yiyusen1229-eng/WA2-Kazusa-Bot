/* wt-choices.js —— 选择分支：让 AI 按当前对话给几个分歧选项，点一条就当玩家发言发出去。
 *
 * 结构（每条 .choiceRow 是 490×45 的绝对定位盒子，几何见 choice.css 顶部注释）：
 *   .choiceBg     条身贴图（常态永远画段1 bar_off.png，整张等比铺满）
 *   .choiceHl     悬停高亮（段2 bar_on.png，plus-lighter 加法叠在条身上，不是替换）
 *   .choiceSnow   两端雪花（snow.png，和条身同画布同原点）
 *   .choiceTag    小白牌（tag.png，真素材）
 *   .choiceTxt    一整张字模：「1.」+ 选项正文，白字/金字两层叠着做交叉淡入
 *
 * 字体走 /api/text 的补丁字模（白字 + 2px 黑描边，和对话框同一套渲染）；
 * 悬停那层用同样的字加 color= 染色，所以"字变金"是烘出来的，不是滤镜凑的。
 *
 * 交互：悬停整条变亮 + 字变金；点击整层淡出后发送；数字键 1~5 选择，Esc 关闭。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  var VER = "202611052300";            /* 字模缓存版本：改字号/描边要 bump */

  /* 几何（舞台 px，原版整帧实测；改之前先读 choice.css 顶部注释） */
  var BAR_X = 154.7;
  var BAR_W = 490;
  var BAR_H = 45;
  var ROW0_Y = 148;                    /* 第 1 条上沿 */
  var PITCH = 52;                      /* 行距 */
  var SAFE_BOTTOM = 318;               /* 别压到对话框（#msgWrap 顶边 320） */
  var FADE_MS = 260;

  var state = { open: false, busy: false, options: [], error: "" };

  var COLORS = { normal: "", gold: "f0e0a0" };

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

  function perf(on) {
    try {
      var p = WA2.perf;
      if (!p) return;
      if (on) p.begin("OVERLAY_OPEN");
      else if (p.active("OVERLAY_OPEN")) p.end("OVERLAY_OPEN");
    } catch (e) {}
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

  /* 一条 = 编号+正文 的一整张字模；color 传空 = 白字，传色号 = 染成那个颜色 */
  function bake(text, color) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.className = color ? "txtGold" : "txtNormal";
      img.alt = "";
      img.onload = function () { resolve(img); };
      img.onerror = function () { resolve(null); };
      img.src = "/api/text?text=" + encodeURIComponent(text) +
                "&chars_per_line=999&max_width=4000&plain=0" +
                (color ? ("&color=" + color) : "") + "&v=" + VER;
    });
  }

  function rowTop(i, n) {
    /* 2 条时就是原版位置；3~5 条整块以 2 条的块心为中心上移，且不许压到对话框 */
    var top = ROW0_Y - (n - 2) * PITCH / 2;
    var maxTop = SAFE_BOTTOM - BAR_H - (n - 1) * PITCH;
    if (top > maxTop) top = maxTop;
    if (top < 24) top = 24;
    return Math.round(top + i * PITCH);
  }

  function buildRow(i, text, normalImg, goldImg) {
    var b = document.createElement("button");
    b.className = "choiceRow";
    b.type = "button";
    b.setAttribute("data-no-uitext", "1");        /* 字模已经烘好了，别再被 uitext 包一层 */
    b.innerHTML = '<span class="choiceBg"></span>' +
                  '<span class="choiceHl"></span>' +
                  '<span class="choiceSnow"></span>' +
                  '<span class="choiceTag"></span>' +
                  '<span class="choiceTxt"></span>';
    var box = b.querySelector(".choiceTxt");
    if (normalImg) box.appendChild(normalImg);
    if (goldImg) box.appendChild(goldImg);
    if (!normalImg) {                              /* 字模没烘出来时退回原生字体，至少能点 */
      box.textContent = (i + 1) + "." + text;
      box.style.cssText = "font-size:13px;color:#fff;line-height:20px;" +
                          "text-shadow:0 0 2px #000,0 1px 2px #000;";
    }
    b.addEventListener("mouseenter", function () { b.classList.add("hover"); se("hover"); });
    b.addEventListener("mouseleave", function () { b.classList.remove("hover"); });
    b.addEventListener("click", function (e) { e.stopPropagation(); pick(i); });
    return b;
  }

  function render(options) {
    var el = layer();
    var list = $("choiceList");
    var n = options.length;
    return Promise.all(options.map(function (txt, i) {
      var line = (i + 1) + "." + txt;
      return Promise.all([bake(line, COLORS.normal), bake(line, COLORS.gold)]);
    })).then(function (pairs) {
      list.innerHTML = "";
      options.forEach(function (txt, i) {
        var row = buildRow(i, txt, pairs[i][0], pairs[i][1]);
        row.style.top = rowTop(i, n) + "px";
        list.appendChild(row);
      });
      el.classList.remove("fading");
      el.classList.add("in", "show");
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { el.classList.remove("in"); });
      });
      state.open = true;
      state.options = options.slice();
      perf(true);
      return state;
    });
  }

  function hide(opts) {
    var el = $("choiceScreen");
    state.open = false;
    perf(false);
    if (!el) return;
    el.classList.remove("show", "in", "fading");
    if (!opts || !opts.keepList) {
      var list = $("choiceList");
      if (list) list.innerHTML = "";
    }
    setBusy(false);
  }

  function pick(i) {
    var txt = state.options[i];
    if (!txt) return;
    se("click");
    state.open = false;
    var el = $("choiceScreen");
    if (el) el.classList.add("fading");           /* 整层淡出，和演出过渡同一个节奏 */
    setTimeout(function () {
      hide();
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

  function setBusy(on) {
    state.busy = !!on;
    var btn = $("choiceBtn");
    if (btn) btn.classList.toggle("busy", state.busy);
  }

  function open() {
    if (state.busy || state.open) return Promise.resolve(state);
    setBusy(true);
    state.error = "";
    var count = prefsCount();
    return fetch("/api/choice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count: count, messages: historyMsgs() })
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !(d.options || []).length) {
          state.error = (d && d.error) || "没有生成选项";
          setBusy(false);
          try { if (window.__toast) window.__toast("选择分支失败：" + state.error, 2400); } catch (e) {}
          return state;
        }
        return render(d.options).then(function () { setBusy(false); return state; });
      })
      .catch(function (e) {
        state.error = String(e);
        setBusy(false);
        try { if (window.__toast) window.__toast("选择分支失败：" + state.error, 2400); } catch (e) {}
        return state;
      });
  }

  function isOpen() { return state.open; }

  /* 键盘：1~5 直接选，Esc 关。Esc 要吃掉事件，不然 wt-nav 会顺手回标题 */
  document.addEventListener("keydown", function (e) {
    if (!state.open) return;
    var k = parseInt(e.key, 10);
    if (k >= 1 && k <= state.options.length) {
      e.preventDefault(); e.stopPropagation();
      pick(k - 1);
    } else if (e.key === "Escape") {
      e.preventDefault(); e.stopPropagation();
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      hide();
    }
  }, true);

  document.addEventListener("DOMContentLoaded", function () {
    var btn = $("choiceBtn");
    if (btn) btn.addEventListener("click", function (e) { e.preventDefault(); open(); });
  });

  WA2.choices = {
    state: state, open: open, openChoices: open, showChoices: open,
    pick: pick, hide: hide, isOpen: isOpen, prefsCount: prefsCount
  };
  WA2.register("choices", WA2.choices);

  window.openChoices = open;
  window.showChoices = open;            /* 旧名，别的模块还在用 */
  window.__openChoices = open;
  window.__closeChoices = function () {   /* 右键 / __closeTopScreen 用：关掉返回 true */
    if (!state.open) return false;
    hide();
    return true;
  };
})();
