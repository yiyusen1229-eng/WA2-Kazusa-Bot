// d3d9.dll 代理 —— 记录游戏通过 GetProcAddress 动态解析的函数
// 编译: cl /LD /O2 /Fe:d3d9.dll d3d9_proxy.c /link /MACHINE:X86 user32.lib
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef void * (WINAPI *pDirect3DCreate9)(UINT);

static HMODULE g_real = NULL;
static FILE *g_log = NULL;
static CRITICAL_SECTION g_cs;
static FARPROC (WINAPI *real_GetProcAddress)(HMODULE, LPCSTR) = NULL;

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

static FARPROC WINAPI hook_GetProcAddress(HMODULE m, LPCSTR name)
{
    if (name && (strstr(name, "Font") || strstr(name, "Text") || strstr(name, "Glyph")))
        logf_("GetProcAddress(\"%s\")", name);
    return real_GetProcAddress(m, name);
}

// 扫描主模块导入表, 替换 kernel32!GetProcAddress
static void patch_iat(void)
{
    HMODULE self = GetModuleHandleA(NULL);
    if (!self) return;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)self;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)((BYTE *)self + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)((BYTE *)self + dir.VirtualAddress);
    if (!dir.Size) return;
    for (; imp->Name; ++imp) {
        const char *dll = (const char *)((BYTE *)self + imp->Name);
        if (_stricmp(dll, "kernel32.dll") != 0) continue;
        IMAGE_THUNK_DATA *thunk = (IMAGE_THUNK_DATA *)((BYTE *)self + imp->FirstThunk);
        for (; thunk->u1.Function; ++thunk) {
            PROC *slot = (PROC *)&thunk->u1.Function;
            FARPROC cur = (FARPROC)*slot;
            if ((HMODULE)cur == GetModuleHandleA("kernel32.dll")) continue;
            // 用导出名判断
            char buf[MAX_PATH];
            if (!GetModuleFileNameA((HMODULE)cur, buf, MAX_PATH)) continue;
            // 简单做法: 逐个比对 GetProcAddress 的地址
            if (cur == (FARPROC)GetProcAddress) {
                DWORD old;
                VirtualProtect(slot, sizeof(PROC), PAGE_READWRITE, &old);
                real_GetProcAddress = (FARPROC (WINAPI *)(HMODULE, LPCSTR))cur;
                *slot = (PROC)hook_GetProcAddress;
                VirtualProtect(slot, sizeof(PROC), old, &old);
                logf_("patched IAT GetProcAddress");
            }
        }
    }
}

__declspec(dllexport) void * WINAPI Direct3DCreate9(UINT version)
{
    if (!g_real) {
        char sys[MAX_PATH];
        GetSystemDirectoryA(sys, MAX_PATH);
        strcat_s(sys, MAX_PATH, "\\d3d9.dll");
        g_real = LoadLibraryA(sys);
    }
    pDirect3DCreate9 fn = (pDirect3DCreate9)GetProcAddress(g_real, "Direct3DCreate9");
    logf_("Direct3DCreate9(%u)", version);
    return fn ? fn(version) : NULL;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        InitializeCriticalSection(&g_cs);
        char path[MAX_PATH];
        GetModuleFileNameA(h, path, MAX_PATH);
        char *p = strrchr(path, '\\');
        if (p) *(p + 1) = 0;
        strcat_s(path, MAX_PATH, "wa2_api_log.txt");
        fopen_s(&g_log, path, "w");
        logf_("=== d3d9 proxy attached ===");
        patch_iat();
    }
    return TRUE;
}
