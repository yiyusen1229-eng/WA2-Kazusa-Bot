/* wt-audio.js —— BGM / SE / 语音音量（从 game.js 搬出来的第一个功能模块）
 *
 * 对外（挂在 WA2.audio）：
 *   bgmSrc(name)        名字 → 音频地址
 *   bgmVolume()         当前 BGM 音量（0~1，已乘全体音量）
 *   voiceVolume()       当前语音音量（0~1，已乘全体音量）
 *   playSE(kind)        播放点击/翻页/取消等音效
 *   setBgm(name, ms)    淡出换 BGM（ms 是淡入淡出时长）
 *   pauseBgm()          暂停 BGM（静音开关用）
 *   applyVolume()       按 prefs 立即应用音量，返回 {bgm, voice}
 *   current / enabled   BGM 名字 / BGM 开关
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};

  var BGM_KEY = { menu: "bgmMenu", calm: "bgmCalm", warm: "bgmWarm", sad: "bgmSad", tense: "bgmTense" };
  var SE_BASE = "assets/snd/";
  var seCache = {};

  function prefs() { return (window.App && window.App.getPrefs) ? window.App.getPrefs() : {}; }
  function catalog() { return (window.App && window.App.catalogGet) ? window.App.catalogGet() : { bgm: [], se: [] }; }

  function bgmSrc(name) {
    var P = prefs(), C = catalog();
    var id = P[BGM_KEY[name] || "bgmCalm"];
    var item = C.bgm && C.bgm[id === undefined ? 0 : id];
    return item ? "assets/snd/" + item.file : "";
  }

  /* OPTION 2 的 BGM 滑块优先（volBgm），没有就退回旧的 bgmVol；两者都要乘全体音量 */
  function bgmVolume() {
    var P = prefs();
    var b = (P.volBgm !== undefined ? P.volBgm : (P.bgmVol === undefined ? 28 : P.bgmVol));
    var m = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
    return (b / 100) * m;
  }

  /* 语音音量：VOICE 滑块 × 全体音量 */
  function voiceVolume() {
    var P = prefs();
    var v = (P.volVoice === undefined ? 90 : P.volVoice);
    var m = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
    return (v / 100) * m;
  }

  function playSE(kind) {
    var P = prefs(), C = catalog();
    var key = kind === "exit" ? (P.seExit || 58)
      : kind === "page" ? (P.sePage || 57)
        : (kind === "click" ? P.seClick : (kind === "cancel" ? P.seCancel : P.seHover));
    var item = C.se && C.se[key || 0];
    if (!item) return;
    var master = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
    var vol = ((P.seVol === undefined ? 35 : P.seVol) / 100) * master;
    var a = seCache[item.file];
    if (!a) { a = new Audio(SE_BASE + item.file); a.preload = "auto"; seCache[item.file] = a; }
    a.volume = vol;
    try { a.currentTime = 0; a.play().catch(function () {}); } catch (e) {}
  }

  var bgm = new Audio();
  bgm.loop = true;
  bgm.volume = 0;
  bgm.preload = "auto";

  var state = { current: null, enabled: true };

  /* 设置界面改音量时立即生效 */
  window.addEventListener("app:prefs", function (e) {
    var P = e.detail || {};
    if (bgm && !bgm.paused) {
      var b = (P.volBgm !== undefined ? P.volBgm : (P.bgmVol === undefined ? 30 : P.bgmVol));
      var m = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
      bgm.volume = (b / 100) * m;
    }
  });

  function setBgm(name, fadeMs) {
    if (!state.enabled) return;
    fadeMs = (fadeMs === undefined) ? 1200 : fadeMs;
    var src = bgmSrc(name);
    if (state.current === name && !bgm.paused) return;
    state.current = name;
    var from = bgm.volume;
    var fadeOut = setInterval(function () {
      bgm.volume = Math.max(0, bgm.volume - from / 12);
    }, fadeMs / 12);
    setTimeout(function () {
      clearInterval(fadeOut);
      bgm.src = src;
      bgm.volume = 0;
      bgm.play().then(function () {
        var to = bgmVolume();
        var v = 0;
        var fadeIn = setInterval(function () {
          v += to / 14;
          bgm.volume = Math.min(to, v);
          if (v >= to) clearInterval(fadeIn);
        }, fadeMs / 14);
      }).catch(function () {});
    }, fadeMs);
  }

  function pauseBgm() {
    try { bgm.pause(); } catch (e) {}
  }

  /* 立即按 prefs 应用音量（给 __applyVolumes 用） */
  function applyVolume() {
    var bv = 0, vv = 0;
    try { bv = bgmVolume(); } catch (e) {}
    try { vv = voiceVolume(); } catch (e) {}
    try { bgm.volume = bv; } catch (e) {}
    window.__volBgm = bv;
    window.__volVoice = vv;
    return { bgm: bv, voice: vv };
  }

  WA2.audio = {
    bgmSrc: bgmSrc,
    bgmVolume: bgmVolume,
    voiceVolume: voiceVolume,
    playSE: playSE,
    setBgm: setBgm,
    pauseBgm: pauseBgm,
    applyVolume: applyVolume,
    get current() { return state.current; },
    set current(v) { state.current = v; },
    get enabled() { return state.enabled; },
    set enabled(v) { state.enabled = !!v; }
  };
  WA2.register("audio", WA2.audio);
})();
