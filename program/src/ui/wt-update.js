/* wt-update.js —— 启动时检查新版本，标题栏弹一条通知；点一下**自己更新**，不用去下载补丁
 *
 * 流程：
 *   1. GET /api/update  → 有新版就插一条 chip 到 #menuBar
 *   2. 点 chip → POST /api/update/apply（后端决定走 git 还是整份 zip 快照）
 *   3. 轮询 GET /api/update/status，chip 上显示「正在更新 42% · 覆盖代码与文档」
 *   4. 成功：「已更新到 x.y · 关掉重开生效」；失败：退回「点此打开下载页」
 *
 * 为什么不用补丁：补丁是「对某个基线」的 diff，用户连着漏两版就打不上；
 * 这里直接取最新整份代码，只覆盖代码/文档，不碰角色、素材、存档。
 *
 * 探针：window.__checkUpdate() 检查；window.__autoUpdate() 直接更新；window.WA2.update.state 看状态
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var state = {
    checked: false, newer: false, latest: "", url: "", error: "",
    auto: false, mode: "", updating: false, percent: 0, message: "",
    done: false, failed: false
  };
  var timer = null;

  function ensureChip() {
    var bar = document.getElementById("menuBar");
    if (!bar) return null;
    var el = document.getElementById("updateNoti");
    if (el) return el;
    el = document.createElement("div");
    el.id = "updateNoti";
    el.className = "upd";
    el.style.display = "none";
    el.title = "发现新版本，点击直接更新";
    var firstBtn = bar.querySelector(".mbWinBtn");
    if (firstBtn) bar.insertBefore(el, firstBtn); else bar.appendChild(el);
    el.addEventListener("click", function (e) {
      e.stopPropagation();
      if (state.done || state.updating) return;
      if (state.auto) { startUpdate(); return; }
      if (!state.url) return;
      el.classList.add("done");
      el.title = "已在浏览器打开下载页";
      window.location.href = "/api/open_url?url=" + encodeURIComponent(state.url);
    });
    return el;
  }

  function setText(t) {
    var el = ensureChip();
    if (!el) return;
    el.textContent = t;
    el.style.display = "";
  }

  function show(info) {
    state.newer = true;
    state.latest = info.latest || "";
    state.url = info.url || "";
    state.auto = !!info.auto;
    state.mode = info.mode || "";
    setText("发现新版本 " + state.latest + (state.auto ? " · 点此一键更新" : " · 点此更新"));
  }

  function startUpdate() {
    state.updating = true;
    state.failed = false;
    setText("正在更新… 0%");
    fetch("/api/update/apply", { method: "POST", cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || d.ok === false) {
          fail((d && d.error) || "启动更新失败");
          return;
        }
        poll();
      })
      .catch(function (e) { fail(String(e)); });
  }

  function poll() {
    if (timer) clearTimeout(timer);
    fetch("/api/update/status", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var p = (d && d.progress) || {};
        state.percent = p.percent || 0;
        state.message = p.message || "";
        if (p.ok === true) {
          state.updating = false;
          state.done = true;
          setText("已更新到 " + (p.version || state.latest) + " · 关掉窗口重开生效");
          var el = document.getElementById("updateNoti");
          if (el) { el.classList.add("done"); el.title = "更新完成，请重新启动程序"; }
          return;
        }
        if (p.ok === false) {
          fail(p.error || "更新失败");
          return;
        }
        setText("正在更新… " + state.percent + "%" +
                (state.message ? " · " + state.message : ""));
        timer = setTimeout(poll, 700);
      })
      .catch(function (e) { fail(String(e)); });
  }

  function fail(msg) {
    state.updating = false;
    state.failed = true;
    state.error = msg;
    setText("更新失败 —— 点此打开下载页");
    var el = document.getElementById("updateNoti");
    if (el) el.title = String(msg).slice(0, 200);
  }

  function check() {
    return fetch("/api/update", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        state.checked = true;
        if (!d) return state;
        if (d.error) state.error = d.error;
        if (d.newer) show(d);
        return state;
      })
      .catch(function (e) { state.checked = true; state.error = String(e); return state; });
  }

  WA2.update = { state: state, check: check, show: show, chip: ensureChip, apply: startUpdate };
  WA2.register("update", WA2.update);
  window.__checkUpdate = check;
  window.__autoUpdate = startUpdate;

  /* 启动 1.2 秒后再查（不跟首屏抢资源；查不到就算了） */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      setTimeout(check, 1200);
    });
  } else {
    setTimeout(check, 1200);
  }
})();
