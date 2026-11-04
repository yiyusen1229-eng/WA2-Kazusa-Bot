/* choices.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.choices；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  /* 随机台词选项 */
  const CHOICE_SETS = [
    ["再稍微说一会话吧", "今天就，回去吧"],
    ["……我先走了。", "一起回去吗？"],
    ["继续练琴吧", "陪我走一段"],
  ];

  function showChoices() {
    const set = CHOICE_SETS[Math.floor(Math.random() * CHOICE_SETS.length)];
    const list = $("choiceList");
    list.innerHTML = "";
    set.forEach(txt => {
      const b = document.createElement("button");
      b.className = "choice";
      b.textContent = txt;
      b.addEventListener("mouseenter", () => playSE("hover"));
      b.addEventListener("click", () => {
        playSE("click");
        $("choiceScreen").classList.remove("show");
        $("input").value = txt;
        send();
      });
      list.appendChild(b);
    });
    $("choiceScreen").classList.add("show");
  }

  /* ---------- 发送 ---------- */
  var _exp = {};
  var _names = ["showChoices"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.choices = _exp;
  WA2.register("choices", _exp);
  /* __export_all__ */
  ["showChoices", "CHOICE_SETS", "WA2", "_exp", "_names", "b", "list", "set"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
