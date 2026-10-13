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
static uintptr_t bound_world;
static unsigned attempts;
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

static int native_name(uintptr_t object,size_t offset,char *out,size_t cap){
 unsigned char *s=(unsigned char*)(object+offset);if(!readable(s,32))return 0;
 uint64_t n=*(uint64_t*)(s+16),c=*(uint64_t*)(s+24);
 if(!n||n>=cap||n>c||c>65536)return 0;
 const char *v=c>15?*(const char**)s:(const char*)s;
 if(!readable(v,n+1)||v[n])return 0;
 for(size_t i=0;i<n;i++)if(!((v[i]>='a'&&v[i]<='z')||(v[i]>='A'&&v[i]<='Z')||(v[i]>='0'&&v[i]<='9')||v[i]=='_'))return 0;
 memcpy(out,v,n);out[n]=0;return 1;
}
static int read_file(const wchar_t *name,char *out,DWORD cap){
 wchar_t file[MAX_PATH];path(file,name);
 HANDLE f=CreateFileW(file,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 0;
 DWORD n=0;BOOL ok=ReadFile(f,out,cap-1,&n,NULL);CloseHandle(f);out[n]=0;
 return ok&&n&&n<cap-1;
}
static void receipt(const char *rid,const char *kind,const char *id,int slot,const char *stage,const char *reason){
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);
 char out[1024];snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"%s\",\"id\":\"%s\",\"slot\":%d,\"stage\":\"%s\",\"reason\":\"%s\",\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,kind,id,slot,stage,reason,(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void select_command(uintptr_t country,uintptr_t world,uintptr_t tech,uintptr_t progress,uintptr_t tree,uint32_t tag){
 char request[512],reqsid[33],rid[33],kind[16],id[160],extra;int slot;
 if(!read_file(L"request.txt",request,sizeof request))return;
 if(sscanf(request,"%32[a-f0-9]|%32[a-f0-9]|%15[a-z]|%159[A-Za-z0-9_]|%d%c",reqsid,rid,kind,id,&slot,&extra)!=5)return;
 if(!hex_id(rid)||strcmp(reqsid,sid)||(!strcmp(kind,"research")?0:strcmp(kind,"focus")))return;
 wchar_t rf[80],full[MAX_PATH];swprintf(rf,80,L"receipt-%hs.json",rid);path(full,rf);
 if(GetFileAttributesW(full)!=INVALID_FILE_ATTRIBUTES)return;
 if(attempts>=64){receipt(rid,kind,id,slot,"rejected","session_limit");return;}
 if(world!=bound_world||*(uint32_t*)(country+8)!=tag){receipt(rid,kind,id,slot,"rejected","world_changed");return;}
 uintptr_t target=0,model=0,slotptr=0;char name[160];int research=strcmp(kind,"research")==0;
 if(research){
  int n=*(int*)(tech+0x94),slots=*(int*)(tech+0xac);uintptr_t a=*(uintptr_t*)(tech+0x88),sa=*(uintptr_t*)(tech+0xa0);
  if(slot<1||slot>slots||!readable((void*)sa,slots*8)){receipt(rid,kind,id,slot,"rejected","invalid_slot");return;}
  slotptr=*(uintptr_t*)(sa+(slot-1)*8);
  if(!readable((void*)slotptr,0x40)||*(uintptr_t*)(slotptr+0x18)){receipt(rid,kind,id,slot,"rejected","slot_busy");return;}
  if(n<1||n>10000||!readable((void*)a,n*8))return;
  for(int i=0;i<n;i++){
   uintptr_t m=*(uintptr_t*)(a+i*8);if(!readable((void*)m,0x1f8)||*(uintptr_t*)m!=image+0x2974ee0||*(uintptr_t*)(m+0x158)!=tech)continue;
   uintptr_t d=*(uintptr_t*)(m+0x160);
   if(!readable((void*)d,0x48)||*(uintptr_t*)d!=image+0x293c2e0||*(int*)(d+0x38)!=i+1)continue;
   if(native_name(d,0x10,name,sizeof name)&&!strcmp(name,id)){target=d;model=m;break;}
  }
  if(target&&(!*(unsigned char*)(target+0x40)||*(unsigned char*)(model+0x1e8))){receipt(rid,kind,id,slot,"rejected","inactive_or_completed");return;}
 }else{
  if(slot!=0){receipt(rid,kind,id,slot,"rejected","invalid_slot");return;}
  if(*(uintptr_t*)(progress+0x10)){receipt(rid,kind,id,slot,"rejected","focus_busy");return;}
  if(!readable((void*)tree,0x40)||*(uintptr_t*)tree!=image+0x2739bb8)return;
  int n=*(int*)(tree+0x3c);uintptr_t a=*(uintptr_t*)(tree+0x30);if(n<1||n>1000||!readable((void*)a,n*8))return;
  for(int i=0;i<n;i++){
   uintptr_t f=*(uintptr_t*)(a+i*8);
   if(!readable((void*)f,0x168)||*(uintptr_t*)f!=image+0x2739c08||*(uintptr_t*)(f+0x160)!=tree)continue;
   if(native_name(f,0x18,name,sizeof name)&&!strcmp(name,id)){target=f;break;}
  }
 }
 if(!target){receipt(rid,kind,id,slot,"rejected","unknown_id");return;}
 /* Persist intent before any native allocation or execution. A crash is uncertain, never retried. */
 char intent[512];snprintf(intent,sizeof intent,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"execution_uncertain\"}",sid,rid);
 if(!write_atomic(rf,intent))return;
 attempts++;
 uintptr_t cmd=((uintptr_t(*)(void))(image+(research?0x11501b0:0x114fd80)))();
 if(!readable((void*)cmd,research?0x40:0x38)||*(uintptr_t*)cmd!=image+(research?0x2994f40:0x2996458)){receipt(rid,kind,id,slot,"rejected","factory_failed");return;}
 *(uint32_t*)(cmd+0x28)=tag;*(uintptr_t*)(cmd+0x30)=target;
 if(research){*(int*)(cmd+0x38)=slot-1;*(unsigned char*)(cmd+0x3c)=0;}
 int valid=((unsigned char(*)(void*))(image+(research?0x1166bc0:0x1166830)))((void*)cmd);
 if(!valid){receipt(rid,kind,id,slot,"rejected","native_rules_rejected");return;}
 ((void(*)(void*))(image+(research?0x115d2e0:0x115c670)))((void*)cmd);
 int verified=research?(*(uintptr_t*)(slotptr+0x18)==model):(*(uintptr_t*)(progress+0x10)==target);
 receipt(rid,kind,id,slot,verified?"selection_verified":"execution_uncertain",verified?"normal_native_selection":"postcondition_failed");
 /* At most 64 tiny native command allocations are retained until process exit.
    Their deleting-destructor ABI is not assumed by this experimental backend. */
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
 if(!bound_world)bound_world=world;
 select_command(country,world,tech,progress,tree,*tag);
 char out[2048];snprintf(out,sizeof out,
  "{\"stage\":\"script_thread_observed\",\"session_id\":\"%s\",\"pid\":%lu,\"thread_id\":%lu,\"country_tag\":%u,\"country\":\"0x%llx\",\"world\":\"0x%llx\",\"technology_status\":\"0x%llx\",\"research_slots\":%d,\"technology_models\":%d,\"focus_tree\":\"0x%llx\",\"focus_progress\":\"0x%llx\",\"active_focus\":\"0x%llx\",\"focus_elapsed_raw\":%lld,\"uses_keyboard_or_mouse\":false,\"selection_commands_enabled\":true}",
  sid,(unsigned long)GetCurrentProcessId(),(unsigned long)tid,*tag,(unsigned long long)country,(unsigned long long)world,(unsigned long long)tech,slots,models,(unsigned long long)tree,(unsigned long long)progress,(unsigned long long)*(uintptr_t*)(progress+0x10),(long long)*(int64_t*)(progress+0x18));
 write_atomic(L"native-observation.json",out);
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
  write_atomic(L"native-error.json","{\"error\":\"native_observation_exception\",\"selection_commands_enabled\":true}");
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
 if(!readable(slot,sizeof *slot))return 17;
 if(*slot!=(void*)original_log){
  MEMORY_BASIC_INFORMATION m;wchar_t existing[MAX_PATH],expected[MAX_PATH];
  path(expected,L"hoi4-native-probe.dll");
  if(!VirtualQuery(*slot,&m,sizeof m)||!GetModuleFileNameW((HMODULE)m.AllocationBase,existing,MAX_PATH)||_wcsicmp(existing,expected))return 17;
  original_log=(void(*)(void*,void*))*slot;
 }
 DWORD previous=0,ignored=0;
 if(!VirtualProtect(slot,sizeof *slot,PAGE_READWRITE,&previous))return 18;
 void *was=InterlockedCompareExchangePointer(slot,(void*)log_hook,(void*)original_log);
 VirtualProtect(slot,sizeof *slot,previous,&ignored);
 if(was!=(void*)original_log)return 19;
 initialized=1;
 write_atomic(L"native-initialized.json","{\"stage\":\"hook_installed\",\"selection_commands_enabled\":true,\"uses_keyboard_or_mouse\":false}");
 return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved){
 (void)reserved;if(reason==DLL_PROCESS_ATTACH){own_module=module;DisableThreadLibraryCalls(module);}return TRUE;
}
