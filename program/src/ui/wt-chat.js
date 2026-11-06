/* chat.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.chat；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  async function send() {
    if (window.__charSwitching) return;      // 切角色过渡中：先别发，等新角色就位
    /* 新消息先打断重播：回想里正在播的那句要停，状态机也清掉 */
    if (WA2.perf) {
      WA2.perf.interrupt("REPLAYING");
      try { if (WA2.voice && WA2.voice.stopSpeak) WA2.voice.stopSpeak(); } catch (e) {}
      WA2.perf.begin("DIALOGUE_STREAMING");
    }
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
      /* #24：静默降级会让人以为云端模型突然变笨了，所以降级要说一声；
         预算提醒也搭这趟车（后端只在到 80% / 超额时才给这句话） */
      try {
        if (d.degraded && window.__toast) {
          window.__toast("云端不可用（" + (d.degrade_reason || "错误") + "），这一轮用的是本地模型", 3200);
        }
        if (d.budget_warn && window.__toast) window.__toast(d.budget_warn, 4000);
      } catch (e) {}
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
      // 对话框显示中文（有译文用译文），历史记录也显示中文
      const shown = replyZh ? ("「" + replyZh.replace(/^「|」$/g, "") + "」") : reply;
      window.__speakJa = replyZh ? reply.replace(/^「|」$/g, "") : "";
      /* 中日对照：content 保留语言模型原句（含 action/emotion 未过滤），zh 存翻译模型原样输出 */
      history[history.length - 1].zh = replyZh;
      history[history.length - 1].emo = window.__lastEmo || "";   /* 重播要按当时的情绪算缓存 key */
      addHistory("assistant", shown, reply, window.__lastEmo || "");   /* 三参：日文原句；四参：当时的情绪 */
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
      // BGM 按累积氛围切换，不随单句变。
      // 注意要喂**中文**那侧：detectMood 的规则全是中文词，喂日语原文永远判成 calm。
      // 同时把模型给的 <emotion> 一起传进去 —— BGM 优先信它
      // （毒舌是她日常嘴硬、算 calm；只有「沉重」才切冰之刃）。
      accumulateMood(replyZh || shown, window.__lastEmo || "");
      sessionSave();          // 自动存档
      turnCount++;
    } catch (e) {
      $("msgText").textContent = "[网络错误] " + e.message;
    } finally {
      if (WA2.perf) WA2.perf.end("DIALOGUE_STREAMING");
    }
  }

  /* 标题 BGM: 首次交互后播放 */
  let titleBgmStarted = false;

  /* 开新游戏：把「上一局留下的待办量」清掉（这些量的归属在这里，别人别直接写 window.__xxx） */
  function resetPending() {
    window.__lastEmo = "";
    window.__nextScene = "";
    window.__nextOutfit = "";
    window.__lastThinking = "";
    window.__lastAction = "";
    return true;
  }

  WA2.chat = { send: send, resetPending: resetPending };
  WA2.register("chat", WA2.chat);
  window.send = send;
  /* __export_all__ */
  ["resetPending", "WA2", "_want", "act", "actZh", "body", "d", "inp", "mood", "r", "reply", "replyZh", "shown", "text", "titleBgmStarted"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
