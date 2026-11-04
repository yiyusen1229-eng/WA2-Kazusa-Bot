/* sp-pack.js —— 角色包导出 / 导入（特别模式 → 配置角色 → 导出 / 导入）
 *
 * 导出：先选角色（复用角色切换面板，export 模式，点了不切换），再选目录 → 后端打包 zip
 * 导入：后端弹系统选文件窗口（.zip）→ 校验 → 解成 characters/ 下的新角色（不自动切换）
 *
 * 两个按钮的底板就是对话界面发送按钮的三态图（.spRoleBtn → btn_3state.png），
 * 标签是动态文字，由 uitext.js 转成字模，和界面其它文字同一套。
 *
 * 打包 / 解包都在后端做，前端只等结果；窗口开着的时候 fetch 会一直挂着，
 * 取消时后端返回 {ok:false, cancelled:true}，这里按「已取消」提示。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = function (id) { return document.getElementById(id); };

  var busy = false;

  function flash(msg) {
    if (typeof window.flash === "function") window.flash(msg);
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  function setBusy(on) {
    busy = on;
    ["spExport", "spImport"].forEach(function (id) {
      var b = $(id);
      if (!b) return;
      b.disabled = !!on;
      b.style.opacity = on ? "0.55" : "";
    });
  }

  /* ---------- 导出：选角色 → 选目录 → 打包 ---------- */
  function pickCharacterForExport() {
    if (busy) return;
    var spChar = WA2.spChar || {};
    if (typeof spChar.openCharPicker !== "function") { flash("角色面板没加载"); return; }
    spChar.openCharPicker({ mode: "export", onPick: doExport });
  }

  function doExport(c) {
    if (busy || !c || !c.id) return;
    setBusy(true);
    flash("正在打包 " + (c.name || c.id) + " …");
    post("/api/charpack/export", { id: c.id })
      .then(function (d) {
        setBusy(false);
        if (d && d.ok) flash("已导出 " + (d.file || ""));
        else if (d && d.cancelled) flash("已取消导出");
        else flash((d && d.error) || "导出失败");
      })
      .catch(function () { setBusy(false); flash("导出失败"); });
  }

  /* ---------- 导入：选 zip → 解成新角色 ---------- */
  function doImport() {
    if (busy) return;
    setBusy(true);
    flash("正在导入 …");
    post("/api/charpack/import", {})
      .then(function (d) {
        setBusy(false);
        if (d && d.ok) flash("已导入 " + (d.name || d.id || ""));
        else if (d && d.cancelled) flash("已取消导入");
        else flash((d && d.error) || "导入失败");
      })
      .catch(function () { setBusy(false); flash("导入失败"); });
  }

  function bind() {
    var ex = $("spExport");
    var im = $("spImport");
    if (ex) ex.addEventListener("click", function (e) {
      e.stopPropagation();
      pickCharacterForExport();
    });
    if (im) im.addEventListener("click", function (e) {
      e.stopPropagation();
      doImport();
    });
  }

  bind();                                  // 脚本在 body 末尾，元素已经在了

  var _exp = { bind: bind, doExport: doExport, doImport: doImport, pickCharacterForExport: pickCharacterForExport };
  WA2.spPack = _exp;
  WA2.register("spPack", _exp);
})();
