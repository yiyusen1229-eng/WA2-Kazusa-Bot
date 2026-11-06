/* wt-choices.js 的「分支数量」接线自测（纯 Node，不开界面）。
 *
 * 跑法：
 *   cd program
 *   node tools/test_choices_prefs.js
 *
 * 为什么专门测这个：2026-11-06 用户反馈「不管设置里改成几，出现的都是两个」。
 * 原因是 `prefsCount()` 去读 `WA2.prefs.getPrefs()` —— 而**根本没有 `WA2.prefs`**，
 * 设置模块的入口是 `window.App.getPrefs/setPref`。读不到就永远用默认 2，
 * 于是后端每次都被要求给 2 个。
 *
 * 这里用 vm 把模块加载起来（假 document / 假 App），只调 `prefsCount()`。
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const code = fs.readFileSync(path.join(__dirname, "..", "src", "ui", "wt-choices.js"), "utf8");

const fails = [];
function check(name, cond, extra) {
  console.log((cond ? "  ok   " : "  FAIL ") + name + (cond ? "" : "  " + JSON.stringify(extra)));
  if (!cond) fails.push(name);
}

/* 假环境：只给模块加载时需要的一点点 */
function load(prefs, opts) {
  opts = opts || {};
  const doc = {
    addEventListener: function () {},
    getElementById: function () { return null; },
    createElement: function () {
      return { style: {}, classList: { add: function () {}, remove: function () {} },
               appendChild: function () {}, addEventListener: function () {} };
    },
    head: { appendChild: function () {} },
    body: { appendChild: function () {} }
  };
  const win = {
    document: doc,
    WA2: { register: function () {}, perf: null },
    __history: [],
    toast: function () {},
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    Promise: Promise,
    fetch: function () { return Promise.resolve({ json: function () { return Promise.resolve({ ok: true, options: ["a", "b"] }); } }); },
    console: console
  };
  if (prefs !== null) win.App = { getPrefs: function () { return prefs; }, setPref: function () {} };
  if (opts.addWa2Prefs) {
    /* 老代码找的那个（永远不存在）也补上，确认我们没退回去读它 */
    win.WA2.prefs = { getPrefs: function () { return { choiceCount: 5 }; } };
  }
  const sandbox = {
    window: win, document: doc, console: console,
    setTimeout: setTimeout, clearTimeout: clearTimeout, Promise: Promise,
    fetch: win.fetch, Math: Math, parseInt: parseInt, String: String, JSON: JSON,
    Image: function () {}, encodeURIComponent: encodeURIComponent
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  return sandbox.window.WA2.choices;
}

console.log("[1] 读的是 window.App.getPrefs");
let c = load({ choiceCount: 4 });
check("设置 4 个 → prefsCount() = 4", c.prefsCount() === 4, c.prefsCount());

c = load({ choiceCount: 2 });
check("设置 2 个 → 2", c.prefsCount() === 2, c.prefsCount());

c = load({ choiceCount: "5" });
check("字符串 '5' 也认", c.prefsCount() === 5, c.prefsCount());

console.log("[2] 夹取与兜底");
c = load({ choiceCount: 9 });
check("超过 5 → 夹到 5", c.prefsCount() === 5, c.prefsCount());
c = load({ choiceCount: 1 });
check("小于 2 → 夹到 2", c.prefsCount() === 2, c.prefsCount());
c = load({ choiceCount: 0 });
check("0 当没设 → 2", c.prefsCount() === 2, c.prefsCount());
c = load({});
check("没这个键 → 2", c.prefsCount() === 2, c.prefsCount());
c = load(null);
check("App 还没就绪 → 2（不抛异常）", c.prefsCount() === 2, c.prefsCount());

console.log("[3] 不再依赖不存在的 WA2.prefs");
c = load({ choiceCount: 3 }, { addWa2Prefs: true });
check("即使有 WA2.prefs，也以 App.getPrefs 为准（3 而不是 5）", c.prefsCount() === 3, c.prefsCount());

console.log();
if (fails.length) {
  console.log("失败 " + fails.length + " 项：" + fails.join("、"));
  process.exit(1);
}
console.log("全部通过");
