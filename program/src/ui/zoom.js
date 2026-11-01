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

  window.zoomSwap = function (oldEls, newEls, fn, ms) {
    ms = ms || 390;
    var out = Math.round(ms * 0.45);
    var inn = ms - out;
    var olds = oldEls ? [].concat(oldEls) : [];
    var news = newEls ? [].concat(newEls) : [];

    olds.forEach(function (el) {
      el.style.transition = "none";
      el.style.transformOrigin = "50% 50%";
      el.style.transform = "scale(1)";
      el.style.filter = "none";
      el.style.opacity = "1";
      reflow(el);
    });
    requestAnimationFrame(function () {
      olds.forEach(function (el) {
        el.style.transition = "transform " + out + "ms ease-in, opacity " + out +
                              "ms ease-in, filter " + out + "ms ease-in";
        el.style.transform = "scale(0.94)";
        el.style.filter = "blur(5px)";
        el.style.opacity = "0";
      });
    });

    setTimeout(function () {
      try { fn && fn(); } catch (e) {}

      news.forEach(function (el) {
        el.style.transition = "none";
        el.style.transformOrigin = "50% 50%";
        el.style.transform = "scale(1.06)";
        el.style.filter = "blur(4px)";
        el.style.opacity = "0.15";
        reflow(el);
      });
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          news.forEach(function (el) {
            el.style.transition = "transform " + inn + "ms cubic-bezier(.2,.9,.25,1), opacity " +
                                  inn + "ms ease, filter " + inn + "ms ease";
            el.style.transform = "scale(1)";
            el.style.filter = "blur(0)";
            el.style.opacity = "1";
          });
        });
      });
    }, out);
  };

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
      });
    });
  };

  /* 按选择器做缩放换页：因为换内容会重建 DOM，元素必须每步重新查询 */
  window.zoomSwapSel = function (oldSel, newSel, fn, ms) {
    ms = ms || 390;
    var out = Math.round(ms * 0.45);
    var inn = ms - out;
    var olds = Array.prototype.slice.call(document.querySelectorAll(oldSel));
    var reflow = function (el) { void el.offsetWidth; };

    olds.forEach(function (el) {
      el.style.transition = "none";
      el.style.transformOrigin = "50% 50%";
      el.style.transform = "scale(1)";
      el.style.filter = "none";
      el.style.opacity = "1";
      reflow(el);
    });
    requestAnimationFrame(function () {
      olds.forEach(function (el) {
        el.style.transition = "transform " + out + "ms ease-in, opacity " + out +
                              "ms ease-in, filter " + out + "ms ease-in";
        el.style.transform = "scale(0.94)";
        el.style.filter = "blur(5px)";
        el.style.opacity = "0";
      });
    });

    setTimeout(function () {
      try { fn && fn(); } catch (e) {}
      var news = Array.prototype.slice.call(document.querySelectorAll(newSel));
      news.forEach(function (el) {
        el.style.transition = "none";
        el.style.transformOrigin = "50% 50%";
        el.style.transform = "scale(1.06)";
        el.style.filter = "blur(4px)";
        el.style.opacity = "0.15";
        reflow(el);
      });
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          news.forEach(function (el) {
            el.style.transition = "transform " + inn + "ms cubic-bezier(.2,.9,.25,1), opacity " +
                                  inn + "ms ease, filter " + inn + "ms ease";
            el.style.transform = "scale(1)";
            el.style.filter = "blur(0)";
            el.style.opacity = "1";
          });
        });
      });
    }, out);
  };
  /* 用 @keyframes 做换页：给元素加 pgOut / pgIn 类，动画结束自动移除 */
  window.pgSwap = function (el, fn, ms) {
    if (!el) { try { fn && fn(); } catch (e) {} return; }
    el.classList.remove("pgIn");
    el.classList.add("pgOut");
    var outMs = 175, inMs = 215;
    setTimeout(function () {
      try { fn && fn(); } catch (e) {}
      el.classList.remove("pgOut");
      void el.offsetWidth;
      el.classList.add("pgIn");
      setTimeout(function () { el.classList.remove("pgIn"); }, inMs + 60);
    }, outMs);
  };})();
