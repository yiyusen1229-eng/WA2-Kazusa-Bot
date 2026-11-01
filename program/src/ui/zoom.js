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

  /* 按选择器做缩放换页：因为换内容会重建 DOM，元素必须每步重新查询 */
  /* 用 @keyframes 做换页：给元素加 pgOut / pgIn 类，动画结束自动移除 */
  window.pgSwap = function (el, fn, ms) {
    if (!el) { try { fn && fn(); } catch (e) {} return; }
    /* 关键：先清掉之前 zoomIn / 上次动画留在元素上的内联 transform/filter/transition，
       否则内联值优先级高于关键帧，动画被完全压住（这就是前几版一直"没效果"的原因） */
    el.style.transform = "";
    el.style.filter = "";
    el.style.transition = "";
    el.style.opacity = "";
    el.classList.remove("pgIn", "pgOut");
    void el.offsetWidth;
    el.classList.add("pgOut");
    var outMs = 175, inMs = 215;
    setTimeout(function () {
      try { fn && fn(); } catch (e) {}
      el.style.transform = "";
      el.style.filter = "";
      el.style.transition = "";
      el.style.opacity = "";
      el.classList.remove("pgOut");
      void el.offsetWidth;
      el.classList.add("pgIn");
      setTimeout(function () {
        el.classList.remove("pgIn");
        el.style.transform = "";
        el.style.filter = "";
        el.style.opacity = "";
      }, inMs + 60);
    }, outMs);
  }})();

/* ---------- WAAPI 换页动画（交叉缩放淡入淡出） ----------
   实测：这台机器的 WebView2 上 CSS transition / @keyframes 驱动 transform 会被丢弃，
   但 element.animate()（WAAPI）完全有效 —— 容器和槽位子元素都验证过。

   旧页：scale 1 -> 0.94，blur 0 -> 5px，opacity 1 -> 0   （175ms）
   新页：scale 1.06 -> 1，blur 4px -> 0，opacity 0.15 -> 1（215ms）
   总 390ms，与翻页音 SE_9213 等长。 */
window.waapiSwap = function (olds, news, fn, ms) {
  ms = ms || 390;
  var outMs = Math.round(ms * 0.45);
  var inMs = ms - outMs;
  var olds_ = olds ? [].concat(olds) : [];
  var anims = [];

  olds_.forEach(function (el) {
    try {
      anims.push(el.animate(
        [{ transform: "scale(1)", filter: "blur(0px)", opacity: 1 },
         { transform: "scale(0.94)", filter: "blur(5px)", opacity: 0 }],
        { duration: outMs, easing: "ease-in", fill: "forwards" }
      ));
    } catch (e) {}
  });

  setTimeout(function () {
    try { fn && fn(); } catch (e) {}

    var news_ = news ? [].concat(news) : [];
    news_.forEach(function (el) {
      try {
        var a = el.animate(
          [{ transform: "scale(1.06)", filter: "blur(4px)", opacity: 0.15 },
           { transform: "scale(1)", filter: "blur(0px)", opacity: 1 }],
          { duration: inMs, easing: "cubic-bezier(.2,.9,.25,1)", fill: "forwards" }
        );
        a.onfinish = function () {
          try {
            a.cancel();
            el.style.transform = "";
            el.style.filter = "";
            el.style.opacity = "";
          } catch (e) {}
        };
      } catch (e) {}
    });

    setTimeout(function () {
      olds_.forEach(function (el) {
        try { el.style.transform = ""; el.style.filter = ""; el.style.opacity = ""; } catch (e) {}
      });
    }, inMs + 40);
  }, outMs);
};
