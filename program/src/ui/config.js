// 音效/BGM 设置面板
(function () {
  const SND = "assets/snd/";
  let catalog = { se: [], bgm: [] };
  let prefs = {
    seHover: 55, seClick: 56, seCancel: 56, sePage: 57, seExit: 58,   // 55=悬停音 56=点击音（录屏比对得出）
    bgmMenu: 0, bgmCalm: 2, bgmWarm: 3, bgmSad: 4, bgmTense: 6,
    bgmVol: 30, seVol: 35,
  };

  try {
    const s = localStorage.getItem("app_prefs");
    if (s) prefs = Object.assign(prefs, JSON.parse(s));
  } catch (e) {}

  function setPref(k, v) {
  prefs[k] = v;
  savePrefs();
}

function getPrefs() { return prefs; }

function savePrefs() {
    try { localStorage.setItem("app_prefs", JSON.stringify(prefs)); } catch (e) {}
    window.dispatchEvent(new CustomEvent("app:prefs", { detail: prefs }));
  }

  function playPreview(file, vol) {
    const a = new Audio(SND + file);
    a.volume = vol;
    a.play().catch(() => {});
  }

  function buildPanel() {
    const box = document.createElement("div");
    box.id = "cfgPanel";
    box.innerHTML = `
      <div class="cfgCard">
        <div class="cfgTitle">系统设置</div>

        <div class="cfgSec">
          <div class="cfgLbl">界面音效</div>
          <div class="cfgRow"><span>悬停</span><select id="cfgSeHover"></select><button data-listen="seHover">试听</button></div>
          <div class="cfgRow"><span>点击</span><select id="cfgSeClick"></select><button data-listen="seClick">试听</button></div>
          <div class="cfgRow"><span>取消</span><select id="cfgSeCancel"></select><button data-listen="seCancel">试听</button></div>
        </div>

        <div class="cfgSec">
          <div class="cfgLbl">背景音乐</div>
          <div class="cfgRow"><span>平静</span><select id="cfgBgmCalm"></select><button data-listen="bgmCalm">试听</button></div>
          <div class="cfgRow"><span>温柔</span><select id="cfgBgmWarm"></select><button data-listen="bgmWarm">试听</button></div>
          <div class="cfgRow"><span>难过</span><select id="cfgBgmSad"></select><button data-listen="bgmSad">试听</button></div>
          <div class="cfgRow"><span>紧张</span><select id="cfgBgmTense"></select><button data-listen="bgmTense">试听</button></div>
        </div>

        <div class="cfgSec">
          <div class="cfgLbl">音量</div>
          <div class="cfgRow"><span>音乐</span><input id="cfgBgmVol" type="range" min="0" max="100"><b id="cfgBgmVolV"></b></div>
          <div class="cfgRow"><span>音效</span><input id="cfgSeVol" type="range" min="0" max="100"><b id="cfgSeVolV"></b></div>
        </div>

        <div class="cfgBtns">
          <button id="cfgSave">保存</button>
          <button id="cfgClose">关闭</button>
        </div>
      </div>`;
    document.body.appendChild(box);

    const seSel = ["cfgSeHover", "cfgSeClick", "cfgSeCancel"];
    const bgmSel = ["cfgBgmCalm", "cfgBgmWarm", "cfgBgmSad", "cfgBgmTense"];

    seSel.forEach(id => {
      const el = box.querySelector("#" + id);
      catalog.se.forEach((s, i) => {
        const o = document.createElement("option");
        o.value = i;
        o.textContent = s.name || ("SE " + String(i).padStart(2, "0"));
        el.appendChild(o);
      });
    });
    bgmSel.forEach(id => {
      const el = box.querySelector("#" + id);
      catalog.bgm.forEach((b, i) => {
        const o = document.createElement("option");
        o.value = i;
        o.textContent = (b.name || ("BGM " + String(i).padStart(2, "0")));
        el.appendChild(o);
      });
    });

    function sync() {
      box.querySelector("#cfgSeHover").value = prefs.seHover;
      box.querySelector("#cfgSeClick").value = prefs.seClick;
      box.querySelector("#cfgSeCancel").value = prefs.seCancel;
      box.querySelector("#cfgBgmCalm").value = prefs.bgmCalm;
      box.querySelector("#cfgBgmWarm").value = prefs.bgmWarm;
      box.querySelector("#cfgBgmSad").value = prefs.bgmSad;
      box.querySelector("#cfgBgmTense").value = prefs.bgmTense;
      box.querySelector("#cfgBgmVol").value = prefs.bgmVol;
      box.querySelector("#cfgSeVol").value = prefs.seVol;
      box.querySelector("#cfgBgmVolV").textContent = prefs.bgmVol + "%";
      box.querySelector("#cfgSeVolV").textContent = prefs.seVol + "%";
    }
    sync();

    function readBack() {
      prefs.seHover = +box.querySelector("#cfgSeHover").value;
      prefs.seClick = +box.querySelector("#cfgSeClick").value;
      prefs.seCancel = +box.querySelector("#cfgSeCancel").value;
      prefs.bgmCalm = +box.querySelector("#cfgBgmCalm").value;
      prefs.bgmWarm = +box.querySelector("#cfgBgmWarm").value;
      prefs.bgmSad = +box.querySelector("#cfgBgmSad").value;
      prefs.bgmTense = +box.querySelector("#cfgBgmTense").value;
      prefs.bgmVol = +box.querySelector("#cfgBgmVol").value;
      prefs.seVol = +box.querySelector("#cfgSeVol").value;
    }

    box.querySelectorAll("[data-listen]").forEach(btn => {
      btn.addEventListener("click", () => {
        readBack();
        const key = btn.dataset.listen;
        if (key.startsWith("se")) {
          const it = catalog.se[prefs[key]];
          if (it) playPreview(it.file, prefs.seVol / 100);
        } else {
          const it = catalog.bgm[prefs[key]];
          if (it) playPreview(it.file, prefs.bgmVol / 100);
        }
      });
    });

    box.querySelector("#cfgBgmVol").addEventListener("input", e => {
      box.querySelector("#cfgBgmVolV").textContent = e.target.value + "%";
    });
    box.querySelector("#cfgSeVol").addEventListener("input", e => {
      box.querySelector("#cfgSeVolV").textContent = e.target.value + "%";
    });

    box.querySelector("#cfgSave").addEventListener("click", () => {
      readBack();
      savePrefs();
      const it = catalog.se[prefs.seClick];
      if (it) playPreview(it.file, prefs.seVol / 100);
      box.classList.remove("show");
    });
    box.querySelector("#cfgClose").addEventListener("click", () => {
      box.classList.remove("show");
    });

    return box;
  }

window.App = { prefs: null, catalog: null };

  fetch(SND + "catalog.json")
    .then(r => r.json())
    .then(data => {
      catalog = data;
      const panel = buildPanel();
      window.App.catalog = catalog;
      window.App.prefs = prefs;
      window.App.setPref = (k, v) => { prefs[k] = v; savePrefs(); };
      window.App.openConfig = () => { panel.classList.add("show"); };
      window.App.getPrefs = () => prefs;
      window.App.playPreview = playPreview;
      window.App.catalogGet = () => catalog;
      if (location.hash === "#config") panel.classList.add("show");
      window.dispatchEvent(new Event("app:ready"));
    })
    .catch(e => console.warn("音效目录加载失败", e));
})();

