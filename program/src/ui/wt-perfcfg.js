/* 演出 / 切片规则（#19）：拉 /api/performance，给 wt-fade / wt-sprite 用。
 *
 * 这里**只存「每角色的覆盖值」**，不复制一份默认表：
 *   · 没配 → 各模块用自己内置的默认（和平常完全一样）
 *   · 配了 → 覆盖（淡化时长、情绪→表情、场景→衣服）
 *
 * 对外（WA2.perfCfg）：
 *   refresh(cb)   重新拉一次（启动、切角色、改完文件）
 *   get()         整包 {performance, slices, warnings}
 *   fadeMs()      淡化时长（没配返回 0，让 wt-fade 用自己的默认）
 *   moodMap()     情绪 → 表情 覆盖表（可能是空对象）
 *   outfitMap()   场景 → 衣服 覆盖表（可能是空对象）
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var PKG = { performance: {}, slices: {}, warnings: [] };
  var toasted = false;

  function refresh(cb) {
    fetch("/api/performance", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) return;
        PKG.performance = d.performance || {};
        PKG.slices = d.slices || {};
        PKG.warnings = d.warnings || [];
        if (PKG.warnings.length && !toasted) {
          toasted = true;
          try {
            (window.__toast || function () {})("演出配置有误，已用默认值：" + PKG.warnings[0], 4000);
          } catch (e) {}
        }
        try { if (window.__dbg) window.__dbg("CFG", "performance loaded warn=" + PKG.warnings.length); } catch (e) {}
        if (typeof cb === "function") { try { cb(PKG); } catch (e) {} }
      })
      .catch(function () { /* 拿不到就用内置默认，不打扰用户 */ });
  }

  function fadeMs() {
    var v = (PKG.performance || {}).fade_ms;
    return (typeof v === "number" && isFinite(v) && v > 0) ? v : 0;
  }

  function moodMap() {
    return (PKG.performance && PKG.performance.mood_to_emotion) || {};
  }

  function outfitMap() {
    return (PKG.performance && PKG.performance.outfit_by_scene) || {};
  }

  WA2.perfCfg = {
    refresh: refresh,
    get: function () { return PKG; },
    fadeMs: fadeMs,
    moodMap: moodMap,
    outfitMap: outfitMap
  };

  refresh();
})();
