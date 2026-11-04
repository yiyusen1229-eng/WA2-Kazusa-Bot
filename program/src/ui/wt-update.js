/* wt-update.js —— 启动时检查 GitHub 上的新版本，在标题栏里弹一条可点击的通知
 *
 * 流程：/api/update（后端去拉 version.json 比较）→ 有新版就插一条 chip 到 #menuBar
 *      点击 → /api/open_url?url=… → 系统浏览器打开下载页
 *
 * 探针：window.__checkUpdate() 手动触发；window.WA2.update.state 看状态
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var state = { checked: false, newer: false, latest: "", url: "", error: "" };

  function ensureChip() {
    var bar = document.getElementById("menuBar");
    if (!bar) return null;
    var el = document.getElementById("updateNoti");
    if (el) return el;
    el = document.createElement("div");
    el.id = "updateNoti";
    el.className = "upd";
    el.style.display = "none";
    el.title = "发现新版本，点击打开下载页";
    var firstBtn = bar.querySelector(".mbWinBtn");
    if (firstBtn) bar.insertBefore(el, firstBtn); else bar.appendChild(el);
    el.addEventListener("click", function (e) {
      e.stopPropagation();
      if (!state.url) return;
      el.classList.add("done");
      el.title = "已在浏览器打开下载页";
      window.location.href = "/api/open_url?url=" + encodeURIComponent(state.url);
    });
    return el;
  }

  function show(info) {
    var el = ensureChip();
    if (!el) return;
    state.newer = true;
    state.latest = info.latest || "";
    state.url = info.url || "";
    el.textContent = "发现新版本 " + state.latest + " · 点此更新";
    el.style.display = "";
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

  WA2.update = { state: state, check: check, show: show, chip: ensureChip };
  WA2.register("update", WA2.update);
  window.__checkUpdate = check;

  /* 启动 1.2 秒后再查（不跟首屏抢资源；查不到就算了） */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { setTimeout(check, 1200); });
  } else {
    setTimeout(check, 1200);
  }
})();
