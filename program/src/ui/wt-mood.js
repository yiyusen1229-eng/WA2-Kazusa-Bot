/* mood.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.mood；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  function detectMood(text) {
    const t = text || "";
    if (/滚|烦|吵|闭嘴|笨蛋|无聊|别管|哼|少来|自作多情/.test(t)) return "angry";
    if (/抱歉|对不起|哭|寂寞|后悔|离开|再见|讨厌我/.test(t)) return "sad";
    if (/早点睡|注意|吃药|别勉强|你也|小心|累了吧|照顾好/.test(t)) return "warm";
    if (/呵|笑|有趣|真拿你没办法|好吧/.test(t)) return "smile";
    if (/……|没事|没什么|有事|随便|不知道/.test(t)) return "calm";
    return "calm";
  }

  const MOOD_BGM = { angry: "tense", sad: "sad", warm: "warm", smile: "warm", cold: "calm" };
  /* 情绪→表情不在这里：立绘那边已改成中文名别名表（wt-sprite.js 的 EMO_ALIAS），
     这里的 MOOD_SPRITE 早就没人用了，删掉省得以后两边映射打架。 */

  /* ---------- 氛围累积（BGM 不随单句变化） ---------- */
  const moodScore = { calm: 0, warm: 0, sad: 0, tense: 0 };
  let moodStable = { name: "calm", turns: 0 };

  function accumulateMood(reply) {
    const mood = detectMood(reply);
    const bgm = MOOD_BGM[mood] || "calm";
    // 每轮衰减，越近的话权重越大
    for (const k in moodScore) moodScore[k] *= 0.65;
    moodScore[bgm] = (moodScore[bgm] || 0) + 2;
    // 长句、强烈情绪加权
    if (reply.length > 40) moodScore[bgm] += 0.8;
    if (/[！!]{2,}|滚|闭嘴|笨蛋/.test(reply)) moodScore.tense += 1.2;
    if (/[（(]笑|呵|真拿你|好吧/.test(reply)) moodScore.warm += 0.8;

    // 当前氛围的分数
    let best = "calm", bestV = -1;
    for (const k in moodScore) {
      if (moodScore[k] > bestV) { bestV = moodScore[k]; best = k; }
    }
    const curV = moodScore[currentBgmMood()] || 0;

    // 需要连续两轮领先 2 分以上才切换
    if (best !== moodStable.name) {
      moodStable = { name: best, turns: 1 };
    } else {
      moodStable.turns++;
    }
    const enough = bestV - curV >= 2.0 && moodStable.turns >= 2;
    if (best !== currentBgmMood() && enough) {
      setBgm(best);
    }
  }

  function currentBgmMood() {
    for (const k in MOOD_BGM) {
      if (MOOD_BGM[k] === WA2.audio.current) return k === "smile" ? "warm" : MOOD_BGM[k];
    }
    return WA2.audio.current || "calm";
  }

  /* 开新游戏：氛围分归零（不然上一局的「难过/紧张」会带进新局，BGM 一开就偏） */
  function reset() {
    for (const k in moodScore) moodScore[k] = 0;
    moodStable = { name: "calm", turns: 0 };
    return true;
  }


  /* 合并版：按当前角色给开场白 */
  var OPENING_LINE = { zh: "「……」", ja: "", emo: "calm" };
  var _exp = {};
  var _names = ["accumulateMood", "currentBgmMood", "detectMood", "reset"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.mood = _exp;
  WA2.register("mood", _exp);
  /* __export_all__ */
  ["accumulateMood", "currentBgmMood", "detectMood", "MOOD_BGM", "OPENING_LINE", "WA2", "_exp", "_names", "best", "bgm", "curV", "enough", "mood", "moodScore", "moodStable", "reset", "t"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
