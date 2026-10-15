#ifndef HOI4_NATIVE_ARMY_GROUP_H
#define HOI4_NATIVE_ARMY_GROUP_H
/* Semantic new army + army-group from owned CArmy IDs. Caller pins executable,
 * world/game thread and durable request ledger. No input automation/state setters. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#ifndef ARMY_RESOLVE
#define ARMY_RESOLVE(fn,id) ((uintptr_t(*)(const uint32_t*))(fn))(id)
#define ARMY_FACTORY(fn) ((uintptr_t(*)(void))(fn))()
#define ARMY_APPEND(fn,out,in) ((uintptr_t(*)(uintptr_t,const void*))(fn))(out,in)
#define ARMY_VALIDATE(fn,cmd) ((unsigned char(*)(uintptr_t,void*))(fn))(cmd,NULL)
#define ARMY_EXECUTE(fn,cmd) ((void(*)(uintptr_t))(fn))(cmd)
#define ARMY_DESTROY(fn,cmd) ((uintptr_t(*)(uintptr_t,unsigned))(fn))(cmd,1)
#endif
struct army_vector {uintptr_t data;int32_t capacity,count;uintptr_t allocator;};
struct army_group_outcome {const char *reason;int verified;uint32_t group_id[2],army_group_id[2],theater_id[2];size_t unit_count;};
enum army_group_result {ARMY_BAD_ARGUMENT,ARMY_BINDING_CHANGED,ARMY_INTENT_FAILED,
 ARMY_ALLOCATION_FAILED,ARMY_RULES_REJECTED,ARMY_EXECUTION_RETURNED};
static int army_vector_read(uintptr_t where,struct army_vector *v,int(*readable)(const void*,size_t)){
 if(!readable((void*)where,16))return 0;
 memcpy(v,(void*)where,16);v->allocator=0;
 return v->count>=0&&v->count<=v->capacity&&v->capacity<=100000&&(!v->count||readable((void*)v->data,(size_t)v->count*8));
}
static int army_occurrences(const struct army_vector *v,uintptr_t item){int n=0;for(int i=0;i<v->count;i++)if(((uintptr_t*)v->data)[i]==item)n++;return n;}
static int army_handle(uintptr_t image,uintptr_t object,int(*readable)(const void*,size_t)){
 if(!readable((void*)object,16))return 0;
 const uint32_t *id=(uint32_t*)(object+8);return (id[0]|id[1])&&ARMY_RESOLVE(image+0x221f310,id)==object;
}
static int army_owned_unit(uintptr_t image,uintptr_t unit,uint32_t tag,const struct army_vector *units,int(*readable)(const void*,size_t)){
 return readable((void*)unit,0x1dc)&&*(uintptr_t*)unit==image+0x295a2b0&&
  *(uintptr_t*)(unit+0x10)==image+0x295a490&&*(uintptr_t*)(unit+0xb8)==image+0x295a500&&
  *(uint32_t*)(unit+0x1d8)==tag&&army_occurrences(units,unit)==1&&army_handle(image,unit+0x10,readable);
}
static int army_owned_group(uintptr_t image,uintptr_t group,uintptr_t manager,uint32_t tag,
 const struct army_vector *groups,int parent,int(*readable)(const void*,size_t)){
 return readable((void*)group,parent?0x240:0x1c0)&&*(uintptr_t*)group==image+(parent?0x2952348:0x29522b0)&&
  *(unsigned char*)(group+0x10)&&*(unsigned char*)(group+0x39)==parent&&*(uint32_t*)(group+0x3c)==tag&&
  *(uintptr_t*)(group+0x40)==manager&&army_occurrences(groups,group)==1&&army_handle(image,group,readable);
}
static enum army_group_result army_create_from_units(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t manager_id[2],const uint32_t (*ids)[2],size_t count,const char *rid,
 int(*readable)(const void*,size_t),int(*intent)(const char*),struct army_group_outcome *out){
 memset(out,0,sizeof *out);out->reason="invalid_army_group_arguments";
 if(!manager_id||!ids||!count||count>100000||!rid||!rid[0])return ARMY_BAD_ARGUMENT;
 out->reason="army_group_binding_changed";
 if(!tag||!readable((void*)country,0x2a0)||*(uintptr_t*)country!=image+0x27e7360||*(uint32_t*)(country+8)!=tag)return ARMY_BINDING_CHANGED;
 struct army_vector managers,units,groups;
 if(!army_vector_read(country+0x168,&managers,readable)||!army_vector_read(country+0x290,&units,readable))return ARMY_BINDING_CHANGED;
 uintptr_t manager=ARMY_RESOLVE(image+0x221f310,manager_id);
 if(!readable((void*)manager,0xd8)||*(uintptr_t*)manager!=image+0x2975a48||*(uint32_t*)(manager+0x48)!=tag||
    army_occurrences(&managers,manager)!=1||!army_handle(image,manager,readable)||!army_vector_read(manager+0xb0,&groups,readable))return ARMY_BINDING_CHANGED;
 if(count>(size_t)units.count)return ARMY_BAD_ARGUMENT;
 uintptr_t *selected=calloc(count,sizeof *selected);int old_count=groups.count;
 uint64_t *old_ids=calloc(old_count?(size_t)old_count:1,sizeof *old_ids);
 uintptr_t command=0;int constructed=0;enum army_group_result result=ARMY_BINDING_CHANGED;
 if(!selected||!old_ids){result=ARMY_ALLOCATION_FAILED;goto done;}
 for(int i=0;i<old_count;i++){
  uintptr_t g=((uintptr_t*)groups.data)[i];
  if(!readable((void*)g,16)||!army_handle(image,g,readable))goto done;
  memcpy(old_ids+i,(void*)(g+8),8);
 }
 for(size_t i=0;i<count;i++){
  for(size_t j=0;j<i;j++)if(!memcmp(ids[i],ids[j],8)){result=ARMY_BAD_ARGUMENT;out->reason="duplicate_unit_id";goto done;}
  uintptr_t object=ARMY_RESOLVE(image+0x221f310,ids[i]);
  if(object<0x10||!army_owned_unit(image,object-0x10,tag,&units,readable))goto done;
  selected[i]=object-0x10;
 }
 uintptr_t vt=image+0x2a0ac88;
 if(!readable((void*)vt,88)||*(uintptr_t*)vt!=image+0x183c7b0||*(uintptr_t*)(vt+72)!=image+0x184cfc0||*(uintptr_t*)(vt+80)!=image+0x1842970)goto done;
 out->reason="army_group_intent_failed";result=ARMY_INTENT_FAILED;if(!intent(rid))goto done;
 command=ARMY_FACTORY(image+0x183fa60);result=ARMY_ALLOCATION_FAILED;out->reason="army_group_factory_failed";
 if(!readable((void*)command,0x80)||*(uintptr_t*)command!=vt)goto done;
 constructed=1;result=ARMY_BINDING_CHANGED;out->reason="army_group_command_binding_changed";
 if(*(int*)(command+0x3c)||*(int*)(command+0x54)||!readable((void*)(image+0x333d528),8)||
    memcmp((void*)(command+0x60),(void*)(image+0x333d528),8)||
    *(int*)(command+0x68)!=-1||*(int64_t*)(command+0x70)!=-100000||*(int64_t*)(command+0x78)!=-100000)goto done;
 memcpy((void*)(command+0x28),(void*)(manager+8),8);
 struct army_vector input={(uintptr_t)ids,(int32_t)count,(int32_t)count,0};
 ARMY_APPEND(image+0x1835920,command+0x48,&input);
 struct army_vector outer,inner;
 if(!army_vector_read(command+0x48,&outer,readable)||outer.count!=1||!readable((void*)outer.data,24)||
    !army_vector_read(outer.data,&inner,readable)||inner.count!=(int)count||memcmp((void*)inner.data,ids,count*8))goto done;
 out->reason="army_group_intent_failed";result=ARMY_INTENT_FAILED;if(!intent(rid))goto done;
 out->reason="native_rules_rejected";result=ARMY_RULES_REJECTED;
 if(!ARMY_VALIDATE(image+0x184cfc0,command))goto done;
 ARMY_EXECUTE(image+0x1842970,command);result=ARMY_EXECUTION_RETURNED;out->reason="army_group_postcondition_failed";
 if(!army_vector_read(country+0x290,&units,readable)||!army_vector_read(manager+0xb0,&groups,readable)||
    !readable((void*)selected[0],0xc8))goto done;
 uintptr_t child=*(uintptr_t*)(selected[0]+0xc0);
 if(!army_owned_group(image,child,manager,tag,&groups,0,readable))goto done;
 uintptr_t parent=*(uintptr_t*)(child+0x1b8);
 if(!army_owned_group(image,parent,manager,tag,&groups,1,readable))goto done;
 uint64_t child_id,parent_id;memcpy(&child_id,(void*)(child+8),8);memcpy(&parent_id,(void*)(parent+8),8);
 if(child_id==parent_id)goto done;
 for(int i=0;i<old_count;i++)if(old_ids[i]==child_id||old_ids[i]==parent_id)goto done;
 struct army_vector members,children,ordinary,parents,theaters,theater_members;
 if(!army_vector_read(child+0x50,&members,readable)||members.count!=(int)count||
    !army_vector_read(parent+0x230,&children,readable)||children.count!=1||army_occurrences(&children,child)!=1||
    !army_vector_read(manager+0x80,&ordinary,readable)||army_occurrences(&ordinary,child)!=1||
    !army_vector_read(manager+0x98,&parents,readable)||army_occurrences(&parents,parent)!=1)goto done;
 for(size_t i=0;i<count;i++){
  uintptr_t unit=selected[i];if(!army_owned_unit(image,unit,tag,&units,readable)||*(uintptr_t*)(unit+0xc0)!=child||army_occurrences(&members,unit+0xb8)!=1)goto done;
  for(int j=0;j<groups.count;j++){
   uintptr_t g=((uintptr_t*)groups.data)[j];if(g==child)continue;
   if(!readable((void*)g,0x40))goto done;
   if(*(unsigned char*)(g+0x39))continue; /* Parent aggregates are a separate native contract. */
   struct army_vector other;if(!army_vector_read(g+0x50,&other,readable)||army_occurrences(&other,unit+0xb8))goto done;
  }
 }
 uintptr_t theater=*(uintptr_t*)(child+0x180);
 if(!army_vector_read(manager+0xc8,&theaters,readable)||!readable((void*)theater,0x60)||*(uintptr_t*)theater!=image+0x29e5c50||
    *(uintptr_t*)(theater+0x18)!=manager||army_occurrences(&theaters,theater)!=1||!army_handle(image,theater,readable)||
    *(uintptr_t*)(parent+0x180)!=theater||!army_vector_read(theater+0x48,&theater_members,readable)||
    army_occurrences(&theater_members,child)!=1||army_occurrences(&theater_members,parent)!=1)goto done;
 memcpy(out->group_id,(void*)(child+8),8);memcpy(out->army_group_id,(void*)(parent+8),8);memcpy(out->theater_id,(void*)(theater+8),8);
 out->unit_count=count;out->verified=1;out->reason="native_unit_group_membership_verified";
 done:if(constructed)ARMY_DESTROY(image+0x183c7b0,command);free(old_ids);free(selected);return result;
}
#endif
