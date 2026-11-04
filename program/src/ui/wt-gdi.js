/* gdi.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.gdi；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  function gdiRenderName(name, el) {
    if (!el || window.__gdiOK === false) return;
    gdiRenderMsg(name, el, 52, 360, 1).then((ok) => {
      if (!ok) return;
      el.classList.add("gdi");
      const im = el.querySelector("img");
      if (im) im.style.width = (im.naturalWidth * TEXT_SCALE * NAME_BOOST).toFixed(1) + "px";
    });
  }

  const TEXT_VER = "1029strict";  // 每次打包更新, 强制浏览器重新取图
  const GDI_SCALE = 0.625;  // 默认显示比例, 实际用 TEXT_SCALE (Ctrl +/- 可调)
  let TEXT_SCALE = parseFloat(localStorage.getItem("app_textScale") || "0.625");
  if (!(TEXT_SCALE > 0.2 && TEXT_SCALE < 3)) TEXT_SCALE = 0.6;
  function gdiRenderMsg(text, el, size, maxw, emb) {
    // 服务端 GDI 渲染(微软雅黑) -> 图片, 稳定可靠
    return __gdiFallback(text, el, size || 28, maxw || 832, emb === undefined ? 0 : emb);
  }

  function __gdiFallback(text, el, size, maxw, emb) {
    size = size || 56; maxw = maxw || 1200; emb = (emb === undefined ? 0 : emb);
    const url = "/api/text?text=" + encodeURIComponent(text) +
                "&s=" + size + "&w=" + maxw + "&e=" + emb + "&v=" + TEXT_VER;
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        el.innerHTML = "";
        el.appendChild(img);
        img.style.cssText = "display:block;width:" + (img.naturalWidth * TEXT_SCALE).toFixed(1) +
                            "px;height:auto;image-rendering:auto;";
        resolve(true);
      };
      img.onerror = () => resolve(false);
      img.src = url;
    });
  }


  /* ---------- 语音 ---------- */
  let ttsOn = (localStorage.getItem("app_tts") || "1") === "1";
  var _exp = {};
  var _names = ["__gdiFallback", "gdiRenderMsg", "gdiRenderName"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.gdi = _exp;
  WA2.register("gdi", _exp);
  /* __export_all__ */
  ["__gdiFallback", "gdiRenderMsg", "gdiRenderName", "GDI_SCALE", "TEXT_SCALE", "TEXT_VER", "WA2", "_exp", "_names", "im", "img", "ttsOn", "url"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();

/* gdi 可用性标记：默认当作可用，失败时由 wt-text 置 false */
if (window.__gdiOK === undefined) { window.__gdiOK = true; }
