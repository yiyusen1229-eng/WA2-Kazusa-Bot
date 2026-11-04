/* 特别模式：存读档设置（百分比滑条 + 实时 token 换算）与角色配置（资源导入）
 *
 * 存读档设置：
 *   · 4 个滑条改的是 memory.json 里的 cloud_ctx / trigger_ratio / recent_ratio / entries_ratio
 *   · 打开界面时读 /api/special/cfg；拖动结束（或键盘调整后 400ms）写回文件
 *   · token 读数由 /api/text 出字模图，和界面其它文字同一套
 *
 * 角色配置：
 *   · 5 个底框是「框头」，点一下三角箭头顺时针转 90°（朝下），并从框下
 *     滑出一个面板，面板里两个按钮：
 *       导入文件 → 弹系统选文件窗口（<input type=file>，WebView2 里就是 Windows 原生对话框）
 *       查看文件 → 后端在资源管理器里打开这一类资源所在的目录
 *   · 前端按类型给 accept 提示，真正的类型校验在后端 special_files.py
 *   · 选好的文件上传后落到 char/<kind>/ 下，成功后闪一下「已保存」
 *
 * 排版坐标是 800x450 舞台坐标；文字全部走统一字模。
 */
(function () {
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- 参数 ---------- */
  var CTX_MAX = window.__spCTXMAX = 32000;            // 会被 /api/special/cfg 返回的 ctx_max 覆盖
  var FIXED_OVERHEAD = 1200;      // 人设 / 世界书 / 系统提示的固定开销（粗略）
  var EST_OUT_TOKENS = 200;       // 估一轮的回复长度（真实花费含输出，不估会偏低）

  var state = window.__spState = { ctx: 100, trigger: 60, recent: 25, entries: 12 };
  /* 恢复默认用的值：打开时从后端 defaults 取，取不到就用上面这份 */
  var DEF = window.__spDEF = { ctx: 100, trigger: 60, recent: 25, entries: 12 };
  /* 每轮费用：不开本地估算，直接问后端要（和右下角花费同口径，随模型/高峰变） */
  var priceState = { cost: null, phase: "", model: "" };

  /* ---------- 统一字模 ----------
     实际渲染交给 uitext.js 的 __uiTextRender（和界面其它文字同一条 /api/text 链路），
     这里只做「同样内容不重复渲染」的缓存判断。 */
  function setGlyph(el, text) {
    if (!el || el.__txt === text) return;
    el.__txt = text;
    if (window.__uiTextRender) {
      window.__uiTextRender(el, text, { tight: true });   // tight：数字不撑满全角格
    } else {
      el.textContent = text;                              // 极端情况下的兜底
    }
  }

  /* ---------- 换算 ---------- */
  function tokens() {
    var ctx = Math.round(CTX_MAX * state.ctx / 100);
    var trigger = Math.round(ctx * state.trigger / 100);
    var recent = Math.round(ctx * state.recent / 100);
    var entries = Math.round(ctx * state.entries / 100);
    var turn = recent + entries + FIXED_OVERHEAD;
    return { ctx: ctx, trigger: trigger, recent: recent, entries: entries, turn: turn };
  }

  /* ---------- 每轮费用：问后端，不自己乘常数 ----------
     /api/price/estimate 走 pricing.py：同一个价目表、同一套高峰判断，
     所以换模型 / 进高峰时段，这里和右下角的实际花费会一起变。 */
  var priceTimer = null, priceSeq = 0;

  function activeModel() {
    try {
      var a = JSON.parse(localStorage.getItem("app_active_model") || "{}");
      return a.model || "";
    } catch (e) { return ""; }
  }

  function refreshPrice() {
    var seq = ++priceSeq;
    var url = "/api/price/estimate?tokens=" + Math.max(1, Math.round(tokens().turn)) +
              "&out=" + EST_OUT_TOKENS;
    var m = activeModel();
    if (m) url += "&model=" + encodeURIComponent(m);
    fetch(url, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (seq !== priceSeq || !d || !d.ok) return;
        priceState = { cost: d.cost, phase: d.phase, model: d.model };
        renderCost();
      })
      .catch(function () { /* 后端没起来就保留上一次的数 */ });
  }

  /* 和右下角花费同一套小数位规则（game.js 的 moneyStr），保证两边看起来同口径 */
  function formatCost(c) {
    if (typeof c !== "number" || !isFinite(c)) return null;
    if (c === 0) return "0";
    if (c < 0.01) return c.toFixed(6);
    if (c < 1) return c.toFixed(4);
    return c.toFixed(3);
  }

  function renderCost() {
    var el = $("spv-cost");
    if (!el) return;
    var s = formatCost(priceState.cost);
    setNum(el, s === null ? "¥—" : "¥" + s);
    el.title = (s === null ? "取不到实时价格" :
                ("按 " + (priceState.model || "当前模型") +
                 (priceState.phase === "peak" ? "（高峰时段）" : "（空闲时段）") + " 估算"));
  }

  /* ---------- 读数 ---------- */
  var readTimer = null;

  /* ---------- 读数：用已经烤好的素材拼 ----------
     数字 → cost_d0~9，小数点 → cost_dot，¥ → cost_yen（都是花费栏那套，不重烤）
     字母 token → cost_token（在「每轮 token 预估」标签里）
     只有 % = ≈ 这三个符号是新烤的 sp_pct / sp_eq / sp_approx */
  var NUM_SRC = {
    "0": "assets/ui/text/cost_d0.png", "1": "assets/ui/text/cost_d1.png",
    "2": "assets/ui/text/cost_d2.png", "3": "assets/ui/text/cost_d3.png",
    "4": "assets/ui/text/cost_d4.png", "5": "assets/ui/text/cost_d5.png",
    "6": "assets/ui/text/cost_d6.png", "7": "assets/ui/text/cost_d7.png",
    "8": "assets/ui/text/cost_d8.png", "9": "assets/ui/text/cost_d9.png",
    ".": "assets/ui/text/cost_dot.png",
    "¥": "assets/ui/text/cost_yen.png",
    "%": "assets/ui/text/sp_pct.png",
    "=": "assets/ui/text/sp_eq.png",
    "≈": "assets/ui/text/sp_approx.png"
  };

  function numHTML(text) {
    var out = "";
    for (var i = 0; i < text.length; i++) {
      var c = text.charAt(i);
      if (c === " ") { out += '<span class="spGap"></span>'; continue; }
      var src = NUM_SRC[c];
      if (src) out += '<img' + (c === "%" || c === "=" || c === "≈" ? ' class="sym"' : "") + ' src="' + src + '" alt="">';
    }
    return out;
  }

  function setNum(el, text) {
    if (!el) return;
    var html = numHTML(text);
    if (el.__num === html) return;
    el.__num = html;
    el.innerHTML = html;
  }

  function renderReadouts() {
    var t = tokens();
    setNum($("spv-ctx"), state.ctx + "% = " + t.ctx);
    setNum($("spv-trigger"), state.trigger + "% = " + t.trigger);
    setNum($("spv-recent"), state.recent + "% = " + t.recent);
    setNum($("spv-entries"), state.entries + "% = " + t.entries);
    setNum($("spv-turn"), "≈ " + t.turn);
    renderCost();
  }

  function scheduleReadouts() {
    if (readTimer) clearTimeout(readTimer);
    readTimer = setTimeout(function () { readTimer = null; renderReadouts(); }, 60);
    /* 价格问后端要，拖滑条时别每帧都发：250ms 一次，最后一个请求说了算 */
    if (priceTimer) clearTimeout(priceTimer);
    priceTimer = setTimeout(function () { priceTimer = null; refreshPrice(); }, 250);
  }

  /* ---------- 滑条 ---------- */
  var KNOB_PAD = window.__spKnobPad = 8;      // 滑块中心离轨道两端留的距离（舞台像素），两端不贴边框
  var dirty = false;     // 有改动还没写回文件

/* placeKnob / setValue / layout 已搬到 spSliders.js（WA2.spSliders） */

/* afterCharacter / postCharacter / openCharPicker 已搬到 spChar.js（WA2.spChar） */

/* renderNameView / editName / loadName 已搬到 spPanels.js（WA2.spPanels） */

  window.__spPrice = function () { return priceState; };

  window.__openSpecial = function () {
    var s = window.__showUIScreen
      ? window.__showUIScreen("specialScreen")
      : document.getElementById("specialScreen");
    if (s && !s.classList.contains("show")) s.classList.add("show");

    if (!window.__spBound) {
      window.__spBound = true;
      ["ctx", "trigger", "recent", "entries"].forEach(function (k) {
        var sl = $("sps-" + k);
        if (sl) bindSlider(sl);
      });
      bindSave();
      bindFrames();
      bindCharacters();
      var rb = $("spReset");
      if (rb) rb.addEventListener("click", resetDefaults);
    }
    layout();
    closePanels(null);               // 每次打开都是收起状态
    loadCfg();                       // 读文件里的实际值，覆盖默认值
    refreshStatus();                 // 每个框「当前用的是哪个文件」
    renderNameView();                // 先摆默认名，读到 char/name.txt 再覆盖
    loadName();
    /* 隐藏时 uitext 不会处理标签，显示后补扫一遍 */
    if (s && window.__uiTextScan) window.__uiTextScan(s);
  };

  /* sp-* 模块（sliders/char/panels）是本文件拆出去的，它们要用这里的函数和状态 */
  window.__spExported = true;
  ["CTX_MAX", "DEF", "EST_OUT_TOKENS", "FIXED_OVERHEAD", "KNOB_PAD", "NUM_SRC", "a", "activeModel", "c", "ctx", "dirty", "el", "entries", "formatCost", "html", "m", "numHTML", "out", "priceState", "priceTimer", "rb", "readTimer", "recent", "refreshPrice", "renderCost", "renderReadouts", "s", "scheduleReadouts", "seq", "setGlyph", "setNum", "sl", "src", "state", "t", "tokens", "trigger", "turn", "url"].forEach(function (n) {
    try { var v = eval(n); window[n] = v; } catch (e) {}
  });
})();
