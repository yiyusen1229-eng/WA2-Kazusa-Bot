/* 首次设置向导（#23）：把「还差什么」一屏摆出来，每项一个「去设置」。
 *
 * 数据来自 /api/firstrun（只读检查，不写配置）。
 * 行为：
 *   - 首次启动（prefs 里没有 firstrunDone）且 required 项没全绿时自动弹一次
 *   - 点「知道了」/「跳过」都记 firstrunDone，不再自动弹
 *   - 菜单「系统 → 首次设置向导」随时能重跑（不受标记影响）
 *
 * 为什么不做成拦路的多步向导：程序本来就能用（缺语音只是没声音），
 * 拦着不让进比缺配置更烦人。这里只负责「告诉你缺什么、从哪进」。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var box = null;
  var DONE_KEY = "firstrunDone";

  function el(tag, style, text) {
    var e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  var S_BOX = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9600;" +
    "width:min(720px,92vw);max-height:80vh;overflow:auto;background:rgba(10,16,24,.97);" +
    "border:1px solid #6f8ba8;border-radius:6px;color:#dfe9f2;padding:18px 20px;" +
    "font-family:inherit;font-size:15px;line-height:1.60;box-shadow:0 8px 32px rgba(0,0,0,.6);";
  var S_ROW = "margin:0 0 10px;padding:9px 12px;border:1px solid #3b4d61;border-radius:4px;" +
    "background:rgba(255,255,255,.03);display:flex;align-items:flex-start;gap:10px;";
  var S_TITLE = "font-size:16px;color:#fff;margin:0 0 6px;letter-spacing:.5px;";
  var S_HINT = "color:#9fb3c6;font-size:13px;";
  var S_BTN = "cursor:pointer;background:rgba(255,255,255,.08);color:#dfe9f2;" +
    "border:1px solid #6f8ba8;border-radius:4px;padding:5px 14px;font-size:14px;margin-left:8px;";
  var S_OK = "color:#8fd694;font-size:18px;line-height:1;";
  var S_BAD = "color:#ffb4a2;font-size:18px;line-height:1;";
  var S_OPT = "color:#7d8fa3;font-size:12px;";

  function prefs() {
    try { return (window.App && window.App.getPrefs) ? window.App.getPrefs() : {}; } catch (e) { return {}; }
  }
  function setPref(k, v) {
    try { if (window.App && window.App.setPref) window.App.setPref(k, v); } catch (e) {}
  }

  function close() {
    if (box && box.parentNode) box.parentNode.removeChild(box);
    box = null;
  }

  /* 每项对应去哪儿改：opt=设置页 / special=特别模式 / asset=素材检查 */
  function goto(fix) {
    try {
      if (fix === "opt" && window.WA2 && WA2.screens) { WA2.screens.show("opt"); return; }
      if (fix === "special" && window.WA2 && WA2.screens) { WA2.screens.show("special"); return; }
      if (fix === "asset") {
        close();
        if (window.__openAssetWizard) window.__openAssetWizard();
        return;
      }
    } catch (e) {}
    try { if (window.__toast) window.__toast("自己去菜单里找一下：环境设置 / 系统设置", 2400); } catch (e) {}
  }

  function render(data) {
    close();
    box = el("div", S_BOX);
    var head = el("div", S_TITLE + "display:flex;align-items:center;justify-content:space-between;");
    head.appendChild(el("span", "", "首次设置检查"));
    var x = el("span", "cursor:pointer;color:#9fb3c6;padding:0 4px;", "✕");
    x.addEventListener("click", close);
    head.appendChild(x);
    box.appendChild(head);
    box.appendChild(el("div", S_HINT + "margin:0 0 12px;",
      data.ready ? "必需的都就绪了 —— 可以直接开始。下面这些是可选项。"
                 : "还有必需项没配好，这些配上就能正常玩了："));

    (data.items || []).forEach(function (it) {
      var row = el("div", S_ROW);
      row.appendChild(el("span", it.ok ? S_OK : S_BAD, it.ok ? "✓" : "✕"));
      var mid = el("div", "flex:1;");
      var t = el("div", "color:#fff;");
      t.appendChild(document.createTextNode(it.title));
      if (it.optional) t.appendChild(el("span", S_OPT, "（可选）"));
      mid.appendChild(t);
      mid.appendChild(el("div", S_HINT, it.detail || ""));
      row.appendChild(mid);
      if (!it.ok && it.fix) {
        var b = el("button", S_BTN, "去设置");
        b.addEventListener("click", function () { goto(it.fix); });
        row.appendChild(b);
      }
      box.appendChild(row);
    });

    var tail = el("div", "text-align:right;margin-top:14px;");
    var re = el("button", S_BTN, "重新检查");
    re.addEventListener("click", function () { run(true); });
    tail.appendChild(re);
    var ok = el("button", S_BTN, data.ready ? "知道了" : "跳过，先这样");
    ok.addEventListener("click", function () {
      setPref(DONE_KEY, true);
      close();
    });
    tail.appendChild(ok);
    box.appendChild(tail);
    document.body.appendChild(box);
  }

  function run(silent) {
    return fetch("/api/firstrun", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) return d;
        if (!silent || !box) render(d);
        return d;
      })
      .catch(function () { return null; });
  }

  /* 首次启动：只有「必需项不全绿」且没记过标记时才自动弹 */
  function autoOpen() {
    var p = prefs();
    if (p[DONE_KEY]) return;
    fetch("/api/firstrun", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok && !d.ready) render(d);
      })
      .catch(function () {});
  }

  WA2.firstrun = { open: function () { return run(false); }, autoOpen: autoOpen, close: close };
  window.__openFirstRun = function () { run(false); };

  document.addEventListener("DOMContentLoaded", function () {
    setTimeout(autoOpen, 2500);      /* 让主界面先画出来，别一开机就怼脸 */
  });
})();
