// gdi32.dll 代理 —— 记录游戏调用的字体相关 GDI 函数
// 编译: cl /LD /O2 /Fe:gdi32.dll gdi32_proxy.c
#include <windows.h>
#include <stdio.h>

static HMODULE g_real = NULL;
static FILE *g_log = NULL;
static CRITICAL_SECTION g_cs;

typedef HFONT (WINAPI *pCreateFontW)(int, int, int, int, int, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPCWSTR);
typedef HFONT (WINAPI *pCreateFontA)(int, int, int, int, int, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPCSTR);
typedef HFONT (WINAPI *pCreateFontIndirectW)(const LOGFONTW *);
typedef HGDIOBJ (WINAPI *pSelectObject)(HDC, HGDIOBJ);
typedef BOOL (WINAPI *pDeleteObject)(HGDIOBJ);
typedef COLORREF (WINAPI *pSetTextColor)(HDC, COLORREF);
typedef int (WINAPI *pSetBkMode)(HDC, int);
typedef BOOL (WINAPI *pTextOutW)(HDC, int, int, LPCWSTR, int);
typedef BOOL (WINAPI *pGetTextExtentPoint32W)(HDC, LPCWSTR, int, LPSIZE);
typedef DWORD (WINAPI *pGetGlyphOutlineW)(HDC, UINT, UINT, LPGLYPHMETRICS, DWORD, LPVOID, const MAT2 *);
typedef HGDIOBJ (WINAPI *pGetStockObject)(int);
typedef int (WINAPI *pGetDeviceCaps)(HDC, int);
typedef int (WINAPI *pEnumFontFamiliesExW)(HDC, LPLOGFONTW, FONTENUMPROCW, LPARAM, DWORD);

static pCreateFontW r_CreateFontW;
static pCreateFontA r_CreateFontA;
static pCreateFontIndirectW r_CreateFontIndirectW;
static pSelectObject r_SelectObject;
static pDeleteObject r_DeleteObject;
static pSetTextColor r_SetTextColor;
static pSetBkMode r_SetBkMode;
static pTextOutW r_TextOutW;
static pGetTextExtentPoint32W r_GetTextExtentPoint32W;
static pGetGlyphOutlineW r_GetGlyphOutlineW;
static pGetStockObject r_GetStockObject;
static pGetDeviceCaps r_GetDeviceCaps;
static pEnumFontFamiliesExW r_EnumFontFamiliesExW;

static void logf_(const char *fmt, ...)
{
    if (!g_log) return;
    EnterCriticalSection(&g_cs);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fputc('\n', g_log);
    fflush(g_log);
    LeaveCriticalSection(&g_cs);
}

static void wide_to_utf8(const WCHAR *w, char *out, int cap)
{
    if (!w) { out[0] = 0; return; }
    WideCharToMultiByte(CP_UTF8, 0, w, -1, out, cap, NULL, NULL);
}

static void load_real(void)
{
    if (g_real) return;
    char sys[MAX_PATH];
    GetSystemDirectoryA(sys, MAX_PATH);
    strcat_s(sys, MAX_PATH, "\\gdi32.dll");
    g_real = LoadLibraryA(sys);
    if (!g_real) return;
    r_CreateFontW = (pCreateFontW)GetProcAddress(g_real, "CreateFontW");
    r_CreateFontA = (pCreateFontA)GetProcAddress(g_real, "CreateFontA");
    r_CreateFontIndirectW = (pCreateFontIndirectW)GetProcAddress(g_real, "CreateFontIndirectW");
    r_SelectObject = (pSelectObject)GetProcAddress(g_real, "SelectObject");
    r_DeleteObject = (pDeleteObject)GetProcAddress(g_real, "DeleteObject");
    r_SetTextColor = (pSetTextColor)GetProcAddress(g_real, "SetTextColor");
    r_SetBkMode = (pSetBkMode)GetProcAddress(g_real, "SetBkMode");
    r_TextOutW = (pTextOutW)GetProcAddress(g_real, "TextOutW");
    r_GetTextExtentPoint32W = (pGetTextExtentPoint32W)GetProcAddress(g_real, "GetTextExtentPoint32W");
    r_GetGlyphOutlineW = (pGetGlyphOutlineW)GetProcAddress(g_real, "GetGlyphOutlineW");
    r_GetStockObject = (pGetStockObject)GetProcAddress(g_real, "GetStockObject");
    r_GetDeviceCaps = (pGetDeviceCaps)GetProcAddress(g_real, "GetDeviceCaps");
    r_EnumFontFamiliesExW = (pEnumFontFamiliesExW)GetProcAddress(g_real, "EnumFontFamiliesExW");
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        InitializeCriticalSection(&g_cs);
        load_real();
        char path[MAX_PATH];
        GetModuleFileNameA(h, path, MAX_PATH);
        char *p = strrchr(path, '\\');
        if (p) *(p + 1) = 0;
        strcat_s(path, MAX_PATH, "wa2_gdi_log.txt");
        fopen_s(&g_log, path, "w");
        logf_("=== gdi32 proxy attached ===");
    }
    return TRUE;
}

__declspec(dllexport) HFONT WINAPI CreateFontW(int h, int w, int esc, int ori, int wt,
        DWORD it, DWORD un, DWORD so, DWORD cs, DWORD op, DWORD cp, DWORD q, DWORD pf, LPCWSTR face)
{
    char f[256];
    wide_to_utf8(face, f, sizeof(f));
    logf_("CreateFontW  height=%d weight=%d charset=%lu quality=%lu face=\"%s\"",
          h, wt, cs, q, f);
    return r_CreateFontW ? r_CreateFontW(h, w, esc, ori, wt, it, un, so, cs, op, cp, q, pf, face) : NULL;
}

__declspec(dllexport) HFONT WINAPI CreateFontA(int h, int w, int esc, int ori, int wt,
        DWORD it, DWORD un, DWORD so, DWORD cs, DWORD op, DWORD cp, DWORD q, DWORD pf, LPCSTR face)
{
    logf_("CreateFontA  height=%d weight=%d charset=%lu quality=%lu face=\"%s\"",
          h, wt, cs, q, face ? face : "");
    return r_CreateFontA ? r_CreateFontA(h, w, esc, ori, wt, it, un, so, cs, op, cp, q, pf, face) : NULL;
}

__declspec(dllexport) HFONT WINAPI CreateFontIndirectW(const LOGFONTW *lf)
{
    char f[256];
    if (lf) wide_to_utf8(lf->lfFaceName, f, sizeof(f)); else f[0] = 0;
    if (lf) logf_("CreateFontIndirectW height=%d weight=%d charset=%d quality=%d face=\"%s\"",
                  lf->lfHeight, lf->lfWeight, lf->lfCharSet, lf->lfQuality, f);
    return r_CreateFontIndirectW ? r_CreateFontIndirectW(lf) : NULL;
}

__declspec(dllexport) BOOL WINAPI TextOutW(HDC dc, int x, int y, LPCWSTR s, int n)
{
    if (s && n > 0 && n < 200) {
        char buf[512];
        WideCharToMultiByte(CP_UTF8, 0, s, n, buf, sizeof(buf) - 1, NULL, NULL);
        int lim = n * 4; if (lim > (int)sizeof(buf) - 1) lim = (int)sizeof(buf) - 1;
        buf[lim] = 0;
        logf_("TextOutW    len=%d text=\"%s\"", n, buf);
    }
    return r_TextOutW ? r_TextOutW(dc, x, y, s, n) : FALSE;
}

__declspec(dllexport) BOOL WINAPI GetTextExtentPoint32W(HDC dc, LPCWSTR s, int n, LPSIZE sz)
{
    BOOL r = r_GetTextExtentPoint32W ? r_GetTextExtentPoint32W(dc, s, n, sz) : FALSE;
    return r;
}

__declspec(dllexport) HGDIOBJ WINAPI GetStockObject(int i)
{
    return r_GetStockObject ? r_GetStockObject(i) : NULL;
}

__declspec(dllexport) int WINAPI GetDeviceCaps(HDC dc, int i)
{
    return r_GetDeviceCaps ? r_GetDeviceCaps(dc, i) : 0;
}

__declspec(dllexport) HGDIOBJ WINAPI SelectObject(HDC dc, HGDIOBJ o)
{
    return r_SelectObject ? r_SelectObject(dc, o) : NULL;
}

__declspec(dllexport) BOOL WINAPI DeleteObject(HGDIOBJ o)
{
    return r_DeleteObject ? r_DeleteObject(o) : FALSE;
}

__declspec(dllexport) COLORREF WINAPI SetTextColor(HDC dc, COLORREF c)
{
    return r_SetTextColor ? r_SetTextColor(dc, c) : 0;
}

__declspec(dllexport) int WINAPI SetBkMode(HDC dc, int m)
{
    return r_SetBkMode ? r_SetBkMode(dc, m) : 0;
}

__declspec(dllexport) DWORD WINAPI GetGlyphOutlineW(HDC dc, UINT ch, UINT fmt,
        LPGLYPHMETRICS gm, DWORD cb, LPVOID buf, const MAT2 *m)
{
    logf_("GetGlyphOutlineW char=U+%04X", ch);
    return r_GetGlyphOutlineW ? r_GetGlyphOutlineW(dc, ch, fmt, gm, cb, buf, m) : GDI_ERROR;
}

__declspec(dllexport) int WINAPI EnumFontFamiliesExW(HDC dc, LPLOGFONTW lf,
        FONTENUMPROCW cb, LPARAM p, DWORD flags)
{
    return r_EnumFontFamiliesExW ? r_EnumFontFamiliesExW(dc, lf, cb, p, flags) : 0;
}
