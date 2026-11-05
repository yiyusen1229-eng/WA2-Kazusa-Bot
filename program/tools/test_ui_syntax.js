/* 前端脚本语法自测（纯 Node，不开界面）。
 *
 * 跑法：
 *   cd program
 *   node tools/test_ui_syntax.js
 *
 * 为什么要它：`check_split.py` 是正则扫的（同名覆盖 / 丢语句 / 未定义引用），
 * **不解析语法**——一个缩进写坏（注释把函数吞了、括号少一个）它会照报「函数齐全」，
 * 但浏览器整个文件不执行，菜单/演出直接消失。这类問題让 `vm.Script` 一次扫出来。
 *
 * 只解析、不执行：脚本里的 document / WA2 / fetch 一个都不会跑。
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DIR = path.join(__dirname, "..", "src", "ui");

const fails = [];
let n = 0;

fs.readdirSync(DIR)
  .filter((f) => f.endsWith(".js"))
  .sort()
  .forEach((f) => {
    n++;
    const code = fs.readFileSync(path.join(DIR, f), "utf8");
    try {
      new vm.Script(code, { filename: f });
    } catch (e) {
      fails.push(f + ": " + e.message);
      console.log("  FAIL " + f + "  " + e.message);
    }
  });

/* 顺手检查样式表没被写坏（花括号数对不上多半是漏了一行） */
const cssDir = DIR;
fs.readdirSync(cssDir)
  .filter((f) => f.endsWith(".css"))
  .sort()
  .forEach((f) => {
    n++;
    const css = fs.readFileSync(path.join(cssDir, f), "utf8");
    const open = (css.match(/\{/g) || []).length;
    const close = (css.match(/\}/g) || []).length;
    if (open !== close) {
      fails.push(f + ": { " + open + " 个，} " + close + " 个");
      console.log("  FAIL " + f + "  花括号对不上（{ " + open + " / } " + close + "）");
    }
  });

console.log("  检查了 " + n + " 个文件");
console.log();
if (fails.length) {
  console.log("失败 " + fails.length + " 项：");
  fails.forEach((x) => console.log("  - " + x));
  process.exit(1);
}
console.log("全部通过");
