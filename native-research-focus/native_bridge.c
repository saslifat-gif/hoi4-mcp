/* Build-pinned HOI4 native bridge. Initial stage observes the script thread only.
 * No keyboard, mouse, window messages or direct gameplay-field setters.
 * The sole hook is the verified CLogScriptEffect execution vtable entry. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#pragma comment(lib,"bcrypt.lib")
static HMODULE own_module;
static uintptr_t image;
static char sid[33];
static wchar_t root[MAX_PATH];
static volatile LONG initialized=0;
static void (*original_log)(void*,void*);
static DWORD script_thread;
static const char expected_sha[]="7dc947be34970da1e1c787bcddbe7f62b610ff258aebf8f06aa8b348f3a031d5";
static int readable(const void *p,SIZE_T n){
 MEMORY_BASIC_INFORMATION m;
 if(!p || !n || (uintptr_t)p+n<(uintptr_t)p || !VirtualQuery(p,&m,sizeof m))return 0;
 return m.State==MEM_COMMIT && !(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)) &&
        (uintptr_t)p+n<=(uintptr_t)m.BaseAddress+m.RegionSize;
}
static int hex_id(const char *s){
 if(strlen(s)!=32)return 0;
 for(int i=0;i<32;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return 0;
 return 1;
}
static void path(wchar_t *out,const wchar_t *name){swprintf(out,MAX_PATH,L"%ls\\%ls",root,name);}
static int write_atomic(const wchar_t *name,const char *data){
 wchar_t dest[MAX_PATH],tmp[MAX_PATH];path(dest,name);swprintf(tmp,MAX_PATH,L"%ls.pending",dest);
 HANDLE f=CreateFileW(tmp,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 0;
 DWORD done=0,n=(DWORD)strlen(data);BOOL ok=WriteFile(f,data,n,&done,NULL)&&done==n;
 if(ok)ok=FlushFileBuffers(f);CloseHandle(f);
 if(ok)ok=MoveFileExW(tmp,dest,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
 if(!ok)DeleteFileW(tmp);return ok;
}
static int module_hash_matches(void){
 wchar_t exe[MAX_PATH];if(!GetModuleFileNameW(NULL,exe,MAX_PATH))return 0;
 HANDLE f=CreateFileW(exe,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 0;
 BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;DWORD len=0,got=0;unsigned char digest[32],buf[65536];void *object=NULL;int ok=0;
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0)goto end;
 if(BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,(PUCHAR)&len,sizeof len,&got,0)<0)goto end;
 object=HeapAlloc(GetProcessHeap(),0,len);if(!object)goto end;
 if(BCryptCreateHash(alg,&hash,object,len,NULL,0,0)<0)goto end;
 for(;;){if(!ReadFile(f,buf,sizeof buf,&got,NULL))goto end;if(!got)break;if(BCryptHashData(hash,buf,got,0)<0)goto end;}
 if(BCryptFinishHash(hash,digest,sizeof digest,0)<0)goto end;
 char hex[65];for(int i=0;i<32;i++)sprintf(hex+2*i,"%02x",digest[i]);hex[64]=0;ok=strcmp(hex,expected_sha)==0;
 end:if(hash)BCryptDestroyHash(hash);if(object)HeapFree(GetProcessHeap(),0,object);if(alg)BCryptCloseAlgorithmProvider(alg,0);CloseHandle(f);return ok;
}
static int literal(void *effect,char *out,size_t cap){
 /* CLogScriptEffect's std::string is at +0x58, observed in its native parser/executor. */
 unsigned char *s=(unsigned char*)effect+0x58;
 if(!readable(s,32))return 0;
 uint64_t n=*(uint64_t*)(s+16),capacity=*(uint64_t*)(s+24);
 if(n==0 || n>=cap || capacity<n || capacity>65536)return 0;
 const char *text=capacity>15?*(const char**)s:(const char*)s;
 if(!readable(text,(SIZE_T)n+1)||text[n])return 0;
 memcpy(out,text,(size_t)n);out[n]=0;return 1;
}
static void observe(void *scope){
 /* Native CLogScriptEffect calls this exact scope accessor when logging country context. */
 const uint32_t *tag=((const uint32_t*(*)(void*))(image+0x537fb0))(scope);
 if(!readable(tag,4)||!*tag)return;
 uintptr_t country=((uintptr_t(*)(const uint32_t*))(image+0xbb48f0))(tag);
 uintptr_t world=*(uintptr_t*)(image+0x332f260);
 if(!readable((void*)country,0x1390)||!readable((void*)world,0x528))return;
 if(*(uint32_t*)(country+8)!=*tag)return;
 uintptr_t tech=*(uintptr_t*)(country+0xf60),progress=*(uintptr_t*)(country+0x1380),tree=*(uintptr_t*)(country+0x1370);
 if(!readable((void*)tech,0xb0)||!readable((void*)progress,0x40))return;
 int slots=*(int*)(tech+0xac),models=*(int*)(tech+0x94);
 if(slots<1||slots>16||models<1||models>10000)return;
 DWORD tid=GetCurrentThreadId();if(script_thread&&script_thread!=tid)return;script_thread=tid;
 char out[2048];snprintf(out,sizeof out,
  "{\"stage\":\"script_thread_observed\",\"session_id\":\"%s\",\"pid\":%lu,\"thread_id\":%lu,\"country_tag\":%u,\"country\":\"0x%llx\",\"world\":\"0x%llx\",\"technology_status\":\"0x%llx\",\"research_slots\":%d,\"technology_models\":%d,\"focus_tree\":\"0x%llx\",\"focus_progress\":\"0x%llx\",\"active_focus\":\"0x%llx\",\"focus_elapsed_raw\":%lld,\"uses_keyboard_or_mouse\":false,\"selection_commands_enabled\":false}",
  sid,(unsigned long)GetCurrentProcessId(),(unsigned long)tid,*tag,(unsigned long long)country,(unsigned long long)world,(unsigned long long)tech,slots,models,(unsigned long long)tree,(unsigned long long)progress,(unsigned long long)*(uintptr_t*)(progress+0x10),(long long)*(int64_t*)(progress+0x18));
 /* Only the selection module owns the command-enabled handshake. */
 write_atomic(L"native-probe-observation.json",out);
}
static void log_hook(void *effect,void *scope){
 original_log(effect,scope);
 if(initialized!=1)return;
 __try{
  char text[512],prefix[128];
  snprintf(prefix,sizeof prefix,"CODEX_COMMAND_SESSION|%s|LIVE|country=GER",sid);
  if(literal(effect,text,sizeof text)&&strcmp(text,prefix)==0)observe(scope);
 }__except(EXCEPTION_EXECUTE_HANDLER){
  initialized=2;
  write_atomic(L"native-error.json","{\"error\":\"native_observation_exception\",\"selection_commands_enabled\":false}");
 }
}
__declspec(dllexport) DWORD WINAPI Initialize(LPVOID unused){
 (void)unused;if(initialized)return 10;
 DWORD n=GetModuleFileNameW(own_module,root,MAX_PATH);if(!n||n>=MAX_PATH)return 11;
 wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 12;*slash=0;if(wcslen(root)>180)return 12;
 wchar_t cfg[MAX_PATH];path(cfg,L"session-id.txt");HANDLE f=CreateFileW(cfg,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 13;
 DWORD got=0;BOOL ok=ReadFile(f,sid,33,&got,NULL);CloseHandle(f);
 if(!ok||got!=32)return 14;sid[32]=0;if(!hex_id(sid))return 15;
 if(!module_hash_matches())return 16;
 image=(uintptr_t)GetModuleHandleW(NULL);
 void **slot=(void**)(image+0x29b73d8+13*8);
 original_log=(void(*)(void*,void*))(image+0x1393df0);
 if(!readable(slot,sizeof *slot)||*slot!=(void*)original_log)return 17;
 DWORD previous=0,ignored=0;
 if(!VirtualProtect(slot,sizeof *slot,PAGE_READWRITE,&previous))return 18;
 void *was=InterlockedCompareExchangePointer(slot,(void*)log_hook,(void*)original_log);
 VirtualProtect(slot,sizeof *slot,previous,&ignored);
 if(was!=(void*)original_log)return 19;
 initialized=1;
 write_atomic(L"native-initialized.json","{\"stage\":\"hook_installed\",\"selection_commands_enabled\":false,\"uses_keyboard_or_mouse\":false}");
 return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved){
 (void)reserved;if(reason==DLL_PROCESS_ATTACH){own_module=module;DisableThreadLibraryCalls(module);}return TRUE;
}
