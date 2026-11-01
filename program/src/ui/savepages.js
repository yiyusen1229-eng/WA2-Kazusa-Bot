/* 存档槽分页：10 页 × 10 槽 = 100 个槽位
 *
 * 布局只有一套：10 个 .saveSlot 元素位置固定，翻页只改每个槽绑定的
 * 编号（data-slot）和状态（empty / filled），不新建不移动任何元素。
 *
 * 编号沿用原版：第 N 页 = (N-1)*10+1 .. N*10
 *   第 1 页 1~10，第 7 页 61~70（和游戏截图一致）
 */
(function () {
  var PER = 10;      // 每页槽数
  var PAGES = 10;    // 总页数

  var state = {};    // "61" -> {slot, saved_at, count}

  function slotEls() {
    return Array.prototype.slice.call(
      document.querySelectorAll("#saveScreen .saveSlot"));
  }

  /* 编号字形：0~9 取自 sys_00019（见 tools/make_slot_digits.py）
     1~9 补零成 01~09；100 是三位 */
  function numHTML(idx) {
    var s = idx < 10 ? "0" + idx : String(idx);
    var h = "";
    for (var i = 0; i < s.length; i++) {
      h += '<img src="assets/ui/save/d' + s.charAt(i) + '.png" alt="">';
    }
    return h;
  }

  /* 三位数（100）右对齐：末两位留在两位数的位置，多出来的位往左排
     ——原版第 10 页 100 的 "00" 与 99 的两位数字同列，"1" 在前面一格 */
  var NUM_CELL = 7.786;    // 单格宽，和 save-screen.css 里 .num img 的宽度一致

  /* 时间戳："2026-11-01 03:12:16" → "2026 11/01 03:12"，数字取自 sys_01013 */
  function dateHTML(s) {
    if (!s) return "";
    var m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    var str = m ? (m[1] + " " + m[2] + "/" + m[3] + " " + m[4] + ":" + m[5])
                : String(s).slice(0, 16);
    var h = "";
    for (var i = 0; i < str.length; i++) {
      var c = str.charAt(i);
      if (c === " ") { h += '<i class="sp"></i>'; continue; }
      var f = c === "/" ? "dt_slash" : (c === ":" ? "dt_colon" : ("dt" + c));
      h += '<img src="assets/ui/save/' + f + '.png" alt="">';
    }
    return h;
  }

  /* 槽位里的缩略图 / 时间戳 / 首句（有数据才有） */
  function fillContent(el, d) {
    var parts = ["thumb", "date", "sent"];
    if (!d) {
      parts.forEach(function (k) {
        var n = el.querySelector("." + k);
        if (n) n.remove();
      });
      return;
    }
    /* 缩略图：走 /api/session/thumb（列表里只带"有没有"，图本体由浏览器缓存）；
       老存档没有缩略图就用场景背景兜底 */
    var th = el.querySelector(".thumb");
    if (!th) { th = document.createElement("div"); th.className = "thumb"; el.appendChild(th); }
    var src = d.thumb
      ? ("/api/session/thumb?slot=" + encodeURIComponent(String(d.slot || "")) +
         "&v=" + encodeURIComponent(d.saved_at || ""))
      : (window.__bgThumb ? window.__bgThumb(d.bg || "") : "");
    if (src && th.getAttribute("data-src") !== src) {
      th.setAttribute("data-src", src);
      th.innerHTML = '<img src="' + src + '" alt="">';
    }
    /* 时间戳 */
    var dt = el.querySelector(".date");
    if (!dt) { dt = document.createElement("div"); dt.className = "date"; el.appendChild(dt); }
    var dh = dateHTML(d.saved_at);
    if (dt.getAttribute("data-k") !== dh) {
      dt.setAttribute("data-k", dh);
      dt.innerHTML = dh;
    }
    /* 首句（最后一条和纱的话，中文），太长截断；显示成游戏里的「…」样式 */
    var se = el.querySelector(".sent");
    if (!se) { se = document.createElement("div"); se.className = "sent"; el.appendChild(se); }
    var raw = (d.preview || "").replace(/\s+/g, " ").trim()
      .replace(/^[「『]/, "").replace(/[」』]$/, "");
    var txt = raw ? ("「" + (raw.length > 18 ? raw.slice(0, 18) + "…" : raw)) : "";
    if (se.getAttribute("data-t") !== txt) {
      se.setAttribute("data-t", txt);
      se.innerHTML = txt
        ? '<img src="/api/text?text=' + encodeURIComponent(txt) + '&plain=1" alt="">'
        : "";
    }
  }

  function paint(page) {
    var els = slotEls();
    if (!els.length) return;
    els.forEach(function (el, k) {
      var idx = (page - 1) * PER + k + 1;
      el.dataset.slot = String(idx);
      var d = state[String(idx)];
      el.classList.toggle("filled", !!d);
      el.classList.toggle("empty", !d);
      /* 编号：每个槽里相对位置相同，只换数字 */
      var n = el.querySelector(".num");
      if (!n) {
        n = document.createElement("span");
        n.className = "num";
        el.appendChild(n);
      }
      var html = numHTML(idx);
      if (n.innerHTML !== html) n.innerHTML = html;
      var shift = (html.match(/<img/g) || []).length - 2;
      n.style.transform = shift > 0 ? "translateX(-" + (shift * NUM_CELL) + "px)" : "";
      /* 缩略图 / 时间戳 / 首句 */
      fillContent(el, d);
    });
  }

  function fetchList() {
    return fetch("/api/session/list", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        state = {};
        ((d && d.slots) || []).forEach(function (x) {
          if (x && x.slot !== undefined) state[String(x.slot)] = x;
        });
      })
      .catch(function () { state = {}; });
  }

  /* 翻页 / 打开存档界面时调用：先用旧数据占位，再按服务器结果重画一次 */
  window.__renderSaveSlots = function (page) {
    page = page || window.__savePage || 1;
    page = Math.max(1, Math.min(PAGES, page));
    paint(page);
    return fetchList().then(function () { paint(page); });
  };

  /* 调试用：当前已知的存档列表 */
  window.__saveSlotState = function () { return state; };

  /* ---------- 底栏翻页箭头 ----------
     左箭头上一页、右箭头下一页，10 页循环（第 1 页再往左 → 第 10 页） */
  function go(d) {
    var cur = window.__savePage || 1;
    try { window.playSE && window.playSE("page"); } catch (e) {}
      if (window.__setSavePage) window.__setSavePage(cur + d);
    else window.__renderSaveSlots(((cur - 1 + d) % 10 + 10) % 10 + 1);
  }
  function wirePager() {
    var prev = document.getElementById("pagerPrev");
    var next = document.getElementById("pagerNext");
    if (prev) prev.addEventListener("click", function () { go(-1); });
    if (next) next.addEventListener("click", function () { go(1); });
  }

  /* ---------- 槽位点击 ----------
     存档模式：空槽、已有档都直接写（覆盖不二次确认），写完留在界面
     读档模式：空槽不可点（CSS 里 pointer-events:none），已有档载入后进游戏 —— 下一步做 */
  var busy = false;

  /* 「存档已保存」提示：sys_00110 的框 + /api/text 渲染的字，1.4 秒后自己消失 */
  var toastTimer = null;
  function showToast(msg) {
    var t = document.getElementById("dlgToast");
    if (!t) return;
    t.classList.add("on");
    var txt = document.getElementById("dlgToastTxt");
    if (txt) {
      txt.textContent = msg;
      if (window.__uiTextScan) window.__uiTextScan(txt);
    }
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("on"); }, 1000);
  }

  function saveTo(idx) {
    busy = true;
    var meta = (window.__saveMeta && window.__saveMeta()) || {};
    /* 存档时把当前画面截图放进缩略图 */
    if (window.__grabThumb) {
      try { meta.thumb = window.__grabThumb() || ""; } catch (e) { meta.thumb = ""; }
    }
    var body = {
      slot: String(idx),
      messages: (window.__history || []).slice(-40),
      meta: meta
    };
    fetch("/api/session/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        busy = false;
        if (d && d.ok) {
          showToast("存档已保存");
          /* 重新拉一次列表再重画：preview / 缩略图都由服务器读档文件给出，
             不能只用返回值覆盖本地状态（那样会把 preview、thumb 丢掉） */
          window.__renderSaveSlots(window.__savePage || 1);
        } else {
          console.warn("[save] 失败", d);
        }
      })
      .catch(function (e) { busy = false; console.warn("[save] 失败", e); });
  }

  /* 覆盖确认：点「是」才写，点「否」/外面什么都不做 */
  var pendingIdx = 0;
  function askOverwrite(idx) {
    pendingIdx = idx;
    var d = document.getElementById("dlgConfirm");
    if (!d) return;
    d.classList.add("on");
    if (window.__uiTextScan) {
      window.__uiTextScan(document.getElementById("dlgConfirmT1"));
      window.__uiTextScan(document.getElementById("dlgConfirmT2"));
    }
  }
  function closeConfirm() {
    var d = document.getElementById("dlgConfirm");
    if (d) d.classList.remove("on");
    pendingIdx = 0;
  }
  function wireConfirm() {
    var yes = document.getElementById("dlgYes");
    var no = document.getElementById("dlgNo");
    if (yes) yes.addEventListener("click", function (e) {
      e.stopPropagation();
      var idx = pendingIdx;
      closeConfirm();
      if (idx) saveTo(idx);
    });
    if (no) no.addEventListener("click", function (e) {
      e.stopPropagation();
      closeConfirm();
    });
  }

  /* 读档：载入这条记录，回到游戏，之后的和纱从这句话往下接 */
  function loadFrom(idx) {
    busy = true;
    fetch("/api/session/load?slot=" + idx, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        busy = false;
        if (d && d.ok) {
          if (window.__closeScreens) window.__closeScreens();
          if (window.__loadSession) window.__loadSession(d);
        } else {
          showToast("这个槽位读不出来");
        }
      })
      .catch(function () { busy = false; showToast("读档失败"); });
  }

  function onSlotClick(e) {
    var el = e.target && e.target.closest ? e.target.closest(".saveSlot") : null;
    if (!el || busy) return;
    var idx = parseInt(el.dataset.slot, 10);
    if (!idx) return;
    /* 模式以界面上的类为准（比全局变量稳，避免状态过期） */
    var sc = document.getElementById("saveScreen");
    var isSaveMode = !!(sc && sc.classList.contains("mode-save"));

    if (isSaveMode) {
      /* 规则：当前历史至少两条对话才允许存档 */
      var n = (window.__history || []).length;
      if (n < 2) {
        showToast("对话不足两条，不能存档");
        return;
      }
      if (el.classList.contains("filled")) askOverwrite(idx);
      else saveTo(idx);
    } else {
      if (!el.classList.contains("filled")) {
        showToast("这个槽位没有存档");
        return;
      }
      loadFrom(idx);
    }
  }

  function wireSlots() {
    var sc = document.getElementById("saveScreen");
    if (sc) sc.addEventListener("click", onSlotClick);
    wireConfirm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { wirePager(); wireSlots(); });
  } else { wirePager(); wireSlots(); }
})();
