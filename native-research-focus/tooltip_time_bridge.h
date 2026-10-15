/* Isolated native_time.c adapter. Included after paused() and the existing
 * notification_refresh.h helper. It adds no secondhook or processinput calls. */
#include "native_tooltip.h"
#include "tooltip_selector.h"
struct TooltipWindowProbe {DWORD pid,thread;HWND hwnd;};
static HWND tooltip_owned_hwnd;
static const char *tooltip_active_rid;
static int tooltip_has_intent;
static BOOL CALLBACK tooltip_find_window(HWND hwnd,LPARAM opaque){
 struct TooltipWindowProbe *probe=(struct TooltipWindowProbe*)opaque;DWORD pid=0;
 DWORD thread=GetWindowThreadProcessId(hwnd,&pid);
 if(pid==probe->pid&&thread==probe->thread&&IsWindowVisible(hwnd)){probe->hwnd=hwnd;return FALSE;}
 return TRUE;
}
static int tooltip_frame_ui_thread(uintptr_t owner){
 (void)owner;struct TooltipWindowProbe probe={GetCurrentProcessId(),GetCurrentThreadId(),NULL};
 EnumWindows(tooltip_find_window,(LPARAM)&probe);tooltip_owned_hwnd=probe.hwnd;return probe.hwnd!=NULL;
}
static void tooltip_native_elect(uintptr_t fn,uintptr_t target,int threshold){((void(*)(uintptr_t,int))fn)(target,threshold);}
static void tooltip_native_update(uintptr_t fn,uintptr_t owner,unsigned char force){((void(*)(uintptr_t,unsigned char))fn)(owner,force);}
static int tooltip_paused_gate(uintptr_t owner){return paused(owner);}
static int tooltip_persisted_gate(const char *rid){return tooltip_has_intent&&tooltip_active_rid&&!strcmp(rid,tooltip_active_rid);}
static int tooltip_selector_file(const char *rid,struct TooltipSelectorFields *fields){
 wchar_t name[80],full[MAX_PATH];swprintf(name,80,L"tooltip-selector-%hs.txt",rid);path(full,name);
 HANDLE file=CreateFileW(full,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(file==INVALID_HANDLE_VALUE)return 0;
 char data[1093];DWORD n=0;BOOL ok=ReadFile(file,data,sizeof data,&n,NULL);CloseHandle(file);
 return ok&&n<sizeof data&&parse_tooltip_selector(data,n,sid,rid,fields);
}
static int tooltip_json_cstring(char *out,SIZE_T cap,SIZE_T *used,const char *text){
 /* Reuse the existing bounded JSON encoder with a borrowed native CString view.
  * This stack view owns no memory and is never passed to an engine destructor. */
 unsigned char view[32]={0};SIZE_T n=strlen(text);
 if(n<=15){memcpy(view,text,n);*(SIZE_T*)(view+24)=15;}
 else{*(const char**)view=text;*(SIZE_T*)(view+24)=n;}
 *(SIZE_T*)(view+16)=n;return json_alert_string(out,cap,used,view);
}
static int tooltip_append_pair(char *out,SIZE_T cap,SIZE_T *used,const char *key,const char *text){
 int n=snprintf(out+*used,cap-*used,",\"%s\":",key);
 if(n<0||(SIZE_T)n>=cap-*used)return 0;*used+=(SIZE_T)n;return tooltip_json_cstring(out,cap,used,text);
}
static void tooltip_time_result(uintptr_t idler,uintptr_t world,const char *rid,const wchar_t *receipt_name,int tick){
 struct TooltipSelectorFields fields;
 if(!tooltip_selector_file(rid,&fields)){
  char rejected[256];snprintf(rejected,sizeof rejected,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"rejected\",\"reason\":\"tooltip_selector_invalid\",\"attempted\":false,\"native_generated\":false,\"nonempty\":false}",sid,rid);write_atomic(receipt_name,rejected);return;
 }
 struct TooltipSelector selector={fields.source,fields.name};struct TooltipOutcome result;
 struct TooltipCalls calls={readable,tooltip_native_elect,tooltip_native_update,tooltip_paused_gate,tooltip_frame_ui_thread,tooltip_persisted_gate};
 tooltip_active_rid=rid;tooltip_has_intent=1;tooltip_owned_hwnd=NULL;
 int ok=tooltip_generate(image,idler,&selector,rid,&calls,&result);
 tooltip_has_intent=0;tooltip_active_rid=NULL;
 int generated=result.updated&&(!strcmp(result.reason,"native_tooltip_generated")||!strcmp(result.reason,"native_tooltip_empty"));
 if(*(int*)(world+0x468)!=tick){generated=ok=0;result.reason="game_tick_changed_during_tooltip";}
 const char *stage=generated?"tooltip_generated":result.attempted?"execution_uncertain":"rejected";
 char out[65536];SIZE_T used=(SIZE_T)snprintf(out,sizeof out,
  "{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"attempted\":%s,\"native_generated\":%s,\"nonempty\":%s,\"native_tick\":%d,\"thread_id\":%lu,\"owned_window\":\"0x%llx\",\"widget_id\":\"0x%llx\",\"core_widget_id\":\"0x%llx\",\"rendered_equals_combined\":%s,\"engine_local_shown\":%s,\"ui_state_writes\":%s,\"uses_keyboard_or_mouse\":false,\"physical_display_verified\":false,\"independent_asset_readback_required\":true}",
  sid,rid,stage,result.reason,result.attempted?"true":"false",generated?"true":"false",ok&&result.nonempty?"true":"false",tick,
  (unsigned long)GetCurrentThreadId(),(unsigned long long)(uintptr_t)tooltip_owned_hwnd,(unsigned long long)result.target,(unsigned long long)result.core,
  result.rendered_equals_combined?"true":"false",result.local_shown?"true":"false",result.attempted?"true":"false");
 /* Replace the closingbrace so all selector/text values use the existing JSON
  * encoder, preserving native control bytes for actual MCP asset readback. */
 if(used>=sizeof out||!used)return;out[--used]=0;
 int encoded=tooltip_append_pair(out,sizeof out,&used,"source",fields.source)&&tooltip_append_pair(out,sizeof out,&used,"name",fields.name)&&
  tooltip_append_pair(out,sizeof out,&used,"raw_rendered",result.rendered)&&tooltip_append_pair(out,sizeof out,&used,"raw_combined",result.combined)&&
  tooltip_append_pair(out,sizeof out,&used,"raw_title",result.title)&&tooltip_append_pair(out,sizeof out,&used,"raw_body",result.body);
 if(!encoded||used+2>=sizeof out){
  snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"execution_uncertain\",\"reason\":\"tooltip_receipt_text_limit\",\"attempted\":%s,\"native_generated\":%s,\"nonempty\":%s}",sid,rid,result.attempted?"true":"false",generated?"true":"false",ok&&result.nonempty?"true":"false");
 }else{out[used++]='}';out[used]=0;}
 write_atomic(receipt_name,out);
}
