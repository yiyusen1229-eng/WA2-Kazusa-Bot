// WHITE ALBUM 2 风格对话界面 —— 使用游戏原始素材
const $ = (id) => document.getElementById(id);

let history = [];
let typing = false;
let fullText = "";
let turnCount = 0;
let backlogOpen = false;
let currentBgm = null;
let bgmEnabled = true;
/* 角色名：存在 char/name.txt，特别模式里改的就是它 */
let CHAR_NAME = "和纱";

/* ---------- 素材表 ---------- */
/* 旧的四张通用背景：新场景图还没导入、或读档时遇到旧存档的场景名，就退回这里 */
const BGS = {
  classroom: "assets/bg_classroom.png",
  music:     "assets/bg_music.png",
  corridor:  "assets/bg_corridor.png",
  street:    "assets/bg_street.png",
};

/* 场景 CG：assets/cg/index.json 由 tools/import_cg.py 生成，id 就是图片文件名（去掉扩展名）。
   对话里换场景时后端已经按文件名标签匹配好了（scene_cg.py），这里只负责按 id 取图。 */
const CG_URL = {};
fetch("assets/cg/index.json", { cache: "no-store" })
  .then(function (r) { return r.json(); })
  .then(function (d) {
    (d && d.items || []).forEach(function (it) { CG_URL[it.id] = "assets/cg/" + it.file; });
    /* 目录比背景晚到时（刚打开页面就读档）补渲染一次，免得停在兜底教室图上 */
    if (currentBg) { var _n = currentBg; currentBg = null; setBg(_n); }
  })
  .catch(function () {});

/* 场景名 → 图片地址。认三种：CG 的 id / 旧的四张背景 / 都没有就用教室 */
function bgSrc(name) {
  if (name && CG_URL[name]) return CG_URL[name];
  if (name && BGS[name]) return BGS[name];
  return BGS.classroom;
}


const BGM_KEY = { menu: "bgmMenu", calm: "bgmCalm", warm: "bgmWarm", sad: "bgmSad", tense: "bgmTense" };
function bgmSrc(name) {
  const P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
  const C = (window.App && window.App.catalogGet) ? window.App.catalogGet() : { bgm: [] };
  const id = P[BGM_KEY[name] || "bgmCalm"];
  const item = C.bgm && C.bgm[id === undefined ? 0 : id];
  return item ? "assets/snd/" + item.file : "";
}
function bgmVolume() {
  const P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
  /* OPTION 2 的 BGM 滑块优先（volBgm），没有就退回旧的 bgmVol；两者都要乘全体音量 */
  const b = (P.volBgm !== undefined ? P.volBgm : (P.bgmVol === undefined ? 28 : P.bgmVol));
  const m = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
  return (b / 100) * m;
}

/* 语音音量：OPTION 2 的 VOICE 滑块 × 全体音量（原来 playback 里写死 1.0，滑块等于没用） */
function voiceVolume() {
  const P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
  const v = (P.volVoice === undefined ? 90 : P.volVoice);
  const m = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
  return (v / 100) * m;
}

/* ---------- 开场动画 ---------- */
(function intro() {
  const scr = $("introScreen");
  const vid = $("introVideo");
  if (!scr) return;
  // 没有视频元素（已改成静态开场）：直接点任意处 / 1.2 秒后进入标题
  if (!vid) {
    let done2 = false;
    function finish() {
      if (done2) return;
      done2 = true;
      scr.classList.remove("active");
      const t = document.getElementById("titleScreen");
      if (t) t.classList.add("active");
      try { setBgm("menu", 900); } catch (e) {}
    }
    window.__endIntro = finish;
    scr.addEventListener("click", finish);
    document.addEventListener("keydown", function (e) {
      if (!done2 && (e.key === "Escape" || e.key === " " || e.key === "Enter")) finish();
    });
    setTimeout(finish, 1200);
    return;
  }
  let done = false;

  function endIntro() {
    if (done) return;
    done = true;
    /* 跳过时必须把视频彻底停掉：只 pause 不够——fetch 完之后那串 play() 的异步链
       可能在你点过之后又把音轨拉起来，于是画面没了声音还在放。
       这里静音 + 断源 + load()，把解码器一起关掉。 */
    try {
      vid.pause();
      vid.muted = true;
      vid.removeAttribute("src");
      vid.load();
    } catch (e) {}
    scr.classList.remove("active");
    $("titleScreen").classList.add("active");
    if (window.App && window.App.getPrefs) { try { setBgm("menu", 900); } catch (e) {} }
  }
  window.__endIntro = endIntro;

  vid.muted = false;
  vid.volume = 0.9;

  /* 开屏按原版顺序播两段：Leaf 社 logo → 游戏 OP → 标题
     点一下 / Esc = 跳过当前这一段，跳到下一段；最后一段再跳过才进标题 */
  var SEQ = ["assets/leaf_logo.mp4", (vid.dataset.src || "assets/opening.mp4")];
  var seqIdx = 0;

  function playSeq(i) {
    if (done) return;
    if (i >= SEQ.length) { endIntro(); return; }
    seqIdx = i;
    var url = SEQ[i];
    fetch(url, { cache: "force-cache" })
      .then(function (r) { return r.blob(); })
      .then(function (b) {
        if (done || seqIdx !== i) return;
        vid.src = URL.createObjectURL(b);
        vid.load();          /* preload="none" 时必须显式 load，否则一直卡在 readyState=0 */
        /* 一段播完再切下一段：用 onended（不用全局 ended 监听，避免旧段的残留事件把序列顶掉） */
        vid.onended = function () {
          if (done || seqIdx !== i) return;
          playSeq(i + 1);
        };
        var p = vid.play();
        if (p && p.catch) p.catch(function () {
          try { vid.muted = true; vid.play().catch(function () {}); } catch (e) {}
        });
      })
      .catch(function () { if (seqIdx === i) playSeq(i + 1); });   /* 取不到就跳下一段 */
  }

  function nextOrFinish() {
    if (done) return;
    if (seqIdx + 1 < SEQ.length) {
      try { vid.pause(); } catch (e) {}
      vid.onended = null;
      playSeq(seqIdx + 1);
    } else {
      endIntro();
    }
  }

  scr.addEventListener("click", nextOrFinish);
  document.addEventListener("keydown", (e) => {
    if (!done && (e.key === "Escape" || e.key === " " || e.key === "Enter")) nextOrFinish();
  });

  // 等首屏资源（界面图/字体/音频）都加载完再拉视频，避免抢带宽
  function startVideo() {
    if (vid.dataset.started) return;
    vid.dataset.started = "1";
    playSeq(0);          /* 从 Leaf logo 开始，后面的段由 playSeq 按顺序拉 */
  }
  if (document.readyState === "complete") {
    setTimeout(startVideo, 300);
  } else {
    window.addEventListener("load", function () { setTimeout(startVideo, 300); });
  }

  // 开场视频是从本地 HTTP 服务慢慢下载的（38MB，可能要 20~30 秒），
  // 所以不能按「3 秒没播起来就跳过」来判断——那会导致没点屏幕就自动跳过。
  // 只在真正出错（解码失败 / 文件缺失）时才自动跳过；其余情况等用户点击或播完。
  vid.addEventListener("stalled", () => {}, { passive: true });
  let loadFail = 0;
  const failTimer = setInterval(() => {
    if (done) { clearInterval(failTimer); return; }
    // readyState=0 且已经等很久，才认为加载失败
    if (vid.readyState === 0 && ++loadFail >= 60) {   // 60 × 2s = 120s
      clearInterval(failTimer);
      endIntro();
    }
  }, 2000);
})();

/* ---------- 音频 ---------- */
const SE_BASE = "assets/snd/";
const seCache = {};
function playSE(kind) {
  const P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
  const C = (window.App && window.App.catalogGet) ? window.App.catalogGet() : { se: [] };
  const key = kind === "exit" ? (P.seExit || 58)
                 : kind === "page" ? (P.sePage || 57)
                 : (kind === "click" ? P.seClick : (kind === "cancel" ? P.seCancel : P.seHover));
  const item = C.se && C.se[key || 0];
  if (!item) return;
  const master = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
  const vol = ((P.seVol === undefined ? 35 : P.seVol) / 100) * master;
  let a = seCache[item.file];
  if (!a) { a = new Audio(SE_BASE + item.file); a.preload = "auto"; seCache[item.file] = a; }
  a.volume = vol;
  try { a.currentTime = 0; a.play().catch(() => {}); } catch (e) {}
}

const bgmAudio = new Audio();
bgmAudio.loop = true;
bgmAudio.volume = 0;
bgmAudio.preload = "auto";

// 设置界面改音量时立即生效
window.addEventListener("app:prefs", function (e) {
  const P = e.detail || {};
  if (bgmAudio && !bgmAudio.paused) {
    /* OPTION2 的 BGM 滑块优先（volBgm），没有就退回旧的 bgmVol */
  var _b = (P.volBgm !== undefined ? P.volBgm : (P.bgmVol === undefined ? 30 : P.bgmVol));
  var _m = (P.volMaster === undefined ? 100 : P.volMaster) / 100;
  bgmAudio.volume = (_b / 100) * _m;
  }
});

function setBgm(name, fadeMs = 1200) {
  if (!bgmEnabled) return;
  const src = bgmSrc(name);
  if (currentBgm === name && !bgmAudio.paused) return;
  currentBgm = name;
  const from = bgmAudio.volume;
  const fadeOut = setInterval(() => {
    bgmAudio.volume = Math.max(0, bgmAudio.volume - from / 12);
  }, fadeMs / 12);
  setTimeout(() => {
    clearInterval(fadeOut);
    bgmAudio.src = src;
    bgmAudio.volume = 0;
    bgmAudio.play().then(() => {
      const to = bgmVolume();
      let v = 0;
      const fadeIn = setInterval(() => {
        v += to / 14;
        bgmAudio.volume = Math.min(to, v);
        if (v >= to) clearInterval(fadeIn);
      }, fadeMs / 14);
    }).catch(() => {});
  }, fadeMs);
}

/* ---------- 情绪判断 ---------- */
function detectMood(text) {
  const t = text || "";
  if (/滚|烦|吵|闭嘴|笨蛋|无聊|别管|哼|少来|自作多情/.test(t)) return "angry";
  if (/抱歉|对不起|哭|寂寞|后悔|离开|再见|讨厌我/.test(t)) return "sad";
  if (/早点睡|注意|吃药|别勉强|你也|小心|累了吧|照顾好/.test(t)) return "warm";
  if (/呵|笑|有趣|真拿你没办法|好吧/.test(t)) return "smile";
  if (/……|没事|没什么|有事|随便|不知道/.test(t)) return "cold";
  return "cold";
}

const MOOD_BGM = { angry: "tense", sad: "sad", warm: "warm", smile: "warm", cold: "calm" };
const MOOD_SPRITE = { angry: "angry", sad: "sad", warm: "school", smile: "smile", cold: "cold" };

/* ---------- 氛围累积（BGM 不随单句变化） ---------- */
const moodScore = { calm: 0, warm: 0, sad: 0, tense: 0 };
let moodStable = { name: "calm", turns: 0 };

function accumulateMood(reply) {
  const mood = detectMood(reply);
  const bgm = MOOD_BGM[mood] || "calm";
  // 每轮衰减，越近的话权重越大
  for (const k in moodScore) moodScore[k] *= 0.65;
  moodScore[bgm] = (moodScore[bgm] || 0) + 2;
  // 长句、强烈情绪加权
  if (reply.length > 40) moodScore[bgm] += 0.8;
  if (/[！!]{2,}|滚|闭嘴|笨蛋/.test(reply)) moodScore.tense += 1.2;
  if (/[（(]笑|呵|真拿你|好吧/.test(reply)) moodScore.warm += 0.8;

  // 当前氛围的分数
  let best = "calm", bestV = -1;
  for (const k in moodScore) {
    if (moodScore[k] > bestV) { bestV = moodScore[k]; best = k; }
  }
  const curV = moodScore[currentBgmMood()] || 0;

  // 需要连续两轮领先 2 分以上才切换
  if (best !== moodStable.name) {
    moodStable = { name: best, turns: 1 };
  } else {
    moodStable.turns++;
  }
  const enough = bestV - curV >= 2.0 && moodStable.turns >= 2;
  if (best !== currentBgmMood() && enough) {
    setBgm(best);
  }
}

function currentBgmMood() {
  for (const k in MOOD_BGM) {
    if (MOOD_BGM[k] === currentBgm) return k === "smile" ? "warm" : MOOD_BGM[k];
  }
  return currentBgm || "calm";
}


/* ---------- 会话存档 ---------- */
function sessionSave() {
  try {
    fetch("/api/session/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slot: "auto",
        messages: (window.__history || history || []),
        meta: { bg: currentBg || "", outfit: currentOutfit || "", at: Date.now() }
      })
    }).catch(function () {});
  } catch (e) {}
}

function sessionRestore() {
  return fetch("/api/session/load?slot=auto", { cache: "no-store" })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d || !d.ok || !d.messages || !d.messages.length) return false;
      history = d.messages;
      window.__history = history;
      const meta = d.meta || {};
      if (meta.bg) { currentBg = null; setBg(meta.bg); }
      if (meta.outfit) { currentOutfit = meta.outfit; }
      // 把最后一句和纱的话显示出来
      let last = "";
      for (let i = history.length - 1; i >= 0; i--) {
        if (history[i].role === "assistant") { last = history[i].zh || history[i].content || ""; break; }
      }
      if (last) {
        try { showReply(last); } catch (e) { $("msgText").textContent = last; }
      }
      if (meta.outfit) {
        try { setSpriteByScene(meta.bg || "classroom", "cold", true, meta.outfit); } catch (e) {}
      }
      console.log("[session] 已恢复", history.length, "条");
      try { rebuildBacklog(); } catch (e) {}
      return true;
    })
    .catch(function () { return false; });
}

/* 读档：把存档恢复到当前对话并进入游戏 */
window.__loadSession = function (data) {
  try {
    history = data.messages || [];
    window.__history = history;
    const meta = data.meta || {};
    showScreen("gameScreen");
    titleBgmStarted = true;
    if (meta.bg) { currentBg = null; setBg(meta.bg); } else { setBg("classroom"); }
    if (meta.outfit) { currentOutfit = meta.outfit; }
    setSpriteByScene(meta.bg || "classroom", "cold", true, meta.outfit || "");
    gdiRenderName(CHAR_NAME, $("namePlate"));
    setBgm("calm", 600);
    let last = "";
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].role === "assistant") { last = history[i].zh || history[i].content || ""; break; }
    }
    if (last) {
      try { showReply(last); } catch (e) { $("msgText").textContent = last; }
    }
    try { rebuildBacklog(); } catch (e) {}
    setTimeout(function () { $("input").focus(); }, 300);
  } catch (e) { console.warn("load session failed", e); }
};

/* 存档界面用：取当前会话要写进 meta 的东西（背景 / 立绘）
   currentBg、currentOutfit 是模块内变量，这里只读不写 */
window.__saveMeta = function () {
  return {
    bg: (typeof currentBg !== "undefined" && currentBg) || "",
    outfit: (typeof currentOutfit !== "undefined" && currentOutfit) || "",
    at: Date.now()
  };
};
/* 存档界面用：按场景名取背景图，给槽位缩略图用 */
window.__bgThumb = function (name) { return bgSrc(name); };
/* 调试/探针用：直接切到某张场景图（传 CG 的 id，或旧背景名） */
window.__scenePreview = function (name) { currentBg = null; setBg(name); return { bg: currentBg, url: bgSrc(name) }; };
/* 工具栏提示（快速存档/读档暂未开放时用） */
window.__saveHint = function (msg) {
  var h = document.getElementById("tbHint");
  if (!h) return;
  h.textContent = msg;
  clearTimeout(window.__saveHintTimer);
  window.__saveHintTimer = setTimeout(function () { h.textContent = ""; }, 1500);
};

/* 存档界面用：把当前画面（背景 CG + 立绘）截成缩略图
   160x100，和槽位的缩略图框同比例 */
window.__grabThumb = function () {
  try {
    var W = 160, H = 100;
    var cv = document.createElement("canvas");
    cv.width = W; cv.height = H;
    var g = cv.getContext("2d");
    g.fillStyle = "#0a1622"; g.fillRect(0, 0, W, H);

    var bg = window.__curBg;
    if (bg && bg.complete && bg.naturalWidth) {
      var s = Math.max(W / bg.naturalWidth, H / bg.naturalHeight);
      var w = bg.naturalWidth * s, h = bg.naturalHeight * s;
      g.drawImage(bg, (W - w) / 2, (H - h) / 2, w, h);
    }
    var stage = document.getElementById("stage");
    var sp = document.getElementById("sprite");
    if (stage && sp && sp.naturalWidth) {
      var sr = stage.getBoundingClientRect();
      var r = sp.getBoundingClientRect();
      if (sr.width > 0 && sr.height > 0) {
        g.drawImage(sp,
          (r.left - sr.left) / sr.width * W,
          (r.top - sr.top) / sr.height * H,
          r.width / sr.width * W,
          r.height / sr.height * H);
      }
    }
    return cv.toDataURL("image/jpeg", 0.72);
  } catch (e) { return ""; }
};

/* ---------- 场景切换 ---------- */
let currentBg = null;
function setBg(name) {
  if (currentBg === name) return;
  currentBg = name;
  const l = $("bgLayer");
  l.style.opacity = "0.25";
  setTimeout(() => {
    const bgUrl = bgSrc(name);
    l.style.backgroundImage = `url("${bgUrl}")`;
    l.style.opacity = "1";
    window.__curBg = new Image();
    window.__curBg.src = bgUrl;
  }, 260);
}

let currentSprite = null;


/* ---------- 立绘：衣服名（中文）+ 表情 ----------
   目录和文件都用中文：characters/<角色>/portrait/<衣服名>/<表情名>.png，
   索引是同一层的 index.json（自带素材里也有一份，读取时合并）。
   <outfit> 标签用衣服名；模型偶尔给旧编号（001/027…）也认，靠 index 里的 code 兜底。 */
const OUTFIT_BY_SCENE = {
  classroom: "高中·春秋JK制服",
  corridor:  "高中·春秋JK制服",
  music:     "舞台演出服",       // 练琴 / 演奏
  stage:     "舞台演出服",
  street:    "coda·常服（眼镜）",
  cafe:      "coda·第二套常服",
  home:      "婚后·居家服",
  night:     "睡衣",
  dress:     "礼服",
  yukata:    "和服（浴衣）",
  winter:    "高中·冬装",
  summer:    "高中·夏季JK制服"
};
const SPRITE_INDEX = {};      // 衣服名 -> {code, label, default, emotions, variants}
let currentOutfit = "";       // 空 = 按场景表推

fetch("/api/character/sprite/index.json")
  .then(function (r) { return r.json(); })
  .then(function (d) { Object.assign(SPRITE_INDEX, d.outfits || {}); })
  .catch(function () {});

/* 切换 / 新建角色之后重拉立绘索引（服务端已经把角色自己的 portrait/index.json
   和自带的 assets/sprites/index.json 合并好），再强制重画一次当前立绘 */
window.__reloadSprites = function () {
  fetch("/api/character/sprite/index.json", { cache: "no-store" })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      Object.keys(SPRITE_INDEX).forEach(function (k) { delete SPRITE_INDEX[k]; });
      Object.assign(SPRITE_INDEX, (d && d.outfits) || {});
      currentSprite = "";
      try { setSpriteByScene(currentBg || "classroom", window.__lastEmo || "", true); } catch (e) {}
    })
    .catch(function () {});
};

/* 给配置角色界面显示：一共几套衣服、几张图 */
window.__spriteSummary = function () {
  var outfits = 0, files = 0;
  for (var k in SPRITE_INDEX) {
    outfits++;
    var vs = (SPRITE_INDEX[k] || {}).variants || [];
    files += vs.length;
  }
  return outfits ? (outfits + " 套衣服 · " + files + " 张") : "";
};

/* 名字 / 旧编号 / label → index 里的衣服名（合并过的衣服有多个编号，都在 codes 里） */
function resolveOutfit(v) {
  v = (v || "").trim();
  if (!v) return "";
  if (SPRITE_INDEX[v]) return v;
  for (const k in SPRITE_INDEX) {
    const o = SPRITE_INDEX[k] || {};
    if (o.code === v || o.label === v) return k;
    if (o.codes && o.codes.indexOf(v) >= 0) return k;
  }
  return "";
}

function outfitOf(scene) {
  const name = OUTFIT_BY_SCENE[scene];
  if (name && SPRITE_INDEX[name]) return name;
  /* 场景表没命中（或这套衣服没有立绘）：优先校服，再退到索引里的第一套 */
  if (SPRITE_INDEX["高中·春秋JK制服"]) return "高中·春秋JK制服";
  const keys = Object.keys(SPRITE_INDEX);
  return keys.length ? keys[0] : "";
}

// 程序情绪 → 立绘情绪（warm 用微笑）
const MOOD_TO_EMO = {
  angry: "angry", sad: "sad", cold: "cold",
  smile: "smile", warm: "smile"
};

function spritePath(outfit, emotion) {
  const o = SPRITE_INDEX[outfit];
  if (!o) return "assets/kaz_cold.png";
  const emo = emotion ? (MOOD_TO_EMO[emotion] || emotion) : "";
  /* 衣服名 / 文件名都是中文，拼 URL 时按段转义 */
  const u = function (name) {
    return "/api/character/sprite/" + encodeURIComponent(outfit) + "/" + encodeURIComponent(name);
  };
  if (emo && o.emotions && o.emotions[emo]) return u(o.emotions[emo]);
  // 该套衣服没有这个情绪 → 退到「认真」，再退到默认
  if (o.emotions && o.emotions.serious) return u(o.emotions.serious);
  return u(o.default);
}

/** 按场景切换服装 */
function setSpriteByScene(scene, mood, force, wantOutfit) {
  // 服装以 currentOutfit 为准；只有对话明确换衣服（wantOutfit）才改
  const outfit = resolveOutfit(wantOutfit) || currentOutfit || outfitOf(scene) || "";
  const key = outfit + "|" + (mood || "");
  if (currentSprite === key && !force) return;
  currentOutfit = outfit;
  const sp = $("sprite");
  if (!sp) return;
  sp.classList.remove("show");
  setTimeout(function () {
    sp.src = spritePath(outfit, mood);
    sp.classList.add("show");
    currentSprite = key;
  }, 180);
}


/* ---------- 飘雪 ---------- */
(function snow() {
  const box = $("snowLayer");
  for (let i = 0; i < 34; i++) {
    const f = document.createElement("div");
    f.className = "flake";
    const s = 1.4 + Math.random() * 3;
    f.style.width = s + "px"; f.style.height = s + "px";
    f.style.left = Math.random() * 100 + "vw";
    f.style.animationDuration = (11 + Math.random() * 16) + "s";
    f.style.animationDelay = (-Math.random() * 26) + "s";
    f.style.opacity = 0.18 + Math.random() * 0.45;
    box.appendChild(f);
  }
})();

function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  $(id).classList.add("active");
}

/* ---------- GDI 字体渲染(复刻游戏原生方案) ---------- */
const NAME_BOOST = 1.0;   // 人名比正文大一点点(按像素比对)
function gdiRenderName(name, el) {
  if (!el || window.__gdiOK === false) return;
  gdiRenderMsg(name, el, 52, 360, 1).then((ok) => {
    if (!ok) return;
    el.classList.add("gdi");
    const im = el.querySelector("img");
    if (im) im.style.width = (im.naturalWidth * TEXT_SCALE * NAME_BOOST).toFixed(1) + "px";
  });
}

const TEXT_VER = "1029strict";  // 每次打包更新, 强制浏览器重新取图
const GDI_SCALE = 0.625;  // 默认显示比例, 实际用 TEXT_SCALE (Ctrl +/- 可调)
let TEXT_SCALE = parseFloat(localStorage.getItem("app_textScale") || "0.625");
if (!(TEXT_SCALE > 0.2 && TEXT_SCALE < 3)) TEXT_SCALE = 0.6;
function gdiRenderMsg(text, el, size, maxw, emb) {
  // 服务端 GDI 渲染(微软雅黑) -> 图片, 稳定可靠
  return __gdiFallback(text, el, size || 28, maxw || 832, emb === undefined ? 0 : emb);
}

function __gdiFallback(text, el, size, maxw, emb) {
  size = size || 56; maxw = maxw || 1200; emb = (emb === undefined ? 0 : emb);
  const url = "/api/text?text=" + encodeURIComponent(text) +
              "&s=" + size + "&w=" + maxw + "&e=" + emb + "&v=" + TEXT_VER;
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      el.innerHTML = "";
      el.appendChild(img);
      img.style.cssText = "display:block;width:" + (img.naturalWidth * TEXT_SCALE).toFixed(1) +
                          "px;height:auto;image-rendering:auto;";
      resolve(true);
    };
    img.onerror = () => resolve(false);
    img.src = url;
  });
}


/* ---------- 语音 ---------- */
let ttsAudio = null;
let ttsOn = (localStorage.getItem("app_tts") || "1") === "1";
function emoOf(text) {
  const m = detectMood(text || "");
  if (m === "angry") return "angry";
  if (m === "sad") return "sad";
  if (m === "warm" || m === "smile") return "warm";
  return "neutral";
}

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

function speakReply(text) {
  stopSpeak();
  return fetchVoice(text, 15000).then((a) => {
    if (!a) return false;
    ttsAudio = a;
    try { a.volume = voiceVolume(); a.play(); } catch (e) {}
    return true;
  });
}

/* ---------- 分页（和 galgame 一样：放不下就分两次） ---------- */
const PAGE_MAX_CHARS = 60;      // 3 行 × 每行 20 字（补丁 FONT_PER_LINE=20）
const PAGE_MAX_LINES = 3;

let pageTexts = [];
let pageIndex = 0;

function splitPages(text) {
  const raw = (text || "").replace(/\r/g, "").trim();
  if (!raw) return ["……"];
  const pages = [];
  let rest = raw;
  const BREAK = "。！？…，、；：」』）)]】";
  while (rest.length > 0) {
    if (rest.length <= PAGE_MAX_CHARS) { pages.push(rest); break; }
    let cut = PAGE_MAX_CHARS;
    // 在 60 字内找最后一个句读，找不到就硬切
    for (let i = PAGE_MAX_CHARS - 1; i >= PAGE_MAX_CHARS - 18 && i > 0; i--) {
      if (BREAK.indexOf(rest[i]) >= 0) { cut = i + 1; break; }
    }
    pages.push(rest.slice(0, cut));
    rest = rest.slice(cut);
  }
  return pages.length ? pages : ["……"];
}

function renderPage() {
  const box = $("msgText");
  const txt = pageTexts[pageIndex] || "";
  hidePageCursor();                /* 换页先收起来，打完再出 */
  if (gdiRenderMsg && window.__gdiOK !== false) {
    gdiRenderMsg(txt, box, 56, 1200, 1).then((ok) => {
      if (ok) { box.classList.add("gdi"); startReveal(box, txt); }
      else { window.__gdiOK = false; legacyTypewriter(txt); }
      updatePageCursor();
    });
  } else {
    legacyTypewriter(txt);
  }
}

/* ---------- 翻页提示：文字末尾的页面图标 ----------
   和原版一样：一段话打完、后面还有下一页时，在最后一个字后面闪动页面图标。
   文字是 /api/text 出的整段图（每字 28×32 的固定格子，见 sub_render.py），
   所以最后一字的位置可以直接由字数算出来，不用测量排版。 */
function pageCursorEl() {
  const box = $("msgText");
  if (!box) return null;
  let cur = document.getElementById("pageCursor");
  if (!cur) {
    cur = document.createElement("div");
    cur.id = "pageCursor";
    box.appendChild(cur);
  } else if (cur.parentNode !== box) {
    box.appendChild(cur);          /* 每次重渲染 msgText 都会被清空，补回来 */
  }
  return cur;
}

function hidePageCursor() {
  const cur = document.getElementById("pageCursor");
  if (cur) cur.style.display = "none";
}

function updatePageCursor() {
  const cur = pageCursorEl();
  if (!cur) return;
  const text = pageTexts[pageIndex] || "";
  /* 只有「这一段还没打完 → 不能显示」和「还有下一页」两个条件同时不满足才显示 */
  if (typing || !text || pageIndex >= pageTexts.length - 1) {
    cur.style.display = "none";
    return;
  }
  const img = $("msgText") && $("msgText").querySelector("img");
  if (!img || !img.naturalWidth || !img.clientWidth) {
    hidePageCursor();              /* 兜底打字机走文字：没有格子可对，先不显示 */
    return;
  }
  const scale = img.clientWidth / img.naturalWidth;
  const n = text.length;                       /* 1 起算的最后一个字 */
  const line = Math.floor((n - 1) / PER_LINE);
  const col = ((n - 1) % PER_LINE) + 1;
  cur.style.left = Math.round(col * CHAR_ADV * scale) + "px";
  cur.style.top = Math.round((line * LINE_H + 2) * scale) + "px";
  cur.style.transform = "scale(" + scale + ")";
  cur.style.display = "block";
}

function showReply(text) {
  pageTexts = splitPages(text);
  pageIndex = 0;
  renderPage();
}

function nextPage() {
  if (pageIndex < pageTexts.length - 1) {
    pageIndex++;
    renderPage();
    return true;
  }
  return false;
}

/* ---------- 打字机 ---------- */
/* 文字显示速度（OPTION 1）：0 瞬间 / 1 高速 / 2 普通 / 3 顺滑，值是「每字毫秒」 */
const SPEED_MS = [0, 14, 30, 50];

/* 服务端排版是固定的：每字占 32×32 格子、水平步进 28px、每行 20 字、行高 32px
   （见 sub_render.py 的 FONT_ADVANCE / FONT_PER_LINE / FONT_OCCUPATION）。
   所以拿到整段的渲染图后，可以由「显示到第几个字」反推裁剪区域，
   用 clip-path 把还没轮到的字裁掉：不用逐字出图，也不会重排。 */
const PER_LINE = 20, CHAR_ADV = 28, LINE_H = 32;

function textSpeed() {
  const P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
  const s = parseInt(P.textSpeed, 10);
  return isNaN(s) ? 2 : Math.max(0, Math.min(3, s));
}

let revealTimer = null, revealEl = null;

function stopReveal() {
  if (revealTimer) { clearTimeout(revealTimer); revealTimer = null; }
  if (revealEl) {
    revealEl.style.clipPath = "";
    revealEl.style.webkitClipPath = "";
    revealEl = null;
  }
  typing = false;
}

/* 只显示前 k 个字；返回 false 表示排版模型和图对不上（不做动画） */
function revealTo(el, text, k) {
  const img = el.querySelector("img");
  if (!img || !img.naturalWidth) return false;
  const W = img.naturalWidth, H = img.naturalHeight;
  const lines = Math.ceil(text.length / PER_LINE);
  if (Math.abs(H - lines * LINE_H) > 2) return false;
  if (k >= text.length) {
    el.style.clipPath = ""; el.style.webkitClipPath = "";
    return true;
  }
  if (k <= 0) {
    el.style.clipPath = "polygon(0 0, 0 0, 0 0)";
    return true;
  }
  const line = Math.floor((k - 1) / PER_LINE);
  const col = ((k - 1) % PER_LINE) + 1;
  const y0 = line * LINE_H, y1 = (line + 1) * LINE_H;
  const x1 = col * CHAR_ADV + 4;                 /* 末字右侧还带 2px 描边 */
  const px = (v, total) => (v / total * 100).toFixed(3) + "%";
  const poly = "polygon(0 0, 100% 0, 100% " + px(y0, H) +
               ", " + px(x1, W) + " " + px(y0, H) +
               ", " + px(x1, W) + " " + px(y1, H) +
               ", 0 " + px(y1, H) + ")";
  el.style.clipPath = poly;
  el.style.webkitClipPath = poly;
  return true;
}

function startReveal(el, text) {
  stopReveal();
  text = text || "";
  if (!el || !text) return;
  const sp = textSpeed();
  if (sp === 0) { updatePageCursor(); return; }   /* 瞬间显示：整段直接出来 */
  const img = el.querySelector("img");
  if (!img) return;
  if (!img.complete || !img.naturalWidth) {
    img.addEventListener("load", () => startReveal(el, text), { once: true });
    return;
  }
  if (!revealTo(el, text, 0)) return;       /* 模型不匹配：直接整段显示，别卡住 */
  typing = true;
  revealEl = el;
  fullText = text;
  let i = 0;
  const step = () => {
    if (revealEl !== el) return;
    i++;
    if (!revealTo(el, text, i)) { stopReveal(); return; }
    if (i >= text.length) { stopReveal(); updatePageCursor(); return; }
    const ch = text.charAt(i - 1);
    const d = SPEED_MS[sp] * (/[，。！？…、,\.!?]/.test(ch) ? 3 : 1);
    revealTimer = setTimeout(step, d);
  };
  revealTimer = setTimeout(step, SPEED_MS[sp]);
}
window.__startReveal = startReveal;
window.__stopReveal = stopReveal;

function typewriter(text, done) {
  const box = $("msgText");
  if (box && window.__gdiOK !== false) {
    // 先按 17px/520px 宽度渲染整段
    gdiRenderMsg(text, box, 56, 1200, 1).then((ok) => {
      if (ok) {
        fullText = text;
        box.classList.add("gdi");
        startReveal(box, text);
        if (done) done();
      } else {
        window.__gdiOK = false;
        legacyTypewriter(text, done);
      }
    });
    return;
  }
  legacyTypewriter(text, done);
}

function legacyTypewriter(text, done) {
  const el = $("msgText");
  fullText = text; el.textContent = ""; typing = true;
  let i = 0;
  const base = SPEED_MS[textSpeed()];
  if (base === 0) { el.textContent = text; typing = false; done && done(); hidePageCursor(); return; }
  const tick = () => {
    if (!typing) { el.textContent = fullText; typing = false; done && done(); hidePageCursor(); return; }
    if (i >= text.length) { typing = false; done && done(); hidePageCursor(); return; }
    const ch = text[i++];
    el.textContent += ch;
    setTimeout(tick, "，。！？…、".includes(ch) ? base * 3 : base);
  };
  tick();
}

/* ---------- Backlog ---------- */
function addHistory(role, text, raw) {
  const d = document.createElement("div");
  d.className = "hline " + (role === "user" ? "me" : "her");
  if (raw) d.dataset.ja = raw;      /* 原始日文（含 action/emotion），只存不显示 */
  const ico = document.createElement("div");
  ico.className = "ico";
  const ic = document.createElement("img");
  ic.alt = "";
  /* 图标取自 sys_00031：灰气泡=用户（无语音）、白气泡=和纱、白气泡+播放三角=悬停 */
  const canReplay = (role === "assistant") && !!raw && !!window.__voiceOk;
  ic.src = "assets/ui/history/" + (canReplay ? "icon_her" : "icon_me") + ".png";
  ico.appendChild(ic);
  const body = document.createElement("div");
  body.className = "body";
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? "你" : "和纱";
  /* 和纱的话统一加「」：存档里的 zh 是翻译原文（不带括号），实时消息带括号，这里统一 */
  if (role === "assistant") {
    text = "「" + String(text).replace(/^[「『]/, "").replace(/[」』]$/, "") + "」";
  }
  /* 长句按面板宽度折行：每行最多 26 个全角字（游戏里也是这个宽度） */
  const CH = 26;
  const lines = [];
  for (let i = 0; i < text.length; i += CH) lines.push(text.slice(i, i + CH));
  const txt = document.createElement("div");
  txt.className = "txtwrap";
  lines.forEach(function (ln) {
    const row = document.createElement("div");
    row.className = "txt";
    row.dataset.uitxtPerLine = "26";   /* 回想面板一行 26 字，和游戏一致 */
    row.textContent = ln;
    txt.appendChild(row);
  });
  body.appendChild(who);
  body.appendChild(txt);
  d.appendChild(ico); d.appendChild(body);
  /* 悬停高亮 + 点击重播（只有和纱且有日文原句、且语音可用时才挂） */
  if (canReplay) {
    ico.style.cursor = "pointer";
    ico.title = "重播这句的语音";
    ico.addEventListener("mouseenter", function () {
      ic.src = "assets/ui/history/icon_her_hover.png";
      setRowHighlight(d, true);
    });
    ico.addEventListener("mouseleave", function () {
      ic.src = "assets/ui/history/icon_her.png";
      if (d.dataset.playing !== "1") setRowHighlight(d, false);
    });
    ico.addEventListener("click", function (e) {
      e.stopPropagation();
      replayBacklogVoice(d);
    });
  }
  $("historyList").appendChild(d);
  $("historyList").scrollTop = $("historyList").scrollHeight;
}

/* 高亮色：取游戏原图里黄字字芯的颜色 RGB(250,246,164) = #FAF6A4 */
const HL_COLOR = "faf6a4";
function setRowHighlight(row, on) {
  if (!row) return;
  /* 只切 class；黄色由 CSS 滤镜给（参数按游戏原图黄字字芯色反解出来的） */
  row.classList.toggle("hl", !!on);
}

/* 重播某一行：把这条记录的日文原句重新丢给语音模型 */
let backlogPlayingRow = null;
function replayBacklogVoice(row) {
  const ja = (row.dataset.ja || "").trim();
  if (!ja || !window.__voiceOk) return;
  if (backlogPlayingRow && backlogPlayingRow !== row) {
    delete backlogPlayingRow.dataset.playing;
    setRowHighlight(backlogPlayingRow, false);
    const prevIc = backlogPlayingRow.querySelector(".ico img");
    if (prevIc) prevIc.src = "assets/ui/history/icon_her.png";
  }
  backlogPlayingRow = row;
  try { stopSpeak(); } catch (e) {}
  row.dataset.playing = "1";
  setRowHighlight(row, true);
  const clean = ja.replace(/<[^>]*>/g, "")
                  .replace(/^[「『]/, "").replace(/[」』]$/, "").trim();
  const done = function () {
    delete row.dataset.playing;
    setRowHighlight(row, false);
    if (backlogPlayingRow === row) backlogPlayingRow = null;
  };
  fetch("/api/tts?text=" + encodeURIComponent(clean) + "&lang=ja&emotion=neutral&speak_ja=" + encodeURIComponent(clean))
    .then(function (r) { if (!r.ok) throw new Error("tts " + r.status); return r.blob(); })
    .then(function (b) {
      const u = URL.createObjectURL(b);
      const a = new Audio(u);
      ttsAudio = a;
      try { a.volume = voiceVolume(); } catch (e) {}
      a.onended = function () { URL.revokeObjectURL(u); done(); };
      a.onerror = function () { URL.revokeObjectURL(u); done(); };
      a.play().catch(function () { done(); });
    })
    .catch(function () { done(); });
}
/* 用当前 history 重建回想列表（读档 / 自动恢复 / 开新游戏时用） */
function rebuildBacklog() {
  const list = $("historyList");
  if (!list) return;
  list.innerHTML = "";
  (window.__history || []).forEach(function (m) {
    if (!m) return;
    const isHer = m.role === "assistant";
    const shown = isHer ? (m.zh || m.content || "") : (m.content || "");
    if (!shown) return;
    addHistory(m.role, shown, isHer ? (m.content || "") : "");
  });
}
window.__rebuildBacklog = rebuildBacklog;

function toggleBacklog(force) {
  backlogOpen = force !== undefined ? force : !backlogOpen;
  $("historyPanel").classList.toggle("show", backlogOpen);
  document.body.classList.toggle("histOpen", backlogOpen);
  if (backlogOpen) {
    const list = $("historyList");
    const toBottom = function () {
      if (!list) return;
      list.scrollTop = list.scrollHeight;      // 最新一句在最底部
      try { syncHistThumb(); } catch (e) {}
    };
    // 面板刚显示时高度还没算出来，分几拍滚到底
    requestAnimationFrame(function () {
      toBottom();
      requestAnimationFrame(toBottom);
    });
    // 布局稳定前多试几次（面板刚显示时高度为 0）
    [40, 80, 140, 220, 320, 480, 700].forEach(function (t) {
      setTimeout(toBottom, t);
    });
    // 历史面板里的文字同样走 /api/text 渲染（面板显示后才有尺寸）
    if (window.__uiTextScan) window.__uiTextScan(document.getElementById("historyList"));
  }
  playSE(backlogOpen ? "click" : "cancel");
}

/* ---------- 选项 ---------- */
const CHOICE_SETS = [
  ["再稍微说一会话吧", "今天就，回去吧"],
  ["……我先走了。", "一起回去吗？"],
  ["继续练琴吧", "陪我走一段"],
];

function showChoices() {
  const set = CHOICE_SETS[Math.floor(Math.random() * CHOICE_SETS.length)];
  const list = $("choiceList");
  list.innerHTML = "";
  set.forEach(txt => {
    const b = document.createElement("button");
    b.className = "choice";
    b.textContent = txt;
    b.addEventListener("mouseenter", () => playSE("hover"));
    b.addEventListener("click", () => {
      playSE("click");
      $("choiceScreen").classList.remove("show");
      $("input").value = txt;
      send();
    });
    list.appendChild(b);
  });
  $("choiceScreen").classList.add("show");
}

/* ---------- 发送 ---------- */
async function send() {
  const inp = $("input");
  const text = inp.value.trim();
  if (!text || typing) return;
  inp.value = "";

  addHistory("user", text);
  history.push({ role: "user", content: text });
  window.__history = history;      // 用户消息也要同步到全局，否则存档规则读到的是旧长度
  // 等待提示也用字模渲染，避免冒出系统字体
  if (window.gdiRenderMsg) {
    stopReveal();
    gdiRenderMsg("「……」", $("msgText"), 56, 1200, 1);
    $("msgText").classList.add("gdi");
  } else {
    $("msgText").textContent = "「……」";
  }
  hidePageCursor();

  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify((function () {
    let act = {};
    try { act = JSON.parse(localStorage.getItem("app_active_model") || "{}"); } catch (e) {}
    // 不写死模型: 只有用户在设置里明确选过才传, 否则由后端用 DEFAULT_MODEL
      // 注意：整段历史都发给后端 —— 裁剪/记忆书由后端按 token 预算决定（前端不砍）
      const body = { messages: history.map(function (m) { return { role: m.role, content: m.content }; }) };
      if (act.model) body.model = act.model;
    if (act.url) body.base_url = act.url;
    // 让后端做一次剧本检索：和这句话相关的「原作里发生过的事」会单独拼进 system
    body.memory = true;
    // 当前背景一并带上：模型只说地点没说时间时，新场景沿用现在的时段（白天/晚上）
    if (currentBg) body.bg = currentBg;
    return body;
  })()),
    });
    const d = await r.json();
    if (d && d.usage) { try { renderCost(d.usage); } catch (e) {} }
    if (d.error) { $("msgText").textContent = "[错误] " + d.error; return; }
    const reply = (d.reply || "").trim();
      const replyZh = (d.reply_zh || "").trim();
      const actZh = (d.action_zh || "").trim();
  window.__lastEmo = (d.emotion || "").trim();   // 服务端给的情绪标签
  window.__nextScene = (d.bg || "").trim();      // 服务端已按文件名标签匹配好；没匹配上就是空
  window.__nextOutfit = (d.outfit || "").trim(); // 只有明确换衣服才有值
  window.__lastThinking = (d.thinking || "").trim();
  window.__lastAction = (d.action_zh || d.action || "").trim();
  renderThinking();
    history.push({ role: "assistant", content: reply });
    window.__history = history;
    window.__lastReply = reply;
    window.__lastReplyZh = replyZh;
    // 对话框显示中文（有译文用译文），历史记录也显示中文
    const shown = replyZh ? ("「" + replyZh.replace(/^「|」$/g, "") + "」") : reply;
    window.__speakJa = replyZh ? reply.replace(/^「|」$/g, "") : "";
    /* 中日对照：content 保留语言模型原句（含 action/emotion 未过滤），zh 存翻译模型原样输出 */
    history[history.length - 1].zh = replyZh;
    addHistory("assistant", shown, reply);   /* 第三参：日文原句，只存不显示 */
    // 先合成语音；语音没准备好就先不出文字，等语音出来一起出
    speakReply(reply).then(() => {
      // 场景/服装只在模型明确标记时才切，且与文字同一时刻出现
      const _want = window.__nextOutfit || "";
      if (window.__nextScene) { setBg(window.__nextScene); window.__nextScene = ""; }
      window.__nextOutfit = "";
      setSpriteByScene(currentBg || "classroom", mood, true, _want);
      showReply(shown);
    });

    const mood = detectMood(shown);
    // 立绘表情随情绪变，服装与场景只在模型明确标记时切换
    accumulateMood(reply);            // BGM 按累积氛围切换，不随单句变

    sessionSave();          // 自动存档
    turnCount++;
  } catch (e) {
    $("msgText").textContent = "[网络错误] " + e.message;
  }
}

/* 标题 BGM: 首次交互后播放 */
let titleBgmStarted = false;
function playTitleBgm() {
  if (titleBgmStarted) return;
  titleBgmStarted = true;
  setBgm("menu", 400);
}
document.addEventListener("pointerdown", function once(e) {
  if ($("titleScreen").classList.contains("active")) playTitleBgm();
}, { once: false });

/* ---------- 菜单 ---------- */
$("mainMenu").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  playSE("click");
  const act = btn.dataset.act;
  if (act === "quit") { if (confirm("要结束游戏吗？")) window.close(); return; }
        if (act === "continue") {
          if (window.__openScreen) window.__openScreen("save", "load");
          return;
        }
        if (act === "config") { if (window.__openOptions) window.__openOptions(); return; }
        if (act === "special") { if (window.__openSpecial) window.__openSpecial(); return; }

    /* 进游戏前关掉所有浮层（统一走 screens.js，别在这里各自 remove("show")） */
  if (window.__closeScreens) window.__closeScreens();
  showScreen("gameScreen");
  titleBgmStarted = true;
  setBg("classroom");
  setSpriteByScene("classroom", "cold", true);
  gdiRenderName(CHAR_NAME, $("namePlate"));
  setBgm("calm", 600);
  if (window.__wantRestore) {
    window.__wantRestore = false;
    sessionRestore().then(function (ok) {
      if (!ok) setTimeout(() => { typewriter("「……有事？」"); }, 200);
    });
  } else {
    // 开始游戏 = 新对话：清空历史与自动存档
    history = [];
    window.__history = history;
    try { rebuildBacklog(); } catch (e) {}   /* 新游戏：回想清空 */
    try {
      fetch("/api/session/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot: "auto", messages: [], meta: {} })
      }).catch(function () {});
    } catch (e) {}
    setTimeout(() => { typewriter("「……有事？」"); }, 460);
  }
  setTimeout(() => $("input").focus(), 700);
});

$("mainMenu").addEventListener("mouseover", (e) => {
  if (e.target.closest("button")) playSE("hover");
});

(function () {
  const b = $("cfgBtn");
  if (b) b.addEventListener("click", () => {
    playSE("click");
    if (window.__openScreen) window.__openScreen("opt");
  });
})();

($("sendBtn")||{addEventListener:function(){}}).addEventListener("click", send);
($("input")||{addEventListener:function(){}}).addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); send(); }
});
/* 回标题：菜单「返回标题」和 ESC 共用 */
function backToTitle() {
  playSE("cancel");
  showScreen("titleScreen");
  toggleBacklog(false);
  $("choiceScreen").classList.remove("show");
  titleBgmStarted = false;
  setBgm("menu", 800);
}

($("backBtn")||{addEventListener:function(){}}).addEventListener("click", backToTitle);

/* ESC：对话界面直接回标题（回想 / 浮层先各自关掉，不抢） */
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (backlogOpen) return;
  if (window.__optOpen) return;
  if (window.__isScreenOpen && window.__isScreenOpen()) return;
  var gs = $("gameScreen");
  if (!gs || !gs.classList.contains("active")) return;
  backToTitle();
});

($("msgBox")||{addEventListener:function(){}}).addEventListener("click", () => {
  if (typing) { stopReveal(); updatePageCursor(); return; }   // 打字途中点一下 = 立刻显示整句
  nextPage();          // 还有下一页就翻页
});

/* 工具栏 */
document.querySelectorAll("#toolbar .tb").forEach(el => {
  el.addEventListener("click", () => {
    const a = el.dataset.act;
    if (a === "save")  window.__openScreen && window.__openScreen("save", "save");
    if (a === "load")  window.__openScreen && window.__openScreen("save", "load");
    /* 快速存档 / 快速读档：暂不实现（按钮先提示一下，避免误以为打开的是存档界面） */
    if (a === "qsave") { if (window.__saveHint) window.__saveHint("快速存档暂未开放"); return; }
    if (a === "qload") { if (window.__saveHint) window.__saveHint("快速读档暂未开放"); return; }
        if (a === "config") { window.__openOptions && window.__openOptions(); return; }
    if (a === "rew")   toggleBacklog(true);          // 浏览本次对话历史
    if (a === "close") {
      /* 右下角那个 ✕ = 隐藏窗口（只留 CG 与立绘），和右键「隐藏窗口」同一套；
         再点一次右键或这个按钮就回来 */
      document.body.classList.toggle("uiHidden");
      return;
    }
  });
  el.addEventListener("mouseenter", () => {
    playSE("hover");
    $("tbHint").textContent = el.dataset.tip ? "▶ " + el.dataset.tip : "";
  });
  el.addEventListener("mouseleave", () => { $("tbHint").textContent = ""; });
  el.addEventListener("click", () => {
    playSE("click");
    if (el.dataset.act === "log") toggleBacklog();
    if (el.dataset.act === "bgm") {
      bgmEnabled = !bgmEnabled;
      if (!bgmEnabled) bgmAudio.pause(); else setBgm(currentBgm || "calm", 300);
      el.style.opacity = bgmEnabled ? "1" : ".4";
    }
  });
});

/* 键盘 */
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "c") showChoices();
  if (e.key === "l" || e.key === "L") toggleBacklog();
  if (e.key === "Escape") toggleBacklog(false);
});






/* ---------- 思考显示开关 ---------- */
function thinkOn() {
  return localStorage.getItem("app_show_think") === "1";
}

function renderThinking() {
  const box = $("thinkBox");
  const btn = $("thinkBtn");
  const on = thinkOn();
  if (btn) {
  var v = btn.querySelector("img.val");
  var k = on ? "log_act_onv" : "log_act_offv";
  if (v && v.dataset.baked !== k) { v.dataset.baked = k; v.src = "assets/ui/text/" + k + ".png"; }
  }
  if (!box) return;
  const act = (window.__lastAction || "").trim();
  const t = (window.__lastThinking || "").trim();
  const body = act || t;
  if (on && body) {
    // 模型有时自己带了（）/「」，先剥掉再统一包一层
    var clean = body.replace(/^[（(【\[]+/, "").replace(/[）)】\]]+$/, "").trim();
    box.textContent = "（" + clean + "）";
    // 文字越长字号越小，保证不超出左上角区域
    const L = body.length;
    const fs = L <= 40 ? 9 : L <= 80 ? 8 : L <= 140 ? 7 : 6.2;
    box.style.fontSize = fs + "px";
    box.style.webkitLineClamp = L <= 40 ? 7 : L <= 80 ? 8 : 9;
    box.classList.remove("hidden");
  } else {
    box.textContent = "";
    box.classList.add("hidden");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const btn = $("thinkBtn");
  if (btn) {
    btn.addEventListener("click", function () {
      localStorage.setItem("app_show_think", thinkOn() ? "0" : "1");
      renderThinking();
    });
  }
  renderThinking();
});


/* ---------- 按钮三态: 松开时闪现第三帧 ---------- */
document.addEventListener("DOMContentLoaded", function () {
  (function bakeSend() {
    var b = document.getElementById("sendBtn");
    if (b && b.dataset.baked !== "log_send") {
      b.dataset.baked = "log_send";
      b.innerHTML = '<img src="assets/ui/text/log_send.png" alt="">';
    }
  })();
  ["thinkBtn", "sendBtn"].forEach(function (id) {
    const b = document.getElementById(id);
    if (!b) return;
    b.addEventListener("pointerup", function () {
      b.classList.add("released");
      setTimeout(function () { b.classList.remove("released"); }, 130);
    });
  });
});


/* ===================== 历史对话面板 ===================== */
const HIST_THUMB_RATIO = 0.158;
let histMaxTop = 1, histTopGap = 3, histBottomGap = 5;   // 滑块占滑条高度比例（游戏实测 176/1366）

function syncHistThumb() {
  const list = $("historyList"), thumb = $("hsThumb"), track = $("hsTrack");
  if (!list || !thumb || !track) return;
  const trackH = track.clientHeight || 1;
  // 滑块长度固定，按轨道高度算，不随内容变化
  const fixedH = Math.max(18, Math.round(trackH * HIST_THUMB_RATIO));
  thumb.style.height = fixedH + "px";
  const thumbH = fixedH;
  histTopGap = 3; histBottomGap = 5;   // 底部留白（游戏实测 16px@2730 ≈ 4.7px@450）
  histMaxTop = Math.max(1, trackH - thumbH - histBottomGap - histTopGap);
  const scrollable = Math.max(0, list.scrollHeight - list.clientHeight);
  // 内容不足一屏时停在顶部
  // 打开即最新: 内容不足一屏时滑块也停在底部
  const ratio = scrollable > 2 ? Math.min(1, Math.max(0, list.scrollTop / scrollable)) : 1;
  thumb.style.top = Math.round(histTopGap + histMaxTop * ratio) + "px";
  /* 内容不足一屏时不允许拖动 */
  if (scrollable > 2) delete thumb.dataset.nodrag; else thumb.dataset.nodrag = "1";
  thumb.style.display = "block";
}

(function initHistory() {
  const list = $("historyList");
  if (list) list.addEventListener("scroll", syncHistThumb);

  // 上下箭头
  document.querySelectorAll("#historyScroll .hsArrow").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dir = parseInt(btn.dataset.dir || "1", 10);
      if (list) list.scrollTop += dir * (list.clientHeight * 0.85);
      playSE("click");
    });
  });

  // 拖动滑块
  const thumb = $("hsThumb"), track = $("hsTrack");
  if (thumb && track) {
    let dragging = false, startY = 0, startTop = 0;
    thumb.addEventListener("mousedown", (e) => {
      if (thumb.dataset.nodrag === "1") return;      /* 内容不足一屏：不给拖 */
      dragging = true; startY = e.clientY;
      startTop = Math.max(0, parseInt(thumb.style.top || "0", 10) - histTopGap);
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging || !list) return;
      const maxTop = histMaxTop;
      // 滑块位移 -> 文本滚动量：同样的位移，内容越多滚得越多
      const scrollable = Math.max(0, list.scrollHeight - list.clientHeight);
      let top = Math.min(maxTop, Math.max(0, startTop + (e.clientY - startY)));
      thumb.style.top = (histTopGap + top) + "px";
      list.scrollTop = (top / maxTop) * scrollable;
    });
    window.addEventListener("mouseup", () => { dragging = false; });
  }

  // 轨道点击翻页
  if (track) {
    track.addEventListener("click", (e) => {
      if (e.target.closest("#hsThumb") || !list) return;
      const r = track.getBoundingClientRect();
      list.scrollTop += (e.clientY < r.top + r.height / 2 ? -1 : 1) * list.clientHeight * 0.85;
    });
  }

  // EXIT 返回
  const ex = $("historyExit");
  if (ex) ex.addEventListener("click", () => toggleBacklog(false));

  window.addEventListener("resize", syncHistThumb);
})();

/* 启动时问一次语音模型是否可用：可用 → 和纱的回想图标是白气泡（可重播），否则用灰气泡 */
(function probeVoice() {
  fetch("/api/voice/ok", { cache: "no-store" })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      window.__voiceOk = !!(d && d.ok);
      try { rebuildBacklog(); } catch (e) {}
    })
    .catch(function () { window.__voiceOk = false; });
})();
/* 内容淡入淡出：换页/换标签时统一走这里，时长和实机一致（约 0.2s 出 + 0.2s 入） */

/* 回想（历史对话）面板滚轮翻动时播翻页音 */
(function () {
  function attach() {
    var box = document.getElementById("historyBox") || document.getElementById("blogList") ||
              document.getElementById("histBox") || document.querySelector(".historyBox");
    if (!box || box.dataset.seWheel) return;
    box.dataset.seWheel = "1";
    var acc = 0;
    box.addEventListener("wheel", function (e) {
      acc += Math.abs(e.deltaY);
      if (acc < 60) return;          /* 累积一点再响，避免一滑响一串 */
      acc = 0;
      try { if (window.playSE) window.playSE("page"); } catch (err) {}
    }, { passive: true });
  }
  document.addEventListener("DOMContentLoaded", attach);
  window.addEventListener("load", attach);
  setInterval(attach, 1500);
})();

/* 回想：已经翻到最底部时继续往下滚 = 直接退出回想（原版手感） */
(function () {
  var panel = document.getElementById("historyPanel");
  if (!panel) return;
  panel.addEventListener("wheel", function (e) {
    if (!backlogOpen || e.deltaY <= 0) return;
    var list = document.getElementById("historyList");
    if (!list) return;
    /* 还差 1px 以内都算到底（子像素滚动会差一点点） */
    if (list.scrollTop + list.clientHeight < list.scrollHeight - 1) return;
    toggleBacklog(false);
    e.preventDefault();
  }, { passive: false });
})();

/* ---------- 音量总控：BGM / 语音 / 音效都乘上主音量 ----------
   注意这里必须用模块内的 bgmAudio / ttsAudio：
   之前写的是 window.__bgmAudio / window.__voiceAudio，那两个变量从来没被赋值过，
   所以「全体音量」「BGM」「VOICE」三个滑块都没有实际效果。 */
window.__applyVolumes = function () {
  var bv = 0, vv = 0;
  try { bv = bgmVolume(); } catch (e) {}
  try { vv = voiceVolume(); } catch (e) {}
  try { bgmAudio.volume = bv; } catch (e) {}
  try { if (ttsAudio) ttsAudio.volume = vv; } catch (e) {}
  window.__volBgm = bv;
  window.__volVoice = vv;
};
window.__applyVolumesV2 = true;
document.addEventListener("DOMContentLoaded", function () {
  try { window.__applyVolumes(); } catch (e) {}
});

/* ---------- 界面显示（OPTION 1 的「窗口」那几项） ----------
   窗口透明度（普通场景）：只淡 UI 底图（对话框发光框 / 输入栏底框 / 按钮底板），
     字模（正文、名字、占位符、按钮标签）保持原样 —— 通过 CSS 变量 --ui-alpha 控制；
   窗口 ON / OFF：整块显示/隐藏（连字一起），这是有意的。 */
window.__applyUiPrefs = function () {
  var P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
  var on = (P.winVisible === undefined) ? true : !!P.winVisible;
  var a = (P.winAlpha === undefined) ? 100 : P.winAlpha;
  a = Math.max(0, Math.min(100, a)) / 100;
  try { document.documentElement.style.setProperty("--ui-alpha", String(a)); } catch (e) {}
  ["msgWrap", "inputBar"].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (on) {
      el.style.removeProperty("opacity");
      el.style.removeProperty("pointer-events");
    } else {
      el.style.setProperty("opacity", "0", "important");
      el.style.setProperty("pointer-events", "none", "important");
    }
  });
  document.body.classList.toggle("dlgHidden", !on);
};
window.addEventListener("app:prefs", function () {
  try { window.__applyUiPrefs(); } catch (e) {}
});
document.addEventListener("DOMContentLoaded", function () {
  try { window.__applyUiPrefs(); } catch (e) {}
});

/* 窗口 / 全屏：和标题栏那条路一样走后端 pywebview 开关（不是浏览器 Fullscreen API） */
window.__setWinMode = function (mode) {
  var on = (mode === "full") ? "1" : "0";
  try {
    fetch("/api/window?action=fullscreen&on=" + on, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        try { if (window.__dbg) window.__dbg("WINMODE", mode + " " + JSON.stringify(d).slice(0, 36)); } catch (e) {}
        /* 后端可能退回最大化，界面高亮要跟真实状态走 */
        if (d && d.ok && typeof d.fullscreen === "boolean" && window.__ct1SetWinModeUI) {
          window.__ct1SetWinModeUI(d.fullscreen);
        }
      })
      .catch(function () {});
  } catch (e) {}
};

/* 一组元素做淡出→改动→淡入（切标签页/切存档页时用，和实机一致约 0.2s） */
/* 换页动画（按原版观感实现）：
   旧页：向内收缩 + 虚化 + 变透明
   新页：从略大开始，向内收缩同时由透明迅速实化
   总时长默认 390ms（与翻页音 SE_9213 等长） */

/* ---------- 滑鼠右键功能（OPTION 2 设置项） ----------
   三种模式：hide = 隐藏所有界面只留 CG/立绘；options = 打开设置；save = 打开存档
   只在「对话界面」生效：浮层（设置 / 存读档 / 回想 / 特别模式）开着时，右键 = 关掉当前这一层，
   不再顺带触发下面的隐藏窗口，否则两个界面会同时响应同一个右键。 */
document.addEventListener("contextmenu", function (e) {
  // 输入框上仍然保留浏览器默认（方便复制粘贴）
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
  e.preventDefault();
  /* 隐藏状态下右键 = 先把界面叫回来（不管右键功能设的是哪一项） */
  if (document.body.classList.contains("uiHidden")) {
    document.body.classList.remove("uiHidden");
    return;
  }

  /* 浮层开着：右键只负责退出这一层（等同右下角 EXIT） */
  if (window.__closeTopScreen && window.__closeTopScreen()) {
    if (window.__dbg) window.__dbg("RMB", "close-screen");
    return;
  }
  /* 回想面板不是 .uiScreen，单独收一下 */
  if (backlogOpen) {
    toggleBacklog(false);
    return;
  }

  var mode = "save";
  try {
    var P = (window.App && window.App.getPrefs) ? window.App.getPrefs() : {};
    if (P.rightClick) mode = P.rightClick;
  } catch (err) {}

  if (window.__dbg) window.__dbg("RMB", mode);

  if (mode === "hide") {
    document.body.classList.toggle("uiHidden");
    return;
  }
  if (mode === "options") {
    try { if (window.__openOptions) window.__openOptions(); } catch (err) {}
    return;
  }
  try { if (window.__openScreen) window.__openScreen("save", "save"); } catch (err) {}
});

/* ---------- 滚轮上滑：对话界面直接打开回想 ----------
   只在对话界面响应（和右键一样）：标题画面、隐藏窗口、任意浮层（设置 / 存读档 / 回想 /
   特别模式）开着的时候都不抢；回想已经开着时滚轮交给面板自己翻。 */
document.addEventListener("wheel", function (e) {
  if (!(e.deltaY < 0)) return;                                      /* 只认上滑 */
  if (backlogOpen) return;
  if (document.body.classList.contains("uiHidden")) return;
  /* 调试面板里滚日志不该弹回想 */
  if (e.target && e.target.closest && e.target.closest("#dbgPanel")) return;
  var gs = $("gameScreen");
  if (!gs || !gs.classList.contains("active")) return;              /* 只在对话界面 */
  if (window.__isScreenOpen && window.__isScreenOpen()) return;     /* 浮层开着不抢 */
  toggleBacklog(true);
  e.preventDefault();
}, { passive: false });

/* ---------- 右下角：本条 / 累计 token 与花费 ----------
   文案与 0~9 都是烤好的字模（tools/bake_cost_ui.py），这里只负责拼图，
   不再请求 /api/text —— 那个渲染器是中文网格，拉丁字母会被撑开。 */
var COST_EL = {};
function costNum(el, str) {
  if (!el) return;
  if (el.dataset.v === str) return;
  el.dataset.v = str;
  var html = "";
  for (var i = 0; i < str.length; i++) {
    var ch = str.charAt(i);
    var key = (ch === ".") ? "cost_dot" : ("cost_d" + ch);
    html += '<img src="assets/ui/text/' + key + '.png" alt="">';
  }
  el.innerHTML = html;
}

/* 金额转成"纯数字串"（币种符号已经是一张固定的 ¥ 图） */
function moneyStr(v) {
  v = Number(v) || 0;
  if (v === 0) return "0";
  if (v < 0.01) return v.toFixed(6);
  if (v < 1) return v.toFixed(4);
  return v.toFixed(3);
}

function renderCost(u) {
  if (!u) return;
  if (u.tokens !== undefined) {
    costNum(COST_EL.nowT, String(Math.round(u.tokens)));
    costNum(COST_EL.nowC, moneyStr(u.cost));
  }
  costNum(COST_EL.totT, String(Math.round(u.cumTokens || 0)));
  costNum(COST_EL.totC, moneyStr(u.cumCost));
}
window.__renderCost = renderCost;

/* 只刷新累计（程序启动时、以及后台总结之后） */
window.__refreshCost = function () {
  try {
    fetch("/api/usage", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok) renderCost({ cumTokens: d.tokens, cumCost: d.cost });
      })
      .catch(function () {});
  } catch (e) {}
};

document.addEventListener("DOMContentLoaded", function () {
  COST_EL.nowT = document.getElementById("costNowT");
  COST_EL.nowC = document.getElementById("costNowC");
  COST_EL.totT = document.getElementById("costTotalT");
  COST_EL.totC = document.getElementById("costTotalC");
  window.__refreshCost();
  setInterval(function () { window.__refreshCost(); }, 20000);
});

/* 隐藏窗口后，左键点一下画面就恢复 ——
   此时 UI 全是 pointer-events:none，点事件落在底层元素上，所以监听在 document 捕获阶段。
   右键不走这里（交给上面的 contextmenu，避免"恢复界面"和"右键功能"同时触发）。 */
document.addEventListener("click", function (e) {
  if (!document.body.classList.contains("uiHidden")) return;
  document.body.classList.remove("uiHidden");
  e.preventDefault();
  e.stopPropagation();   /* 只负责"叫回界面"，不要顺带翻页 */
}, true);

/* 隐藏界面：只留背景与立绘
   注意选择器必须对得上真实 ID：#menubar / .dialogBox / #quickBar 这三个在 DOM 里根本不存在
   （菜单栏是 #menuBar，对话框是 #msgWrap），所以之前「隐藏窗口」只隐藏了底部工具栏。 */
(function () {
  var css = document.createElement("style");
  css.textContent =
    "body.uiHidden #msgWrap,body.uiHidden #inputBar,body.uiHidden #toolbar," +
    "body.uiHidden #menuBar,body.uiHidden #glowBottom,body.uiHidden #historyPanel," +
    "body.uiHidden #thinkBox,body.uiHidden #choiceScreen,body.uiHidden #costBar," +
    "body.uiHidden .uiScreen," +
    "body.uiHidden #dbgPanel{" +
    "opacity:0!important;pointer-events:none!important}";
  document.head.appendChild(css);
})();

/* ---------- 角色名：存在 char/name.txt，特别模式里改的就是它 ---------- */
window.__setCharName = function (n) {
  if (!n) return;
  CHAR_NAME = n;
  window.__charName = n;
  var el = document.getElementById("namePlate");
  if (el && typeof gdiRenderName === "function") gdiRenderName(n, el);
  // 输入框占位符等跟着名字变（uitext.js 监听）
  try {
    document.dispatchEvent(new CustomEvent("wa2:charname", { detail: n }));
  } catch (e) {}
};
fetch("/api/special/name", { cache: "no-store" })
  .then(function (r) { return r.json(); })
  .then(function (d) { if (d && d.ok && d.name) window.__setCharName(d.name); })
  .catch(function () {});