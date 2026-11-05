/**
 * 数据清理入口（#17）—— 看得见体积，才有勇气删。
 *
 * 入口：菜单「环境设置 → 数据清理」，或 window.__openCleanup()。
 *
 * 三件事，全都走后端（`api_cleanup.py`），界面只负责显示和勾选：
 *   1. 清缓存：运行时缓存 / 字模 / 语音 / 旧日志 / 性能采样 / 崩溃现场 / 素材报告 / 临时目录
 *      —— 只删程序能自己再生成的东西；存档和角色内容一个都不动。
 *   2. 导出数据：配置 + 角色内容（人设 / 世界书 / 记忆书 / 演出配置），默认脱敏、不带对话。
 *   3. 删角色：二次确认（先 confirm，再手打角色名），后端再验一遍，且是「挪到
 *      characters/_deleted/」不是真删；当前在用的角色不让删。
 *
 * 后端接口：
 *   GET  /api/cleanup                  概览
 *   POST /api/cleanup/cache            {items:[...]}
 *   POST /api/cleanup/export           {turns:0}
 *   POST /api/cleanup/character        {id, confirm}
 */
(function () {
  "use strict";
  var WA2 = window.WA2 = window.WA2 || {};

  var box = null, mask = null, last = null, busy = false, picked = {};

  var S_BOX = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9500;" +
    "width:min(760px,92vw);max-height:84vh;overflow:auto;background:#0d1620;color:#dfe9f2;" +
    "border:1px solid #3b4d61;border-radius:6px;padding:18px 20px;box-shadow:0 0 24px rgba(0,0,0,.6);" +
    "font-size:14px;line-height:1.6;font-family:inherit;";
  var S_ROW = "margin:0 0 8px;padding:8px 10px;border:1px solid #24333f;border-radius:4px;" +
    "display:flex;align-items:center;gap:10px;";
  var S_TITLE = "font-size:16px;color:#fff;margin:0 0 4px;letter-spacing:.5px;";
  var S_HINT = "color:#9fb3c6;font-size:13px;margin:2px 0 0;";
  var S_BTN = "cursor:pointer;background:rgba(255,255,255,.08);color:#dfe9f2;" +
    "border:1px solid #3b4d61;border-radius:4px;padding:6px 12px;margin-left:8px;font-size:13px;";
  var S_DANGER = "cursor:pointer;background:rgba(255,120,100,.16);color:#ffb4a2;" +
    "border:1px solid #6e3b34;border-radius:4px;padding:4px 10px;font-size:12px;";
  var S_OK = "color:#8fd694;";

  function el(tag, style, text) {
    var e = document.createElement(tag);
    if (style) e.setAttribute("style", style);
    if (text != null) e.textContent = text;
    return e;
  }

  function mb(n) {
    n = Number(n) || 0;
    if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
    if (n >= 1024) return (n / 1024).toFixed(0) + " KB";
    return n + " B";
  }

  function toast(msg) {
    try { if (window.__toast) return window.__toast(msg, 2200); } catch (e) {}
    try { console.log("[cleanup]", msg); } catch (e) {}
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  function close() {
    if (mask) { mask.remove(); mask = null; }
    if (box) { box.remove(); box = null; }
  }

  function need(reload) {
    if (busy) return;
    busy = true;
    fetch("/api/cleanup", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) { busy = false; last = d; render(d); })
      .catch(function (e) { busy = false; close(); toast("读体积失败：" + String(e).slice(0, 60)); });
  }

  /* ---------------- 渲染 ---------------- */
  function render(d) {
    close();
    box = el("div", S_BOX);
    mask = el("div", "position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9400;");
    mask.addEventListener("click", close);

    var head = el("div", "display:flex;justify-content:space-between;align-items:baseline;");
    head.appendChild(el("div", S_TITLE, "数据清理"));
    head.appendChild(el("div", S_HINT, "总占用 " + mb(d.total_bytes) +
      "（缓存 " + mb(d.cache_bytes) + " · 角色 " + mb(d.characters_bytes) + "）"));
    box.appendChild(head);

    box.appendChild(el("div", S_HINT,
      "只清程序能自己再生成的东西：存档、人设、世界书、记忆书、素材一律不碰。"));

    /* --- 清理项 --- */
    box.appendChild(el("div", "margin:12px 0 6px;color:#cfe0ee;", "① 清缓存"));
    (d.items || []).forEach(function (it) {
      var row = el("div", S_ROW);
      var cb = el("input");
      cb.type = "checkbox";
      cb.checked = !!picked[it.key] && it.bytes > 0;
      cb.disabled = it.bytes <= 0;
      cb.addEventListener("change", function () { picked[it.key] = cb.checked; });
      row.appendChild(cb);
      var lab = el("div", "flex:1;");
      lab.appendChild(el("div", "", it.label + "  ·  " + mb(it.bytes) +
        (it.files ? "  ·  " + it.files + " 个文件" : "")));
      lab.appendChild(el("div", S_HINT, it.note || ""));
      if (it.path) {
        var p = el("div", "color:#6f8496;font-size:12px;word-break:break-all;", it.path);
        p.dataset.noUitext = "1";
        lab.appendChild(p);
      }
      row.appendChild(lab);
      box.appendChild(row);
    });

    /* --- 角色 --- */
    box.appendChild(el("div", "margin:14px 0 6px;color:#cfe0ee;", "② 角色数据"));
    (d.characters || []).forEach(function (c) {
      var row = el("div", S_ROW);
      var lab = el("div", "flex:1;");
      lab.appendChild(el("div", "", c.name + "（" + c.id + "）  ·  " + mb(c.bytes) +
        "  ·  " + c.files + " 个文件" + (c.sessions_bytes ? "  ·  存档 " + mb(c.sessions_bytes) : "")));
      lab.appendChild(el("div", S_HINT, c.active
        ? "当前正在用的角色，不能删（先切到别的角色）"
        : "删除 = 挪到 characters/_deleted/，随时能搬回来"));
      row.appendChild(lab);
      var del = el("button", S_DANGER, c.active ? "在用" : "删除");
      del.type = "button";
      del.disabled = !!c.active;
      if (!c.active) del.addEventListener("click", function () { onDelete(c, del); });
      row.appendChild(del);
      box.appendChild(row);
    });

    /* --- 底部 --- */
    var foot = el("div", "text-align:right;margin-top:14px;");
    var bClean = el("button", S_BTN, "清理选中的");
    bClean.type = "button";
    bClean.addEventListener("click", onClean);
    var bExp = el("button", S_BTN, "导出数据（不含对话）");
    bExp.type = "button";
    bExp.addEventListener("click", function () { onExport(0); });
    var bExpD = el("button", S_BTN, "导出（含最近 20 轮）");
    bExpD.type = "button";
    bExpD.addEventListener("click", function () {
      if (!confirm("这个 zip 会包含存档里的对话原文。\n" +
                   "导出后请自己保管；发给别人前建议用「不含对话」那份。\n\n继续吗？")) return;
      onExport(20);
    });
    var bClose = el("button", S_BTN, "关闭");
    bClose.type = "button";
    bClose.addEventListener("click", close);
    foot.appendChild(bClean);
    foot.appendChild(bExp);
    foot.appendChild(bExpD);
    foot.appendChild(bClose);
    box.appendChild(foot);

    document.body.appendChild(mask);
    document.body.appendChild(box);
  }

  /* ---------------- 动作 ---------------- */
  function onClean() {
    var items = Object.keys(picked).filter(function (k) { return picked[k]; });
    if (!items.length) { toast("先勾要清的东西"); return; }
    if (!confirm("清理选中的 " + items.length + " 项？\n\n" +
                 "只删能重新生成的缓存 / 日志，存档和角色内容不动。")) return;
    busy = true;
    post("/api/cleanup/cache", { items: items }).then(function (d) {
      busy = false;
      if (!d || !d.ok) { toast("清理失败：" + ((d && d.error) || "?")); return; }
      picked = {};
      toast("已清理 " + d.freed_files + " 个文件，释放 " + mb(d.freed_bytes));
      need(1);
    }).catch(function (e) { busy = false; toast("清理失败：" + String(e).slice(0, 60)); });
  }

  function onExport(turns) {
    if (busy) return;
    busy = true;
    toast("正在导出…", 1200);
    post("/api/cleanup/export", { turns: turns || 0 }).then(function (d) {
      busy = false;
      if (!d || !d.ok) { toast("导出失败：" + ((d && d.error) || "?")); return; }
      alert("导出完成：\n" + d.path + "\n\n" + mb(d.bytes) + " · " + d.files + " 个文件\n" +
            (d.include_dialogue ? "包含对话存档" : "不含对话存档") +
            "\n（文本已脱敏：密钥 / 用户名 / 绝对路径）");
    }).catch(function (e) { busy = false; toast("导出失败：" + String(e).slice(0, 60)); });
  }

  function onDelete(c, btn) {
    if (busy) return;
    if (!confirm("删除角色「" + c.name + "」？\n\n" +
                 "· 会挪到 characters/_deleted/（不是真删，随时能搬回来）\n" +
                 "· 它的存档、立绘、语音、记忆书都跟着一起挪走\n" +
                 "· 同时清掉这个角色的缓存")) return;
    var typed = prompt("确认删除请**原样输入角色名**：\n" + c.name, "");
    if (typed === null) return;
    busy = true;
    btn.disabled = true;
    post("/api/cleanup/character", { id: c.id, confirm: typed }).then(function (d) {
      busy = false;
      btn.disabled = false;
      if (!d || !d.ok) { toast("没删：" + ((d && d.error) || "?")); return; }
      toast("已挪到 _deleted（" + mb(d.bytes) + "）");
      need(1);
    }).catch(function (e) { busy = false; btn.disabled = false; toast("没删：" + String(e).slice(0, 60)); });
  }

  WA2.cleanup = { open: need, close: close, data: function () { return last; } };
  window.__openCleanup = function () { need(false); };
})();
