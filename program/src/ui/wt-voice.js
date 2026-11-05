/* voice.js —— 从 game.js 搬出的功能块（逻辑未改）
 * 挂载：WA2.voice；同时同步到 window 以兼容旧调用。
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };
  /* 桥接：emoOf 还在 game.js（全局函数），语音对象由本模块持有 */
  var emoOf = function (t) { return window.emoOf ? window.emoOf(t) : "calm"; };
  var ttsAudio = null;
  function _tts(v) { if (v !== undefined) ttsAudio = v; return ttsAudio; }

  function currentVoiceLang() {
    // 每次都用最新设置（菜单切换后立即生效）
    try {
      return localStorage.getItem("app_voiceLang") || window.voiceLang || "zh";
    } catch (e) {
      return "zh";
    }
  }

  function stopSpeak() {
    if (ttsAudio) { try { ttsAudio.pause(); } catch (e) {} ttsAudio = null; }
    _devState = null;
  }

  /* ---------- 音频设备变化（#7）----------
     拔耳机 / 切蓝牙之后，正在播的 <audio> 还挂在已经不存在的设备上：
     记下位置、暂停；设备重建完再从原位置续播。续不上由调用方提示「重播这句」。 */
  var _devState = null;

  function suspendForDevice() {
    if (!ttsAudio) return false;
    try {
      _devState = { t: ttsAudio.currentTime || 0, playing: !ttsAudio.paused };
      ttsAudio.pause();
    } catch (e) {
      _devState = null;
      return false;
    }
    return !!(_devState && _devState.playing);
  }

  function resumeAfterDevice() {
    var st = _devState;
    _devState = null;
    if (!st || !ttsAudio) return Promise.resolve(false);
    var a = ttsAudio;
    return new Promise(function (resolve) {
      try {
        if (st.t > 0) { try { a.currentTime = st.t; } catch (e) {} }
        try { a.volume = voiceVolume(); } catch (e) {}
        var p = a.play();
        if (p && p.then) p.then(function () { resolve(true); }).catch(function () { resolve(false); });
        else resolve(true);
      } catch (e) {
        resolve(false);
      }
    });
  }

  /** 合成语音并返回 Audio（失败或超时返回 null） */
  function fetchVoice(text, timeoutMs) {
    if (!ttsOn) return Promise.resolve(null);
    return new Promise((resolve) => {
      const ctrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
      let done = false;
      const timer = setTimeout(() => {
        if (done) return;
        done = true;
        if (ctrl) { try { ctrl.abort(); } catch (e) {} }
        resolve(null);
      }, timeoutMs || 15000);
      fetch("/api/tts?text=" + encodeURIComponent(text) + "&lang=" + currentVoiceLang() + "&emotion=" + (window.__lastEmo || emoOf(text)) + (window.__speakJa ? "&speak_ja=" + encodeURIComponent(window.__speakJa) : ""), ctrl ? { signal: ctrl.signal } : {})
        .then((r) => {
          if (!r.ok) throw new Error("tts " + r.status);
          return r.blob();
        })
        .then((blob) => {
          if (done) return;
          done = true; clearTimeout(timer);
          const url = URL.createObjectURL(blob);
          const a = new Audio(url);
          a.onended = () => { URL.revokeObjectURL(url); };
          resolve(a);
        })
        .catch(() => {
          if (done) return;
          done = true; clearTimeout(timer);
          /* 语音服务没起来时别静默失败：提示一次（同一局里不反复弹） */
          if (!window.__voiceWarned) {
            window.__voiceWarned = true;
          if (window.__saveHint) window.__saveHint("语音暂时不可用，先显示文字");
          }
          resolve(null);
        });
    });
  }


  /* ---------- 开场白语音 ---------- */
  function waitTtsReady(cb, tries) {
    if (!ttsOn) return;
    fetch("/api/voice/ok", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ready) cb();
        else if (tries > 0) setTimeout(function () { waitTtsReady(cb, tries - 1); }, 1000);
      })
      .catch(function () {
        if (tries > 0) setTimeout(function () { waitTtsReady(cb, tries - 1); }, 1000);
      });
  }

  function speakLineJa(ja, emo) {
    if (!ttsOn) return;
    var clean = (ja || "").replace(/^[「『]|[」』]$/g, "").trim();
    if (!clean) return;
    window.__speakJa = clean;
  window.__lastEmo = emo || window.__lastEmo || "soft";
    waitTtsReady(function () { speakReply(clean); }, 60);
  }

  function speakReply(text) {
    stopSpeak();
    return fetchVoice(text, 15000).then((a) => {
      if (!a) return false;
      ttsAudio = a;
      try { a.volume = voiceVolume(); a.play(); } catch (e) {}
      return true;
    });
  }
  var _exp = {};
  var _names = ["_tts", "currentVoiceLang", "fetchVoice", "speakLineJa", "speakReply", "stopSpeak",
                "suspendForDevice", "resumeAfterDevice", "waitTtsReady"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.voice = _exp;
  WA2.register("voice", _exp);
  /* __export_all__ */
  ["_tts", "currentVoiceLang", "fetchVoice", "speakLineJa", "speakReply", "stopSpeak", "waitTtsReady", "WA2", "_exp", "_names", "a", "clean", "ctrl", "done", "emoOf", "timer", "ttsAudio", "url"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();
