/* chat.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.chat；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  async function send() {
    const inp = $("input");
    const text = inp.value.trim();
    if (!text || typing) return;
    inp.value = "";

    addHistory("user", text);
    history.push({ role: "user", content: text });
    window.__history = history;      // 用户消息也要同步到全局，否则存档规则读到的是旧长度
    // 等待提示也用字模渲染，避免冒出系统字体
    if (window.gdiRenderMsg) {
      stopReveal();
      gdiRenderMsg("「……」", $("msgText"), 56, 1200, 1);
      $("msgText").classList.add("gdi");
    } else {
      $("msgText").textContent = "「……」";
    }
    hidePageCursor();

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify((function () {
      let act = {};
      try { act = JSON.parse(localStorage.getItem("app_active_model") || "{}"); } catch (e) {}
      // 不写死模型: 只有用户在设置里明确选过才传, 否则由后端用 DEFAULT_MODEL
        // 注意：整段历史都发给后端 —— 裁剪/记忆书由后端按 token 预算决定（前端不砍）
        const body = { messages: history.map(function (m) { return { role: m.role, content: m.content }; }) };
        if (act.model) body.model = act.model;
      if (act.url) body.base_url = act.url;
      // 让后端做一次剧本检索：和这句话相关的「原作里发生过的事」会单独拼进 system
      body.memory = true;
      // 当前背景一并带上：模型只说地点没说时间时，新场景沿用现在的时段（白天/晚上）
      if (currentBg) body.bg = currentBg;
      if (WA2.state.outfit) body.outfit = WA2.state.outfit;
      try { var _pm = localStorage.getItem("app_period") || "auto"; if (_pm !== "auto") body.period = _pm; } catch (e) {}
      return body;
    })()),
      });
      const d = await r.json();
      if (d && d.usage) { try { (WA2.cost && WA2.cost.render ? WA2.cost.render : window.renderCost)(d.usage); } catch (e) {} }
      if (d.error) { $("msgText").textContent = "[错误] " + d.error; return; }
      const reply = (d.reply || "").trim();
        const replyZh = (d.reply_zh || "").trim();
        const actZh = (d.action_zh || "").trim();
    window.__lastEmo = (d.emotion || "").trim();   // 服务端给的情绪标签
    window.__nextScene = (d.bg || "").trim();      // 服务端已按文件名标签匹配好；没匹配上就是空
    window.__nextOutfit = (d.outfit || "").trim(); // 只有明确换衣服才有值
    window.__lastThinking = (d.thinking || "").trim();
    window.__lastAction = (d.action_zh || d.action || "").trim();
    renderThinking();
      history.push({ role: "assistant", content: reply });
      window.__history = history;
      window.__history = history;
      // 对话框显示中文（有译文用译文），历史记录也显示中文
      const shown = replyZh ? ("「" + replyZh.replace(/^「|」$/g, "") + "」") : reply;
      window.__speakJa = replyZh ? reply.replace(/^「|」$/g, "") : "";
      /* 中日对照：content 保留语言模型原句（含 action/emotion 未过滤），zh 存翻译模型原样输出 */
      history[history.length - 1].zh = replyZh;
      addHistory("assistant", shown, reply);   /* 第三参：日文原句，只存不显示 */
      // 先合成语音；语音没准备好就先不出文字，等语音出来一起出
      speakReply(reply).then(() => {
        // 场景/服装只在模型明确标记时才切，且与文字同一时刻出现
        const _want = window.__lockOutfit ? "" : (window.__nextOutfit || "");
        if (window.__nextScene && !window.__lockScene) { setBg(window.__nextScene); }
        window.__nextScene = "";
        window.__nextOutfit = "";
        setSpriteByScene(currentBg || "classroom", mood, true, _want);
        showReply(shown);
      });

      const mood = (window.__lastEmo || detectMood(shown));
      // 立绘表情随情绪变，服装与场景只在模型明确标记时切换
      accumulateMood(reply);            // BGM 按累积氛围切换，不随单句变

      sessionSave();          // 自动存档
      turnCount++;
    } catch (e) {
      $("msgText").textContent = "[网络错误] " + e.message;
    }
  }

  /* 标题 BGM: 首次交互后播放 */
  let titleBgmStarted = false;

  WA2.chat = { send: send };
  WA2.register("chat", WA2.chat);
  window.send = send;
  /* __export_all__ */
  ["WA2", "_want", "act", "actZh", "body", "d", "inp", "mood", "r", "reply", "replyZh", "shown", "text", "titleBgmStarted"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
