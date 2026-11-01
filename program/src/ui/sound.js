/* 统一的按键音效：悬停 / 点击 / 翻页
 *
 * 用事件委托挂在 document 上，任何界面（标题、对话、存档、设置、回想、模型管理）
 * 只要元素命中下面的选择器，就自动有声，不需要在每个界面里单独写。
 *
 * 三类声音（对应 snd/catalog.json 里的 id，可在设置界面换）：
 *   悬停  SE_9211   → seHover
 *   点击  点击音效   → seClick
 *   翻页  SE_9213   → sePage
 */
(function () {
  // 悬停/点击都算“可交互”的元素
  var INTERACTIVE =
    ".uiExit,.mbBtn,.mbItem,.optTab,.optPagerBtn,#optPrev,#optNext," +
    "#pagerPrev,#pagerNext,.pagerL,.pagerR,.saveTab,.pageTab,.saveSlot," +
    "[data-act],[data-pg],.cfgRow button,.o3btn,.dlgToast,.dlgConfirm button," +
    ".blogItem,.modelRow,.mgrBtn,button,select";

  // 这些的“点击”用翻页音（切页/切页签/翻页键）
  var PAGE =
    ".optTab,.optPagerBtn,#optPrev,#optNext,#pagerPrev,#pagerNext," +
    ".pagerL,.pagerR,.saveTab,.pageTab,[data-pg]";

  var last = null;

  function se(kind) {
    try { if (window.playSE) window.playSE(kind); } catch (e) {}
  }

  function hit(e, sel) {
    var t = e.target;
    if (!t || !t.closest) return null;
    return t.closest(sel);
  }

  document.addEventListener("mouseover", function (e) {
    var el = hit(e, INTERACTIVE);
    if (!el || el === last) return;
    last = el;
    se("hover");
  }, true);

  document.addEventListener("mouseout", function (e) {
    var el = hit(e, INTERACTIVE);
    if (el && el === last) last = null;
  }, true);

  document.addEventListener("click", function (e) {
    var el = hit(e, INTERACTIVE);
    if (!el) return;
    se(el.closest(".uiExit") ? "exit" : (el.closest(PAGE) ? "page" : "click"));
  }, true);
})();
