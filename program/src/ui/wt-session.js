/* session.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.session；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  function sessionSave() {
    try {
      /* 返回 promise：切角色前要等这一笔写完再换人，
         否则后端已经把存档目录切到新角色，这一笔会落到别人名下 */
      return fetch("/api/session/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot: "auto",
          messages: (window.__history || history || []),
          meta: { bg: currentBg || "", outfit: (WA2.state.outfit || ""), at: Date.now() }
        })
      }).catch(function () {});
    } catch (e) { return null; }
  }

  /* 读档：保持 history 是同一个数组（别的模块持有引用），只换内容 */
  function applyHistory(arr) {
    history.length = 0;
    (arr || []).forEach(function (m) { history.push(m); });
    window.__history = history;
  }

  function sessionRestore() {
    return fetch("/api/session/load?slot=auto", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.messages || !d.messages.length) return false;
        applyHistory(d.messages);
        const meta = d.meta || {};
        if (meta.bg) { currentBg = null; setBg(meta.bg); }
        if (meta.outfit) { WA2.state.outfit = meta.outfit; }
        // 把最后一句和纱的话显示出来
        let last = "";
        for (let i = history.length - 1; i >= 0; i--) {
          if (history[i].role === "assistant") { last = history[i].zh || history[i].content || ""; break; }
        }
        if (last) {
          try { showReply(last); } catch (e) { $("msgText").textContent = last; }
          var _lastJa = "";
          for (var _i = history.length - 1; _i >= 0; _i--) {
            if (history[_i].role === "assistant") { _lastJa = history[_i].content || ""; break; }
          }
          if (_lastJa) speakLineJa(_lastJa, "calm");
        }
        if (meta.outfit) {
          try { setSpriteByScene(meta.bg || "classroom", "calm", true, meta.outfit); } catch (e) {}
        }
        console.log("[session] 已恢复", history.length, "条");
        try { rebuildBacklog(); } catch (e) {}
        return true;
      })
      .catch(function () { return false; });
  }

  /* 读档：把存档恢复到当前对话并进入游戏 */
  window.__loadSession = function (data) {
    try {
      applyHistory(data.messages);
      const meta = data.meta || {};
      showScreen("gameScreen");
      titleBgmStarted = true;
      if (meta.bg) { currentBg = null; setBg(meta.bg); } else { setBg("classroom"); }
      if (meta.outfit) { WA2.state.outfit = meta.outfit; }
      setSpriteByScene(meta.bg || "classroom", "calm", true, meta.outfit || "");
      gdiRenderName(CHAR_NAME, $("namePlate"));
      setBgm("calm", 600);
      let last = "";
      for (let i = history.length - 1; i >= 0; i--) {
        if (history[i].role === "assistant") { last = history[i].zh || history[i].content || ""; break; }
      }
      if (last) {
        try { showReply(last); } catch (e) { $("msgText").textContent = last; }
        var _lastJa = "";
        for (var _i = history.length - 1; _i >= 0; _i--) {
          if (history[_i].role === "assistant") { _lastJa = history[_i].content || ""; break; }
        }
        if (_lastJa) speakLineJa(_lastJa, "calm");
      }
      try { rebuildBacklog(); } catch (e) {}
      setTimeout(function () { $("input").focus(); }, 300);
    } catch (e) { console.warn("load session failed", e); }
  };

  /* 存档界面用：取当前会话要写进 meta 的东西（背景 / 立绘）
     currentBg、currentOutfit 是模块内变量，这里只读不写 */
  window.__saveMeta = function () {
    return {
      bg: (typeof currentBg !== "undefined" && currentBg) || "",
      outfit: (WA2.state.outfit || ""),
      at: Date.now()
    };
  };
  /* 存档界面用：按场景名取背景图，给槽位缩略图用 */
  window.__bgThumb = function (name) { return bgSrc(name); };
  /* 调试/探针用：直接切到某张场景图（传 CG 的 id，或旧背景名） */
  window.__scenePreview = function (name) { currentBg = null; setBg(name); return { bg: currentBg, url: bgSrc(name) }; };
  /* 工具栏提示（快速存档/读档暂未开放时用） */
  window.__saveHint = function (msg) {
    var h = document.getElementById("tbHint");
    if (!h) return;
    h.textContent = msg;
    clearTimeout(window.__saveHintTimer);
    window.__saveHintTimer = setTimeout(function () { h.textContent = ""; }, 1500);
  };

  /* 存档界面用：把当前画面（背景 CG + 立绘）截成缩略图
     160x100，和槽位的缩略图框同比例 */
  window.__grabThumb = function () {
    try {
      var W = 160, H = 100;
      var cv = document.createElement("canvas");
      cv.width = W; cv.height = H;
      var g = cv.getContext("2d");
      g.fillStyle = "#0a1622"; g.fillRect(0, 0, W, H);

      var bg = window.__curBg;
      if (bg && bg.complete && bg.naturalWidth) {
        var s = Math.max(W / bg.naturalWidth, H / bg.naturalHeight);
        var w = bg.naturalWidth * s, h = bg.naturalHeight * s;
        g.drawImage(bg, (W - w) / 2, (H - h) / 2, w, h);
      }
      var stage = document.getElementById("stage");
      var sp = document.getElementById("sprite");
      if (stage && sp && sp.naturalWidth) {
        var sr = stage.getBoundingClientRect();
        var r = sp.getBoundingClientRect();
        if (sr.width > 0 && sr.height > 0) {
          g.drawImage(sp,
            (r.left - sr.left) / sr.width * W,
            (r.top - sr.top) / sr.height * H,
            r.width / sr.width * W,
            r.height / sr.height * H);
        }
      }
      return cv.toDataURL("image/jpeg", 0.72);
    } catch (e) { return ""; }
  };

  /* ---------- 场景切换 ---------- */
  let currentBg = null;
  var _exp = {};
  var _names = ["sessionRestore", "sessionSave"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.session = _exp;
  WA2.register("session", _exp);
  /* __export_all__ */
  ["sessionRestore", "sessionSave", "W", "WA2", "_exp", "_lastJa", "_names", "bg", "currentBg", "cv", "g", "h", "last", "meta", "r", "s", "sp", "sr", "stage", "w"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
