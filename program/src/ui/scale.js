/* 文字大小调节: Ctrl + = / - 实时缩放, Ctrl+0 复位, 自动记忆 */
(function () {
  function toast(msg) {
    var ro = document.getElementById("scaleReadout");
    if (ro) {
      ro.textContent = msg;
      ro.style.display = "block";
    }
    var t = document.getElementById("__scaleToast");
    if (!t) {
      t = document.createElement("div");
      t.id = "__scaleToast";
      t.style.cssText =
        "position:fixed;left:50%;top:70px;transform:translateX(-50%);z-index:99999;" +
        'font:16px/1.4 "Microsoft YaHei";color:#ffe07a;background:rgba(0,0,0,.78);' +
        "padding:8px 16px;border-radius:5px;pointer-events:none";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.display = "block";
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.style.display = "none"; }, 1500);
  }

  function applyAll() {
    var imgs = document.querySelectorAll("#msgText img, #namePlate img");
    for (var i = 0; i < imgs.length; i++) {
      imgs[i].style.width = (imgs[i].naturalWidth * window.TEXT_SCALE).toFixed(1) + "px";
    }
  }
  window.__applyTextScale = applyAll;

  function bump(d) {
    if (typeof window.TEXT_SCALE !== "number") window.TEXT_SCALE = 0.6;
    window.TEXT_SCALE = Math.min(2.5, Math.max(0.3, +(window.TEXT_SCALE + d).toFixed(2)));
    try { localStorage.setItem("app_textScale", String(window.TEXT_SCALE)); } catch (e) {}
    applyAll();
    toast("文字大小 " + Math.round(window.TEXT_SCALE * 100) + "%   (Ctrl + / - 调整)");
  }
  window.app_adjust_scale = bump;

  document.addEventListener("DOMContentLoaded", function () {
    var ro = document.getElementById("scaleReadout");
    if (ro && typeof window.TEXT_SCALE === "number") {
      ro.textContent = "文字 " + Math.round(window.TEXT_SCALE * 100) + "%";
    }
  });

  document.addEventListener("keydown", function (e) {
    if (!e.ctrlKey) return;
    if (e.key === "=" || e.key === "+") { e.preventDefault(); bump(0.05); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); bump(-0.05); }
    else if (e.key === "0") { e.preventDefault(); window.TEXT_SCALE = 0.6; bump(0); }
  });
})();
