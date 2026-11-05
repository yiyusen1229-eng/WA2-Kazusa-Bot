/* wt-hotreload.js 的自测（纯 Node，不开界面）。
 *
 * 跑法：
 *   cd program
 *   node tools/test_hotreload.js
 *
 * 验的是：
 *   1. 第一次拿到 gen 只记基线，不刷新画面
 *   2. gen 没变 → 什么都不做
 *   3. gen 变了 → assetsVer+1、重拉立绘索引、重画当前立绘与背景、提示一次
 *   4. 后端 enabled=false → 不动作
 *   5. 页面隐藏时不发请求
 *   6. stop/start 控制轮询；apply(["character"]) 的提示是「角色素材」
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const code = fs.readFileSync(path.join(__dirname, "..", "src", "ui", "wt-hotreload.js"), "utf8");

const fails = [];
function check(name, cond, extra) {
  if (cond) console.log("  ok   " + name);
  else { console.log("  FAIL " + name + (extra !== undefined ? "  " + JSON.stringify(extra) : "")); fails.push(name); }
}

function make(responses) {
  const toasts = [], dbg = [], calls = [];
  let fetches = 0;
  let queue = responses.slice();
  const timers = { id: 1, fn: null, cleared: false };
  const sb = {
    window: {
      WA2: {
        sprite: {
          loadIndex: function (cb) { calls.push("loadIndex"); if (cb) cb(); },
          refreshCurrent: function () { calls.push("refreshCurrent"); return true; }
        },
        __reapplyBg: function () { calls.push("reapplyBg"); return true; },
        __toast: function (t) { toasts.push(String(t)); },
        __dbg: function (a, b) { dbg.push([a, b]); }
      },
      document: { hidden: false },
      __toast: function (t) { toasts.push(String(t)); },
      __dbg: function (a, b) { dbg.push([a, b]); }
    },
    document: { hidden: false },
    console: console,
    Promise: Promise,
    JSON: JSON,
    String: String,
    setInterval: function (fn) { timers.fn = fn; return timers.id; },
    clearInterval: function () { timers.cleared = true; timers.fn = null; },
    fetch: function (url, opts) {
      fetches += 1;
      if (opts && opts.method === "POST") {
        return Promise.resolve({ json: function () { return Promise.resolve({ ok: true, enabled: true, gen: 9 }); } });
      }
      const next = queue.length ? queue.shift() : { ok: true, enabled: true, gen: -1 };
      return Promise.resolve({ json: function () { return Promise.resolve(next); } });
    }
  };
  // 让 window.__reapplyBg 也能从 window 上取到
  sb.window.__reapplyBg = sb.window.WA2.__reapplyBg;
  vm.createContext(sb);
  vm.runInContext(code, sb);
  return { sb, calls, toasts, dbg, timers, fetches: function () { return fetches; }, queue: queue };
}

const tick = () => new Promise((r) => setTimeout(r, 10));

(async function main() {
  /* 第一次响应的 gen=1：只记基线 */
  const A = make([{ ok: true, enabled: true, gen: 1 }]);
  check("加载时自动轮询了一次", A.fetches() === 1, A.fetches());
  await tick();
  check("基线不触发刷新", A.calls.length === 0, A.calls);
  check("assetsVer 还是 0", A.sb.window.WA2.assetsVer === undefined || A.sb.window.WA2.assetsVer === 0);

  /* gen 没变 */
  A.queue.push({ ok: true, enabled: true, gen: 1 });
  A.sb.window.WA2.hotReload.poll();
  await tick();
  check("gen 没变不动手", A.calls.length === 0, A.calls);

  /* gen 变了 */
  A.queue.push({ ok: true, enabled: true, gen: 2, last_kinds: ["assets"] });
  A.sb.window.WA2.hotReload.poll();
  await tick();
  check("gen 变了：重拉立绘索引", A.calls.indexOf("loadIndex") >= 0, A.calls);
  check("gen 变了：重画当前立绘", A.calls.indexOf("refreshCurrent") >= 0, A.calls);
  check("gen 变了：重画背景", A.calls.indexOf("reapplyBg") >= 0, A.calls);
  check("assetsVer 变成 1", A.sb.window.WA2.assetsVer === 1, A.sb.window.WA2.assetsVer);
  check("提示「素材已更新」", A.toasts.some(function (t) { return t.indexOf("素材已更新") >= 0; }), A.toasts);
  check("时间线记了一条 ASSET", A.dbg.some(function (d) { return d[0] === "ASSET"; }), A.dbg);

  /* 再变一次：版本继续涨（URL 带 ?v= 才能真的换图） */
  A.queue.push({ ok: true, enabled: true, gen: 3, last_kinds: ["character"] });
  A.sb.window.WA2.hotReload.poll();
  await tick();
  check("assetsVer 变成 2", A.sb.window.WA2.assetsVer === 2, A.sb.window.WA2.assetsVer);
  check("角色素材的提示文案", A.toasts.some(function (t) { return t.indexOf("角色素材") >= 0; }), A.toasts);

  /* 后端关了 */
  const before = A.calls.length;
  A.queue.push({ ok: true, enabled: false, gen: 4 });
  A.sb.window.WA2.hotReload.poll();
  await tick();
  check("enabled=false 不动作", A.calls.length === before, A.calls.length - before);

  /* 页面隐藏时不发请求 */
  const B = make([{ ok: true, enabled: true, gen: 1 }]);
  await tick();
  B.sb.document.hidden = true;
  B.sb.window.document.hidden = true;
  const f0 = B.fetches();
  B.sb.window.WA2.hotReload.poll();
  await tick();
  check("隐藏时不发请求", B.fetches() === f0, [f0, B.fetches()]);

  /* stop / start */
  B.sb.window.WA2.hotReload.stop();
  check("stop() 之后不轮询", B.sb.window.WA2.hotReload.polling() === false);
  check("stop() 清了定时器", B.timers.cleared === true);
  B.sb.window.WA2.hotReload.start();
  check("start() 重新开始轮询", B.sb.window.WA2.hotReload.polling() === true);

  /* 开关接口 */
  B.sb.window.WA2.hotReload.setEnabled(false);
  await tick();
  check("setEnabled 会发 POST（本地开关）", B.toasts.length > 0, B.toasts);

  console.log();
  if (fails.length) {
    console.log("失败 " + fails.length + " 项：" + fails.join(" / "));
    process.exit(1);
  }
  console.log("全部通过");
})();
