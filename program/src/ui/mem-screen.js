/* mem-screen.js —— 记忆书界面（查看 + 删除）
 *
 * 数据：GET  /api/memory            → { standing:{file,chars,text}, entries:[{i,text,label,...}], hint }
 * 删除：POST /api/memory/delete     → { index }
 *
 * 入口：标题栏「系统 → 记忆书」（menubar.js 调 window.__openMemory）。
 *
 * 文字走原生 DOM（和回想一样），不用字模：条目是动态长句，字模换行会被压扁。
 * 删除做成两段式（点一次变「确认？」2.6 秒，再点才删），不弹确认框。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = function (id) { return document.getElementById(id); };

  var armed = null;        // 正在等第二次确认的那一条
  var armTimer = null;
  var busy = false;

  function el(tag, cls, text) {
    var d = document.createElement(tag);
    /* 整屏走原生 DOM：不让 uitext 把文字换成字模图（长句换行会被压扁） */
    d.dataset.noUitext = "1";
    if (cls) d.className = cls;
    if (text != null) d.textContent = text;
    return d;
  }

  function clearArm() {
    if (armTimer) { clearTimeout(armTimer); armTimer = null; }
    armed = null;
    var list = $("memList");
    if (!list) return;
    Array.prototype.forEach.call(list.querySelectorAll(".memDel.arm"), function (b) {
      b.classList.remove("arm");
      b.textContent = "删除";
    });
  }

  function setHint(text) {
    var h = $("memHint");
    if (h) h.textContent = text || "";
  }

  function paint(d) {
    var list = $("memList");
    var stand = $("memStanding");
    if (!list || !stand) return;
    list.innerHTML = "";
    stand.innerHTML = "";
    setHint("");

    /* 常驻记忆书：角色设定，只读（#3：两段化之后，下半是自动刷新的关系摘要） */
    var st = (d && d.standing) || {};
    var lab = "常驻记忆书（角色设定，只读）" + (st.chars ? " · " + st.chars + " 字" : "");
    if (st.two_part && st.updated_at) {
      lab += " · 关系摘要更新于 " + st.updated_at;
    }
    stand.appendChild(el("span", "lbl", lab));
    if (st.text) {
      stand.appendChild(el("div", "", st.text));
    } else {
      stand.appendChild(el("div", "memEmpty", "还没有常驻记忆书，可以在「特别模式 → 记忆书」导入。"));
    }
    if (st.hint) stand.appendChild(el("div", "memEmpty", st.hint));

    /* 自动摘要条目：可删 */
    var entries = (d && d.entries) || [];
    if (!entries.length) {
      list.appendChild(el("div", "memEmpty", "还没有自动摘要条目。"));
    } else {
      entries.forEach(function (e) {
        var row = el("div", "memRow");
        row.appendChild(el("span", "memKind", e.label || "其他"));
        var t = el("div", "memText", e.text || "");
        t.dataset.noUitext = "1";
        row.appendChild(t);
        var btn = el("button", "memDel", "删除");
        btn.type = "button";
        btn.dataset.noUitext = "1";
        btn.addEventListener("click", function () { onDelete(e, btn); });
        row.appendChild(btn);
        list.appendChild(row);
      });
    }

    if (d && d.hint) {
      setHint(d.hint);
    } else if (entries.length) {
      setHint("共 " + entries.length + " 条" +
        (d.covered ? "，覆盖到第 " + d.covered + " 句" : "") +
        "。删掉的条目只影响这一轮注入，存档里的快照不动。");
    }
  }

  function onDelete(entry, btn) {
    if (busy) return;
    if (armed !== entry.i) {          // 第一次点：进入确认态
      clearArm();
      armed = entry.i;
      btn.classList.add("arm");
      btn.textContent = "确认？";
      armTimer = setTimeout(clearArm, 2600);
      return;
    }
    clearArm();
    busy = true;
    fetch("/api/memory/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: entry.i })
    }).then(function (r) { return r.json(); })
      .then(function (res) {
        busy = false;
        if (res && res.ok) load();
        else setHint((res && res.error) || "删除失败");
      })
      .catch(function () { busy = false; setHint("删除失败（后端没响应）"); });
  }

  function load() {
    return fetch("/api/memory", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) { paint(d); })
      .catch(function () { paint({ ok: false }); });
  }

  function open() {
    var s = window.__showUIScreen ? window.__showUIScreen("memScreen") : $("memScreen");
    if (!s) return;
    clearArm();
    load();
  }

  window.__openMemory = open;

  var _exp = { open: open, load: load, paint: paint };
  WA2.memoryScreen = _exp;
  WA2.register("memoryScreen", _exp);
})();
