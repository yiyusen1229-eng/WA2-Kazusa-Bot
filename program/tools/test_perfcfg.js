/* wt-perfcfg.js 的自测（纯 Node，不开界面）。
 *
 * 跑法：
 *   cd program
 *   node tools/test_perfcfg.js
 *
 * 验的是：
 *   1. 拿到之前：fadeMs 是 0、两张表是空对象（**不复制默认表**，让各模块用自己的）
 *   2. 拿到之后：fade_ms / 情绪映射 / 场景映射 / 切片预算都对
 *   3. warnings 非空 → 弹一次 toast，第二次 refresh 不再弹
 *   4. 接口报错 / 网络失败 → 保留上一次的值，不抛
 *   5. refresh(cb) 会把整包交给回调
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const code = fs.readFileSync(path.join(__dirname, "..", "src", "ui", "wt-perfcfg.js"), "utf8");

const fails = [];
function check(name, cond, extra) {
  if (cond) {
    console.log("  ok   " + name);
  } else {
    console.log("  FAIL " + name + (extra !== undefined ? "  " + JSON.stringify(extra) : ""));
    fails.push(name);
  }
}

function make(resp) {
  const toasts = [];
  const dbg = [];
  const sb = {
    window: {
      WA2: {},
      __toast: function (t) { toasts.push(t); },
      __dbg: function (a, b) { dbg.push([a, b]); }
    },
    console: console,
    setTimeout: setTimeout,
    isFinite: isFinite,
    Number: Number,
    Object: Object,
    fetch: function () {
      if (resp instanceof Error) return Promise.reject(resp);
      return Promise.resolve({ json: function () { return Promise.resolve(resp); } });
    }
  };
  vm.createContext(sb);
  vm.runInContext(code, sb);
  return { sb, pkg: sb.window.WA2.perfCfg, toasts, dbg };
}

const tick = () => new Promise((r) => setTimeout(r, 10));

(async function main() {
  /* ---------- 1：拿到之前 ---------- */
  const A = make({
    ok: true,
    performance: { fade_ms: 280, mood_to_emotion: { shy: "sad" }, outfit_by_scene: { "夜の学校": "冬季校服" } },
    slices: { story_k: 3, worldbook_chars: 1400 },
    warnings: []
  });
  check("拿到之前 fadeMs() 是 0", A.pkg.fadeMs() === 0, A.pkg.fadeMs());
  check("拿到之前情绪表是空的（不复制默认表）",
    Object.keys(A.pkg.moodMap()).length === 0, A.pkg.moodMap());
  check("拿到之前场景表是空的",
    Object.keys(A.pkg.outfitMap()).length === 0, A.pkg.outfitMap());

  /* ---------- 2：拿到之后 ---------- */
  await tick();
  check("fade_ms 生效", A.pkg.fadeMs() === 280, A.pkg.fadeMs());
  check("情绪映射生效", A.pkg.moodMap().shy === "sad", A.pkg.moodMap());
  check("场景映射生效", A.pkg.outfitMap()["夜の学校"] === "冬季校服", A.pkg.outfitMap());
  check("切片预算也能读到", A.pkg.get().slices.story_k === 3, A.pkg.get().slices);
  check("没有 warning 就不弹 toast", A.toasts.length === 0, A.toasts);
  check("调试时间线记了一条", A.dbg.length === 1 && A.dbg[0][0] === "CFG", A.dbg);

  /* ---------- 3：warning 只弹一次 ---------- */
  const B = make({ ok: true, performance: { fade_ms: 999 }, slices: {}, warnings: ["performance.json：fade_ms=999 超出 200~300，夹到边界"] });
  await tick();
  check("有 warning 会弹 toast", B.toasts.length === 1 && B.toasts[0].indexOf("演出配置有误") === 0, B.toasts);
  B.pkg.refresh();
  await tick();
  check("第二次 refresh 不再重复弹", B.toasts.length === 1, B.toasts);

  /* ---------- 4：接口报错 / 网络失败保留旧值 ---------- */
  const C = make({ ok: false, error: "读演出配置失败" });
  await tick();
  check("ok:false 时 fadeMs 保持 0", C.pkg.fadeMs() === 0, C.pkg.fadeMs());

  C.sb.fetch = function () { return Promise.reject(new Error("offline")); };
  C.pkg.refresh();
  await tick();
  check("fetch 失败不抛、值不变", C.pkg.fadeMs() === 0, C.pkg.fadeMs());
  check("fetch 失败也不弹 toast", C.toasts.length === 0, C.toasts);

  /* ---------- 5：refresh(cb) ---------- */
  let seen = null;
  const D = make({ ok: true, performance: { fade_ms: 220 }, slices: {}, warnings: [] });
  await tick();
  D.pkg.refresh(function (p) { seen = p; });
  await tick();
  check("refresh(cb) 把整包交给回调", seen && seen.performance.fade_ms === 220, seen);

  /* ---------- 6：没有 __toast 也不炸 ---------- */
  const E = make({ ok: true, performance: {}, slices: {}, warnings: ["x"] });
  delete E.sb.window.__toast;
  await tick();
  check("没有 __toast 也不抛", true);

  console.log();
  if (fails.length) {
    console.log("失败 " + fails.length + " 项：" + fails.join(" / "));
    process.exit(1);
  }
  console.log("全部通过");
})();
