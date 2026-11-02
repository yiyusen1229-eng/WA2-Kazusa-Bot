# -*- coding: utf-8 -*-
"""界面快照：逐个界面存「计算样式指纹 + 截图」，用来验证改 CSS 后视觉没变。

为什么不用肉眼/单张截图：game450.css 里同一个选择器被反复覆盖，删错一条
可能只在某个界面的某个 hover 状态下才看出来。这里把**所有元素**的
getComputedStyle 哈希下来，前后两次一一对比；再配一张截图兜底。

用法（先起后端）：
    python tools/ui_snap.py --url http://127.0.0.1:8791/game/index.html --out snap_before
    # 改完 CSS 再跑一次
    python tools/ui_snap.py --url http://127.0.0.1:8791/game/index.html --out snap_after
    python tools/ui_snap.py --diff snap_before snap_after

约定：
  · 只读不改：存读档接口用桩顶掉，不写 sessions/
  · 隐藏飘雪层（位置是随机数），否则每次截图都不一样
"""
import argparse
import ctypes
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import webview                     # noqa: E402
from PIL import Image, ImageChops  # noqa: E402
import ui_probe as UP              # noqa: E402  （复用它的窗口查找与截图）

# 每个界面：名字 / 打开动作 / 等多久（毫秒）
PREP = """
window.__snapPrep = function () {
  if (!window.__snapReady) {
    window.__snapReady = true;
    window.__origFetch = window.fetch.bind(window);
    window.fetch = function (u, o) {
      var url = String((u && u.url) || u);
      if (url.indexOf('/api/session/') >= 0) {
        return Promise.resolve(new Response(
          JSON.stringify({ok: true, slots: []}),
          {status: 200, headers: {'Content-Type': 'application/json'}}));
      }
      return window.__origFetch(u, o);
    };
    /* 关掉所有过渡/动画：截图时必须是最终状态，不能停在淡入中途。
       标题栏（#menuBar）会自己隐藏/弹出，热区还会因为鼠标状态变化，
       一并藏掉，否则每次截图它都不一样。 */
    var st = document.createElement('style');
    st.id = '__snapNoAnim';
    st.textContent = '*{transition:none !important;animation:none !important;}' +
      '#menuBar,#mbHotZone,#cfgPanel,#dbgPanel,#scaleReadout,#__BUILDSTAMP' +
      '{display:none !important;}';
    document.head.appendChild(st);
  }
  var snow = document.getElementById('snowLayer');
  if (snow) snow.style.display = 'none';
  var mb = document.querySelector('.menuBar');
  if (mb) mb.classList.add('mbHidden');
};

/* 可见的图片（字模、立绘、背景）都加载完了吗 */
window.__snapImagesReady = function () {
  var imgs = document.querySelectorAll('img');
  for (var i = 0; i < imgs.length; i++) {
    var im = imgs[i];
    if (!im.getBoundingClientRect().width) continue;
    if (!im.complete) return false;
  }
  return true;
};
"""

STEPS = [
    # 打开开屏之后的标题画面
    ("title", """
(function(){
  window.__snapPrep();
  try { if (window.__endIntro) window.__endIntro(); } catch (e) {}
  try { window.__closeScreens && window.__closeScreens(); } catch (e) {}
  document.querySelectorAll('.screen').forEach(function (s) { s.classList.remove('active'); });
  var t = document.getElementById('titleScreen');
  if (t) t.classList.add('active');
  return true;
})()
""", 1500),

    # 进游戏：点「开始游戏」，等背景/立绘/名字牌都出来
    ("game", """
(function(){
  window.__snapPrep();
  var b = document.querySelector('[data-act="start"]');
  if (b) b.click();
  return true;
})()
""", 2200),

    # 读档界面（存读档列表用桩，永远 10 个空槽）
    ("save", """
(function(){
  window.__snapPrep();
  try { window.__closeScreens && window.__closeScreens(); } catch (e) {}
  if (window.__openScreen) window.__openScreen('save', 'load');
  return true;
})()
""", 1200),

    # 回想（塞两条固定记录，别依赖运行时历史）
    ("blog", """
(function(){
  window.__snapPrep();
  window.__history = [
    {role: 'assistant', content: '「……你来了。」'},
    {role: 'assistant', content: '「别站在那儿，坐吧。」'}
  ];
  try { window.__closeScreens && window.__closeScreens(); } catch (e) {}
  if (window.__openScreen) window.__openScreen('blog');
  return true;
})()
""", 1200),

    # 设置（OPTION 1 默认页）
    ("option", """
(function(){
  window.__snapPrep();
  try { window.__closeScreens && window.__closeScreens(); } catch (e) {}
  if (window.__openOptions) window.__openOptions();
  return true;
})()
""", 1400),

    # 特别模式
    ("special", """
(function(){
  window.__snapPrep();
  try { window.__closeScreens && window.__closeScreens(); } catch (e) {}
  if (window.__openSpecial) window.__openSpecial();
  return true;
})()
""", 1400),
]

FINGERPRINT_JS = """
(function () {
  var PROPS = ['display','position','top','left','right','bottom','width','height',
    'min-width','max-width','min-height','max-height','margin-top','margin-right',
    'margin-bottom','margin-left','padding-top','padding-right','padding-bottom',
    'padding-left','border-top-width','border-right-width','border-bottom-width',
    'border-left-width','border-top-color','border-bottom-color','border-radius',
    'background-color','background-image','background-position','background-size',
    'background-repeat','color','font-family','font-size','font-weight','line-height',
    'letter-spacing','text-align','text-shadow','opacity','transform','filter',
    'box-shadow','z-index','overflow','overflow-y','flex-direction','flex-wrap',
    'align-items','justify-content','gap','visibility','white-space'];
  function hash(s) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h.toString(16);
  }
  function path(el) {
    var parts = [];
    while (el && el.nodeType === 1) {
      var i = 1, n = el;
      while ((n = n.previousElementSibling)) i++;
      parts.push(el.tagName + ':' + i);
      el = el.parentElement;
    }
    return parts.reverse().join('/');
  }
  var out = {};
  var all = document.querySelectorAll('*');
  for (var k = 0; k < all.length; k++) {
    var el = all[k], cs = getComputedStyle(el), s = '';
    /* 只记「当前真的在渲染」的元素：display:none 的元素没有布局盒，
       它们的 width/height 会随加载时机变，却根本不影响画面 */
    if (!el.getClientRects().length) continue;
    for (var j = 0; j < PROPS.length; j++) {
      s += PROPS[j] + '=' + cs.getPropertyValue(PROPS[j]) + ';';
    }
    out[path(el)] = hash(s);
  }
  return out;
})()
"""


def _park_cursor():
    """把鼠标挪到屏幕左上角：不然窗口里停在哪个按钮上，hover 状态每次都不一样"""
    try:
        ctypes.windll.user32.SetCursorPos(0, 0)
    except Exception:
        pass


def run(url, outdir, title, width, height):
    os.makedirs(outdir, exist_ok=True)
    report = {}

    def runner(window):
        try:
            for _ in range(80):
                time.sleep(0.25)
                try:
                    if window.evaluate_js("document.readyState") == "complete":
                        break
                except Exception:
                    pass
            time.sleep(1.2)
            window.evaluate_js(PREP)

            for name, js, wait in STEPS:
                _park_cursor()
                try:
                    window.evaluate_js(js)
                except Exception as e:
                    report[name] = {"error": "setup: %s" % e}
                    continue
                time.sleep(max(0, wait) / 1000.0)
                # 等可见图片全部加载完（字模是逐张请求的，早了会量到 0 宽）
                for _ in range(30):
                    try:
                        if window.evaluate_js("window.__snapImagesReady()"):
                            break
                    except Exception:
                        pass
                    time.sleep(0.1)
                time.sleep(0.2)
                try:
                    styles = window.evaluate_js(FINGERPRINT_JS)
                except Exception as e:
                    styles = {}
                    report.setdefault(name, {})["fingerprint_error"] = str(e)
                shot = os.path.join(outdir, name + ".png")
                hwnd = UP.find_window(title)
                size = None
                if hwnd:
                    _park_cursor()
                    try:
                        size = UP.grab(hwnd, shot)
                    except Exception as e:
                        report.setdefault(name, {})["shot_error"] = str(e)
                rec = report.get(name) or {}
                rec["styles"] = styles
                rec["shot"] = os.path.basename(shot) if size else ""
                rec["size"] = size
                report[name] = rec
        finally:
            try:
                window.destroy()
            except Exception:
                pass

    win = webview.create_window(title, url, width=width, height=height)
    webview.start(runner, win, private_mode=True, debug=False)
    with open(os.path.join(outdir, "snap.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)
    print("快照写入 %s：%d 个界面" % (outdir, len(report)))


def diff(a_dir, b_dir):
    """对比两次快照：计算样式指纹 + 截图像素"""
    a = json.load(open(os.path.join(a_dir, "snap.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(b_dir, "snap.json"), encoding="utf-8"))
    bad = 0
    for name in sorted(set(a) | set(b)):
        ra, rb = a.get(name) or {}, b.get(name) or {}
        sa, sb = ra.get("styles") or {}, rb.get("styles") or {}
        changed = [k for k in sa if k in sb and sa[k] != sb[k]]
        added = [k for k in sb if k not in sa]
        removed = [k for k in sa if k not in sb]
        pix = None
        pa = os.path.join(a_dir, ra.get("shot") or "")
        pb = os.path.join(b_dir, rb.get("shot") or "")
        if ra.get("shot") and rb.get("shot") and os.path.exists(pa) and os.path.exists(pb):
            ia = Image.open(pa).convert("RGB")
            ib = Image.open(pb).convert("RGB")
            if ia.size == ib.size:
                # 跳过窗口标题栏：那是系统的，会随窗口激活状态变色，不算界面
                top = min(70, ia.height)
                d = ImageChops.difference(ia.crop((0, top, ia.width, ia.height)),
                                          ib.crop((0, top, ib.width, ib.height))).convert("L")
                mask = d.point(lambda v: 255 if v > 8 else 0)
                pix = sum(1 for p in mask.getdata() if p)
            else:
                pix = "size %s vs %s" % (ia.size, ib.size)
        ok = not (changed or added or removed) and (pix in (0, None))
        if not ok:
            bad += 1
        print("%-8s 样式差异 %-4d 新增 %-3d 删除 %-3d 像素差异 %s %s" %
              (name, len(changed), len(added), len(removed),
               pix, "OK" if ok else "◀ 有变化"))
        for k in changed[:5]:
            print("    ~ %s" % k)
    print("\n%s" % ("全部一致" if not bad else "%d 个界面有变化" % bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description="界面快照 / 对比（真实 WebView2）")
    ap.add_argument("--url")
    ap.add_argument("--out")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--title", default="WA2 Snap")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()
    if args.diff:
        return diff(*args.diff)
    if not args.url or not args.out:
        ap.error("要么给 --url/--out，要么给 --diff")
    run(args.url, args.out, args.title, args.width, args.height)
    return 0


if __name__ == "__main__":
    sys.exit(main())
