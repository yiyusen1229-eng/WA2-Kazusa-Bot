/* 换页动画：收缩 + 虚化（按实机观感）
 *
 * 旧页：scale 1 → 0.94，blur 0 → 5px，opacity 1 → 0
 * 新页：scale 1.06 → 1，blur 4px → 0，opacity 0.15 → 1
 * 总时长默认 390ms，与翻页音 SE_9213 等长。
 *
 * 单独成文件，避免 game.js 里任何一处运行时报错把这里的定义一起带掉。
 */
(function () {
  function reflow(el) { void el.offsetWidth; }

  /* 打开界面时也做一次同样的入场：从略大收缩到正常，边收缩边实化 */
  window.zoomIn = function (el, ms) {
    if (!el) return;
    ms = ms || 390;
    el.style.transition = "none";
    el.style.transformOrigin = "50% 50%";
    el.style.transform = "scale(1.06)";
    el.style.filter = "blur(4px)";
    el.style.opacity = "0";
    reflow(el);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        el.style.transition = "transform " + ms + "ms cubic-bezier(.2,.9,.25,1), opacity " +
                              ms + "ms ease, filter " + ms + "ms ease";
        el.style.transform = "scale(1)";
        el.style.filter = "blur(0)";
        el.style.opacity = "1";
        setTimeout(function () {
          el.style.transition = "";
          el.style.transform = "";
          el.style.filter = "";
          el.style.opacity = "";
        }, ms + 60);
      });
    });
  };
})();
