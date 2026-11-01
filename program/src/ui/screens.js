// 存读档 / 设置 / 回想 三个界面
(function () {
  const $ = (id) => document.getElementById(id);
  /* 统一音效：翻页/切页 —— 页签、EXIT、OPTION 标签、回想滚轮都用它 */
  function playPageSE() {
    try { if (window.playSE) window.playSE("page"); } catch (e) {}
  }
  window.__pageSE = playPageSE;


  /* ---------- 存读档 ---------- */
  let saveMode = "load";           // load | save

  /* ---------- 回想 ---------- */
  function renderBlog() {
    const box = $("blogList");
    if (!box) return;
    const hist = (window.__history || []).filter(m => m.role === "assistant");
    box.innerHTML = "";
    if (!hist.length) {
      box.innerHTML = '<div class="blogItem"><div class="txt">还没有对话记录</div></div>';
      return;
    }
    hist.forEach(m => {
      const d = document.createElement("div");
      d.className = "blogItem";
      d.innerHTML = '<div class="who">和纱</div><div class="txt">' +
        m.content.replace(/[「」]/g, "") + '</div>';
      box.appendChild(d);
    });
    box.scrollTop = box.scrollHeight;
  }

  /* ---------- 浮层界面统一开关 ----------
     所有 .uiScreen（存读档 / 回想 / 设置 / 模型管理 / 特别模式）都走这一套，
     各自模块里不要再直接 classList.add("show") —— 否则关不干净、层级互相盖住。 */
  function allScreens() {
    return Array.prototype.slice.call(document.querySelectorAll(".uiScreen"));
  }

  /* 关一个浮层 */
  function hideScreen(el) {
    if (!el) return;
    el.classList.remove("show");
    el.style.transition = "none";
    el.style.opacity = "";
  }

  /* 关全部。except：先关别的、再开自己时用，别把自己也关了 */
  function closeAll(except) {
    allScreens().forEach(function (el) { if (el !== except) hideScreen(el); });
  }

  /* 浮层入场：先压透明，加 show 后两帧再推到 1（等 display 生效） */
  function fadeIn(el) {
    if (!el) return;
    el.style.transition = "none";
    el.style.opacity = "0";
    el.classList.add("show");
    if (window.zoomIn) window.zoomIn(el, 390);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        el.style.transition = "opacity 220ms ease";
        el.style.opacity = "1";
      });
    });
  }
  window.__fadeInScreen = fadeIn;

  window.__hideUIScreen = hideScreen;
  window.__closeScreens = function () { closeAll(null); };
  /* 打开任意浮层：先关掉其它浮层，再显示自己 */
  window.__showUIScreen = function (elOrId) {
    var el = typeof elOrId === "string" ? $(elOrId) : elOrId;
    if (!el) return null;
    closeAll(el);
    el.classList.remove("fading");
    el.classList.add("show");
    return el;
  };
  window.__openScreen = function (name, mode) {
    try { closeAll(); } catch (e) {}
    try {
      if (name === "save") {
        saveMode = mode || "load";
        /* 底栏横幅：存档模式 = 储存数据/SAVE，读档模式 = 读取数据/LOAD */
        try {
          var bn = document.getElementById("pagerBanner");
          if (bn) bn.src = "assets/ui/save/banner_" + (saveMode === "save" ? "save" : "load") + ".png";
        } catch (e) {}
        /* 顶栏：存档用 sys_01000（Save セーブ），读档用 sys_02000（Load ロード） */
        try {
          var hd = document.getElementById("uiHeadImg");
          if (hd) hd.src = "assets/ui/" + (saveMode === "save" ? "sys_01000" : "sys_02000") + ".png";
        } catch (e) {}
        /* 按当前页把这 10 个槽绑到本页的 10 个编号上（见 savepages.js） */
        try { window.__renderSaveSlots && window.__renderSaveSlots(window.__savePage || 1); } catch (e) {}
        if (window.__saveTabsPaint) setTimeout(window.__saveTabsPaint, 0);
        /* 关掉可能还开着的提示框 */
        var dlg = document.getElementById("dlgConfirm");
        if (dlg) dlg.classList.remove("on");
        var tst = document.getElementById("dlgToast");
        if (tst) tst.classList.remove("on");
        var sc = $("saveScreen");
        if (sc) {
          /* 存档 / 读档是同一套界面，靠这个类区分点击行为与光标 */
          sc.classList.toggle("mode-save", saveMode === "save");
          sc.classList.toggle("mode-load", saveMode !== "save");
          window.__saveMode = saveMode;
          fadeIn(sc);
        }
      }
      if (name === "blog") {
        try { renderBlog(); } catch (e) {}
        var bc = $("blogScreen");
        if (bc) bc.classList.add("show");
      }
      /* uiOpen 已回滚 */
    } catch (e) {
      console.warn("openScreen failed", e);
      /* uiOpen 已回滚 */
    }
  };;
  /* 有没有任意浮层开着？（ESC 关闭用，覆盖全部 .uiScreen，不只是存读档） */
  window.__isScreenOpen = function () {
    return allScreens().some(function (el) { return el.classList.contains("show"); });
  };

  document.addEventListener("DOMContentLoaded", () => {
    // ESC 关闭
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && window.__isScreenOpen()) closeAll();
    });
  });

  /* 右下角 EXIT：统一走 hideScreen（模型界面由它自己的关闭逻辑收尾） */
  function wireExit() {
    document.querySelectorAll(".uiExit").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var sc = btn.closest(".uiScreen");
        if (!sc) return;
        hideScreen(sc);
        /* 存读档的提示框跟着关掉 */
        var dlg = document.getElementById("dlgConfirm");
        if (dlg) dlg.classList.remove("on");
        var tst = document.getElementById("dlgToast");
        if (tst) tst.classList.remove("on");
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wireExit);
  else wireExit();
})();
