# -*- coding: utf-8 -*-
import re

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\ui2\opt.js"
s = open(P, encoding="utf-8").read()

# 1) 标签页选中态 + 底栏 BGM 名
anchor = '    const lab = $("optPageLabel");'
assert anchor in s, "找不到 optPageLabel 行"

patch = '''    // 标签页选中态
    document.querySelectorAll(".optTabs .t").forEach(function (t, i) {
      t.classList.toggle("on", i === page);
    });
    // 底栏左侧显示当前 BGM 名
    var fl = document.getElementById("optFootL");
    if (fl) {
      var nm = (window.__bgmTitle && window.__bgmTitle()) || "Extended Winter";
      fl.textContent = nm;
    }
'''

if "标签页选中态" not in s:
    s = s.replace(anchor, patch + anchor, 1)

# 2) 标签尺寸
s = s.replace('{ left: "437px", right: "auto", top: "47px", width: "328px", height: "15px" }',
              '{ left: "430px", right: "auto", top: "44px", width: "340px", height: "42px" }')

open(P, "w", encoding="utf-8").write(s)
print("opt.js 已更新")
print("含标签高亮:", "标签页选中态" in s)
