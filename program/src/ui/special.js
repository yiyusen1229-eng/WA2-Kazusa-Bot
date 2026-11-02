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
  var CTX_MAX = 32000;            // 会被 /api/special/cfg 返回的 ctx_max 覆盖
  var FIXED_OVERHEAD = 1200;      // 人设 / 世界书 / 系统提示的固定开销（粗略）
  var EST_OUT_TOKENS = 200;       // 估一轮的回复长度（真实花费含输出，不估会偏低）

  var state = { ctx: 100, trigger: 60, recent: 25, entries: 12 };
  /* 恢复默认用的值：打开时从后端 defaults 取，取不到就用上面这份 */
  var DEF = { ctx: 100, trigger: 60, recent: 25, entries: 12 };
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
  var KNOB_PAD = 8;      // 滑块中心离轨道两端留的距离（舞台像素），两端不贴边框
  var dirty = false;     // 有改动还没写回文件

  function placeKnob(slider) {
    var knob = slider.querySelector(".spKnob");
    if (!knob) return;
    var w = slider.clientWidth || 300;
    var pct = state[slider.dataset.k];
    knob.style.left = (KNOB_PAD + (w - KNOB_PAD * 2) * pct / 100).toFixed(1) + "px";
  }

  function setValue(key, pct) {
    pct = Math.max(0, Math.min(100, Math.round(pct)));
    if (state[key] === pct) return;
    state[key] = pct;
    dirty = true;
    var slider = $("sps-" + key);
    if (slider) placeKnob(slider);
    scheduleReadouts();
  }

  function pctFromEvent(slider, ev) {
    var r = slider.getBoundingClientRect();
    var w = slider.clientWidth || 300;
    var scale = r.width / w || 1;
    var pad = KNOB_PAD * scale;
    var usable = Math.max(1, r.width - pad * 2);
    return (ev.clientX - r.left - pad) / usable * 100;
  }

  function layout() {
    ["ctx", "trigger", "recent", "entries"].forEach(function (k) {
      var s = $("sps-" + k);
      if (!s) return;
      s.tabIndex = 0;
      s.setAttribute("role", "slider");
      s.setAttribute("aria-label", k);
      placeKnob(s);
    });
    renderReadouts();
    refreshPrice();          // 每次打开都重新取一次价（模型 / 时段可能变了）
  }

  function bindSlider(slider) {
    var key = slider.dataset.k;

    slider.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      slider.classList.add("dragging");
      try { slider.setPointerCapture(e.pointerId); } catch (err) {}
      slider.__drag = true;
      setValue(key, pctFromEvent(slider, e));
    });
    slider.addEventListener("pointermove", function (e) {
      if (!slider.__drag) return;
      setValue(key, pctFromEvent(slider, e));
    });
    function endDrag() {
      slider.__drag = false;
      slider.classList.remove("dragging");
      commitCfg();          // 拖动停止就写文件
    }
    slider.addEventListener("pointerup", endDrag);
    slider.addEventListener("pointercancel", endDrag);
    slider.addEventListener("lostpointercapture", endDrag);

    slider.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") { setValue(key, state[key] - 1); e.preventDefault(); }
      else if (e.key === "ArrowRight" || e.key === "ArrowUp") { setValue(key, state[key] + 1); e.preventDefault(); }
      else return;
      if (readTimer) clearTimeout(readTimer);
      readTimer = setTimeout(function () { readTimer = null; renderReadouts(); commitCfg(); }, 400);
    });
  }

  /* ---------- 存读档设置 ↔ memory.json ---------- */
  function loadCfg() {
    return fetch("/api/special/cfg", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.cfg) return;
        if (d.ctx_max) CTX_MAX = d.ctx_max;
        if (d.defaults) {
          DEF = { ctx: Math.round(d.defaults.cloud_ctx / CTX_MAX * 100),
                  trigger: Math.round(d.defaults.trigger_ratio * 100),
                  recent: Math.round(d.defaults.recent_ratio * 100),
                  entries: Math.round(d.defaults.entries_ratio * 100) };
        }
        var c = d.cfg;
        state.ctx = Math.round(c.cloud_ctx / CTX_MAX * 100);
        state.trigger = Math.round(c.trigger_ratio * 100);
        state.recent = Math.round(c.recent_ratio * 100);
        state.entries = Math.round(c.entries_ratio * 100);
        layout();
      })
      .catch(function () { /* 后端没起来就先用默认值 */ });
  }

  function commitCfg() {
    if (!dirty) return;
    dirty = false;
    var body = {
      cloud_ctx: Math.round(CTX_MAX * state.ctx / 100),
      trigger_ratio: state.trigger / 100,
      recent_ratio: state.recent / 100,
      entries_ratio: state.entries / 100
    };
    fetch("/api/special/cfg", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { flash(d && d.ok ? "已保存" : "保存失败"); })
      .catch(function () { flash("保存失败"); });
  }

  /* ---------- 角色名称 + 保存 ---------- */
  var savedTimer = null;

  function flash(msg) {
    var el = $("spSaved");
    if (!el) return;
    if (msg === "已保存") {
      /* 固定文案用烤好的图；其它（报错）是动态的，仍走 /api/text */
      el.innerHTML = '<img src="assets/ui/text/sp_saved.png" alt="">';
      el.__txt = null;
    } else {
      setGlyph(el, msg);
    }
    el.classList.add("on");
    if (savedTimer) clearTimeout(savedTimer);
    savedTimer = setTimeout(function () { el.classList.remove("on"); }, 1600);
  }

  /* ---------- 切换角色 / 新建角色 ----------
     · 切换：后端弹系统的文件夹选择窗口，从「总角色资源文件夹」里挑一个
     · 新建：后端在那个总目录里新建一个角色文件夹，建完直接切过去
     成功后：名字、五项资源的「当前：xxx」、立绘索引全部刷新（下一条消息就生效） */
  function afterCharacter(res) {
    nameValue = res.name || nameValue;
    renderNameView();
    if (window.__setCharName && res.name) window.__setCharName(res.name);
    try { if (window.__reloadSprites) window.__reloadSprites(); } catch (e) {}
    refreshStatus();
    loadName();
  }

  function postCharacter(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  var charBusy = false;

  function switchCharacter() {
    if (charBusy) return;
    charBusy = true;
    flash("正在选择角色文件夹…");
    postCharacter("/api/character/pick")
      .then(function (d) {
        charBusy = false;
        if (d && d.ok) { afterCharacter(d); flash("已切换到 " + (d.name || d.id)); return; }
        /* 取消 / 选错：也从后端重读一次名字和状态，
           让「角色名称」永远显示真正生效的那个角色，而不是上一屏残留 */
        loadName();
        refreshStatus();
        if (d && d.error) flash(d.error);
        else if (d && d.cancelled) flash("已取消，当前角色：" + (d.name || d.active || ""));
      })
      .catch(function () {
        charBusy = false;
        loadName();
        refreshStatus();
        flash("切换失败");
      });
  }

  function newCharacter() {
    if (charBusy) return;
    charBusy = true;
    postCharacter("/api/character/new")
      .then(function (d) {
        charBusy = false;
        if (d && d.ok) { afterCharacter(d); flash("已新建 " + (d.name || d.id)); }
        else flash((d && d.error) || "新建失败");
      })
      .catch(function () { charBusy = false; flash("新建失败"); });
  }

  var charsBound = false;
  function bindCharacters() {
    if (charsBound) return;
    charsBound = true;
    var sw = $("spSwitch");
    var nw = $("spNew");
    if (sw) sw.addEventListener("click", function (e) { e.stopPropagation(); switchCharacter(); });
    if (nw) nw.addEventListener("click", function (e) { e.stopPropagation(); newCharacter(); });
  }

  function bindSave() {
    var btn = $("spSave");
    var inp = $("spName");
    var view = $("spNameView");
    if (view) view.addEventListener("click", editName);
    if (btn) {
      /* 按住保存键时别让 blur 先把输入框收回去 */
      btn.addEventListener("mousedown", function () { keepInput = true; });
      btn.addEventListener("click", function () { saveName(); });
    }
    if (inp) {
      inp.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); saveName(); }
        else if (e.key === "Escape") { e.preventDefault(); renderNameView(); }
      });
      inp.addEventListener("blur", function () {
        setTimeout(function () {
          if (keepInput) { keepInput = false; return; }
          renderNameView();          // 没保存就还原成字模
        }, 160);
      });
    }
  }

  /* ---------- 角色名：char/name.txt（对话框左上角显示的就是这个） ---------- */
  var nameValue = "和纱";
  var keepInput = false;

  /* 平时：字模显示，输入框藏起来 */
  function renderNameView() {
    var view = $("spNameView");
    var inp = $("spName");
    if (inp) inp.style.display = "none";
    if (view) {
      view.style.display = "flex";
      setGlyph(view, nameValue);
    }
  }

  /* 点一下名字：换成输入框并选中 */
  function editName() {
    var view = $("spNameView");
    var inp = $("spName");
    if (!view || !inp) return;
    view.style.display = "none";
    inp.style.display = "block";
    inp.value = nameValue;
    inp.focus();
    try { inp.select(); } catch (e) {}
  }

  function loadName() {
    fetch("/api/special/name", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok && d.name) nameValue = d.name;
        renderNameView();
      })
      .catch(function () { renderNameView(); });
  }

  function saveName() {
    var inp = $("spName");
    /* 输入框藏着的时候，保存的是当前显示的名字（点「保存」不该报「名字不能为空」） */
    var editing = !!(inp && inp.style.display !== "none");
    var name = (editing ? inp.value : nameValue || "").trim();
    if (!name) { flash("名字不能为空"); return; }
    keepInput = true;
    fetch("/api/special/name", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok) {
          nameValue = d.name;
          renderNameView();                    // 存完变回字模
          flash("已保存");
          if (window.__setCharName) window.__setCharName(d.name);   // 对话框名字立刻跟着变
        } else {
          flash((d && d.error) || "保存失败");
        }
      })
      .catch(function () { flash("保存失败"); });
  }

  /* ---------- 恢复默认设置（sys_03030 按钮） ---------- */
  function resetDefaults() {
    state.ctx = DEF.ctx;
    state.trigger = DEF.trigger;
    state.recent = DEF.recent;
    state.entries = DEF.entries;
    layout();
    dirty = true;
    commitCfg();
  }

  /* ---------- 角色资源：选文件 → 上传落盘 ---------- */
  var FILE_ACCEPT = {
    portrait: "image/*,.png,.jpg,.jpeg,.webp,.bmp,.gif",
    prompt: ".txt,.md,text/plain",
    worldbook: ".txt,.md,.json,text/plain,application/json",
    memory: ".txt,.md,text/plain",
    voice: "audio/*,.wav,.mp3,.ogg,.flac,.m4a"
  };
  var pickers = {};

  function picker(kind) {
    var inp = pickers[kind];
    if (inp) return inp;
    inp = document.createElement("input");
    inp.type = "file";
    inp.accept = FILE_ACCEPT[kind] || "";
    inp.setAttribute("data-no-uitext", "1");
    inp.style.cssText = "position:fixed;left:-9999px;top:0;width:1px;height:1px;opacity:0";
    inp.addEventListener("change", function () {
      var f = inp.files && inp.files[0];
      try { inp.value = ""; } catch (e) {}
      if (f) upload(kind, f);
    });
    document.body.appendChild(inp);
    pickers[kind] = inp;
    return inp;
  }

  function upload(kind, file) {
    var reader = new FileReader();
    reader.onload = function () {
      fetch("/api/special/upload?kind=" + encodeURIComponent(kind) +
            "&name=" + encodeURIComponent(file.name), {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: reader.result
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok) {
            flash("已保存");
            refreshStatus();          // 「当前：xxx（已导入）」立刻更新
          } else {
            flash((d && d.error) || "保存失败");
          }
        })
        .catch(function () { flash("保存失败"); });
    };
    reader.onerror = function () { flash("读取失败"); };
    reader.readAsArrayBuffer(file);
  }

  /* ---------- 配置项：点一下框头，箭头转 90° 并滑出面板 ----------
     面板里两个按钮：
       · 导入文件 → 原来的系统选文件窗口，选完上传落盘
       · 查看文件 → 让后端在资源管理器里打开这一类资源的目录，方便自己看/替换 */
  var PANEL_BTNS = [
    { act: "import", img: "assets/ui/text/sp_btn_import.png", title: "导入文件" },
    { act: "open",   img: "assets/ui/text/sp_btn_open.png",   title: "查看文件" }
  ];

  function buildPanel() {
    var panel = document.createElement("div");
    panel.className = "spPanel";
    var row = document.createElement("div");
    row.className = "spPanelBtns";
    PANEL_BTNS.forEach(function (b) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "spPanelBtn";
      btn.dataset.act = b.act;
      btn.title = b.title;
      var img = document.createElement("img");
      img.src = b.img;
      img.alt = b.title;
      btn.appendChild(img);
      row.appendChild(btn);
    });
    panel.appendChild(row);
    /* 「当前用的是哪个文件」——导入目录只是中转站，程序优先读这里，没有就用默认文件 */
    var now = document.createElement("div");
    now.className = "spPanelNow";
    panel.appendChild(now);
    return panel;
  }

  /* ---------- 当前生效的资源（/api/special/status） ----------
     没导入时显示程序默认读的文件，免得以为「查看文件」打开的目录就是全部。 */
  function shortName(s, max) {
    s = s || "";
    return s.length > max ? (s.slice(0, max - 1) + "…") : s;
  }

  function renderResourceStatus(files) {
    var items = document.querySelectorAll("#specialScreen .spItem");
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var kind = item.dataset.item;
      var el = item.querySelector(".spPanelNow");
      if (!el) continue;
      if (kind === "portrait") {
        setGlyph(el, "当前：角色文件夹的 portrait/（按变化的文件名归类）");
        continue;
      }
      var f = files && files[kind];
      if (!f) {
        setGlyph(el, "当前：还没设置");
        continue;
      }
      var name = f.file || ((f.path || "").split(/[\\/]/).pop() + "/");
      var tag = f.source === "character" ? "（角色文件夹）"
              : (f.source === "imported" ? "（已导入）" : "（默认）");
      setGlyph(el, "当前：" + shortName(name, 22) + tag);
    }
  }

  function refreshStatus() {
    fetch("/api/special/status", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.ok) renderResourceStatus(d.files); })
      .catch(function () { /* 后端没起来就不显示，不影响其它功能 */ });
  }

  /* 同一时间只开一个：开新的先把别的收起来（箭头跟着转回去） */
  function closePanels(except) {
    var open = document.querySelectorAll("#specialScreen .spItem.open");
    for (var i = 0; i < open.length; i++) {
      if (open[i] === except) continue;
      open[i].classList.remove("open");
      var h = open[i].querySelector(".spHead");
      if (h) h.setAttribute("aria-expanded", "false");
    }
  }

  function togglePanel(item, head) {
    var willOpen = !item.classList.contains("open");
    closePanels(item);
    item.classList.toggle("open", willOpen);
    head.setAttribute("aria-expanded", willOpen ? "true" : "false");
  }

  /* 「查看文件」：后端会打开这一类资源**实际被读取**的位置
     （导入过就是导入的那份，没导入就是程序默认文件） */
  function openFolder(kind) {
    fetch("/api/special/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: kind })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) { flash((d && d.error) || "打不开文件夹"); return; }
        if (d.source === "empty") flash("还没有默认文件，先导入一份");
      })
      .catch(function () { flash("打不开文件夹"); });
  }

  function bindFrames() {
    var items = document.querySelectorAll("#specialScreen .spItem");
    for (var i = 0; i < items.length; i++) {
      (function (item) {
        var head = item.querySelector(".spHead");
        if (!head) return;
        var kind = item.dataset.item;
        if (!item.querySelector(".spPanel")) item.appendChild(buildPanel());

        head.addEventListener("pointerdown", function (e) {
          e.preventDefault();
          head.classList.add("down");
        });
        ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) {
          head.addEventListener(n, function () { head.classList.remove("down"); });
        });
        head.addEventListener("click", function () {
          head.classList.remove("down");
          togglePanel(item, head);
        });
        head.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            togglePanel(item, head);
          }
        });

        var btns = item.querySelectorAll(".spPanelBtn");
        for (var j = 0; j < btns.length; j++) {
          (function (btn) {
            btn.addEventListener("click", function (e) {
              e.stopPropagation();
              if (btn.dataset.act === "import") {
                item.classList.remove("open");            // 选完文件就收起来
                head.setAttribute("aria-expanded", "false");
                picker(kind).click();
              } else if (btn.dataset.act === "open") {
                openFolder(kind);
              }
            });
          })(btns[j]);
        }
      })(items[i]);
    }
  }

  /* ---------- 打开 / 关闭 ---------- */
  var bound = false;

  /* 调试/探针：读当前每轮费用估算 */
  window.__spPrice = function () { return priceState; };

  window.__openSpecial = function () {
    var s = window.__showUIScreen
      ? window.__showUIScreen("specialScreen")
      : document.getElementById("specialScreen");
    if (s && !s.classList.contains("show")) s.classList.add("show");

    if (!bound) {
      bound = true;
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
})();
