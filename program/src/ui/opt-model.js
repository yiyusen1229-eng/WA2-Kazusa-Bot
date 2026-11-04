/* optModel.js —— 从 opt.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.optModel；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

    function txtUrl(t) {
      return "/api/text?text=" + encodeURIComponent(t) + "&plain=1&v=" + TEXT_VER + "&max_width=4000";
    }

    function modelApi(cb, body) {
      var xhr = new XMLHttpRequest();
      xhr.open(body ? "POST" : "GET", "/api/modelcfg", true);
      if (body) xhr.setRequestHeader("Content-Type", "application/json");
      xhr.onload = function () {
        var d = null;
        try { d = JSON.parse(xhr.responseText); } catch (err) {}
        cb(d);
      };
      xhr.onerror = function () { cb(null); };
      xhr.send(body ? JSON.stringify(body) : null);
    }

    /* 按钮标签优先用「预先烤好的字模」（assets/ui/text/*.png），
       没有对应图片时才退回 /api/text 实时渲染。
       好处：点击切换状态时图片已存在，不会出现一瞬间的空字。 */
    var BAKED = {
      "切换模型": "mgr_switch",
      "连接": "mgr_connect",
      "已连接": "mgr_ok",
      "连接失败": "mgr_fail"
    };

    function setConnLabel(btn, text) {
      var old = btn.querySelector("img");
      if (old) old.remove();
      if (!text) return;
      var im = new Image();
      var key = BAKED[text];
      im.src = key ? ("assets/ui/text/" + key + ".png") : txtUrl(text);
      btn.appendChild(im);
    }

    var modelBound = false;
    function bindModelFields() {
      if (modelBound) return;
      modelBound = true;

      var box = byId("optContent3");
      if (!box) return;

      // 显示一个值：优先字模图；若渲染成多行则退回单行文本
      function showValue(wrap, text) {
        var img = wrap.querySelector(".o3val");
        var sp = wrap.querySelector(".o3plain");
        if (!img) {
          img = document.createElement("img");
          img.className = "o3val";
          wrap.insertBefore(img, sp || null);
        }
        if (!sp) {
          sp = document.createElement("span");
          sp.className = "o3plain";
          sp.setAttribute("data-no-uitext", "1");
          wrap.appendChild(sp);
        }
        img.classList.remove("show");
        sp.classList.remove("show");
        img.removeAttribute("src");
        if (!text) { sp.textContent = ""; return; }

        img.onload = function () {
          var ratio = (img.naturalWidth > 0)
            ? img.naturalHeight / img.naturalWidth : 1;
          if (ratio > 0.30) {           // 高/宽偏大 → 图是多行
            img.classList.remove("show");
            sp.textContent = text;
            sp.classList.add("show");
          } else {
            img.classList.add("show");
            sp.textContent = "";
            sp.classList.remove("show");
          }
        };
        img.onerror = function () {
          img.classList.remove("show");
          sp.textContent = text;
          sp.classList.add("show");
        };
        img.src = txtUrl(text);
      }

      // ---------- 字段：提交时把 input 移出 DOM ----------
      function maskKey(v) {
        if (!v) return "";
        return new Array(Math.min(v.length, 24) + 1).join("•");
      }

      function fieldOf(k) {
        return box.querySelector('.o3field[data-k="' + k + '"]');
      }

      function commitField(wrap) {
        var inp = wrap._inp || wrap.querySelector(".o3input");
        if (!inp) return;
        wrap._inp = inp;
        var v = inp.value;
        var isKey = (inp.dataset.k || "").indexOf(".key") >= 0;
        var show = isKey ? maskKey(v) : v;
        var img = wrap.querySelector(".o3val");

        if (!v) {
          wrap.classList.remove("committed");
          if (!inp.parentNode) wrap.appendChild(inp);
          var sp0 = wrap.querySelector(".o3plain");
          if (sp0) { sp0.textContent = ""; sp0.classList.remove("show"); }
          var im0 = wrap.querySelector(".o3val");
          if (im0) { im0.classList.remove("show"); im0.removeAttribute("src"); }
          return;
        }
        wrap.classList.add("committed");
        // 把 input 从 DOM 拿掉，再用单行文本显示
        if (inp.parentNode) inp.parentNode.removeChild(inp);
        showValue(wrap, show);
      }

      function beginEdit(wrap) {
        var inp = wrap._inp;
        if (!inp) return;
        wrap.classList.remove("committed");
        var sp = wrap.querySelector(".o3plain");
        if (sp) sp.textContent = "";
        if (!inp.parentNode) wrap.appendChild(inp);
        inp.style.display = "";
        setTimeout(function () { inp.focus(); }, 0);
      }

      Array.prototype.forEach.call(box.querySelectorAll(".o3field"), function (wrap) {
        var inp = wrap.querySelector(".o3input");
        if (!inp) return;
        wrap._inp = inp;
        wrap.dataset.k = inp.dataset.k || "";

        inp.addEventListener("focus", function () { wrap.classList.remove("committed"); });
        inp.addEventListener("blur", function () { commitField(wrap); });
        inp.addEventListener("keydown", function (e) {
          e.stopPropagation();
          if (e.key === "Enter") inp.blur();
        });
        wrap.addEventListener("click", function () {
          if (wrap.classList.contains("committed")) beginEdit(wrap);
        });
      });

      // ---------- 模型名：只显示 ----------
      function setModelName(sec, name) {
        var wrap = fieldOf(sec + ".model");
        if (!wrap) return;
        if (wrap._inp && wrap._inp.parentNode) wrap._inp.parentNode.removeChild(wrap._inp);
        wrap.classList.add("committed");
        showValue(wrap, name || "");
      }

      // 本地端点隐藏密钥行
      function syncKeyRow(sec, endpoint) {
        var wrap = fieldOf(sec + ".key");
        if (!wrap) return;
        var row = wrap.closest(".o3row");
        if (!row) return;
        var ep = (endpoint || "").toLowerCase();
        var local = ep.indexOf("127.0.0.1") >= 0 || ep.indexOf("localhost") >= 0
                    || ep.indexOf("0.0.0.0") >= 0 || ep.indexOf("::1") >= 0;
        row.style.display = local ? "none" : "";
      }

      // 清空某个板块：恢复成刚打开时的空白状态（密钥输入框重新出现）
      function resetSection(sec) {
        MODEL_FIELDS.forEach(function (f) {
          var wrap = fieldOf(sec + "." + f);
          if (!wrap) return;
          var inp = wrap._inp || wrap.querySelector(".o3input");
          if (inp) {
            inp.value = "";
            if (!inp.parentNode) wrap.appendChild(inp);
            inp.style.display = "";
          }
          wrap.classList.remove("committed");
          var sp = wrap.querySelector(".o3plain");
          if (sp) { sp.textContent = ""; sp.classList.remove("show"); }
          var im = wrap.querySelector(".o3val");
          if (im) { im.classList.remove("show"); im.removeAttribute("src"); }
        });
        // 密钥行恢复显示
        var kwrap = fieldOf(sec + ".key");
        if (kwrap) {
          var row = kwrap.closest(".o3row");
          if (row) row.style.display = "";
        }
        // 按钮回到未连接
        var b = btns[sec];
        if (b) { b.classList.remove("on"); b.classList.remove("fail"); setConnLabel(b, "连接"); }
        // 后端也清空，下次打开是空白
        modelApi(function () {}, { section: sec, endpoint: "", key: "", model: "", probe: false });
      }

      // ---------- 连接按钮 ----------
      var btns = {};
      MODEL_SECTIONS.forEach(function (sec, i) {
        var b = document.createElement("button");
        b.className = "o3conn";
        b.dataset.sec = sec;
        setConnLabel(b, "连接");
        var secEl = box.querySelector(".o3sec" + (i + 1));
        if (secEl) secEl.appendChild(b);
        btns[sec] = b;

        var sw = document.createElement("button");
        sw.className = "o3switch";
        setConnLabel(sw, "切换模型");
        if (secEl) secEl.appendChild(sw);
        sw.addEventListener("click", function (e) {
          e.stopPropagation();
          if (b.classList.contains("on")) {
            // 已连接：先断开，再重置
            modelApi(function () { resetSection(sec); }, { section: sec, disconnect: true });
          } else {
            resetSection(sec);
          }
        });

        b.addEventListener("click", function (e) {
          e.stopPropagation();

          if (b.classList.contains("on")) {
            modelApi(function (d) {
              b.classList.remove("on");
              b.classList.remove("fail");
              setConnLabel(b, "连接");
              if (d && d.cfg && d.cfg[sec]) syncKeyRow(sec, d.cfg[sec].endpoint);
            }, { section: sec, disconnect: true });
            return;
          }

          var payload = { section: sec, probe: true };
          MODEL_FIELDS.forEach(function (f) {
            var w = fieldOf(sec + "." + f);
            var inp = w ? (w._inp || w.querySelector(".o3input")) : null;
            payload[f] = inp ? inp.value.trim() : "";
          });

          // 端点是空的：明确提示，别让它默默失败
          if (!payload.endpoint) {
            setConnLabel(b, "请填端点");
            setTimeout(function () { setConnLabel(b, "连接"); }, 1800);
            var w0 = fieldOf(sec + ".endpoint");
            if (w0) {
              w0.classList.remove("committed");
              var i0 = w0._inp || w0.querySelector(".o3input");
              if (i0) {
                if (!i0.parentNode) w0.appendChild(i0);
                i0.style.display = "";
                i0.focus();
              }
            }
            return;
          }

          setConnLabel(b, "连接中");
          b.disabled = true;
          modelApi(function (d) {
            b.disabled = false;
            if (d && d.ok) {
              b.classList.add("on");
              b.classList.remove("fail");
              setConnLabel(b, "已连接");
              var got = d.cfg && d.cfg[sec];
              if (got) {
                setModelName(sec, got.model);
                syncKeyRow(sec, got.endpoint);
              }
            } else {
              b.classList.remove("on");
              b.classList.add("fail");
              setConnLabel(b, "连接失败");
              setTimeout(function () {
                b.classList.remove("fail");
                setConnLabel(b, "连接");
              }, 2000);
            }
          }, payload);
        });
      });

      // ---------- 打开时回填 ----------
      modelApi(function (d) {
        if (!d) return;
        MODEL_SECTIONS.forEach(function (sec) {
          var got = d[sec];
          if (!got) return;
          MODEL_FIELDS.forEach(function (f) {
            if (f === "model") return;
            var wrap = fieldOf(sec + "." + f);
            if (!wrap) return;
            var inp = wrap._inp || wrap.querySelector(".o3input");
            if (!inp) return;
            wrap._inp = inp;
            inp.value = got[f] || "";
            commitField(wrap);
          });
          setModelName(sec, got.model);
          syncKeyRow(sec, got.endpoint);
          var b = btns[sec];
          if (b) {
            if (got.connected) {
              b.classList.add("on");
              setConnLabel(b, "已连接");
            } else {
              setConnLabel(b, "连接");
            }
          }
        });
      });
    }

    // ---------- 右下角 EXIT：三态 ----------
    var exitBound = false;
  var _exp = {};
  var _names = ["beginEdit", "bindModelFields", "commitField", "fieldOf", "maskKey", "modelApi", "resetSection", "setConnLabel", "setModelName", "showValue", "syncKeyRow", "txtUrl"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.optModel = _exp;
  WA2.register("optModel", _exp);
  /* __export_all__ */
  ["beginEdit", "bindModelFields", "commitField", "fieldOf", "maskKey", "modelApi", "resetSection", "setConnLabel", "setModelName", "showValue", "syncKeyRow", "txtUrl", "BAKED", "WA2", "_exp", "_names", "b", "box", "btns", "d", "ep", "exitBound", "got", "i0", "im", "im0", "img", "inp", "isKey", "key", "kwrap", "local", "modelBound", "old", "payload", "ratio", "row", "secEl", "show", "sp", "sp0", "sw", "v", "w", "w0", "wrap", "xhr"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
