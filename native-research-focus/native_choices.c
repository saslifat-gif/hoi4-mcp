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
#include <stdarg.h>
#pragma comment(lib,"bcrypt.lib")
static HMODULE own_module;
static uintptr_t image;
static char sid[33];
static wchar_t root[MAX_PATH];
static volatile LONG initialized=0;
static void (*original_log)(void*,void*);

static DWORD expected_thread;
static uintptr_t bound_world;
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

static int native_name(uintptr_t p,size_t offset,char *out,size_t cap){
 unsigned char *v=(unsigned char*)(p+offset);if(!readable(v,32))return 0;
 uint64_t n=*(uint64_t*)(v+16),c=*(uint64_t*)(v+24);if(!n||n>=cap||c<n||c>65536)return 0;
 const char *t=c>15?*(const char**)v:(const char*)v;if(!readable(t,n+1)||t[n])return 0;
 for(size_t i=0;i<n;i++)if(!((t[i]>='a'&&t[i]<='z')||(t[i]>='A'&&t[i]<='Z')||(t[i]>='0'&&t[i]<='9')||t[i]=='_'))return 0;
 memcpy(out,t,n);out[n]=0;return 1;
}
static void choice_error(const char *rid,const char *reason){
 wchar_t n[80];swprintf(n,80,L"choices-%hs.json",rid);char b[512];
 snprintf(b,sizeof b,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"error\",\"reason\":\"%s\"}",sid,rid,reason);write_atomic(n,b);
}
static int append(char *b,size_t cap,size_t *used,const char *fmt,...){
 va_list args;va_start(args,fmt);int n=vsnprintf(b+*used,cap-*used,fmt,args);va_end(args);
 if(n<0||(size_t)n>=cap-*used)return 0;*used+=(size_t)n;return 1;
}
#include "native_construction.h"
static void capture_choices(void *scope,const char *rid){
 if(GetCurrentThreadId()!=expected_thread){choice_error(rid,"unexpected_game_thread");return;}
 const uint32_t *tag=((const uint32_t*(*)(void*))(image+0x537fb0))(scope);
 if(!readable(tag,4)||!*tag){choice_error(rid,"invalid_scope");return;}
 uintptr_t country=((uintptr_t(*)(const uint32_t*))(image+0xbb48f0))(tag),world=*(uintptr_t*)(image+0x332f260);
 if(!readable((void*)country,0x1390)||!readable((void*)world,0x500)||*(uint32_t*)(country+8)!=*tag){choice_error(rid,"invalid_world");return;}
 if(bound_world&&world!=bound_world){choice_error(rid,"world_changed");return;}bound_world=world;
 uintptr_t tech=*(uintptr_t*)(country+0xf60),tree=*(uintptr_t*)(country+0x1370),progress=*(uintptr_t*)(country+0x1380);
 if(!readable((void*)tech,0xb0)||!readable((void*)tree,0x40)||!readable((void*)progress,0x20)){choice_error(rid,"invalid_country_data");return;}
 int models=*(int*)(tech+0x94),slots=*(int*)(tech+0xac),focuses=*(int*)(tree+0x3c);
 uintptr_t ma=*(uintptr_t*)(tech+0x88),sa=*(uintptr_t*)(tech+0xa0),fa=*(uintptr_t*)(tree+0x30);
 if(models<1||models>10000||slots<1||slots>16||focuses<1||focuses>1000||!readable((void*)ma,models*8)||!readable((void*)sa,slots*8)||!readable((void*)fa,focuses*8)||*(uintptr_t*)tree!=image+0x2739bb8){choice_error(rid,"invalid_catalog");return;}
 char *b=HeapAlloc(GetProcessHeap(),0,2*1024*1024);if(!b){choice_error(rid,"allocation_failed");return;}
 size_t cap=2*1024*1024,used=0;int ok=1;char name[160];int empty=0;
 ok&=append(b,cap,&used,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"validated\",\"pid\":%lu,\"thread_id\":%lu,\"world\":\"0x%llx\",\"native_tick\":%d,\"empty_research_slots\":[",sid,rid,(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long long)world,*(int*)(world+0x468));
 for(int i=0;i<slots;i++){
  uintptr_t sl=*(uintptr_t*)(sa+8*i);if(!readable((void*)sl,0x20)){ok=0;break;}
  if(!*(uintptr_t*)(sl+0x18)){ok&=append(b,cap,&used,"%s%d",empty?",":"",i+1);empty++;}
 }
 ok&=append(b,cap,&used,"],\"research\":[");
 for(int i=0;ok&&i<models;i++){
  uintptr_t m=*(uintptr_t*)(ma+i*8);if(!readable((void*)m,0x1f8)||*(uintptr_t*)m!=image+0x2974ee0||*(uintptr_t*)(m+0x158)!=tech){ok=0;break;}
  uintptr_t d=*(uintptr_t*)(m+0x160);if(!readable((void*)d,0x48)||*(uintptr_t*)d!=image+0x293c2e0||*(int*)(d+0x38)!=i+1||!native_name(d,0x10,name,sizeof name)){ok=0;break;}
  int allowed=((unsigned char(*)(void*,void*,unsigned char))(image+0xed8f00))((void*)tech,(void*)d,0)!=0;
  int guard=*(unsigned char*)(d+0x40)&&!*(unsigned char*)(m+0x1e8);
  ok&=append(b,cap,&used,"%s{\"id\":\"%s\",\"engine_allowed\":%s,\"backend_guard_allowed\":%s,\"available\":%s}",i?",":"",name,allowed?"true":"false",guard?"true":"false",allowed&&guard&&empty?"true":"false");
 }
 int busy=*(uintptr_t*)(progress+0x10)!=0;
 ok&=append(b,cap,&used,"],\"focus_busy\":%s,\"focuses\":[",busy?"true":"false");
 for(int i=0;ok&&i<focuses;i++){
  uintptr_t f=*(uintptr_t*)(fa+i*8);if(!readable((void*)f,0x168)||*(uintptr_t*)f!=image+0x2739c08||*(uintptr_t*)(f+0x160)!=tree||!native_name(f,0x18,name,sizeof name)){ok=0;break;}
  /* This exact validator reads only +0x28/+0x30 and handles its own
     temporary native diagnostic string. No factory, execute or gameplay setter. */
  __declspec(align(16)) unsigned char cmd[0x40]={0};
  *(uintptr_t*)cmd=image+0x2996458;*(uint32_t*)(cmd+0x28)=*tag;*(uintptr_t*)(cmd+0x30)=f;
  int allowed=((unsigned char(*)(void*))(image+0x1166830))(cmd)!=0;
  ok&=append(b,cap,&used,"%s{\"id\":\"%s\",\"engine_allowed\":%s,\"available\":%s}",i?",":"",name,allowed?"true":"false",allowed&&!busy?"true":"false");
 }
 ok&=append(b,cap,&used,"]");
 if(ok)ok=capture_capacity(b,cap,&used,world,*tag);
 ok&=append(b,cap,&used,",\"uses_keyboard_or_mouse\":false}");
 if(ok){wchar_t file[80];swprintf(file,80,L"choices-%hs.json",rid);write_atomic(file,b);}
 else choice_error(rid,"catalog_validation_failed");HeapFree(GetProcessHeap(),0,b);
}
static void log_hook(void *effect,void *scope){
 original_log(effect,scope);if(initialized!=1)return;
 char rid[33]={0};
 __try{
  char text[512],prefix[128];snprintf(prefix,sizeof prefix,"CODEX_PEACETIME|%s|",sid);
  size_t n=strlen(prefix);
  if(!literal(effect,text,sizeof text))return;
  char action[128];snprintf(action,sizeof action,"CODEX_NATIVE_CONSTRUCT|%s|",sid);
  if(!strncmp(text,action,strlen(action))){construct_native(scope,text+strlen(action));return;}
  if(strncmp(text,prefix,n)||strlen(text)<n+39)return;
  memcpy(rid,text+n,32);rid[32]=0;if(!hex_id(rid)||strncmp(text+n+32,"|BEGIN|",7))return;
  capture_choices(scope,rid);
 }__except(EXCEPTION_EXECUTE_HANDLER){initialized=2;if(hex_id(rid))choice_error(rid,"native_validation_exception");}
}
__declspec(dllexport) DWORD WINAPI Initialize(LPVOID unused){
 (void)unused;if(initialized)return 10;
 DWORD n=GetModuleFileNameW(own_module,root,MAX_PATH);if(!n||n>=MAX_PATH)return 11;
 wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 12;*slash=0;if(wcslen(root)>180)return 12;
 wchar_t cfg[MAX_PATH];path(cfg,L"session-id.txt");HANDLE f=CreateFileW(cfg,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 13;
 DWORD got=0;BOOL ok=ReadFile(f,sid,33,&got,NULL);CloseHandle(f);
 if(!ok||got!=32)return 14;sid[32]=0;if(!hex_id(sid))return 15;
 wchar_t thread_file[MAX_PATH];path(thread_file,L"expected-thread.txt");
 HANDLE tf=CreateFileW(thread_file,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(tf==INVALID_HANDLE_VALUE)return 20;char tb[32]={0};DWORD tn=0;
 BOOL tok=ReadFile(tf,tb,31,&tn,NULL);CloseHandle(tf);
 if(!tok||sscanf(tb,"%lu",&expected_thread)!=1||!expected_thread)return 21;
 if(!module_hash_matches())return 16;
 image=(uintptr_t)GetModuleHandleW(NULL);
 if(!initialize_buildings())return 22;
 void **slot=(void**)(image+0x29b73d8+13*8);
 original_log=(void(*)(void*,void*))(image+0x1393df0);
 if(!readable(slot,sizeof *slot))return 17;
 MEMORY_BASIC_INFORMATION m;wchar_t actual[MAX_PATH],expected[MAX_PATH];path(expected,L"hoi4-native-selection.dll");
 if(!VirtualQuery(*slot,&m,sizeof m)||!GetModuleFileNameW((HMODULE)m.AllocationBase,actual,MAX_PATH)||_wcsicmp(actual,expected))return 17;
 original_log=(void(*)(void*,void*))*slot;
 DWORD previous=0,ignored=0;
 if(!VirtualProtect(slot,sizeof *slot,PAGE_READWRITE,&previous))return 18;
 void *was=InterlockedCompareExchangePointer(slot,(void*)log_hook,(void*)original_log);
 VirtualProtect(slot,sizeof *slot,previous,&ignored);
 if(was!=(void*)original_log)return 19;
 initialized=1;
 write_atomic(L"choices-initialized.json","{\"stage\":\"hook_installed\",\"selection_commands_enabled\":false,\"uses_keyboard_or_mouse\":false}");
 return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved){
 (void)reserved;if(reason==DLL_PROCESS_ATTACH){own_module=module;DisableThreadLibraryCalls(module);}return TRUE;
}
