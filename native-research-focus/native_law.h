/* Ordinary ReplaceIdea path, called only on the pinned, bound game thread.
 * Definitions/ownership come from native registries; no gameplay-field writes. */
#include "native_politics.h"
#ifndef LAW_COST
#define LAW_COST(fn,manager,out,idea) ((int64_t*(*)(uintptr_t,int64_t*,uintptr_t))(fn))((manager),(out),(idea))
#endif
#ifndef LAW_RESOURCE_MANAGER
#define LAW_RESOURCE_MANAGER(fn,country) ((uintptr_t(*)(uintptr_t))(fn))(country)
#endif
#ifndef LAW_RESOURCE_VALUE
#define LAW_RESOURCE_VALUE(fn,out,value) ((int64_t*(*)(int64_t*,uintptr_t))(fn))((out),(value))
#endif
struct law_outcome {const char *reason;int verified,cost_computed,resource;uintptr_t previous,requested;int64_t cost,before,after;};
static int law_balance(uintptr_t image,uintptr_t country,uintptr_t manager,int resource,
 int(*can_read)(const void*,size_t),int64_t *out){
 if(resource==0||resource==1){
  if(!can_read((void*)(manager+0xe0),8))return 0;
  *out=*(int64_t*)(manager+0xe0);return 1;
 }
 if(resource<2||resource>4)return 0;
 uintptr_t values=LAW_RESOURCE_MANAGER(image+0x6cf690,country);
 if(!can_read((void*)values,0x58))return 0;
 LAW_RESOURCE_VALUE(image+0x24ed580,out,values+0x10+(resource-2)*0x18);return 1;
}
static int law_membership(uintptr_t manager,uintptr_t old,uintptr_t requested,
 int(*can_read)(const void*,size_t)){
 if(!can_read((void*)(manager+0x50),16))return 0;
 uintptr_t array=*(uintptr_t*)(manager+0x50);int capacity=*(int*)(manager+0x58),count=*(int*)(manager+0x5c),found=0;
 if(count<1||count>capacity||capacity>100000||!can_read((void*)array,(size_t)count*8))return 0;
 for(int i=0;i<count;i++){uintptr_t idea=((uintptr_t*)array)[i];if(idea==old)return 0;if(idea==requested)found++;}
 return found==1;
}
static enum politics_result law_replace(uintptr_t image,uintptr_t country,uint32_t tag,
 const char *group_id,const char *idea_id,const char *rid,int(*can_read)(const void*,size_t),
 int(*read_name)(uintptr_t,size_t,char*,size_t),int(*intent)(const char*),struct law_outcome *out){
 memset(out,0,sizeof *out);out->reason="law_binding_changed";
 if(!can_read((void*)country,0xf98)||*(uint32_t*)(country+8)!=tag||!tag)return POLITICS_BINDING_CHANGED;
 uintptr_t requested=politics_resolve_idea(image,idea_id,can_read,read_name);out->requested=requested;
 out->reason="unknown_law";if(!requested)return POLITICS_BAD_ARGUMENT;
 if(!can_read((void*)requested,0xac8))return POLITICS_BINDING_CHANGED;
 uintptr_t group=*(uintptr_t*)(requested+0xaa0);char name[160];out->reason="not_requested_law_group";
 /* Token 'law' is3571 (registration a850a); parser fd5de0 writes group+58. */
 if(!can_read((void*)group,0x78)||*(uintptr_t*)group!=image+0x2946650||*(unsigned char*)(group+0x58)!=1||
    !read_name(group,0x38,name,sizeof name)||strcmp(name,group_id))return POLITICS_BAD_ARGUMENT;
 uintptr_t category=*(uintptr_t*)(group+0x60),manager=*(uintptr_t*)(country+0xf90);
 out->reason="law_binding_changed";
 if(!can_read((void*)category,0x88)||*(uintptr_t*)category!=image+0x2981648||!can_read((void*)manager,0xe8))return POLITICS_BINDING_CHANGED;
 out->resource=*(int*)(category+0x78);
 out->reason="unsupported_cost_resource";if(out->resource<0||out->resource>4)return POLITICS_BAD_ARGUMENT;
 uintptr_t array=*(uintptr_t*)(manager+0x50);int capacity=*(int*)(manager+0x58),count=*(int*)(manager+0x5c);
 out->reason="law_binding_changed";
 if(count<1||count>capacity||capacity>100000||!can_read((void*)array,(size_t)count*8))return POLITICS_BINDING_CHANGED;
 for(int i=0;i<count;i++){
  uintptr_t idea=((uintptr_t*)array)[i];
  if(!can_read((void*)idea,0xac8)||*(uintptr_t*)idea!=image+0x29815e0)return POLITICS_BINDING_CHANGED;
  if(*(uintptr_t*)(idea+0xaa0)!=group)continue;
  out->reason="ambiguous_current_law";if(out->previous)return POLITICS_BAD_ARGUMENT;
  out->previous=idea;
 }
 out->reason="no_current_law";if(!out->previous)return POLITICS_BAD_ARGUMENT;
 out->reason="already_selected";if(out->previous==requested)return POLITICS_BAD_ARGUMENT;
 uintptr_t command=0;
 enum politics_result result=politics_construct_tagged(image,0x29958a0,tag,out->previous,requested,rid,can_read,intent,&command);
 out->reason="law_construction_failed";if(result!=POLITICS_OBJECT_CONSTRUCTED)return result;
 if(*(unsigned char*)(command+0x40)!=1)return POLITICS_BINDING_CHANGED;
 out->reason="cost_balance_unreadable";
 if(!law_balance(image,country,manager,out->resource,can_read,&out->before))return POLITICS_BINDING_CHANGED;
 /* Match executor1159b70 exactly, including native ranked/modifier-adjusted cost. */
 int64_t old_cost=0,new_cost=0;
 LAW_COST(image+0xba9410,manager,&old_cost,out->previous);
 LAW_COST(image+0xba92b0,manager,&new_cost,requested);
 out->reason="cost_overflow";
 if((new_cost>0&&old_cost>INT64_MAX-new_cost)||(new_cost<0&&old_cost<INT64_MIN-new_cost))return POLITICS_BAD_ARGUMENT;
 out->cost=old_cost+new_cost;out->cost_computed=1;out->reason="native_rules_rejected";
 result=politics_execute_resolved(image,command,NULL,rid,can_read,intent);
 if(result==POLITICS_BINDING_CHANGED)out->reason="law_binding_changed";
 if(result!=POLITICS_EXECUTION_RETURNED)return result;
 out->reason="law_postcondition_failed";
 if(!law_balance(image,country,manager,out->resource,can_read,&out->after))return result;
 int64_t charged=out->cost>0?out->cost:0;
 if(out->before<INT64_MIN+charged)return result;
 out->verified=law_membership(manager,out->previous,requested,can_read)&&out->after==out->before-charged&&
  *(unsigned char*)(command+0x40)==(out->cost>0?1:0);
 if(out->verified)out->reason="native_law_and_payment_verified";
 return result;
}
