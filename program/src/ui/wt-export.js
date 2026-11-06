/* 聊天导出（#23）：先预览、再下载；默认脱敏。
 *
 * 后端 /api/export/chat：
 *   ?preview=1 → {ok, lines, her, mine, masked, chars, preview, filename}
 *   不带 preview → 附件下载（Markdown / 纯文本，带 BOM）
 *
 * 为什么要预览：导出是为了发给别人。发出去之前得让人看见「里面有什么、哪些被抹掉了」——
 * 尤其是她说过的话里可能有你不想公开的内容。预览默认只显示前 800 字，够看清格式和开头。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var box = null;
  var opts = { slot: "auto", onlyReply: false };

  function el(tag, style, text) {
    var e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  var S_BOX = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9600;" +
    "width:min(820px,94vw);max-height:84vh;overflow:auto;background:rgba(10,16,24,.97);" +
    "border:1px solid #6f8ba8;border-radius:6px;color:#dfe9f2;padding:18px 20px;" +
    "font-family:inherit;font-size:15px;line-height:1.62;box-shadow:0 8px 32px rgba(0,0,0,.6);";
  var S_TITLE = "font-size:16px;color:#fff;margin:0 0 6px;letter-spacing:.5px;";
  var S_HINT = "color:#9fb3c6;font-size:13px;margin:0 0 12px;";
  var S_PRE = "white-space:pre-wrap;word-break:break-word;background:rgba(0,0,0,.35);" +
    "border:1px solid #33455a;border-radius:4px;padding:10px 12px;max-height:44vh;" +
    "overflow:auto;font-size:14px;line-height:1.7;color:#cfdae6;";
  var S_BTN = "cursor:pointer;background:rgba(255,255,255,.08);color:#dfe9f2;" +
    "border:1px solid #6f8ba8;border-radius:4px;padding:5px 14px;font-size:14px;margin-left:8px;";
  var S_PRIMARY = S_BTN + "background:rgba(120,170,220,.22);border-color:#8fb3d0;";

  function close() {
    if (box && box.parentNode) box.parentNode.removeChild(box);
    box = null;
  }

  function statsLine(d) {
    return "共 " + d.lines + " 句（她 " + d.her + " 句" +
      (d.mine ? "，你 " + d.mine + " 句" : "") + "）· " + d.chars + " 字" +
      (d.masked ? " · 已脱敏 " + d.masked + " 处" : " · 没发现密钥或本机路径");
  }

  function download() {
    var q = "/api/export/chat?slot=" + encodeURIComponent(opts.slot) +
      "&fmt=md&redact=1" + (opts.onlyReply ? "&only_reply=1" : "");
    try {
      var a = document.createElement("a");
      a.href = q;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      if (window.__toast) window.__toast("已开始下载（Markdown）", 2200);
    } catch (e) {
      window.open(q, "_blank");
    }
    close();
  }

  function render(d) {
    close();
    box = el("div", S_BOX);
    var head = el("div", S_TITLE + "display:flex;align-items:center;justify-content:space-between;");
    head.appendChild(el("span", "", "导出对话"));
    var x = el("span", "cursor:pointer;color:#9fb3c6;padding:0 4px;", "✕");
    x.addEventListener("click", close);
    head.appendChild(x);
    box.appendChild(head);
    box.appendChild(el("div", S_HINT, statsLine(d) +
      "　·　下面只是前 " + (d.preview || "").length + " 字，下载的是全文"));
    box.appendChild(el("div", S_PRE, d.preview || "（空）"));

    var tail = el("div", "text-align:right;margin-top:14px;");
    var only = el("button", S_BTN, opts.onlyReply ? "☑ 只要她的话" : "☐ 只要她的话");
    only.addEventListener("click", function () {
      opts.onlyReply = !opts.onlyReply;
      load();                       /* 切选项后重新预览，所见即所得 */
    });
    tail.appendChild(only);
    var cancel = el("button", S_BTN, "取消");
    cancel.addEventListener("click", close);
    tail.appendChild(cancel);
    var go = el("button", S_PRIMARY, "下载 Markdown");
    go.addEventListener("click", download);
    tail.appendChild(go);
    box.appendChild(tail);
    document.body.appendChild(box);
  }

  function load() {
    var q = "/api/export/chat?slot=" + encodeURIComponent(opts.slot) +
      "&preview=1&redact=1" + (opts.onlyReply ? "&only_reply=1" : "");
    return fetch(q, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) {
          var msg = (d && d.error) || "导出失败";
          try { if (window.__toast) window.__toast("没法导出：" + msg, 3000); } catch (e) {}
          return null;
        }
        render(d);
        return d;
      })
      .catch(function () {
        try { if (window.__toast) window.__toast("后端没响应，导出失败", 2600); } catch (e) {}
        return null;
      });
  }

  /* slot 不传就导当前自动存档；传数字导那一档 */
  WA2.exporter = {
    open: function (slot) {
      opts.slot = (slot === undefined || slot === null || slot === "") ? "auto" : String(slot);
      return load();
    },
    close: close
  };
  window.__openExport = function (slot) { return WA2.exporter.open(slot); };
})();
