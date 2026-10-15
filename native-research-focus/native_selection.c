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
#include "native_law.h"
#include "native_advisor.h"
#include "native_decision_candidate.h"
#include "native_army_group.h"
#include "native_unit_payload.h"
#include "native_theater.h"
#include "native_attack_gate.h"
#include "native_trade.h"
#include "native_deployment_execute.h"
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
#include "native_name.h"
static int hex_id(const char *s){
 if(strlen(s)!=32)return 0;
 for(int i=0;i<32;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return 0;
 return 1;
}
static void path(wchar_t *out,const wchar_t *name){swprintf(out,MAX_PATH,L"%ls\\%ls",root,name);}
#include "native_country.h"
#include "native_atomic_publish.h"
static int write_atomic(const wchar_t *name,const char *data){
 wchar_t dest[MAX_PATH],tmp[MAX_PATH];path(dest,name);swprintf(tmp,MAX_PATH,L"%ls.pending",dest);
 HANDLE f=CreateFileW(tmp,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 0;
 DWORD done=0,n=(DWORD)strlen(data);BOOL ok=WriteFile(f,data,n,&done,NULL)&&done==n;
 if(ok)ok=FlushFileBuffers(f);CloseHandle(f);
 if(ok)ok=native_publish_file(tmp,dest);
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
static int politics_intent(const char *rid){
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);
 char out[256];snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"execution_uncertain\"}",sid,rid);
 return write_atomic(file,out);
}
static void law_command(const char *rid,const char *id,int slot,uintptr_t country,uint32_t tag){
 const char *separator=strchr(id,':');char group[160],target[160];
 if(slot||!separator||separator==id||!separator[1]||strchr(separator+1,':')){receipt(rid,"law",id,slot,"rejected","invalid_law_id");return;}
 size_t n=(size_t)(separator-id);memcpy(group,id,n);group[n]=0;strcpy(target,separator+1);
 struct law_outcome result;
 enum politics_result status=law_replace(image,country,tag,group,target,rid,readable,native_name,politics_intent,&result);
 if(status==POLITICS_INTENT_FAILED)return;
 attempts++;
 const char *stage=result.verified?"law_verified":status==POLITICS_EXECUTION_RETURNED?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[1536];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"law\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"native_cost_resource_type\":%d,\"cost_computed\":%s,\"computed_cost_raw\":%lld,\"balance_before_raw\":%lld,\"balance_after_raw\":%lld,\"cost_verified\":%s,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,id,stage,result.reason,result.resource,result.cost_computed?"true":"false",(long long)result.cost,(long long)result.before,(long long)result.after,result.verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void army_group_command(const char *rid,const char *id,int slot,uintptr_t country,uint32_t tag){
 uint32_t manager[2],units[64][2];size_t used=0;
 if(slot<1||slot>64||!unit_payload_handle(id,manager,&used)||id[used]){receipt(rid,"armygroup",id,slot,"rejected","invalid_army_group_arguments");return;}
 wchar_t payload_file[80];swprintf(payload_file,80,L"army-units-%hs.txt",rid);char payload[2048];
 if(!read_file(payload_file,payload,sizeof payload)||!unit_payload_parse(payload,sid,rid,(size_t)slot,units)){receipt(rid,"armygroup",id,slot,"rejected","owned_unit_payload_invalid");return;}
 struct army_group_outcome result;
 enum army_group_result status=army_create_from_units(image,country,tag,manager,(const uint32_t(*)[2])units,(size_t)slot,rid,readable,politics_intent,&result);
 if(status==ARMY_INTENT_FAILED)return;
 attempts++;
 const char *stage=result.verified?"army_group_verified":status==ARMY_EXECUTION_RETURNED?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[1024];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"armygroup\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"group_id\":\"%u:%u\",\"army_group_id\":\"%u:%u\",\"theater_id\":\"%u:%u\",\"unit_count\":%llu,\"membership_verified\":%s,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,id,stage,result.reason,result.group_id[0],result.group_id[1],result.army_group_id[0],result.army_group_id[1],result.theater_id[0],result.theater_id[1],(unsigned long long)result.unit_count,result.verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void theater_command(const char *rid,const char *id,int slot,uintptr_t country,uint32_t tag){
 uint32_t target[2],groups[64][2];size_t used=0;int create=!strcmp(id,"new");
 if(slot<1||slot>64||(!create&&(!unit_payload_handle(id,target,&used)||id[used]))){receipt(rid,"theater",id,slot,"rejected","invalid_theater_arguments");return;}
 wchar_t payload_file[80];swprintf(payload_file,80,L"theater-groups-%hs.txt",rid);char payload[2048];
 if(!read_file(payload_file,payload,sizeof payload)||!unit_payload_parse(payload,sid,rid,(size_t)slot,groups)){receipt(rid,"theater",id,slot,"rejected","owned_group_payload_invalid");return;}
 struct theater_outcome result;
 enum theater_result status=theater_change(image,country,tag,(const uint32_t(*)[2])groups,(size_t)slot,create?NULL:target,"",rid,readable,native_name,politics_intent,&result);
 if(status==THEATER_INTENT_FAILED)return;
 attempts++;
 const char *stage=result.verified?"theater_verified":status==THEATER_EXECUTION_RETURNED?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[1024];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"theater\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"theater_id\":\"%u:%u\",\"affected_groups\":%llu,\"membership_verified\":%s,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,id,stage,result.reason,result.target_id[0],result.target_id[1],(unsigned long long)result.affected_groups,result.verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void deployment_command(const char *rid,const char *kind,const char *id,int slot,uintptr_t country,uint32_t tag){
 uint32_t handle[2];size_t used=0;
 if(!unit_payload_handle(id,handle,&used)||id[used]||
    (!strcmp(kind,"queue")&&slot)||
    (!strcmp(kind,"deploy")&&slot)||(!strcmp(kind,"deployloc")&&slot<1)){
  receipt(rid,kind,id,slot,"rejected","invalid_deployment_arguments");return;
 }
 struct deployment_outcome result;const char *error;
 if(!strcmp(kind,"queue"))error=deployment_create_queue(image,country,tag,handle,rid,readable,politics_intent,&result);
 else if(!strcmp(kind,"deployloc"))error=deployment_set_location(image,country,tag,handle,slot,rid,readable,politics_intent,&result);
 else error=deployment_deploy_line(image,country,tag,handle,rid,readable,politics_intent,&result);
 if(error&&!strcmp(error,"deployment_intent_failed"))return;
 attempts++;
 const char *stage=result.verified?"deployment_verified":result.executed?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[1400];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"%s\",\"id\":\"%s\",\"slot\":%d,\"stage\":\"%s\",\"reason\":\"%s\",\"conveyor_id\":\"%u:%u\",\"line_id\":\"%u:%u\",\"unit_id\":\"%u:%u\",\"executed\":%s,\"outcome_verified\":%s,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,kind,id,slot,stage,error?error:"",result.conveyor_id[0],result.conveyor_id[1],result.line_id[0],result.line_id[1],result.unit_id[0],result.unit_id[1],result.executed?"true":"false",result.verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void trade_command(const char *rid,const char *id,int slot,uintptr_t country,uintptr_t world,uint32_t tag){
 const char *separator=strchr(id,':');char partner[4],resource[65];
 if(slot<1||slot>1000||!separator||separator-id!=3||!separator[1]||strlen(separator+1)>64||strchr(separator+1,':')){receipt(rid,"trade",id,slot,"rejected","invalid_trade_arguments");return;}
 memcpy(partner,id,3);partner[3]=0;strcpy(resource,separator+1);
 struct trade_outcome result;
 enum politics_result status=trade_select(image,country,world,tag,partner,resource,slot,rid,readable,native_name,politics_intent,&result);
 if(status==POLITICS_INTENT_FAILED)return;
 attempts++;
 const char *stage=result.verified?"trade_verified":status==POLITICS_EXECUTION_RETURNED?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[2048];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"trade\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"requested_factories\":%d,\"resource_units\":%d,\"native_cost_raw\":%lld,\"available_cic\":%d,\"max_resource_raw\":%lld,\"required_before\":%d,\"required_after\":%d,\"lended_before\":%d,\"lended_after\":%d,\"nominal_requested_raw\":%lld,\"delivered_before_raw\":%lld,\"delivered_after_raw\":%lld,\"importer_tag\":%u,\"exporter_tag\":%u,\"cost_computed\":%s,\"offer_checked\":%s,\"record_verified\":%s,\"delivery_verified\":false,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,id,stage,result.reason,result.requested_factories,result.resource_units,(long long)result.native_cost_raw,result.available_cic,(long long)result.max_resource_raw,result.required_before,result.required_after,result.lended_before,result.lended_after,(long long)result.nominal_requested_raw,(long long)result.delivered_before_raw,(long long)result.delivered_after_raw,result.importer_tag,result.exporter_tag,result.cost_computed?"true":"false",result.offer_checked?"true":"false",result.record_verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void decision_command(const char *rid,const char *id,int slot,uintptr_t country,uint32_t tag){
 if(slot){receipt(rid,"decision",id,slot,"rejected","ordinary_decision_requires_zero_slot");return;}
 struct decision_outcome result;
 enum politics_result status=decision_select(image,country,tag,id,rid,readable,native_name,politics_intent,&result);
 if(status==POLITICS_INTENT_FAILED)return;
 attempts++;
 const char *stage=result.verified?"decision_verified":status==POLITICS_EXECUTION_RETURNED?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[1536];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"decision\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"cost_computed\":%s,\"political_power_cost_raw\":%lld,\"political_power_before_raw\":%lld,\"political_power_after_raw\":%lld,\"counter_before\":%d,\"counter_after\":%d,\"counter_verified\":%s,\"cost_verified\":%s,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,id,stage,result.reason,result.cost_computed?"true":"false",(long long)result.pp_cost,(long long)result.pp_before,(long long)result.pp_after,result.counter_before,result.counter_after,result.counter_verified?"true":"false",result.payment_verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void advisor_command(const char *rid,const char *id,int slot,uintptr_t country,uint32_t tag){
 const char *separator=strchr(id,':');char character[160],role[160];
 if(slot||!separator||separator==id||!separator[1]||strchr(separator+1,':')){receipt(rid,"advisor",id,slot,"rejected","invalid_advisor_id");return;}
 size_t n=(size_t)(separator-id);memcpy(character,id,n);character[n]=0;strcpy(role,separator+1);
 struct advisor_outcome result;
 enum politics_result status=advisor_appoint(image,country,tag,character,role,rid,readable,native_name,politics_intent,&result);
 if(status==POLITICS_INTENT_FAILED)return;
 attempts++;
 const char *stage=result.verified?"advisor_verified":status==POLITICS_EXECUTION_RETURNED?"execution_uncertain":"rejected";
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);char out[1536];
 snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"advisor\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"cost_computed\":%s,\"political_power_cost_raw\":%lld,\"command_power_cost_raw\":%lld,\"political_power_before_raw\":%lld,\"political_power_after_raw\":%lld,\"command_power_before_raw\":%lld,\"command_power_after_raw\":%lld,\"cost_verified\":%s,\"pid\":%lu,\"thread_id\":%lu,\"uses_keyboard_or_mouse\":false}",sid,rid,id,stage,result.reason,result.cost_computed?"true":"false",(long long)result.pp_cost,(long long)result.cp_cost,(long long)result.pp_before,(long long)result.pp_after,(long long)result.cp_before,(long long)result.cp_after,result.verified?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId());
 write_atomic(file,out);
}
static void military_command(const char *rid,const char *kind,const char *id,int slot,uintptr_t country,uintptr_t world){
 unsigned first,second;char extra,canonical[32];
 int attack=!strcmp(kind,"attack"),stop_combat=!strcmp(kind,"combatstop"),move=!strcmp(kind,"move")||attack;
 if((move?slot<1:slot!=0)||sscanf(id,"%u:%u%c",&first,&second,&extra)!=2||!first||!second){receipt(rid,kind,id,slot,"rejected","invalid_unit_id");return;}
 snprintf(canonical,sizeof canonical,"%u:%u",first,second);
 if(strcmp(canonical,id)){receipt(rid,kind,id,slot,"rejected","invalid_unit_id");return;}
 uintptr_t array=*(uintptr_t*)(country+0x290),unit=0;
 int capacity=*(int*)(country+0x298),count=*(int*)(country+0x29c);
 if(count<0||count>capacity||capacity>100000||!readable((void*)array,count*8)){receipt(rid,kind,id,slot,"rejected","invalid_unit_list");return;}
 for(int i=0;i<count;i++){
  uintptr_t candidate=*(uintptr_t*)(array+i*8);
  if(!readable((void*)candidate,0x310)||*(uintptr_t*)candidate!=image+0x295a2b0||*(uintptr_t*)(candidate+16)!=image+0x295a490)continue;
  if(*(unsigned*)(candidate+24)==first&&*(unsigned*)(candidate+28)==second){unit=candidate;break;}
 }
 unsigned handle[2]={first,second};
 if(!unit||((uintptr_t(*)(const unsigned*))(image+0x221f310))(handle)!=unit+16){receipt(rid,kind,id,slot,"rejected","unit_not_in_country");return;}
 uintptr_t destination=0;
 if(move){
  /* Verified world+8 lookup rejects IDs below 1 or at/above its count. */
  if(memcmp((void*)(image+0x1ca1b0),"\x83\xfa\x01\x7c\x17\x3b\x91\xb4\x02\x00\x00\x7d\x0f",13)){receipt(rid,kind,id,slot,"rejected","province_lookup_changed");return;}
  destination=((uintptr_t(*)(uintptr_t,int))(image+0x1ca1b0))(world+8,slot);
  if(!readable((void*)destination,0xa8)||*(int*)(destination+0xa4)!=slot){receipt(rid,kind,id,slot,"rejected","invalid_province_id");return;}
 }
 if(attack){
  uintptr_t checked_unit=0,checked_province=0;
  const char *error=combat_attack_preflight(image,world,country,*(uint32_t*)(country+8),handle,slot,readable,&checked_unit,&checked_province);
  if(error){receipt(rid,kind,id,slot,"rejected",error);return;}
  if(checked_unit!=unit||checked_province!=destination){receipt(rid,kind,id,slot,"rejected","attack_binding_changed");return;}
 }
 wchar_t file[80];swprintf(file,80,L"receipt-%hs.json",rid);
 char intent[256];snprintf(intent,sizeof intent,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"execution_uncertain\"}",sid,rid);
 if(!write_atomic(file,intent))return;
 attempts++;
 uintptr_t cmd=((uintptr_t(*)(void))(image+(move?0x1365020:0x1364cc0)))();
 if(!readable((void*)cmd,move?0x88:0x48)||*(uintptr_t*)cmd!=image+(move?0x29b1bc8:0x29b1e20)){receipt(rid,kind,id,slot,"rejected","factory_failed");return;}
 if(move){
  /* Matches the normal engine call at 1a4c8ae; no direct gameplay setters. */
  ((uintptr_t(*)(uintptr_t,uintptr_t,int,unsigned char,int,unsigned char,unsigned char,unsigned char,unsigned char,unsigned char))(image+0x1360730))(cmd,unit,slot,1,2,0,0,0,0,0);
  uintptr_t provinces=*(uintptr_t*)(cmd+0x40);
  if(memcmp((void*)(cmd+0x38),handle,8)||*(int*)(cmd+0x4c)!=1||!readable((void*)provinces,4)||*(int*)provinces!=slot){receipt(rid,kind,id,slot,"rejected","command_identity_mismatch");return;}
 }else{
  uintptr_t one[1]={unit};struct {uintptr_t data;int capacity,count;uintptr_t allocator;} selected={(uintptr_t)one,1,1,0};
  ((uintptr_t(*)(uintptr_t,void*))(image+0x135fb30))(cmd,&selected);
  uintptr_t ids=*(uintptr_t*)(cmd+0x28);
  if(*(int*)(cmd+0x34)!=1||!readable((void*)ids,8)||memcmp((void*)ids,handle,8)){receipt(rid,kind,id,slot,"rejected","command_identity_mismatch");return;}
 }
 if(!((unsigned char(*)(uintptr_t,void*))(image+(move?0x1369cb0:0x1368790)))(cmd,NULL)){receipt(rid,kind,id,slot,"rejected","native_rules_rejected");return;}
 int combat_before=*(int*)(unit+0x1b4);
 if(stop_combat){
  int capacity=*(int*)(unit+0x1b0);uintptr_t data=*(uintptr_t*)(unit+0x1a8);
  if(combat_before<1){receipt(rid,kind,id,slot,"rejected","no_active_unit_combat");return;}
  if(combat_before>capacity||capacity>100000||!readable((void*)data,(size_t)combat_before*8)){receipt(rid,kind,id,slot,"rejected","combat_membership_binding_changed");return;}
 }
 ((void(*)(uintptr_t))(image+(move?0x13669e0:0x1365c20)))(cmd);
 uintptr_t path=*(uintptr_t*)(unit+0x200);int path_count=*(int*)(unit+0x20c),path_capacity=*(int*)(unit+0x208);
 /* The engine clears +1e8 after issuing movement; the forward path retains its target. */
 int verified=move?(path_count>0&&path_count<=path_capacity&&path_capacity<=100000&&readable((void*)path,path_count*4)&&((int*)path)[path_count-1]==slot):(*(uintptr_t*)(unit+0x1e8)==0&&path_count==0);
 if(stop_combat){
  int after=*(int*)(unit+0x1b4),capacity=*(int*)(unit+0x1b0);
  int removed=after>=0&&after<=capacity&&capacity<=100000&&after<combat_before;
  verified=verified&&removed;
  char out[1024];
  snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"%s\",\"id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"combat_count_before\":%d,\"combat_count_after\":%d,\"combat_membership_removed\":%s,\"uses_keyboard_or_mouse\":false}",sid,rid,kind,id,verified?"military_verified":"execution_uncertain",verified?"native_combat_membership_cancelled":"combat_stop_postcondition_failed",combat_before,after,removed?"true":"false");
  write_atomic(file,out);
 }else receipt(rid,kind,id,slot,verified?"military_verified":"execution_uncertain",verified?(move?"native_movement_ordered":"native_movement_cancelled"):"postcondition_failed");
}
static void select_command(uintptr_t country,uintptr_t world,uintptr_t tech,uintptr_t progress,uintptr_t tree,uint32_t tag){
 char request[512],reqsid[33],rid[33],kind[16],id[160],extra;int slot;
 if(!read_file(L"request.txt",request,sizeof request))return;
 if(sscanf(request,"%32[a-f0-9]|%32[a-f0-9]|%15[a-z]|%159[A-Za-z0-9_.:-]|%d%c",reqsid,rid,kind,id,&slot,&extra)!=5)return;
 if(!hex_id(rid)||strcmp(reqsid,sid)||(strcmp(kind,"research")&&strcmp(kind,"focus")&&strcmp(kind,"cancel")&&strcmp(kind,"combatstop")&&strcmp(kind,"move")&&strcmp(kind,"attack")&&strcmp(kind,"law")&&strcmp(kind,"advisor")&&strcmp(kind,"decision")&&strcmp(kind,"armygroup")&&strcmp(kind,"theater")&&strcmp(kind,"trade")&&strcmp(kind,"queue")&&strcmp(kind,"deployloc")&&strcmp(kind,"deploy")))return;
 wchar_t rf[80],full[MAX_PATH];swprintf(rf,80,L"receipt-%hs.json",rid);path(full,rf);
 if(GetFileAttributesW(full)!=INVALID_FILE_ATTRIBUTES)return;
 if(attempts>=64){receipt(rid,kind,id,slot,"rejected","session_limit");return;}
 if(world!=bound_world||*(uint32_t*)(country+8)!=tag){receipt(rid,kind,id,slot,"rejected","world_changed");return;}
 if(!strcmp(kind,"queue")||!strcmp(kind,"deployloc")||!strcmp(kind,"deploy")){deployment_command(rid,kind,id,slot,country,tag);return;}
 if(!strcmp(kind,"trade")){trade_command(rid,id,slot,country,world,tag);return;}
 if(!strcmp(kind,"theater")){theater_command(rid,id,slot,country,tag);return;}
 if(!strcmp(kind,"armygroup")){army_group_command(rid,id,slot,country,tag);return;}
 if(!strcmp(kind,"decision")){decision_command(rid,id,slot,country,tag);return;}
 if(!strcmp(kind,"advisor")){advisor_command(rid,id,slot,country,tag);return;}
 if(!strcmp(kind,"law")){law_command(rid,id,slot,country,tag);return;}
 if(!strcmp(kind,"combatstop")||!strcmp(kind,"cancel")||!strcmp(kind,"move")||!strcmp(kind,"attack")){military_command(rid,kind,id,slot,country,world);return;}
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
  "{\"stage\":\"script_thread_observed\",\"country_code\":\"%s\",\"session_id\":\"%s\",\"pid\":%lu,\"thread_id\":%lu,\"country_tag\":%u,\"country\":\"0x%llx\",\"world\":\"0x%llx\",\"technology_status\":\"0x%llx\",\"research_slots\":%d,\"technology_models\":%d,\"focus_tree\":\"0x%llx\",\"focus_progress\":\"0x%llx\",\"active_focus\":\"0x%llx\",\"focus_elapsed_raw\":%lld,\"uses_keyboard_or_mouse\":false,\"selection_commands_enabled\":true}",
  country_code,sid,(unsigned long)GetCurrentProcessId(),(unsigned long)tid,*tag,(unsigned long long)country,(unsigned long long)world,(unsigned long long)tech,slots,models,(unsigned long long)tree,(unsigned long long)progress,(unsigned long long)*(uintptr_t*)(progress+0x10),(long long)*(int64_t*)(progress+0x18));
 write_atomic(L"native-observation.json",out);
}
static void log_hook(void *effect,void *scope){
 original_log(effect,scope);
 if(initialized!=1)return;
 __try{
  char text[512],prefix[128];
  snprintf(prefix,sizeof prefix,"CODEX_COMMAND_SESSION|%s|LIVE|country=%s",sid,country_code);
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
 if(!load_country_code())return 20;
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
