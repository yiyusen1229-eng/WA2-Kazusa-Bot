/* spChar.js —— 从 special.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.spChar；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

    function afterCharacter(res) {
      nameValue = res.name || nameValue;
      renderNameView();
      if (window.__setCharName && res.name) window.__setCharName(res.name);
      try { if (window.__reloadSprites) window.__reloadSprites(); } catch (e) {}
      try { if (window.__loadOpeningLine) window.__loadOpeningLine(); } catch (e) {}
      refreshStatus();
      loadName();
    }

    function postCharacter(url, body) {
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {})
      }).then(function (r) { return r.json(); });
    }

    var charBusy = false;

    /* 面板标题：切换模式用烤好的「切换角色」图；导出模式换成动态文字 */
    function setPickerTitle(mode) {
      var img = $("spcpTitleImg");
      var txt = $("spcpTitleText");
      var isExport = (mode === "export");
      if (img) img.style.display = isExport ? "none" : "";
      if (txt) {
        txt.style.display = isExport ? "" : "none";
        if (isExport) {
          var s = "选择要导出的角色";
          try { setGlyph(txt, s); } catch (e) { txt.textContent = s; }
        }
      }
    }

    /* opts.mode = "switch"（默认，点了就切过去）| "export"（点了交给 onPick） */
    function openCharPicker(opts) {
      var mode = (opts && opts.mode) || "switch";
      var onPick = (opts && opts.onPick) || null;
      var panel = $("spCharPick");
      var list = $("spcpList");
      if (!panel || !list) return;
      setPickerTitle(mode);
      list.innerHTML = "";
      var loading = document.createElement("div");
      loading.className = "spcpMsg";
      loading.textContent = "读取角色列表…";
      list.appendChild(loading);
      panel.classList.add("show");
      panel.setAttribute("aria-hidden", "false");
      fetch("/api/character/list", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          var chars = (d && d.characters) || [];
          list.innerHTML = "";
          if (!chars.length) {
            var empty = document.createElement("div");
            empty.className = "spcpMsg";
            empty.textContent = "还没有角色";
            list.appendChild(empty);
            return;
          }
          chars.forEach(function (c) {
            var b = document.createElement("button");
            b.type = "button";
            b.className = "spcpItem" + (c.active ? " active" : "");
            var name = document.createElement("span");
            name.className = "spcpName";
            var display = c.name || c.id || "未命名";
            name.textContent = display;
            b.appendChild(name);
            b.addEventListener("click", function () {
              if (mode === "export") {          // 导出：选中即打包，不切换
                closeCharPicker();
                if (onPick) onPick(c);
                return;
              }
              if (c.active) { closeCharPicker(); return; }
              doSwitchCharacter(c.id);
            });
            list.appendChild(b);
            try { setGlyph(name, display); } catch (e) {}
          });
        })
        .catch(function () {
          list.innerHTML = "";
          var err = document.createElement("div");
          err.className = "spcpMsg";
          err.textContent = "读取失败";
          list.appendChild(err);
        });
    }

    function closeCharPicker() {
      var panel = $("spCharPick");
      if (!panel) return;
      panel.classList.remove("show");
      panel.setAttribute("aria-hidden", "true");
    }

    function doSwitchCharacter(id) {
      if (charBusy || !id) return;
      charBusy = true;
      postCharacter("/api/character/switch", { id: id })
        .then(function (d) {
          charBusy = false;
          if (d && d.ok) {
            closeCharPicker();
            afterCharacter(d);
            flash("已切换到 " + (d.name || d.id));
          } else {
            flash((d && d.error) || "切换失败");
          }
        })
        .catch(function () {
          charBusy = false;
          flash("切换失败");
        });
    }

    function switchCharacter() {
      openCharPicker();
    }

    function newCharacter() {
      if (charBusy) return;
      charBusy = true;
      postCharacter("/api/character/new")
        .then(function (d) {
          charBusy = false;
          if (d && d.ok) { afterCharacter(d); flash("已新建 " + (d.name || d.id)); }
          else flash((d && d.error) || "新建失败");
        })
        .catch(function () { charBusy = false; flash("新建失败"); });
    }

    var charsBound = false;
    function bindCharacters() {
      if (charsBound) return;
      charsBound = true;
      var sw = $("spSwitch");
      var nw = $("spNew");
      if (sw) sw.addEventListener("click", function (e) { e.stopPropagation(); switchCharacter(); });
      if (nw) nw.addEventListener("click", function (e) { e.stopPropagation(); newCharacter(); });
      var cancel = $("spcpCancel");
      if (cancel) cancel.addEventListener("click", function (e) { e.stopPropagation(); closeCharPicker(); });
      var pick = $("spCharPick");
      if (pick) pick.addEventListener("click", function (e) {
        if (e.target === pick) closeCharPicker();
      });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && pick && pick.classList.contains("show")) {
          e.preventDefault();
          closeCharPicker();
        }
      });
    }

    function bindSave() {
      var btn = $("spSave");
      var inp = $("spName");
      var view = $("spNameView");
      if (view) view.addEventListener("click", editName);
      if (btn) {
        /* 按住保存键时别让 blur 先把输入框收回去 */
        btn.addEventListener("mousedown", function () { keepInput = true; });
        btn.addEventListener("click", function () { saveName(); });
      }
      if (inp) {
        inp.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); saveName(); }
          else if (e.key === "Escape") { e.preventDefault(); renderNameView(); }
        });
        inp.addEventListener("blur", function () {
          setTimeout(function () {
            if (keepInput) { keepInput = false; return; }
            renderNameView();          // 没保存就还原成字模
          }, 160);
        });
      }
    }

    /* ---------- 角色名：char/name.txt（对话框左上角显示的就是这个） ---------- */
    var nameValue = "角色";
    var keepInput = false;

    /* 平时：字模显示，输入框藏起来 */
  var _exp = {};
  var _names = ["afterCharacter", "bindCharacters", "bindSave", "closeCharPicker", "doSwitchCharacter", "newCharacter", "openCharPicker", "postCharacter", "setPickerTitle", "switchCharacter"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.spChar = _exp;
  WA2.register("spChar", _exp);
  /* __export_all__ */
  ["afterCharacter", "bindCharacters", "bindSave", "closeCharPicker", "doSwitchCharacter", "newCharacter", "openCharPicker", "postCharacter", "switchCharacter", "WA2", "_exp", "_names", "b", "btn", "cancel", "charBusy", "chars", "charsBound", "display", "empty", "err", "inp", "keepInput", "list", "loading", "name", "nameValue", "nw", "panel", "pick", "sw", "view"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
