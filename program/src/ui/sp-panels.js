/* spPanels.js —— 从 special.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.spPanels；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

    function renderNameView() {
      var view = $("spNameView");
      var inp = $("spName");
      if (inp) inp.style.display = "none";
      if (view) {
        view.style.display = "flex";
        setGlyph(view, nameValue);
      }
    }

    /* 点一下名字：换成输入框并选中 */
    function editName() {
      var view = $("spNameView");
      var inp = $("spName");
      if (!view || !inp) return;
      view.style.display = "none";
      inp.style.display = "block";
      inp.value = nameValue;
      inp.focus();
      try { inp.select(); } catch (e) {}
    }

    function loadName() {
      fetch("/api/special/name", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok && d.name) nameValue = d.name;
          renderNameView();
        })
        .catch(function () { renderNameView(); });
    }

    function saveName() {
      var inp = $("spName");
      /* 输入框藏着的时候，保存的是当前显示的名字（点「保存」不该报「名字不能为空」） */
      var editing = !!(inp && inp.style.display !== "none");
      var name = (editing ? inp.value : nameValue || "").trim();
      if (!name) { flash("名字不能为空"); return; }
      keepInput = true;
      fetch("/api/special/name", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name })
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok) {
            nameValue = d.name;
            renderNameView();                    // 存完变回字模
            flash("已保存");
            if (window.__setCharName) window.__setCharName(d.name);   // 对话框名字立刻跟着变
          } else {
            flash((d && d.error) || "保存失败");
          }
        })
        .catch(function () { flash("保存失败"); });
    }

    /* ---------- 恢复默认设置（sys_03030 按钮） ---------- */
    function resetDefaults() {
      state.ctx = DEF.ctx;
      state.trigger = DEF.trigger;
      state.recent = DEF.recent;
      state.entries = DEF.entries;
      layout();
      dirty = true;
      commitCfg();
    }

    /* ---------- 角色资源：选文件 → 上传落盘 ---------- */
    var FILE_ACCEPT = {
      portrait: "image/*,.png,.jpg,.jpeg,.webp,.bmp,.gif",
      prompt: ".txt,.md,text/plain",
      worldbook: ".txt,.md,.json,text/plain,application/json",
      memory: ".txt,.md,text/plain",
      voice: "audio/*,.wav,.mp3,.ogg,.flac,.m4a"
    };
    var pickers = {};

    function picker(kind) {
      var inp = pickers[kind];
      if (inp) return inp;
      inp = document.createElement("input");
      inp.type = "file";
      inp.accept = FILE_ACCEPT[kind] || "";
      inp.setAttribute("data-no-uitext", "1");
      inp.style.cssText = "position:fixed;left:-9999px;top:0;width:1px;height:1px;opacity:0";
      inp.addEventListener("change", function () {
        var f = inp.files && inp.files[0];
        try { inp.value = ""; } catch (e) {}
        if (f) upload(kind, f);
      });
      document.body.appendChild(inp);
      pickers[kind] = inp;
      return inp;
    }

    function upload(kind, file) {
      var reader = new FileReader();
      reader.onload = function () {
        fetch("/api/special/upload?kind=" + encodeURIComponent(kind) +
              "&name=" + encodeURIComponent(file.name), {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: reader.result
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d && d.ok) {
              flash("已保存");
              refreshStatus();          // 「当前：xxx（已导入）」立刻更新
            } else {
              flash((d && d.error) || "保存失败");
            }
          })
          .catch(function () { flash("保存失败"); });
      };
      reader.onerror = function () { flash("读取失败"); };
      reader.readAsArrayBuffer(file);
    }

    /* ---------- 配置项：点一下框头，箭头转 90° 并滑出面板 ----------
       面板里两个按钮：
         · 导入文件 → 原来的系统选文件窗口，选完上传落盘
         · 查看文件 → 让后端在资源管理器里打开这一类资源的目录，方便自己看/替换 */
    var PANEL_BTNS = [
      { act: "import", img: "assets/ui/text/sp_btn_import.png", title: "导入文件" },
      { act: "open",   img: "assets/ui/text/sp_btn_open.png",   title: "查看文件" }
    ];

    function buildPanel() {
      var panel = document.createElement("div");
      panel.className = "spPanel";
      var row = document.createElement("div");
      row.className = "spPanelBtns";
      PANEL_BTNS.forEach(function (b) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "spPanelBtn";
        btn.dataset.act = b.act;
        btn.title = b.title;
        var img = document.createElement("img");
        img.src = b.img;
        img.alt = b.title;
        btn.appendChild(img);
        row.appendChild(btn);
      });
      panel.appendChild(row);
      /* 「当前用的是哪个文件」——导入目录只是中转站，程序优先读这里，没有就用默认文件 */
      var now = document.createElement("div");
      now.className = "spPanelNow";
      panel.appendChild(now);
      return panel;
    }

    /* ---------- 当前生效的资源（/api/special/status） ----------
       没导入时显示程序默认读的文件，免得以为「查看文件」打开的目录就是全部。 */
    function shortName(s, max) {
      s = s || "";
      return s.length > max ? (s.slice(0, max - 1) + "…") : s;
    }

    function renderResourceStatus(files) {
      var items = document.querySelectorAll("#specialScreen .spItem");
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var kind = item.dataset.item;
        var el = item.querySelector(".spPanelNow");
        if (!el) continue;
        if (kind === "portrait") {
          var sum = window.__spriteSummary ? window.__spriteSummary() : "";
          setGlyph(el, sum ? ("当前：" + sum + "（角色文件夹的 portrait/）") : "当前：还没设置");
          continue;
        }
        var f = files && files[kind];
        if (!f) {
          setGlyph(el, "当前：还没设置");
          continue;
        }
        /* 参考音频是按情绪分组的，显示条数比显示目录名有用 */
        if (f.count) {
          setGlyph(el, "当前：" + f.count + " 条参考音频（按情绪分组）");
          continue;
        }
        var name = f.file || ((f.path || "").split(/[\\/]/).pop() + "/");
        var tag = f.source === "character" ? "（角色文件夹）"
                : (f.source === "imported" ? "（已导入）" : "（默认）");
        setGlyph(el, "当前：" + shortName(name, 22) + tag);
      }
    }

    function refreshStatus() {
      fetch("/api/special/status", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (d) { if (d && d.ok) renderResourceStatus(d.files); })
        .catch(function () { /* 后端没起来就不显示，不影响其它功能 */ });
    }

    /* 同一时间只开一个：开新的先把别的收起来（箭头跟着转回去） */
    function closePanels(except) {
      var open = document.querySelectorAll("#specialScreen .spItem.open");
      for (var i = 0; i < open.length; i++) {
        if (open[i] === except) continue;
        open[i].classList.remove("open");
        var h = open[i].querySelector(".spHead");
        if (h) h.setAttribute("aria-expanded", "false");
      }
    }

    function togglePanel(item, head) {
      var willOpen = !item.classList.contains("open");
      closePanels(item);
      item.classList.toggle("open", willOpen);
      head.setAttribute("aria-expanded", willOpen ? "true" : "false");
    }

    /* 「查看文件」：后端会打开这一类资源**实际被读取**的位置
       （导入过就是导入的那份，没导入就是程序默认文件） */
    function openFolder(kind) {
      fetch("/api/special/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: kind })
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || !d.ok) { flash((d && d.error) || "打不开文件夹"); return; }
          if (d.source === "empty") flash("还没有默认文件，先导入一份");
        })
        .catch(function () { flash("打不开文件夹"); });
    }

    function bindFrames() {
      var items = document.querySelectorAll("#specialScreen .spItem");
      for (var i = 0; i < items.length; i++) {
        (function (item) {
          var head = item.querySelector(".spHead");
          if (!head) return;
          var kind = item.dataset.item;
          if (!item.querySelector(".spPanel")) item.appendChild(buildPanel());

          head.addEventListener("pointerdown", function (e) {
            e.preventDefault();
            head.classList.add("down");
          });
          ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) {
            head.addEventListener(n, function () { head.classList.remove("down"); });
          });
          head.addEventListener("click", function () {
            head.classList.remove("down");
            togglePanel(item, head);
          });
          head.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              togglePanel(item, head);
            }
          });

          var btns = item.querySelectorAll(".spPanelBtn");
          for (var j = 0; j < btns.length; j++) {
            (function (btn) {
              btn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (btn.dataset.act === "import") {
                  item.classList.remove("open");            // 选完文件就收起来
                  head.setAttribute("aria-expanded", "false");
                  picker(kind).click();
                } else if (btn.dataset.act === "open") {
                  openFolder(kind);
                }
              });
            })(btns[j]);
          }
        })(items[i]);
      }
    }

    /* ---------- 打开 / 关闭（开关状态在 special.js 的 window.__spBound） ---------- */

    /* 调试/探针：读当前每轮费用估算 */
  var _exp = {};
  var _names = ["bindFrames", "buildPanel", "closePanels", "editName", "loadName", "openFolder", "picker", "refreshStatus", "renderNameView", "renderResourceStatus", "resetDefaults", "saveName", "shortName", "togglePanel", "upload"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.spPanels = _exp;
  WA2.register("spPanels", _exp);
  /* __export_all__ */
  ["bindFrames", "buildPanel", "closePanels", "editName", "loadName", "openFolder", "picker", "refreshStatus", "renderNameView", "renderResourceStatus", "resetDefaults", "saveName", "shortName", "togglePanel", "upload", "FILE_ACCEPT", "PANEL_BTNS", "WA2", "_exp", "_names", "btn", "btns", "editing", "el", "f", "h", "head", "img", "inp", "item", "items", "kind", "name", "now", "open", "panel", "pickers", "reader", "row", "sum", "tag", "view", "willOpen"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
