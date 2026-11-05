/* perf.js 的自测（纯 Node，不开界面）。
 *
 * 跑法：
 *   cd program
 *   node tools/test_perf.js
 *
 * 验的是：
 *   1. 初始 IDLE
 *   2. 流式输出时不许重播；结束后恢复
 *   3. 浮层不算忙（回想本身就在浮层里），重播照常
 *   4. 重播优先级高于浮层；interrupt 能整个掐掉
 *   5. 切角色时重播、流式都禁止
 *   6. begin/end 计数成对，嵌套不丢
 *   7. onChange 能收到状态变化
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const code = fs.readFileSync(path.join(__dirname, "..", "src", "ui", "wt-perf.js"), "utf8");
const sandbox = { window: { WA2: { register: function () {} } }, console: console };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

const perf = sandbox.window.WA2.perf;
const S = perf.STATES;

const fails = [];
function check(name, cond, extra) {
  if (cond) {
    console.log("  ok   " + name);
  } else {
    console.log("  FAIL " + name + (extra !== undefined ? "  " + JSON.stringify(extra) : ""));
    fails.push(name);
  }
}

check("初始是 IDLE", perf.current() === S.IDLE, perf.current());

perf.begin(S.DIALOGUE_STREAMING);
check("流式输出 → DIALOGUE_STREAMING", perf.current() === S.DIALOGUE_STREAMING, perf.current());
check("流式中不许重播", perf.can(S.REPLAYING) === false);
perf.end(S.DIALOGUE_STREAMING);
check("流式结束 → IDLE", perf.current() === S.IDLE, perf.current());
check("空闲时能重播", perf.can(S.REPLAYING) === true);

perf.begin(S.OVERLAY_OPEN);
check("开浮层 → OVERLAY_OPEN", perf.current() === S.OVERLAY_OPEN, perf.current());
check("浮层里仍能重播（回想就在浮层里）", perf.can(S.REPLAYING) === true);

perf.begin(S.REPLAYING);
check("重播优先级高于浮层", perf.current() === S.REPLAYING, perf.current());
perf.interrupt(S.REPLAYING);
check("interrupt 掐掉重播 → 回到浮层", perf.current() === S.OVERLAY_OPEN, perf.current());
perf.end(S.OVERLAY_OPEN);
check("关浮层 → IDLE", perf.current() === S.IDLE, perf.current());

perf.begin(S.CHARACTER_SWITCHING);
check("切角色 → CHARACTER_SWITCHING", perf.current() === S.CHARACTER_SWITCHING, perf.current());
check("切角色时不许重播", perf.can(S.REPLAYING) === false);
check("切角色时不许流式", perf.can(S.DIALOGUE_STREAMING) === false);
perf.end(S.CHARACTER_SWITCHING);
check("切角色结束 → IDLE", perf.current() === S.IDLE, perf.current());

// 嵌套计数
perf.begin(S.VOICE_PLAYING);
perf.begin(S.VOICE_PLAYING);
perf.end(S.VOICE_PLAYING);
check("嵌套 begin/end 还在 VOICE_PLAYING", perf.current() === S.VOICE_PLAYING, perf.current());
perf.end(S.VOICE_PLAYING);
check("两层都结束 → IDLE", perf.current() === S.IDLE, perf.current());
perf.end(S.VOICE_PLAYING);
check("多余的 end 不把计数弄负", perf.current() === S.IDLE, perf.current());

// onChange
let seen = [];
perf.onChange(function (now, prev) { seen.push(prev + "->" + now); });
perf.begin(S.REPLAYING);
perf.end(S.REPLAYING);
check("onChange 收到变化", seen.length === 2, seen);

console.log();
if (fails.length) {
  console.log("失败 " + fails.length + " 项：" + fails.join(" / "));
  process.exit(1);
}
console.log("全部通过");
