/* 素材检查 / 导入向导（#20）：把「缺什么」按步骤摆出来，每一步都能跳过。
 *
 * 数据来自 /api/assets/wizard（后端读 logs/asset_report.json，?refresh=1 时现扫一遍）。
 * 这里不做导入：导入面板已经有了（特别模式），向导只负责「告诉你缺什么、从哪进」。
 *
 * 入口：菜单「环境设置 → 素材检查」，或 window.__openAssetWizard()。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var box = null;
  var last = null;

  function el(tag, style, text) {
    var e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  var S_BOX = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9500;" +
    "width:min(760px,92vw);max-height:80vh;overflow:auto;background:rgba(10,16,24,.96);" +
    "border:1px solid #6f8ba8;border-radius:6px;color:#dfe9f2;padding:18px 20px;" +
    "font-family:inherit;font-size:15px;line-height:1.60;box-shadow:0 8px 32px rgba(0,0,0,.6);";
  var S_ROW = "margin:0 0 12px;padding:10px 12px;border:1px solid #3b4d61;border-radius:4px;" +
    "background:rgba(255,255,255,.03);";
  var S_TITLE = "font-size:16px;color:#fff;margin:0 0 8px;letter-spacing:.5px;";
  var S_HINT = "color:#9fb3c6;font-size:13px;margin:2px 0 0;";
  var S_BTN = "cursor:pointer;background:rgba(255,255,255,.08);color:#dfe9f2;" +
    "border:1px solid #6f8ba8;border-radius:4px;padding:5px 14px;font-size:14px;margin-left:8px;";
  var S_OK = "color:#8fd694;";
  var S_BAD = "color:#ffb4a2;";

  function close() {
    if (box && box.parentNode) box.parentNode.removeChild(box);
    box = null;
  }

  function render(d) {
    last = d;
    if (box) close();
    box = el("div", S_BOX);
    box.id = "assetWizard";

    var head = el("div");
    head.appendChild(el("div", S_TITLE, "素材检查"));
    head.appendChild(el("p", S_HINT,
      d && d.ok ? (d.hint || "") : ("读不到素材报告：" + ((d && d.error) || "未知错误"))));
    if (d && d.ok) {
      head.appendChild(el("p", S_HINT,
        "检查了 " + (d.checked || 0) + " 个文件（" +
        Math.round((d.bytes || 0) / 1048576) + " MB）· 缺 " + (d.missing_total || 0) +
        " 项 · 0 字节 " + (d.zero_total || 0) + " 项"));
    }
    box.appendChild(head);

    ((d && d.steps) || []).forEach(function (s) {
      var row = el("div", S_ROW);
      var line = el("div");
      var mark = el("span", s.ok ? S_OK : S_BAD, s.ok ? "✔ " : "✘ ");
      line.appendChild(mark);
      line.appendChild(el("span", "font-size:15px;color:#fff;", s.title || ""));
      line.appendChild(el("span", S_HINT,
        "　" + (s.ok ? "齐全" : ("缺 " + (s.missing || 0) + " 项")) + " · 可跳过"));
      row.appendChild(line);
      (s.examples || []).slice(0, 6).forEach(function (x) {
        row.appendChild(el("div", "color:#c8d6e2;font-size:13px;padding-left:22px;", "· " + x));
      });
      if (!s.ok && s.hint) row.appendChild(el("p", S_HINT, s.hint));
      box.appendChild(row);
    });

    var foot = el("div", "text-align:right;margin-top:6px;");
    var rescan = el("button", S_BTN, "重新扫描");
    rescan.onclick = function () { load(true); };
    var skip = el("button", S_BTN, "跳过（以后在特别模式里补）");
    skip.onclick = close;
    var ok = el("button", S_BTN, "关闭");
    ok.onclick = close;
    foot.appendChild(rescan);
    foot.appendChild(skip);
    foot.appendChild(ok);
    box.appendChild(foot);

    var mask = el("div", "position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9400;");
    mask.onclick = close;
    mask.appendChild(box);
    document.body.appendChild(mask);
  }

  function load(refresh) {
    fetch("/api/assets/wizard" + (refresh ? "?refresh=1" : ""), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function (e) { render({ ok: false, error: String(e).slice(0, 120) }); });
  }

  WA2.wizard = { open: load, close: close, data: function () { return last; } };
  window.__openAssetWizard = function () { load(false); };
})();
