/* wt-fade.js 的自测（纯 Node，不开界面、不需要浏览器）。
 *
 * 跑法：
 *   cd program
 *   node tools/test_fade.js
 *
 * 验的是：
 *   1. 默认开、默认 240ms
 *   2. prefs.xfade === false → 关；没这个键 → 开
 *   3. xfadeMs 夹在 200~300（乱填回默认）
 *   4. set() 写进 prefs，值同样被夹住
 *   5. 没有 DOM 时 crossBg / crossSprite 不抛异常，fail 回调照常
 *   6. 有 DOM 时：两层交替当「前层」，过渡结束后图回到 #bgLayer
 *   7. describe() 的字段齐全
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const code = fs.readFileSync(path.join(__dirname, "..", "src", "ui", "wt-fade.js"), "utf8");

/* 假的 prefs：测试里随时换 */
const prefs = { xfade: true, xfadeMs: 240 };
const saved = [];
const sandbox = {
  window: {
    WA2: { register: function () {} },
    App: {
      getPrefs: function () { return prefs; },
      setPref: function (k, v) { saved.push([k, v]); prefs[k] = v; }
    }
  },
  console: console,
  setTimeout: setTimeout,
  isFinite: isFinite,
  Number: Number,
  Math: Math
};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

const fade = sandbox.window.WA2.fade;

const fails = [];
function check(name, cond, extra) {
  if (cond) {
    console.log("  ok   " + name);
  } else {
    console.log("  FAIL " + name + (extra !== undefined ? "  " + JSON.stringify(extra) : ""));
    fails.push(name);
  }
}

/* ---------- 1~4：配置 ---------- */
check("默认开", fade.enabled() === true);
check("默认 240ms", fade.ms() === 240, fade.ms());

prefs.xfade = false;
check("xfade=false 就是关", fade.enabled() === false);
delete prefs.xfade;
check("没这个键算开（老设置文件）", fade.enabled() === true);

prefs.xfadeMs = 50;
check("太小夹到 200", fade.ms() === 200, fade.ms());
prefs.xfadeMs = 999;
check("太大夹到 300", fade.ms() === 300, fade.ms());
prefs.xfadeMs = 250;
check("范围内原样", fade.ms() === 250, fade.ms());
prefs.xfadeMs = "abc";
check("乱填回默认", fade.ms() === 240, fade.ms());
prefs.xfadeMs = 0;
check("0 回默认（不是夹到 200）", fade.ms() === 240, fade.ms());

/* ---------- 4b：#19 角色演出配置 performance.json 的 fade_ms ---------- */
delete prefs.xfadeMs;
sandbox.window.WA2.perfCfg = { fadeMs: function () { return 280; } };
check("没设 xfadeMs → 用角色配置 280", fade.ms() === 280, fade.ms());
prefs.xfadeMs = 250;
check("prefs 设了 → 压过角色配置", fade.ms() === 250, fade.ms());
delete prefs.xfadeMs;
sandbox.window.WA2.perfCfg = { fadeMs: function () { return 999; } };
check("角色配置超上限 → 夹到 300", fade.ms() === 300, fade.ms());
sandbox.window.WA2.perfCfg = { fadeMs: function () { return 10; } };
check("角色配置太小 → 夹到 200", fade.ms() === 200, fade.ms());
sandbox.window.WA2.perfCfg = { fadeMs: function () { return "abc"; } };
check("角色配置乱填 → 内置默认 240", fade.ms() === 240, fade.ms());
sandbox.window.WA2.perfCfg = { fadeMs: function () { throw new Error("boom"); } };
check("角色配置抛错 → 内置默认 240", fade.ms() === 240, fade.ms());
delete sandbox.window.WA2.perfCfg;
check("没有 perfCfg → 内置默认 240", fade.ms() === 240, fade.ms());

fade.set(false);
check("set(false) 写进 prefs", prefs.xfade === false && saved.length === 1, saved);
fade.set(true, 500);
check("set(true,500) 把 ms 夹到 300", prefs.xfade === true && prefs.xfadeMs === 300, prefs);
fade.set(true, 220);
check("set(true,220) 保留 220", prefs.xfadeMs === 220, prefs);

/* ---------- 5：没有 DOM ---------- */
let failed = 0;
const okNoDom = fade.crossBg("a.png", null, function () { failed++; });
check("没有 DOM 时 crossBg 返回 false", okNoDom === false);
check("没有 DOM 时 fail 被调用一次", failed === 1, failed);
failed = 0;
fade.crossSprite("a.png", null, function () { failed++; });
check("没有 DOM 时 crossSprite 也走 fail", failed === 1, failed);

/* ---------- 6：有 DOM（两层交替） ---------- */
function fakeEl(id) {
  return {
    id: id,
    style: {},
    offsetWidth: 1,
    classList: { _s: {}, add: function (c) { this._s[c] = 1; }, remove: function (c) { delete this._s[c]; }, contains: function (c) { return !!this._s[c]; } }
  };
}
const els = { bgLayer: fakeEl("bgLayer"), bgLayer2: fakeEl("bgLayer2") };
sandbox.document = { getElementById: function (id) { return els[id] || null; } };

fade.crossBg("/game/assets/a.png");
check("第一次过渡：新图落在 #bgLayer2（后加的层在上面）",
  els.bgLayer2.style.backgroundImage === 'url("/game/assets/a.png")', els.bgLayer2.style);
check("第一次过渡：#bgLayer 被压到 0", els.bgLayer.style.opacity === "0", els.bgLayer.style);

fade.settle("/game/assets/a.png");
check("收尾后图回到 #bgLayer",
  els.bgLayer.style.backgroundImage === 'url("/game/assets/a.png")' && els.bgLayer.style.opacity === "1",
  els.bgLayer.style);
check("收尾后 #bgLayer2 归零并清图",
  els.bgLayer2.style.opacity === "0" && els.bgLayer2.style.backgroundImage === "none",
  els.bgLayer2.style);

fade.crossBg("/game/assets/b.png");
check("收尾之后的新过渡：#bgLayer2 重新当「淡入层」",
  els.bgLayer2.style.backgroundImage === 'url("/game/assets/b.png")' &&
  els.bgLayer2.style.opacity === "1" &&
  els.bgLayer.style.opacity === "0",
  [els.bgLayer.style, els.bgLayer2.style]);

/* 连着换两张、中间不 settle：第二次要落在另一层（不然新图先盖旧图再淡自己，会闪） */
fade.settle("/game/assets/b.png");
fade.crossBg("/game/assets/c.png");
fade.crossBg("/game/assets/d.png");
check("连着换时第二张落在 #bgLayer 上（前层交替）",
  els.bgLayer.style.backgroundImage === 'url("/game/assets/d.png")' &&
  els.bgLayer.style.opacity === "1" &&
  els.bgLayer2.style.backgroundImage === 'url("/game/assets/c.png")',
  [els.bgLayer.style, els.bgLayer2.style]);

/* 关掉过渡：立刻换，不留中间态 */
prefs.xfade = false;
fade.crossBg("/game/assets/c.png");
check("关过渡时直接换到 #bgLayer",
  els.bgLayer.style.backgroundImage === 'url("/game/assets/c.png")' &&
  els.bgLayer.style.opacity === "1" && els.bgLayer.style.transition === "none",
  els.bgLayer.style);

/* ---------- 7：describe ---------- */
const d = fade.describe();
check("describe 有 enabled/ms", typeof d.enabled === "boolean" && typeof d.ms === "number", d);
check("describe 的 enabled 跟着 prefs 走", d.enabled === false, d);

console.log();
if (fails.length) {
  console.log("失败 " + fails.length + " 项：" + fails.join(" / "));
  process.exit(1);
}
console.log("全部通过");
