/* wt-sprite.js —— 立绘 / 服装 / 表情（从 game.js 搬出）
 *
 * 对外（WA2.sprite）：resolveOutfit / outfitOf / spritePath / setSpriteByScene /
 *                      reload / summary / index（衣服索引）
 * 兼容老调用：window.setSpriteByScene / resolveOutfit / outfitOf / spritePath /
 *             __reloadSprites / __spriteSummary 都指到这里
 *
 * 衣服名和文件名都是中文：characters/<角色>/portrait/<衣服名>/<表情名>.png
 */
(function () {
  var WA2 = window.WA2 = window.WA2 || {};
  var $ = (WA2.util && WA2.util.$) || function (id) { return document.getElementById(id); };

  var OUTFIT_BY_SCENE = {
    classroom: "高中·春秋JK制服",
    corridor: "高中·春秋JK制服",
    music: "舞台演出服",       // 练琴 / 演奏
    stage: "舞台演出服",
    street: "coda·常服（眼镜）",
    cafe: "coda·第二套常服",
    home: "婚后·居家服",
    night: "睡衣",
    dress: "礼服",
    yukata: "和服（浴衣）",
    winter: "高中·冬装",
    summer: "高中·夏季JK制服"
  };

  var SPRITE_INDEX = {};       // 衣服名 -> {code, label, default, emotions, variants}
  var currentSprite = null;

  function loadIndex(cb) {
    fetch("/api/character/sprite/index.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        Object.keys(SPRITE_INDEX).forEach(function (k) { delete SPRITE_INDEX[k]; });
        Object.assign(SPRITE_INDEX, (d && d.outfits) || {});
        if (cb) cb();
      })
      .catch(function () {});
  }
  loadIndex(null);

  /* 名字 / 旧编号 / label → index 里的衣服名（合并过的衣服有多个编号，都在 codes 里） */
  function resolveOutfit(v) {
    v = (v || "").trim();
    if (!v) return "";
    if (SPRITE_INDEX[v]) return v;
    for (var k in SPRITE_INDEX) {
      var o = SPRITE_INDEX[k] || {};
      if (o.code === v || o.label === v) return k;
      if (o.codes && o.codes.indexOf(v) >= 0) return k;
    }
    return "";
  }

  function outfitOf(scene) {
    var name = OUTFIT_BY_SCENE[scene];
    if (name && SPRITE_INDEX[name]) return name;
    /* 场景表没命中（或这套衣服没有立绘）：优先校服，再退到索引里的第一套 */
    var keys = Object.keys(SPRITE_INDEX);
    for (var i = 0; i < keys.length; i++) {
      var o = SPRITE_INDEX[keys[i]] || {};
      if (String(o.code || "") === "001") return keys[i];
    }
    return keys.length ? keys[0] : "";
  }

  // 程序情绪 → 立绘情绪（warm 用微笑）
  var MOOD_TO_EMO = { angry: "angry", sad: "sad", cold: "cold", smile: "smile", warm: "smile" };

  function spritePath(outfit, emotion) {
    var o = SPRITE_INDEX[outfit];
    if (!o) return "assets/kaz_cold.png";
    var emo = emotion ? (MOOD_TO_EMO[emotion] || emotion) : "";
    var u = function (name) {
      return "/api/character/sprite/" + encodeURIComponent(outfit) + "/" + encodeURIComponent(name);
    };
    if (emo && o.emotions && o.emotions[emo]) return u(o.emotions[emo]);
    // 该套衣服没有这个情绪 → 退到「认真」，再退到默认
    if (o.emotions && o.emotions.serious) return u(o.emotions.serious);
    return u(o.default);
  }

  /** 按场景切换服装 */
  function setSpriteByScene(scene, mood, force, wantOutfit) {
    // 服装以 WA2.state.outfit 为准；只有对话明确换衣服（wantOutfit）才改
    var cur = (WA2.state && WA2.state.outfit) || "";
    var outfit = resolveOutfit(wantOutfit) || resolveOutfit(cur) || outfitOf(scene) || "";
    var key = outfit + "|" + (mood || "");
    if (currentSprite === key && !force) return;
    if (WA2.state) WA2.state.outfit = outfit;
    var sp = $("sprite");
    if (!sp) return;
    sp.classList.remove("show");
    setTimeout(function () {
      /* 立绘缺图时别让画面留个破图标：藏起来、保留名字，提示一次 */
      sp.onerror = function () {
        sp.classList.remove("show");
        if (!window.__spriteWarned) {
          window.__spriteWarned = true;
          (window.__toast || function () {})("立绘缺失，先用文字继续", 2500);
        }
      };
      sp.src = spritePath(outfit, mood);
      sp.classList.add("show");
      currentSprite = key;
    }, 180);
  }

  /* 切换 / 新建角色之后重拉索引，再强制重画一次当前立绘 */
  function reload(scene, emo) {
    loadIndex(function () {
      currentSprite = "";
      try { setSpriteByScene(scene || "classroom", emo || "", true); } catch (e) {}
    });
  }

  function summary() {
  var outfits = 0, files = 0;
    for (var k in SPRITE_INDEX) {
      outfits++;
      var vs = (SPRITE_INDEX[k] || {}).variants || [];
      files += vs.length;
    }
    return outfits ? (outfits + " 套衣服 · " + files + " 张") : "";
  }

  WA2.sprite = {
    resolveOutfit: resolveOutfit,
    outfitOf: outfitOf,
    spritePath: spritePath,
    setSpriteByScene: setSpriteByScene,
    reload: reload,
    summary: summary,
    index: SPRITE_INDEX
  };

  // 兼容老调用点（game.js / menubar.js 直接用了这些全局名）
  window.__reloadSprites = function () { reload(window.__curBg || "classroom", window.__lastEmo || ""); };
  var _exp = {};
  var _names = ["loadIndex", "outfitOf", "reload", "resolveOutfit", "setSpriteByScene", "spritePath", "summary"];
  for (var _i = 0; _i < _names.length; _i++) {
    try { var _f = eval(_names[_i]); if (typeof _f === "function") { _exp[_names[_i]] = _f; window[_names[_i]] = _f; } } catch (e) {}
  }
  WA2.sprite = _exp;
  WA2.register("sprite", _exp);
  /* __export_all__ */
  ["loadIndex", "outfitOf", "reload", "resolveOutfit", "setSpriteByScene", "spritePath", "summary", "MOOD_TO_EMO", "OUTFIT_BY_SCENE", "SPRITE_INDEX", "WA2", "_exp", "_names", "cur", "currentSprite", "emo", "key", "keys", "name", "o", "outfit", "outfits", "sp", "u", "vs"].forEach(function (n) {
    try { var v = eval(n); if (v !== undefined) { window[n] = v; } } catch (e) {}
  });
})();

/* 兼容层（必须在 IIFE 之后）：special.js 用 __spriteSummary；面板统计读 WA2.sprite.index */
(function () {
  var s = window.WA2 && window.WA2.sprite;
  if (!s) { return; }
  s.index = window.SPRITE_INDEX || {};
  window.__spriteSummary = s.summary || function () { return ""; };
})();
