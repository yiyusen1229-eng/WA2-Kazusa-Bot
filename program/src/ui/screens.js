// 存读档 / 设置 / 回想 三个界面
(function () {
  const $ = (id) => document.getElementById(id);
  // 元素被移走时不要抛错
  function need(id) { return document.getElementById(id); }


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

  /* ---------- 开关 ---------- */
  function closeAll() {
    /* uiOpen 已回滚 */
    ["saveScreen", "blogScreen"].forEach(id => $(id) && $(id).classList.remove("show"));
  }
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
          sc.classList.add("show");
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
  window.__closeScreens = closeAll;
  window.__isScreenOpen = () => ["saveScreen","blogScreen"].some(id => $(id) && $(id).classList.contains("show"));

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".optTabs .t").forEach(t => t.addEventListener("click", () => {
      window.__setOptPage && window.__setOptPage(+t.dataset.opt); playSE && playSE("click");
    }));
    // ESC 关闭
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && window.__isScreenOpen()) closeAll();
    });
  });

  /* 右下角 EXIT：点一下退出当前界面（模型界面走它自己的关闭逻辑） */
  function wireExit() {
    document.querySelectorAll(".uiExit").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var sc = btn.closest(".uiScreen");
        if (!sc) return;
        if (sc.id === "modelScreen" && window.__closeModel) { window.__closeModel(); return; }
        sc.classList.remove("show");
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
