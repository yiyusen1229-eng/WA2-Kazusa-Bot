/* wt-window.js —— 桌面行为（#18）：置顶 / 不透明度 / 夹回本屏。
 *
 * 挂在 WA2.win。后端动作在 api_window.py（action=topmost/alpha/workarea/clamp），
 * 用纯 user32（没有 pystray / keyboard 依赖）。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  var state = { topmost: false, alpha: 255 };

  function toast(msg, ms) {
    try { (window.__toast || function () {}) (msg, ms || 2200); } catch (e) {}
  }

  function api(action, params) {
    var q = "/api/window?action=" + encodeURIComponent(action);
    if (params) {
      Object.keys(params).forEach(function (k) {
        q += "&" + k + "=" + encodeURIComponent(params[k]);
      });
    }
    return fetch(q, { cache: "no-store" }).then(function (r) { return r.json(); });
  }

  function prefs() {
    try { return (window.App && window.App.getPrefs) ? window.App.getPrefs() : {}; } catch (e) { return {}; }
  }
  function setPref(k, v) {
    try {
      if (window.App && window.App.setPref) window.App.setPref(k, v);
      else { var p = prefs(); p[k] = v; }
    } catch (e) {}
  }

  /* ---------- 置顶 ---------- */
  function setTopmost(on, silent) {
    return api("topmost", { on: on ? 1 : 0 }).then(function (d) {
      state.topmost = !!(d && d.topmost);
      setPref("winTopmost", state.topmost);
      if (!silent) toast(state.topmost ? "窗口已置顶" : "已取消置顶", 1500);
      return state.topmost;
    }).catch(function () { return state.topmost; });
  }

  /* ---------- 不透明度 ---------- */
  function setAlpha(v, silent) {
    var a = Math.max(40, Math.min(255, parseInt(v, 10) || 255));
    return api("alpha", { v: a }).then(function (d) {
      state.alpha = (d && typeof d.alpha === "number") ? d.alpha : a;
      setPref("winAlpha", state.alpha);
      if (!silent) toast("窗口不透明度 " + Math.round(state.alpha / 255 * 100) + "%", 1500);
      return state.alpha;
    }).catch(function () { return state.alpha; });
  }

  /* ---------- 多显示器：把窗口拉回可见区域 ---------- */
  function clampBack() {
    return api("clamp").then(function (d) {
      if (d && d.ok) toast(d.moved && d.moved.length ? "窗口已拉回本屏" : "窗口本来就在屏幕内", 1800);
      else toast("拉回失败：" + ((d && d.error) || "未知"), 2200);
      return d;
    }).catch(function () { return null; });
  }

  /* ---------- 启动时套用记住的设置 ---------- */
  function applySaved() {
    var p = prefs();
    if (p.winTopmost) setTopmost(true, true);
    if (p.winAlpha && parseInt(p.winAlpha, 10) < 255) setAlpha(p.winAlpha, true);
    return api("state").then(function (d) {
      if (d && d.ok) {
        state.topmost = !!d.topmost;
        state.alpha = typeof d.alpha === "number" ? d.alpha : 255;
      }
      return state;
    }).catch(function () { return state; });
  }

  /* ---------- 睡眠唤醒：重建音频与连接（#18） ----------
     机器睡一觉回来，<audio> 常常哑掉（和「音频设备切换」是同一类问题），
     所以直接复用 wt-audio 已有的 suspendForDevice / rebuildAfterDevice，
     不再另写一份重建逻辑。网络那边没有长连接，顺手让热重载重新对一次基线就行。 */
  var lastPowerGen = -1;

  function onResume(gapS) {
    try {
      var was = WA2.audio && WA2.audio.suspendForDevice ? WA2.audio.suspendForDevice() : null;
      if (was && WA2.audio.rebuildAfterDevice) WA2.audio.rebuildAfterDevice(was);
    } catch (e) {}
    try { if (WA2.hotReload && WA2.hotReload.poll) WA2.hotReload.poll(); } catch (e) {}
    toast("已从睡眠恢复" + (gapS ? "（离开 " + Math.round(gapS) + " 秒）" : "") + "：音频已重建", 2800);
    try { if (window.__dbg) window.__dbg("PWR", "resume gap=" + gapS); } catch (e) {}
  }

  function pollPower() {
    fetch("/api/power", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) return;
        var g = d.gen || 0;
        if (lastPowerGen < 0) { lastPowerGen = g; return; }   /* 第一轮只记基线 */
        if (g !== lastPowerGen) {
          lastPowerGen = g;
          onResume(d.last_gap || 0);
        }
      })
      .catch(function () {});
  }

  function summary() {
    return { topmost: state.topmost, alpha: state.alpha, powerGen: lastPowerGen };
  }

  WA2.win = {
    setTopmost: setTopmost, setAlpha: setAlpha,
    clampBack: clampBack, applySaved: applySaved, summary: summary,
    pollPower: pollPower, onResume: onResume, state: state
  };
  WA2.register("win", WA2.win);
  /* 兼容老调用 */
  window.__winSetTopmost = setTopmost;
  window.__winSetAlpha = setAlpha;
  window.__winClampBack = clampBack;
  window.__winSummary = summary;

  document.addEventListener("DOMContentLoaded", function () {
    setTimeout(applySaved, 800);
    /* 睡眠唤醒检测：后端每 5 秒看一次墙钟，跳一大截就 +1，这里跟着重建音频 */
    setInterval(pollPower, 5000);
    setTimeout(pollPower, 1200);
    /* 关窗/刷新前把不透明度还回去：它是**进程级窗口样式**，不还下次启动整窗是灰的 */
    window.addEventListener("beforeunload", function () {
      try {
        if (navigator.sendBeacon) navigator.sendBeacon("/api/window?action=alpha&v=255");
      } catch (e) {}
    });
  });
})();
