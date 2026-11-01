/* 特别模式：外壳部分（顶栏 / 底栏 / EXIT / 雪花 logo）
 *
 * 这个界面以后要放的东西：
 *   · 上下文限制设置（窗口大小、每轮大概消耗多少 token 的参考值）
 *   · 角色配置（名称 / 立绘 / 提示词 / 世界书 / 常驻记忆书 / 语音参考音频）
 * 现在只做外框，结构和存读档、回想界面完全一致：
 *   .uiHead（顶栏图）/ .uiLogo（雪花）/ .uiFoot（底栏）/ .uiExit（右下角 EXIT）
 * 样式直接复用 screens-base.css，开关直接复用 screens.js 的
 * __showUIScreen / __hideUIScreen（互斥、层级、EXIT 都统一在那边管），
 * 这个文件只保留"特别模式"自己的入口。
 */
(function () {
  window.__openSpecial = function () {
    if (window.__showUIScreen) window.__showUIScreen("specialScreen");
  };

  window.__closeSpecial = function () {
    var s = document.getElementById("specialScreen");
    if (s && window.__hideUIScreen) window.__hideUIScreen(s);
  };
})();
