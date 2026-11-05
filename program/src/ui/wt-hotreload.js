/* 素材热重载（#20）：每几秒问一次后端「素材变了吗」，变了就把画面刷新一遍。
 *
 * 为什么轮询而不是 WebSocket：后端本来就是同步的 SimpleHTTPServer，
 * 一个 2 秒的 GET 比引一套推送简单得多；页面隐藏时不问。
 *
 * 变了之后做什么：
 *   1. `WA2.assetsVer + 1`（立绘 / 背景 URL 会带 ?v=，绕过 WebView2 的图片缓存）
 *   2. 重拉立绘索引（`WA2.sprite.loadIndex`）并按当前衣服+情绪重画
 *   3. 重画当前背景（`__reapplyBg`，game.js 提供）
 *   4. 提示一次「素材已更新」
 *
 * 后端关了热重载（`WA2_HOTRELOAD=0` 或 POST /api/hotreload {"on":false}）时这里什么都不做。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var POLL_MS = 4000;
  var timer = null;
  var lastGen = -1;
  var version = 0;

  function toast(msg) {
    try { (window.__toast || function () {}) (msg, 2200); } catch (e) {}
  }

  function apply(kinds) {
    version += 1;
    WA2.assetsVer = version;
    var didSprite = false;
    try {
      if (WA2.sprite && WA2.sprite.loadIndex) {
        WA2.sprite.loadIndex(function () {
          try { if (WA2.sprite.refreshCurrent) WA2.sprite.refreshCurrent(); } catch (e) {}
        });
        didSprite = true;
      }
    } catch (e) {}
    try { if (window.__reapplyBg) window.__reapplyBg(); } catch (e) {}
    var what = (kinds || []).indexOf("character") >= 0 ? "角色素材" : "素材";
    toast(what + "已更新" + (didSprite ? "" : "（下次切换时生效）"));
    try { if (window.__dbg) window.__dbg("ASSET", "hot reload v" + version + " " + (kinds || []).join("/")); } catch (e) {}
    return version;
  }

  function poll() {
    if (typeof document !== "undefined" && document.hidden) return;
    fetch("/api/hotreload", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) return;
        if (!d.enabled) return;
        if (lastGen < 0) { lastGen = d.gen || 0; return; }   /* 第一次只记基线 */
        if ((d.gen || 0) !== lastGen) {
          lastGen = d.gen || 0;
          apply(d.last_kinds || []);
        }
      })
      .catch(function () { /* 后端没起来 / 不关心，下次再问 */ });
  }

  function start() {
    if (timer) return;
    timer = setInterval(poll, POLL_MS);
    poll();
  }

  function stop() {
    if (!timer) return;
    clearInterval(timer);
    timer = null;
  }

  function setEnabled(on) {
    fetch("/api/hotreload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ on: !!on })
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        toast(d && d.enabled ? "素材热重载已打开" : "素材热重载已关闭");
        if (d && d.enabled) { lastGen = d.gen || 0; }
      })
      .catch(function () {});
  }

  WA2.hotReload = {
    start: start,
    stop: stop,
    poll: poll,
    apply: apply,
    setEnabled: setEnabled,
    version: function () { return version; },
    polling: function () { return !!timer; }
  };

  start();
})();
