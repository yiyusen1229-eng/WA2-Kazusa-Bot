/* spSliders.js —— 从 special.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.spSliders；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };
  /* 共享状态在 special.js 的 window 上（special.js 是 IIFE，变量不是全局） */
  var state = (window.__spState = window.__spState || { ctx: 100, trigger: 60, recent: 25, entries: 12 });
  var DEF = (window.__spDEF = window.__spDEF || { ctx: 100, trigger: 60, recent: 25, entries: 12 });

    function placeKnob(slider) {
      var knob = slider.querySelector(".spKnob");
      if (!knob) return;
      var w = slider.clientWidth || 300;
      var pct = state[slider.dataset.k];
      knob.style.left = (window.__spKnobPad + (w - window.__spKnobPad * 2) * pct / 100).toFixed(1) + "px";
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
      var pad = window.__spKnobPad * scale;
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
          if (d.ctx_max) window.__spCTXMAX = d.ctx_max;
          if (d.defaults) {
            DEF = { ctx: Math.round(d.defaults.cloud_ctx / window.__spCTXMAX * 100),
                    trigger: Math.round(d.defaults.trigger_ratio * 100),
                    recent: Math.round(d.defaults.recent_ratio * 100),
                    entries: Math.round(d.defaults.entries_ratio * 100) };
          }
          var c = d.cfg;
          state.ctx = Math.round(c.cloud_ctx / window.__spCTXMAX * 100);
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
        cloud_ctx: Math.round(window.__spCTXMAX * state.ctx / 100),
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
  var _exp = {};
  var _names = ["bindSlider", "commitCfg", "endDrag", "flash", "layout", "loadCfg", "pctFromEvent", "placeKnob", "setValue"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.spSliders = _exp;
  WA2.register("spSliders", _exp);
  /* __export_all__ */
  ["bindSlider", "commitCfg", "endDrag", "flash", "layout", "loadCfg", "pctFromEvent", "placeKnob", "setValue", "DEF", "WA2", "_exp", "_names", "body", "c", "el", "key", "knob", "pad", "pct", "r", "s", "savedTimer", "scale", "slider", "state", "usable", "w"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
