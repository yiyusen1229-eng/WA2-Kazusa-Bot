/* 存档页签：三层分离（常态整条 / 悬停单格 / 当前页单格）
   层级见 screens.css：常态和悬停在白线下面，当前页在白线上面。 */
(function () {
  var cur = 1;
  var CELL = 40;   /* 单格宽：匹配 pagetabs 64x32 单格画成 40x20 */

  function activeImg() { return document.getElementById("saveTabsActive"); }
  function hoverImg() { return document.getElementById("saveTabsHover"); }
  function boxEl() { return document.getElementById("saveTabs"); }

  /* 当前页：只换一格，并把这一格挪到对应位置 */
  function showActive(p) {
    var im = activeImg();
    if (!im) return;
    im.src = "assets/ui/save/tab_active_" + p + ".png";
    im.style.left = ((p - 1) * CELL) + "px";
  }
  function showHover(p) {
    var h = hoverImg();
    if (!h) return;
    if (!p || p === cur) { h.style.display = "none"; return; }
    h.src = "assets/ui/save/tab_hover_" + p + ".png";
    h.style.left = ((p - 1) * CELL) + "px";
    h.style.display = "block";
  }

  function hit(x, y) {
    var box = boxEl();
    if (!box) return 0;
    var r = box.getBoundingClientRect();
    if (x < r.left || x > r.right || y < r.top || y > r.bottom) return 0;
    var i = Math.floor((x - r.left) / (r.width / 10));
    return Math.max(1, Math.min(10, i + 1));
  }

  /* 统一入口：点页签、点翻页箭头都走这里（10 页循环） */
  function setPage(p) {
    p = ((p - 1) % 10 + 10) % 10 + 1;
    cur = p;
    window.__savePage = p;
    showActive(cur);
    showHover(0);
    if (window.__renderSaveSlots) window.__renderSaveSlots(p);
  }
  window.__setSavePage = setPage;

  function onMove(e) {
    var p = hit(e.clientX, e.clientY);
    showHover(p);
    var box = boxEl();
    if (box) box.style.cursor = p ? "pointer" : "default";
  }
  function onClick(e) {
    var p = hit(e.clientX, e.clientY);
    if (!p) return;
    setPage(p);
  }

  function init() {
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("click", onClick, true);
    showActive(cur);
    window.__saveTabsPaint = function () { showActive(cur); showHover(0); };
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
