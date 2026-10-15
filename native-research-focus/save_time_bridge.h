/* Normal local save on the bound paused UI frame. No user-supplied pathname. */
#include "native_save_candidate.h"
static const char *save_active_rid;
static int save_persisted_intent(const char *rid){return save_active_rid&&!strcmp(save_active_rid,rid);}
static void save_time_result(uintptr_t idler,uintptr_t world,const char *rid,const wchar_t *receipt_name){
 char basename[96];snprintf(basename,sizeof basename,"mcp_%s_%s",sid,rid);
 struct save_outcome result;memset(&result,0,sizeof result);result.reason="paused_owned_ui_thread_required";
 int ok=0;
 if(paused(idler)&&tooltip_frame_ui_thread(idler)){
  save_active_rid=rid;ok=save_owned_local(image,idler,world,basename,rid,readable,save_persisted_intent,&result);save_active_rid=NULL;
 }
 const char *stage=ok?"save_file_observed":result.requested?"execution_uncertain":"rejected";
 char out[12288];SIZE_T used=(SIZE_T)snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"kind\":\"save\",\"stage\":\"%s\",\"reason\":\"%s\",\"native_requested\":%s,\"native_return\":%s,\"final_exists\":%s,\"temporary_exists\":%s,\"native_file_observation_verified\":%s,\"reload_verified\":false,\"uses_keyboard_or_mouse\":false,\"native_tick\":%d,\"thread_id\":%lu}",sid,rid,stage,result.reason,result.requested?"true":"false",result.native_return?"true":"false",result.final_exists?"true":"false",result.temp_exists?"true":"false",ok?"true":"false",*(int*)(world+0x468),(unsigned long)GetCurrentThreadId());
 if(!used||used>=sizeof out)return;out[--used]=0;
 if(!tooltip_append_pair(out,sizeof out,&used,"basename",basename)||!tooltip_append_pair(out,sizeof out,&used,"path",result.path)||!tooltip_append_pair(out,sizeof out,&used,"temporary_path",result.temporary_path)||used+2>=sizeof out)return;
 out[used++]='}';out[used]=0;write_atomic(receipt_name,out);
}
