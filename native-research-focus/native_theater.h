#ifndef HOI4_NATIVE_THEATER_H
#define HOI4_NATIVE_THEATER_H
/* Caller pins executable/world/game thread and owns the
 * durable request ledger. IDs are COrdersGroup/CArmyGroup IDs, never unit IDs.
 * Uses ordinary constructed CAssignToTheaterGroupCommand, validation/execution,
 * then independent native membership reads. No keyboard/mouse or direct state writes. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#ifndef THEATER_RESOLVE
#define THEATER_RESOLVE(fn,id) ((uintptr_t(*)(const uint32_t*))(fn))(id)
#define THEATER_ALLOC(fn,n) ((uintptr_t(*)(size_t))(fn))(n)
#define THEATER_CONSTRUCT(fn,c,v,t,n) ((uintptr_t(*)(uintptr_t,const void*,uintptr_t,const void*))(fn))(c,v,t,n)
#define THEATER_VALIDATE(fn,c) ((unsigned char(*)(uintptr_t,void*))(fn))(c,NULL)
#define THEATER_EXECUTE(fn,c) ((void(*)(uintptr_t))(fn))(c)
#define THEATER_DESTROY(fn,c) ((uintptr_t(*)(uintptr_t,unsigned))(fn))(c,1)
#endif
struct theater_vector {uintptr_t data;int32_t capacity,count;uintptr_t allocator;};
struct theater_string {union {char text[16];uintptr_t pointer;} data;uint64_t length,capacity;};
struct theater_outcome {const char *reason;int verified;uint32_t target_id[2];size_t affected_groups;};
enum theater_result {THEATER_BAD_ARGUMENT,THEATER_BINDING_CHANGED,THEATER_INTENT_FAILED,
 THEATER_ALLOCATION_FAILED,THEATER_RULES_REJECTED,THEATER_EXECUTION_RETURNED};
static int theater_vector_read(uintptr_t at,struct theater_vector *v,int(*readable)(const void*,size_t)){
 if(!readable((void*)at,16))return 0;
 memcpy(v,(void*)at,16);v->allocator=0;
 return v->count>=0&&v->count<=v->capacity&&v->capacity<=100000&&
  (!v->count||readable((void*)v->data,(size_t)v->count*8));
}
static int theater_occurrences(const struct theater_vector *v,uintptr_t object){
 int found=0;for(int i=0;i<v->count;i++)if(((uintptr_t*)v->data)[i]==object)found++;
 return found;
}
static int theater_handle(uintptr_t image,uintptr_t object,int(*readable)(const void*,size_t)){
 if(!readable((void*)object,16))return 0;
 const uint32_t *id=(uint32_t*)(object+8);
 return id[0]&&id[1]&&THEATER_RESOLVE(image+0x221f310,id)==object;
}
static int theater_owned_group(uintptr_t image,uintptr_t object,uintptr_t manager,uint32_t tag,
 const struct theater_vector *groups,int(*readable)(const void*,size_t)){
 if(!readable((void*)object,0x188))return 0;
 uintptr_t vt=*(uintptr_t*)object;
 if(vt!=image+0x29522b0&&vt!=image+0x2952348)return 0;
 return *(unsigned char*)(object+0x10)&&*(unsigned char*)(object+0x39)==(vt==image+0x2952348)&&
  *(uint32_t*)(object+0x3c)==tag&&*(uintptr_t*)(object+0x40)==manager&&
  theater_occurrences(groups,object)==1&&theater_handle(image,object,readable);
}
static int theater_owned_target(uintptr_t image,uintptr_t target,uintptr_t manager,
 const struct theater_vector *theaters,int(*readable)(const void*,size_t)){
 return readable((void*)target,0x60)&&*(uintptr_t*)target==image+0x29e5c50&&
  *(uintptr_t*)(target+0x18)==manager&&theater_occurrences(theaters,target)==1&&
  theater_handle(image,target,readable);
}
static enum theater_result theater_change(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t (*ids)[2],size_t count,const uint32_t target_id[2],const char *name,const char *rid,
 int(*readable)(const void*,size_t),int(*read_name)(uintptr_t,size_t,char*,size_t),
 int(*intent)(const char*),struct theater_outcome *out){
 memset(out,0,sizeof *out);out->reason="invalid_theater_arguments";
 if(!count||count>100000||!ids||!name||strlen(name)>159||!rid||!rid[0]||
    (target_id&&name[0]))return THEATER_BAD_ARGUMENT;
 out->reason="theater_binding_changed";
 if(!tag||!readable((void*)country,0x178)||*(uintptr_t*)country!=image+0x27e7360||
    *(uint32_t*)(country+8)!=tag)return THEATER_BINDING_CHANGED;
 struct theater_vector managers,groups,theaters;
 if(!theater_vector_read(country+0x168,&managers,readable))return THEATER_BINDING_CHANGED;
 uintptr_t first=THEATER_RESOLVE(image+0x221f310,ids[0]);
 if(!readable((void*)first,0x48))return THEATER_BINDING_CHANGED;
 uintptr_t manager=*(uintptr_t*)(first+0x40);
 if(!readable((void*)manager,0xd8)||*(uintptr_t*)manager!=image+0x2975a48||
    *(uint32_t*)(manager+0x48)!=tag||theater_occurrences(&managers,manager)!=1||
    !theater_vector_read(manager+0xb0,&groups,readable)||
    !theater_vector_read(manager+0xc8,&theaters,readable))return THEATER_BINDING_CHANGED;
 if(count>(size_t)groups.count)return THEATER_BAD_ARGUMENT;
 uintptr_t *sources=calloc((size_t)groups.count,sizeof *sources),*closure=calloc((size_t)groups.count,sizeof *closure);
 int previous_count=theaters.count;
 uint64_t *previous_ids=calloc(theaters.count?(size_t)theaters.count:1,sizeof *previous_ids);
 enum theater_result result=THEATER_BINDING_CHANGED;uintptr_t command=0,target=0;int constructed_ok=0;size_t affected=0;
 if(!sources||!closure||!previous_ids){result=THEATER_ALLOCATION_FAILED;goto done;}
 for(int i=0;i<theaters.count;i++){
  uintptr_t item=((uintptr_t*)theaters.data)[i];
  if(!theater_owned_target(image,item,manager,&theaters,readable))goto done;
  memcpy(&previous_ids[i],(void*)(item+8),8);
 }
 for(size_t i=0;i<count;i++){
  for(size_t j=0;j<i;j++)if(!memcmp(ids[i],ids[j],8)){result=THEATER_BAD_ARGUMENT;out->reason="duplicate_group_id";goto done;}
  uintptr_t group=THEATER_RESOLVE(image+0x221f310,ids[i]);
  if(!theater_owned_group(image,group,manager,tag,&groups,readable))goto done;
  sources[i]=group;closure[affected++]=group;
 }
 /* Assignment recursively includes CArmyGroup children in the ordinary executor. */
 for(size_t i=0;i<affected;i++){
  uintptr_t group=closure[i];if(*(uintptr_t*)group!=image+0x2952348)continue;
  struct theater_vector children;if(!theater_vector_read(group+0x230,&children,readable))goto done;
  for(int j=0;j<children.count;j++){
   uintptr_t child=((uintptr_t*)children.data)[j];size_t k=0;
   if(!theater_owned_group(image,child,manager,tag,&groups,readable))goto done;
   while(k<affected&&closure[k]!=child)k++;
   if(k==affected){if(affected>=(size_t)groups.count)goto done;closure[affected++]=child;}
  }
 }
 if(target_id){
  target=THEATER_RESOLVE(image+0x221f310,target_id);
  if(!theater_owned_target(image,target,manager,&theaters,readable))goto done;
  int already=1;for(size_t i=0;i<affected;i++)if(*(uintptr_t*)(closure[i]+0x180)!=target)already=0;
  if(already){result=THEATER_BAD_ARGUMENT;out->reason="already_assigned";goto done;}
 }
 uintptr_t vt=image+0x2a326d0;
 if(!readable((void*)vt,88)||*(uintptr_t*)vt!=image+0x1a7dc20||
    *(uintptr_t*)(vt+72)!=image+0x1a7fb40||*(uintptr_t*)(vt+80)!=image+0x1a7e8c0)goto done;
 out->reason="theater_intent_failed";result=THEATER_INTENT_FAILED;if(!intent(rid))goto done;
 command=THEATER_ALLOC(image+0x21c9af0,0x68);
 out->reason="theater_allocation_failed";result=THEATER_ALLOCATION_FAILED;if(!command)goto done;
 struct theater_vector input={(uintptr_t)sources,(int32_t)count,(int32_t)count,0};
 struct theater_string text;memset(&text,0,sizeof text);text.length=strlen(name);text.capacity=text.length>15?text.length:15;
 if(text.length>15)text.data.pointer=(uintptr_t)name;else memcpy(text.data.text,name,(size_t)text.length+1);
 uintptr_t constructed=THEATER_CONSTRUCT(image+0x1a7d110,command,&input,target,&text);
 out->reason="theater_command_binding_changed";result=THEATER_BINDING_CHANGED;
 if(constructed!=command||!readable((void*)command,0x68)||*(uintptr_t*)command!=vt)goto done;
 constructed_ok=1;
 /* Incoming RDX is not consumed by validator1a7fb40; first RDX use overwrites it. */
 out->reason="theater_intent_failed";result=THEATER_INTENT_FAILED;if(!intent(rid))goto done;
 out->reason="native_rules_rejected";result=THEATER_RULES_REJECTED;
 if(!THEATER_VALIDATE(image+0x1a7fb40,command))goto done;
 THEATER_EXECUTE(image+0x1a7e8c0,command);result=THEATER_EXECUTION_RETURNED;
 out->reason="theater_postcondition_failed";
 if(!theater_vector_read(manager+0xb0,&groups,readable)||!theater_vector_read(manager+0xc8,&theaters,readable))goto done;
 if(!readable((void*)sources[0],0x188))goto done;
 uintptr_t observed=*(uintptr_t*)(sources[0]+0x180);
 if(!theater_owned_target(image,observed,manager,&theaters,readable)||(target&&observed!=target))goto done;
 uint64_t observed_id;memcpy(&observed_id,(void*)(observed+8),8);
 /* previous_ids uses the pre-execution list; old theaters may be destroyed. */
 for(int i=0;i<previous_count;i++)if(!target&&previous_ids[i]==observed_id)goto done;
 for(size_t i=0;i<affected;i++){
  uintptr_t group=closure[i];if(!theater_owned_group(image,group,manager,tag,&groups,readable)||*(uintptr_t*)(group+0x180)!=observed)goto done;
  int found=0;
  for(int j=0;j<theaters.count;j++){
   uintptr_t item=((uintptr_t*)theaters.data)[j];struct theater_vector members;
   if(!theater_owned_target(image,item,manager,&theaters,readable)||!theater_vector_read(item+0x48,&members,readable))goto done;
   int n=theater_occurrences(&members,group);if(n&&(item!=observed||n!=1))goto done;found+=n;
  }
  if(found!=1)goto done;
 }
 if(name[0]){char actual[160];if(!read_name(observed,0x28,actual,sizeof actual)||strcmp(actual,name))goto done;}
 memcpy(out->target_id,(void*)(observed+8),8);out->affected_groups=affected;out->verified=1;out->reason="native_theater_membership_verified";
 done:
 if(constructed_ok)THEATER_DESTROY(image+0x1a7dc20,command);
 free(previous_ids);free(closure);free(sources);return result;
}
#endif
