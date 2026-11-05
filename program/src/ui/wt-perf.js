/* perf.js —— 演出状态机：把「重播 / 流式输出 / 语音 / 浮层 / 切角色」收成一个仲裁点。
 *
 * 为什么要它：这些演出以前各管各的（回想拿到就播、新消息不打断重播、切角色时语音还在响），
 * 状态一乱就出现「两个人同时说话」「切完了还在播上一句」这类问题。
 *
 * 状态（同时只有一个主状态，语音是叠加在上面的）：
 *   IDLE / DIALOGUE_STREAMING / VOICE_PLAYING / REPLAYING / OVERLAY_OPEN / CHARACTER_SWITCHING
 *
 * 仲裁规则：
 *   - 新消息（DIALOGUE_STREAMING）打断重播（调用方先 interrupt("REPLAYING") 再停语音）
 *   - 切角色 / 流式输出时不许重播
 *   - 浮层不算「忙」：回想本身就在浮层里，重播照常
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var S = {
    IDLE: "IDLE",
    DIALOGUE_STREAMING: "DIALOGUE_STREAMING",
    VOICE_PLAYING: "VOICE_PLAYING",
    REPLAYING: "REPLAYING",
    OVERLAY_OPEN: "OVERLAY_OPEN",
    CHARACTER_SWITCHING: "CHARACTER_SWITCHING"
  };

  /* 主状态优先级（越靠前越"忙"） */
  var ORDER = [S.CHARACTER_SWITCHING, S.DIALOGUE_STREAMING, S.REPLAYING,
               S.OVERLAY_OPEN, S.VOICE_PLAYING];

  var counts = {};       /* 每种状态的占用计数：允许嵌套调用 */
  var cur = S.IDLE;
  var subs = [];

  function recompute() {
    var next = S.IDLE;
    for (var i = 0; i < ORDER.length; i++) {
      if (counts[ORDER[i]]) { next = ORDER[i]; break; }
    }
    if (next !== cur) {
      var prev = cur;
      cur = next;
      for (var j = 0; j < subs.length; j++) {
        try { subs[j](cur, prev); } catch (e) {}
      }
    }
    return cur;
  }

  function begin(kind) {
    if (!kind) return cur;
    counts[kind] = (counts[kind] || 0) + 1;
    return recompute();
  }

  function end(kind) {
    if (!kind) return cur;
    if (counts[kind]) counts[kind]--;
    if (!counts[kind]) delete counts[kind];
    return recompute();
  }

  /* 强行清掉某状态（比如新消息来了，把重播整个掐掉） */
  function interrupt(kind) {
    delete counts[kind];
    return recompute();
  }

  function active(kind) { return !!counts[kind]; }

  function is(kind) { return cur === kind; }

  /* 现在能不能开始某种演出 */
  function can(kind) {
    if (kind === S.REPLAYING) {
      return !counts[S.CHARACTER_SWITCHING] && !counts[S.DIALOGUE_STREAMING];
    }
    if (kind === S.DIALOGUE_STREAMING) {
      return !counts[S.CHARACTER_SWITCHING];
    }
    return true;
  }

  function onChange(fn) { if (typeof fn === "function") subs.push(fn); }

  var api = {
    STATES: S,
    begin: begin,
    end: end,
    interrupt: interrupt,
    active: active,
    is: is,
    can: can,
    current: function () { return cur; },
    onChange: onChange,
    counts: function () { return counts; }
  };

  WA2.perf = api;
  if (WA2.register) WA2.register("perf", api);
  window.__perf = api;
})();
