// 复刻汉化组的字体方案: 32x32 字形图集 + 逐字贴图
(function () {
  const ATLAS_VER = 6;     // 每次重建图集必须 +1, 否则浏览器用缓存
  let CELL = 32;          // 源格大小(由 map.json 决定, 实际 64)
  const DEST = 20;        // 舞台像素尺寸
  const DSF = 1.6;        // 舞台 -> 屏幕 缩放比, 用于高分辨率位图
  const SCALE = 0.625;          // 1280 原生 -> 800 舞台
  let atlas = null, map = null, loading = null;

  function load() {
    if (loading) return loading;
    loading = Promise.all([
      fetch("assets/font/map.json?v=" + ATLAS_VER, { cache: "no-store" }).then(r => r.json()),
      new Promise((res, rej) => {
        const img = new Image();
        img.onload = () => res(img);
        img.onerror = rej;
        img.src = "assets/font/atlas.png?v=" + ATLAS_VER;
      }),
    ]).then(([m, img]) => { map = m; atlas = img; CELL = m.cell || 32; return true; })
      .catch(() => { loading = null; return false; });
    return loading;
  }

  // 折行: 按像素宽度
  function wrap(text, maxW) {
    const k = DEST / CELL;
    const lines = [];
    let cur = "", w = 0;
    for (const ch of text) {
      if (ch === "\n") { lines.push(cur); cur = ""; w = 0; continue; }
      const a = (map.adv[ch] || CELL) * k;
      if (w + a > maxW && cur) { lines.push(cur); cur = ""; w = 0; }
      cur += ch; w += a;
    }
    if (cur || !lines.length) lines.push(cur);
    return lines;
  }

  // 渲染到 canvas
  function draw(el, text, opts) {
    opts = opts || {};
    const size = opts.size || 32;
    const maxW = opts.maxW || 832;
    const lineGap = opts.lineGap || 0;
    const outline = opts.outline === undefined ? 2 : opts.outline;
    const lh = DEST + lineGap;

    const lines = wrap(text, maxW);
    const cw = Math.min(maxW, Math.max(...lines.map(l => {
      let w = 0; for (const ch of l) w += (map.adv[ch] || CELL) * DEST / CELL; return w;
    }))) + outline * 2 + 2;
    const ch2 = lh * lines.length + outline * 2 + 2;

    const cv = document.createElement("canvas");
    // 位图按屏幕分辨率(DSF 倍), CSS 尺寸按舞台像素 -> 图集 32px 字形 1:1 映射到屏幕
    cv.width = Math.max(1, Math.ceil(cw * DSF));
    cv.height = Math.max(1, Math.ceil(ch2 * DSF));
    const g = cv.getContext("2d");
    g.setTransform(DSF, 0, 0, DSF, 0, 0);
    g.imageSmoothingEnabled = true;

    const drawLine = (line, x0, y0, tint) => {
      let x = x0;
      for (const ch of line) {
        const m = map.map[ch];
        if (m) {
          const sx = m[0] * CELL, sy = m[1] * CELL;
          if (tint) {
            // 用特殊合成画暗色描边
            g.save();
            g.globalCompositeOperation = "source-over";
            g.drawImage(atlas, sx, sy, CELL, CELL, x, y0, DEST, DEST);
            g.restore();
          } else {
            g.drawImage(atlas, sx, sy, CELL, CELL, x, y0, DEST, DEST);
          }
        }
        x += (map.adv[ch] || CELL) * DEST / CELL;
      }
    };

    // 描边: 8 方向偏移画暗色
    if (outline > 0) {
      const tmp = document.createElement("canvas");
      tmp.width = cv.width; tmp.height = cv.height;
      const tg = tmp.getContext("2d");
      tg.setTransform(DSF, 0, 0, DSF, 0, 0);
      tg.imageSmoothingEnabled = true;
      lines.forEach((line, i) => {
        let x = outline;
        for (const ch of line) {
          const m = map.map[ch];
          if (m) tg.drawImage(atlas, m[0] * CELL, m[1] * CELL, CELL, CELL, x, outline + i * lh, DEST, DEST);
          x += (map.adv[ch] || CELL) * DEST / CELL;
        }
      });
      // 把字形染成描边色并模糊扩散
      tg.globalCompositeOperation = "source-in";
      tg.fillStyle = opts.outlineColor || "rgb(12,36,62)";
      tg.fillRect(0, 0, tmp.width, tmp.height);
      for (let d = 0; d < outline; d++) {
        g.drawImage(tmp, 0, 0, tmp.width, tmp.height, -d - 1, 0, cw, ch2);
        g.drawImage(tmp, 0, 0, tmp.width, tmp.height, d + 1, 0, cw, ch2);
        g.drawImage(tmp, 0, 0, tmp.width, tmp.height, 0, -d - 1, cw, ch2);
        g.drawImage(tmp, 0, 0, tmp.width, tmp.height, 0, d + 1, cw, ch2);
      }
    }

    // 白色主体
    lines.forEach((line, i) => drawLine(line, outline, outline + i * lh, false));

    el.innerHTML = "";
    el.appendChild(cv);
    cv.style.cssText = "display:block;width:" + Math.ceil(cw) + "px;height:" + Math.ceil(ch2) + "px;";
    return true;
  }

  window.__atlasReady = load;
  window.__renderAtlasText = function (el, text, opts) {
    if (atlas && map) { draw(el, text, opts); return Promise.resolve(true); }
    return load().then(ok => { if (!ok) return false; draw(el, text, opts); return true; });
  };
})();
