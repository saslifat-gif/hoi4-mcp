/* Ordinary AddAdvisor command; caller pins executable, world and game thread. */
#include "native_politics.h"
#ifndef ADVISOR_ROLE
#define ADVISOR_ROLE(fn,character,key) ((uintptr_t(*)(uintptr_t,uintptr_t))(fn))((character),(key))
#endif
#ifndef ADVISOR_COPY_NAME
#define ADVISOR_COPY_NAME(fn,dest,source) ((uintptr_t(*)(uintptr_t,uintptr_t))(fn))((dest),(source))
#endif
#ifndef ADVISOR_COST
#define ADVISOR_COST(fn,role,out) ((int64_t*(*)(uintptr_t,int64_t*))(fn))((role),(out))
#endif
#include "native_advisor_map.h"
struct advisor_outcome {const char *reason;int verified,cost_computed;int64_t pp_cost,cp_cost,pp_before,pp_after,cp_before,cp_after;};
static int advisor_active(uintptr_t manager,uintptr_t role,int(*can_read)(const void*,size_t)){
 if(!can_read((void*)(manager+0x58),16))return -1;
 uintptr_t array=*(uintptr_t*)(manager+0x58);int capacity=*(int*)(manager+0x60),count=*(int*)(manager+0x64),found=0;
 if(count<0||count>capacity||capacity>10000||(count&&!can_read((void*)array,(size_t)count*8)))return -1;
 for(int i=0;i<count;i++)if(((uintptr_t*)array)[i]==role)found++;
 return found;
}
static enum politics_result advisor_appoint(uintptr_t image,uintptr_t country,uint32_t tag,
 const char *character_id,const char *role_id,const char *rid,int(*can_read)(const void*,size_t),
 int(*read_name)(uintptr_t,size_t,char*,size_t),int(*intent)(const char*),struct advisor_outcome *out){
 memset(out,0,sizeof *out);out->reason="advisor_binding_changed";
 if(!can_read((void*)country,0xff8)||!tag||*(uint32_t*)(country+8)!=tag)return POLITICS_BINDING_CHANGED;
 uintptr_t manager=*(uintptr_t*)(country+0xff0),politics=*(uintptr_t*)(country+0xf90);
 if(!can_read((void*)manager,0x68)||*(uintptr_t*)manager!=image+0x298ae18||*(uintptr_t*)(manager+8)!=country||
    !can_read((void*)politics,0xe8))return POLITICS_BINDING_CHANGED;
 uintptr_t array=*(uintptr_t*)(manager+0x40),role=0,character=0;
 int capacity=*(int*)(manager+0x48),count=*(int*)(manager+0x4c);
 if(count<0||count>capacity||capacity>10000||(count&&!can_read((void*)array,(size_t)count*8)))return POLITICS_BINDING_CHANGED;
 for(int i=0;i<count;i++){
  uintptr_t candidate=((uintptr_t*)array)[i];char name[160];
  if(!can_read((void*)candidate,0x58)||*(uintptr_t*)candidate!=image+0x29a7d60)return POLITICS_BINDING_CHANGED;
  uintptr_t owner=*(uintptr_t*)(candidate+0x10);
  if(!can_read((void*)owner,0x6c)||*(uintptr_t*)owner!=image+0x297ea60||*(uint32_t*)(owner+0x68)!=tag)return POLITICS_BINDING_CHANGED;
  if(!read_name(owner,0x48,name,sizeof name))return POLITICS_BINDING_CHANGED;
  if(strcmp(name,character_id))continue;
  if(!read_name(candidate,0x30,name,sizeof name))return POLITICS_BINDING_CHANGED;
  if(strcmp(name,role_id))continue;
  if(role){out->reason="ambiguous_advisor";return POLITICS_BAD_ARGUMENT;}
  role=candidate;character=owner;
 }
 out->reason="advisor_not_in_country";if(!role)return POLITICS_BAD_ARGUMENT;
 out->reason="advisor_binding_changed";
 out->reason="advisor_handle_binding_changed";
 if(!politics_bind_native_handle(image,(const uint32_t*)(character+8),character,can_read))return POLITICS_BINDING_CHANGED;
 char slot_key[160];out->reason="advisor_map_key_not_resolved";
 uintptr_t key=advisor_map_key(image,character,role,can_read,read_name,slot_key);
 if(!key)return POLITICS_BINDING_CHANGED;
 int active=advisor_active(manager,role,can_read);
 if(active<0||active>1)return POLITICS_BINDING_CHANGED;
 out->reason="already_selected";if(active)return POLITICS_BAD_ARGUMENT;
 uintptr_t command=0;
 enum politics_result result=politics_construct_default(image,0x2995580,rid,can_read,intent,&command);
 out->reason="advisor_construction_failed";if(result!=POLITICS_OBJECT_CONSTRUCTED)return result;
 /* Factory114e180 leaves a zero-length SSO string. Constructor1142810 copies
  * character+8 to command+28 and character-map slot CString to command+38 via11e010. */
 if(*(unsigned char*)(command+0x30)!=1||*(uint64_t*)(command+0x48)!=0||*(uint64_t*)(command+0x50)!=15)return POLITICS_BINDING_CHANGED;
 memcpy((void*)(command+0x28),(void*)(character+8),8);
 ADVISOR_COPY_NAME(image+0x11e010,command+0x38,key);
 char copied[160];
 if(!read_name(command,0x38,copied,sizeof copied)||strcmp(copied,slot_key))return POLITICS_BINDING_CHANGED;
 out->pp_before=*(int64_t*)(politics+0xe0);out->cp_before=*(int64_t*)(country+0x1f0);
 ADVISOR_COST(image+0x12a24e0,role,&out->pp_cost);
 ADVISOR_COST(image+0x12a0af0,role,&out->cp_cost);out->cost_computed=1;
 out->reason="native_rules_rejected";
 result=politics_execute_resolved(image,command,NULL,rid,can_read,intent);
 if(result==POLITICS_BINDING_CHANGED)out->reason="advisor_binding_changed";
 if(result!=POLITICS_EXECUTION_RETURNED)return result;
 out->reason="advisor_postcondition_failed";
 if(!can_read((void*)(politics+0xe0),8)||!can_read((void*)(country+0x1f0),8))return result;
 out->pp_after=*(int64_t*)(politics+0xe0);out->cp_after=*(int64_t*)(country+0x1f0);
 int64_t pp_charge=out->pp_cost>0?out->pp_cost:0,cp_charge=out->cp_cost>0?out->cp_cost:0;
 if(out->pp_before<INT64_MIN+pp_charge||out->cp_before<INT64_MIN+cp_charge)return result;
 out->verified=advisor_active(manager,role,can_read)==1&&out->pp_after==out->pp_before-pp_charge&&
  out->cp_after==out->cp_before-cp_charge&&*(unsigned char*)(command+0x30)==1;
 if(out->verified)out->reason="native_advisor_and_payment_verified";
 return result;
}
