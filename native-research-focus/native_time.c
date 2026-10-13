/* Build-pinned HOI4 time bridge using CInGameIdler::frame.
 * No keyboard, mouse, window messages or direct gameplay-field setters. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "time_pause_command.h"
#pragma comment(lib,"bcrypt.lib")
static HMODULE own_module;
static uintptr_t image;
static char sid[33];
static wchar_t root[MAX_PATH];
static volatile LONG initialized=0;
static void (*original_frame)(void*,char);
static DWORD frame_thread;
static ULONGLONG last_status;
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
static int read_file(const wchar_t *name,char *out,DWORD cap){
 wchar_t file[MAX_PATH];path(file,name);
 HANDLE f=CreateFileW(file,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 0;
 DWORD n=0;BOOL ok=ReadFile(f,out,cap-1,&n,NULL);CloseHandle(f);out[n]=0;
 return ok&&n&&n<cap-1;
}
/* All changes go through the ordinary engine commands on CInGameIdler::frame.
 * Hook runs even while paused. No worker-thread execution or input synthesis. */
static int paused(uintptr_t idler){return ((unsigned char(*)(void*))(image+0xdd85c0))((void*)idler)!=0;}
static void status(uintptr_t idler,uintptr_t world){
 char out[512];snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"pid\":%lu,\"thread_id\":%lu,\"world\":\"0x%llx\",\"paused\":%s,\"speed\":%d,\"native_tick\":%d,\"heartbeat_ms\":%llu,\"uses_keyboard_or_mouse\":false}",sid,(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long long)world,paused(idler)?"true":"false",*(int*)(world+0x4bc)+1,*(int*)(world+0x468),(unsigned long long)GetTickCount64());write_atomic(L"time-status.json",out);
}
static void reconcile(uintptr_t idler,uintptr_t world){
 char request[160],reqsid[33],rid[33],kind[16],extra;int value;
 if(!read_file(L"time-request.txt",request,sizeof request))return;
 if(sscanf(request,"%32[a-f0-9]|%32[a-f0-9]|%15[a-z]|%d%c",reqsid,rid,kind,&value,&extra)!=4||strcmp(reqsid,sid)||!hex_id(rid))return;
 if((strcmp(kind,"pause")&&strcmp(kind,"speed"))||(!strcmp(kind,"pause")?(value!=0&&value!=1):(value<1||value>5)))return;
 wchar_t name[80],full[MAX_PATH];swprintf(name,80,L"time-receipt-%hs.json",rid);path(full,name);
 if(GetFileAttributesW(full)!=INVALID_FILE_ATTRIBUTES)return;
 char out[700];int before_pause=paused(idler),before_speed=*(int*)(world+0x4bc)+1;
 if(attempts>=64){snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"rejected\",\"reason\":\"session_limit\"}",sid,rid);write_atomic(name,out);return;}
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"execution_uncertain\"}",sid,rid);if(!write_atomic(name,out))return;attempts++;
 __declspec(align(16)) unsigned char cmd[0x60]={0};
 if(!strcmp(kind,"pause")){
  if(!execute_pause_command(before_pause,value,image+0x296a560,
      (TimePauseFactory)(image+0xde72b0),readable,
      (TimePauseExecute)(image+0xde8360))){
   snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"rejected\",\"reason\":\"pause_factory_failed\"}",sid,rid);
   write_atomic(name,out);return;
  }
 }else{
  *(uintptr_t*)cmd=image+0x29771d0;*(int*)(cmd+0xc)=-1;*(uint32_t*)(cmd+0x14)=0xffff0000;*(int*)(cmd+0x28)=value-1;
  if(!((unsigned char(*)(void*))(image+0xf07270))(cmd))return;
  if(before_speed!=value)((void(*)(void*))(image+0xf07110))(cmd);
 }
 int after_pause=paused(idler),after_speed=*(int*)(world+0x4bc)+1;
 int verified=!strcmp(kind,"pause")?after_pause==value:after_speed==value;
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"%s\",\"kind\":\"%s\",\"value\":%d,\"before_paused\":%s,\"after_paused\":%s,\"before_speed\":%d,\"after_speed\":%d,\"native_tick\":%d,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,verified?"time_verified":"execution_uncertain",kind,value,before_pause?"true":"false",after_pause?"true":"false",before_speed,after_speed,*(int*)(world+0x468),(unsigned long)GetCurrentThreadId());write_atomic(name,out);
}
/* Preserve the fault location for the next live investigation. Never retry an
 * attempted request: its execution_uncertain receipt was persisted first. */
static int time_exception(EXCEPTION_POINTERS *info){
 initialized=2;
 char out[512];uintptr_t address=(uintptr_t)info->ExceptionRecord->ExceptionAddress;
 MEMORY_BASIC_INFORMATION region={0};
 uintptr_t base=VirtualQuery((void*)address,&region,sizeof region)?(uintptr_t)region.AllocationBase:0;
 snprintf(out,sizeof out,"{\"stage\":\"native_time_exception\",\"session_id\":\"%s\",\"exception_code\":\"0x%08lx\",\"exception_address\":\"0x%llx\",\"module_base\":\"0x%llx\",\"module_offset\":\"0x%llx\"}",
          sid,(unsigned long)info->ExceptionRecord->ExceptionCode,
          (unsigned long long)address,(unsigned long long)base,
          (unsigned long long)(base?address-base:0));
 write_atomic(L"time-error.json",out);
 return EXCEPTION_EXECUTE_HANDLER;
}
static void frame_hook(void *self,char flag){
 original_frame(self,flag);
 if(initialized!=1)return;
 __try{
  uintptr_t world=*(uintptr_t*)(image+0x332f260),idler=*(uintptr_t*)(image+0x332f698);
  if((uintptr_t)self!=idler||world!=bound_world||!readable((void*)world,0x528)||*(uintptr_t*)self!=image+0x2968ff0)return;
  DWORD tid=GetCurrentThreadId();if(frame_thread&&frame_thread!=tid)return;frame_thread=tid;
  if(*(int*)(world+0x4bc)<0||*(int*)(world+0x4bc)>4)return;
  reconcile(idler,world);
  if(GetTickCount64()-last_status>=250){status(idler,world);last_status=GetTickCount64();}
 }__except(time_exception(GetExceptionInformation())){}
}
__declspec(dllexport) DWORD WINAPI Initialize(LPVOID unused){
 (void)unused;if(initialized)return 10;
 DWORD n=GetModuleFileNameW(own_module,root,MAX_PATH);if(!n||n>=MAX_PATH)return 11;
 wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 12;*slash=0;if(wcslen(root)>180)return 12;
 char config[64];if(!read_file(L"session-id.txt",config,sizeof config)||!hex_id(config))return 13;strcpy(sid,config);
 if(!module_hash_matches())return 16;image=(uintptr_t)GetModuleHandleW(NULL);
 if(!read_file(L"expected-world.txt",config,sizeof config)||sscanf(config,"%llx",(unsigned long long*)&bound_world)!=1)return 17;
 if(*(uintptr_t*)(image+0x332f260)!=bound_world)return 18;
 void **vt=(void**)(image+0x2968ff0);
 if(vt[4]!=(void*)(image+0xdd3a50)||vt[82]!=(void*)(image+0xddad30)||vt[93]!=(void*)(image+0xdd85c0))return 19;
 original_frame=(void(*)(void*,char))vt[4];DWORD old=0,ignored=0;
 if(!VirtualProtect(&vt[4],sizeof(void*),PAGE_READWRITE,&old))return 20;
 void* was=InterlockedCompareExchangePointer(&vt[4],(void*)frame_hook,(void*)original_frame);VirtualProtect(&vt[4],sizeof(void*),old,&ignored);
 if(was!=(void*)original_frame)return 21;initialized=1;
 write_atomic(L"time-initialized.json","{\"stage\":\"frame_hook_installed\",\"uses_keyboard_or_mouse\":false}");return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved){(void)reserved;if(reason==DLL_PROCESS_ATTACH){own_module=module;DisableThreadLibraryCalls(module);}return TRUE;}
