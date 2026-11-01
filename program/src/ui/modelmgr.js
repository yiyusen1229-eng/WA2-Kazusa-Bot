// 模型管理界面: 复用存档槽 UI, 管理多个模型端点
(function () {
  const $ = (id) => document.getElementById(id);
  const KEY = "app_models_v3";
  const ACTIVE = "app_active_model";

  const DEFAULTS = [
    { name: "和纱 14B v3 (最新)", url: "http://127.0.0.1:11434", type: "auto", model: "kazusa14b-v3", thumb: "" },
    { name: "和纱 14B v2", url: "http://127.0.0.1:11434", type: "auto", model: "kazusa14b-v2", thumb: "" },
    { name: "原版 14B (对照)", url: "http://127.0.0.1:11434", type: "auto", model: "qwen2.5:14b-instruct-q4_K_M", thumb: "" },
    { name: "空闲槽位 4", url: "http://127.0.0.1:11434", type: "auto", model: "", thumb: "" },
    { name: "空闲槽位 5", url: "http://127.0.0.1:11434", type: "auto", model: "", thumb: "" },
    { name: "空闲槽位 6", url: "", type: "auto", model: "", thumb: "" },
  ];

  const PER_PAGE = 6;
  let page = 0;
  let list = load();

  function load() {
    try {
      const s = localStorage.getItem(KEY);
      if (s) return JSON.parse(s);
    } catch (e) {}
    return JSON.parse(JSON.stringify(DEFAULTS));
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {}
  }
  function active() {
    try { return JSON.parse(localStorage.getItem(ACTIVE) || "{}"); } catch (e) { return {}; }
  }
  function setActive(i) {
    const m = list[i];
    try { localStorage.setItem(ACTIVE, JSON.stringify({ index: i, url: m.url, model: m.model, name: m.name })); } catch (e) {}
  }

  function led(ok, text) {
    const d = document.createElement("div");
    d.className = "mLed " + (ok === true ? "on" : ok === false ? "off" : "");
    d.innerHTML = '<i></i><span>' + text + "</span>";
    return d;
  }

  function render() {
    const wrap = $("modelWrap");
    if (!wrap) return;
    wrap.innerHTML = "";
    for (let k = 0; k < PER_PAGE; k++) {
      const idx = page * PER_PAGE + k;
      const m = list[idx] || { name: "", url: "", type: "auto", model: "", thumb: "" };
      const el = document.createElement("div");
      el.className = "slot modelSlot";

      // 预览图(可点击更换)
      const th = document.createElement("div");
      th.className = "mThumb";
      if (m.thumb) th.style.backgroundImage = 'url("' + m.thumb + '")';
      th.title = "点击选择图片";
      th.addEventListener("click", (ev) => {
        ev.stopPropagation();
        pickImage(idx);
      });
      el.appendChild(th);

      // 右侧信息
      const box = document.createElement("div");
      box.className = "mBox";

      const r1 = document.createElement("div");
      r1.className = "mRow";
      const nm = document.createElement("input");
      nm.className = "mName";
      nm.value = m.name || "";
      nm.placeholder = "模型名称";
      nm.addEventListener("click", e => e.stopPropagation());
      nm.addEventListener("change", () => { list[idx].name = nm.value; save(); });
      r1.appendChild(nm);
      const st = led(null, "未检测");
      st.id = "led" + idx;
      r1.appendChild(st);
      box.appendChild(r1);

      const r2 = document.createElement("div");
      r2.className = "mRow";
      const url = document.createElement("input");
      url.className = "mUrl";
      url.value = m.url || "";
      url.placeholder = "http://127.0.0.1:11434";
      url.addEventListener("click", e => e.stopPropagation());
      url.addEventListener("change", () => { list[idx].url = url.value.trim(); save(); });
      r2.appendChild(url);
      const btn = document.createElement("button");
      btn.className = "mBtn";
      btn.textContent = "连接";
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        probe(idx, url.value.trim(), st);
      });
      r2.appendChild(btn);
      box.appendChild(r2);

      const r3 = document.createElement("div");
      r3.className = "mRow mRow3";
      const sel = document.createElement("select");
      sel.className = "mType";
      ["auto", "Ollama", "OpenAI兼容"].forEach((t, i) => {
        const o = document.createElement("option");
        o.value = i === 0 ? "auto" : (i === 1 ? "ollama" : "openai");
        o.textContent = t;
        if ((m.type || "auto") === o.value) o.selected = true;
        sel.appendChild(o);
      });
      sel.addEventListener("click", e => e.stopPropagation());
      sel.addEventListener("change", () => { list[idx].type = sel.value; save(); });
      r3.appendChild(sel);

      const mdl = document.createElement("select");
      mdl.className = "mModel";
      mdl.dataset.idx = idx;
      mdl.addEventListener("click", e => e.stopPropagation());
      mdl.addEventListener("change", () => {
        list[idx].model = mdl.value;
        setActive(idx);
        save();
      });
      const ph = document.createElement("option");
      ph.value = ""; ph.textContent = "（未选择）";
      mdl.appendChild(ph);
      if (m.model) {
        const o = document.createElement("option");
        o.value = m.model; o.textContent = m.model;
        mdl.appendChild(o);
        mdl.value = m.model;
      } else {
        mdl.value = "";
      }
      r3.appendChild(mdl);

      const det = document.createElement("button");
      det.className = "mBtn mDet";
      det.textContent = "详情";
      det.addEventListener("click", (ev) => { ev.stopPropagation(); openDetail(idx); });
      r3.appendChild(det);
      box.appendChild(r3);

      el.appendChild(box);

      el.addEventListener("click", () => openDetail(idx));
      wrap.appendChild(el);
    }
    const lbl = $("modelPageLabel");
    if (lbl) lbl.textContent = "PAGE " + (page + 1);
  }

  function pickImage(idx) {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = "image/*";
    inp.addEventListener("change", () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      const fr = new FileReader();
      fr.onload = () => {
        list[idx].thumb = fr.result;
        save();
        render();
      };
      fr.readAsDataURL(f);
    });
    inp.click();
  }

  async function probe(idx, url, ledEl) {
    if (!url) { ledEl.replaceWith(led(false, "未填写地址")); return; }
    ledEl.replaceWith(led(null, "检测中…"));
    try {
      const r = await fetch("/api/model/probe?url=" + encodeURIComponent(url), { cache: "no-store" });
      const d = await r.json();
      const st = led(!!d.ok, d.ok ? ("已连接 · " + (d.type || "")) : ("未连接" + (d.error ? "：" + d.error : "")));
      st.id = "led" + idx;
      const old = $("led" + idx);
      if (old) old.replaceWith(st); else render();
      if (d.ok && d.models && d.models.length) {
        const mdl = document.querySelector('.mModel[data-idx="' + idx + '"]');
        if (mdl) {
          mdl.innerHTML = "";
          const ph2 = document.createElement("option");
          ph2.value = ""; ph2.textContent = "（未选择）";
          mdl.appendChild(ph2);
          d.models.slice(0, 40).forEach(n => {
            const o = document.createElement("option");
            o.value = n; o.textContent = n;
            if (list[idx].model === n) o.selected = true;
            mdl.appendChild(o);
          });
          // 回显: Ollama 名称常带 :latest 后缀, 做一次兼容
          let want = list[idx].model || "";
          if (want && ![...mdl.options].some(o => o.value === want)) {
            if ([...mdl.options].some(o => o.value === want + ":latest")) want += ":latest";
          }
          mdl.value = want;
          if (want) { list[idx].model = want; save(); }
          save();
        }
      }
    } catch (e) {
      const st = led(false, "未连接：" + e.message);
      const old = $("led" + idx);
      if (old) old.replaceWith(st); else render();
    }
  }

  function openDetail(idx) {
    const m = list[idx] || {};
    const d = $("modelDetail");
    if (!d) return;
    d.dataset.idx = idx;
    d.querySelector(".mdName").textContent = m.name || "（未命名）";
    d.querySelector(".mdUrl").textContent = m.url || "—";
    d.querySelector(".mdModel").textContent = m.model || "—";
    d.querySelector(".mdType").textContent = m.type === "openai" ? "OpenAI 兼容" : (m.type === "ollama" ? "Ollama" : "自动检测");
    d.classList.add("show");
    refreshDetail(idx);
  }

  async function refreshDetail(idx) {
    const m = list[idx] || {};
    const box = $("modelDetail");
    if (!box) return;
    const out = box.querySelector(".mdStat");
    if (!m.url) { out.textContent = "未填写 API 地址"; return; }
    out.textContent = "检测中…";
    try {
      const r = await fetch("/api/model/probe?url=" + encodeURIComponent(m.url), { cache: "no-store" });
      const d = await r.json();
      if (!d.ok) { out.textContent = "未连接：" + (d.error || "未知错误"); return; }
      out.innerHTML =
        "状态：<b class='ok'>已连接</b><br>" +
        "类型：" + (d.type || "—") + "<br>" +
        "延迟：" + d.latency_ms + " ms<br>" +
        "可用模型：" + (d.models || []).length + " 个<br>" +
        "<span class='mdList'>" + (d.models || []).slice(0, 12).join("、") + "</span>";
    } catch (e) {
      out.textContent = "未连接：" + e.message;
    }
  }

  function open() {
    const s = $("modelScreen");
    if (!s) return;
    s.classList.add("show");
    render();
    list.forEach((m, i) => {
      if (m.url) {
        const el = $("led" + i);
        if (el) probe(i, m.url, el);
      }
    });
  }
  function close() {
    const s = $("modelScreen");
    if (s) s.classList.remove("show");
    const d = $("modelDetail");
    if (d) d.classList.remove("show");
  }

  window.__openModel = open;
  window.__closeModel = close;
  window.__modelList = () => list;

  document.addEventListener("DOMContentLoaded", () => {
    const ob = document.getElementById("optModelBtn");
    if (ob) ob.addEventListener("click", (e) => { e.stopPropagation(); open(); });
    const prev = document.querySelector("#modelScreen .pagerBtn.prev");
    const next = document.querySelector("#modelScreen .pagerBtn.next");
    if (prev) prev.addEventListener("click", () => { page = Math.max(0, page - 1); render(); });
    if (next) next.addEventListener("click", () => { page = Math.min(Math.ceil(list.length / PER_PAGE) - 1, page + 1); render(); });
    const back = document.querySelector("#modelScreen .mdBack");
    if (back) back.addEventListener("click", () => { const d = $("modelDetail"); if (d) d.classList.remove("show"); });
    const closeBtn = document.querySelector("#modelScreen .mClose");
    if (closeBtn) closeBtn.addEventListener("click", close);
  });
})();
