#ifndef HOI4_NATIVE_DEPLOYMENT_EXECUTE_H
#define HOI4_NATIVE_DEPLOYMENT_EXECUTE_H
#include <stdlib.h>
#include <string.h>
#include "native_deployment_candidate.h"
#ifndef DEPLOY_EXECUTE
#define DEPLOY_EXECUTE(fn,cmd) ((void(*)(uintptr_t))(fn))(cmd)
#endif
struct deployment_outcome {int executed,verified;uint32_t conveyor_id[2],line_id[2],unit_id[2];const char *reason;};
struct deploy_list {uintptr_t data;int32_t capacity,count;};
static int deploy_list_read(uintptr_t at,struct deploy_list*v,int(*readable)(const void*,size_t)){
 if(!readable((void*)at,16))return 0;memcpy(v,(void*)at,16);
 return v->count>=0&&v->count<=v->capacity&&v->capacity<=100000&&
  (!v->count||readable((void*)v->data,(size_t)v->count*8));
}
static int deploy_bound_id(uintptr_t image,uintptr_t object,uint64_t *id,int(*readable)(const void*,size_t)){
 if(!readable((void*)object,16))return 0;
 memcpy(id,(void*)(object+8),8);
 return (uint32_t)*id&&(*id>>32)&&DEPLOY_RESOLVE(image+0x221f310,(uint32_t*)id)==object;
}
/* Ordinary semantic create: pin ledger intent before preparation and immediately
 * before execution. Caller records executed even when postcondition fails. */
static const char *deployment_create_queue(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t template_id[2],const char *request_id,int(*readable)(const void*,size_t),
 int(*intent)(const char*),struct deployment_outcome *out){
 memset(out,0,sizeof*out);out->reason="invalid_deployment_request";
 if(!request_id||!request_id[0]||!intent)return out->reason;
 if(!intent(request_id))return out->reason="deployment_intent_failed";
 uintptr_t command=0;const char *err=deployment_prepare_queue(image,country,tag,template_id,readable,&command);
 if(err)return out->reason=err;
 uintptr_t manager=*(uintptr_t*)(country+0xf70);struct deploy_list before,after;
 uint64_t *ids=NULL;out->reason="deployment_binding_changed";
 if(!deploy_list_read(manager+0x48,&before,readable))goto done;
 ids=(uint64_t*)calloc((size_t)before.count+1,sizeof*ids);
 if(!ids){out->reason="deployment_allocation_failed";goto done;}
 for(int i=0;i<before.count;i++){
  uintptr_t p=((uintptr_t*)before.data)[i];
  if(!readable((void*)p,0xa0)||*(uintptr_t*)p!=image+0x295e100||!deploy_bound_id(image,p,&ids[i],readable))goto done;
  for(int j=0;j<i;j++)if(ids[i]==ids[j])goto done;
 }
 if(!intent(request_id)){out->reason="deployment_intent_failed";goto done;}
 /* This is the normal command executor, not direct writes to queue memory. */
 DEPLOY_EXECUTE(image+0x1ba3060,command);out->executed=1;
 out->reason="deployment_queue_postcondition_failed";
 if(!readable((void*)country,0xf78)||*(uintptr_t*)(country+0xf70)!=manager||
    *(uint32_t*)(country+8)!=tag||!readable((void*)manager,0x120)||
    *(uintptr_t*)manager!=image+0x295fc38||*(uintptr_t*)(manager+0x118)!=country||
    !deploy_list_read(manager+0x48,&after,readable)||after.count!=before.count+1)goto done;
 uintptr_t added=0;uint64_t added_id=0;int old_matched=0;
 for(int i=0;i<after.count;i++){
  uintptr_t p=((uintptr_t*)after.data)[i];uint64_t id=0;
  if(!readable((void*)p,0xa0)||*(uintptr_t*)p!=image+0x295e100||!deploy_bound_id(image,p,&id,readable))goto done;
  for(int j=0;j<i;j++)if(((uintptr_t*)after.data)[j]==p)goto done;
  int old=0;for(int j=0;j<before.count;j++)if(ids[j]==id){old=1;old_matched++;break;}
  if(!old){if(added)goto done;added=p;added_id=id;}
 }
 if(!added||old_matched!=before.count)goto done;
 uintptr_t templ=DEPLOY_RESOLVE(image+0x221f310,template_id);
 if(!readable((void*)templ,0x260)||*(uintptr_t*)templ!=image+0x294f5b0||
    *(uint32_t*)(templ+0x1ec)!=tag||*(uintptr_t*)(added+0x20)!=templ||
    !deploy_member(country+0x1b8,templ,readable))goto done;
 struct deploy_list lines;if(!deploy_list_read(added+0x78,&lines,readable)||lines.count!=1)goto done;
 uintptr_t line=((uintptr_t*)lines.data)[0];uint64_t lineid=0;
 if(!readable((void*)line,0x40)||*(uintptr_t*)line!=image+0x295e0a8||
    *(uintptr_t*)(line+0x38)!=added||!deploy_bound_id(image,line,&lineid,readable))goto done;
 uintptr_t entry=*(uintptr_t*)(line+0x30);
 if(!readable((void*)entry,0xc8)||*(uintptr_t*)entry!=image+0x295e020||*(uintptr_t*)(entry+0xb8)!=line)goto done;
 memcpy(out->conveyor_id,&added_id,8);memcpy(out->line_id,&lineid,8);
 out->verified=1;out->reason=NULL;
 done:free(ids);DEPLOY_DESTROY(image+0xdb4550,command);return out->reason;
}
static const char *deployment_set_location(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t conveyor_id[2],int32_t province,const char *request_id,
 int(*readable)(const void*,size_t),int(*intent)(const char*),struct deployment_outcome *out){
 memset(out,0,sizeof*out);out->reason="invalid_deployment_request";
 if(!request_id||!request_id[0]||!intent)return out->reason;
 if(!intent(request_id))return out->reason="deployment_intent_failed";
 uintptr_t command=0;const char *err=deployment_prepare_location(image,country,tag,conveyor_id,province,readable,&command);
 if(err)return out->reason=err;
 if(!intent(request_id)){out->reason="deployment_intent_failed";goto done;}
 if(!DEPLOY_VALIDATE(image+0x1ba3c10,command)){out->reason="deployment_native_location_rules_rejected";goto done;}
 DEPLOY_EXECUTE(image+0x1ba3510,command);out->executed=1;out->reason="deployment_location_postcondition_failed";
 if(!readable((void*)country,0xf78)||*(uint32_t*)(country+8)!=tag)goto done;
 uintptr_t manager=*(uintptr_t*)(country+0xf70),conveyor=DEPLOY_RESOLVE(image+0x221f310,conveyor_id);
 if(!readable((void*)manager,0x120)||*(uintptr_t*)manager!=image+0x295fc38||
    *(uintptr_t*)(manager+0x118)!=country||!readable((void*)conveyor,0xa0)||
    *(uintptr_t*)conveyor!=image+0x295e100||!deploy_member(manager+0x48,conveyor,readable)||
    *(int32_t*)(conveyor+0x4c)!=province)goto done;
 uintptr_t templ=*(uintptr_t*)(conveyor+0x20);
 if(!readable((void*)templ,0x260)||*(uintptr_t*)templ!=image+0x294f5b0||
    *(uint32_t*)(templ+0x1ec)!=tag||!deploy_member(country+0x1b8,templ,readable))goto done;
 memcpy(out->conveyor_id,conveyor_id,8);out->verified=1;out->reason=NULL;
 done:DEPLOY_DESTROY(image+0xdb4550,command);return out->reason;
}
/* Compare canonical resource rows independently of allocator/order metadata.
 * Equipment rows24: key pointer+0, quantity+16. Manpower rows8: country key+0,
 * amount+4. One-to-one matching preserves duplicate rows without inventing IDs. */
static int deploy_resources_match(const unsigned char *expected,int32_t count,
 uintptr_t field,size_t width,int(*readable)(const void*,size_t)){
 struct deploy_list actual;if(!deploy_list_read(field,&actual,readable)||actual.count!=count||
   (count&&!readable((void*)actual.data,(size_t)count*width)))return 0;
 unsigned char *used=(unsigned char*)calloc((size_t)count+1,1);if(!used)return 0;
 int matched=1;
 for(int32_t i=0;i<count;i++){
  const unsigned char *row=expected+(size_t)i*width;int found=0;
  for(int32_t j=0;j<count;j++)if(!used[j]){
   const unsigned char *other=(unsigned char*)actual.data+(size_t)j*width;
   if((width==24&&!memcmp(row,other,8)&&!memcmp(row+16,other+16,8))||
      (width==8&&!memcmp(row,other,8))){used[j]=1;found=1;break;}
  }
  if(!found){matched=0;break;}
 }
 free(used);return matched;
}
static int deploy_unit_id(uintptr_t image,uintptr_t unit,uint64_t *id,int(*readable)(const void*,size_t)){
 if(!readable((void*)unit,0x688)||*(uintptr_t*)unit!=image+0x295a2b0||
    *(uintptr_t*)(unit+0x10)!=image+0x295a490)return 0;
 memcpy(id,(void*)(unit+0x18),8);
 return (uint32_t)*id&&(*id>>32)&&DEPLOY_RESOLVE(image+0x221f310,(uint32_t*)id)==unit+0x10;
}
static const char *deployment_deploy_line(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t line_id[2],const char *request_id,int(*readable)(const void*,size_t),
 int(*intent)(const char*),struct deployment_outcome *out){
 memset(out,0,sizeof*out);out->reason="invalid_deployment_request";
 if(!request_id||!request_id[0]||!intent)return out->reason;
 if(!intent(request_id))return out->reason="deployment_intent_failed";
 uintptr_t command=0;const char *err=deployment_prepare_line(image,country,tag,line_id,readable,&command);
 if(err)return out->reason=err;
 uintptr_t line=DEPLOY_RESOLVE(image+0x221f310,line_id),conveyor=*(uintptr_t*)(line+0x38);
 uintptr_t templ=*(uintptr_t*)(conveyor+0x20),entry=*(uintptr_t*)(line+0x30);
 int32_t province=*(int32_t*)(conveyor+0x4c);struct deploy_list before,after,equipment,manpower;
 uint64_t *ids=NULL;unsigned char *eq=NULL,*men=NULL;out->reason="deployment_binding_changed";
 if(province<=0||!deploy_list_read(country+0x290,&before,readable)||
    !deploy_list_read(entry+0x28,&equipment,readable)||!deploy_list_read(entry+0x78,&manpower,readable)||
    (equipment.count&&!readable((void*)equipment.data,(size_t)equipment.count*24)))goto done;
 ids=(uint64_t*)calloc((size_t)before.count+1,8);
 eq=(unsigned char*)malloc((size_t)equipment.count*24+1);men=(unsigned char*)malloc((size_t)manpower.count*8+1);
 if(!ids||!eq||!men){out->reason="deployment_allocation_failed";goto done;}
 if(equipment.count)memcpy(eq,(void*)equipment.data,(size_t)equipment.count*24);
 if(manpower.count)memcpy(men,(void*)manpower.data,(size_t)manpower.count*8);
 for(int i=0;i<before.count;i++){
  uintptr_t p=((uintptr_t*)before.data)[i];
  if(!deploy_unit_id(image,p,&ids[i],readable)||*(uint32_t*)(p+0x1d8)!=tag)goto done;
  for(int j=0;j<i;j++)if(ids[i]==ids[j])goto done;
 }
 if(!intent(request_id)){out->reason="deployment_intent_failed";goto done;}
 if(DEPLOY_RESOLVE(image+0x221f310,line_id)!=line||!DEPLOY_READY(image+0xce7d50,line)||
    !DEPLOY_VALIDATE(image+0x1162ce0,command)){out->reason="deployment_native_rules_rejected";goto done;}
 DEPLOY_EXECUTE(image+0x1ba3270,command);out->executed=1;out->reason="deployment_unit_postcondition_failed";
 /* Never dereference line, conveyor or current entry after native execution. */
 if(!readable((void*)country,0xf78)||*(uint32_t*)(country+8)!=tag||
    !deploy_list_read(country+0x290,&after,readable)||after.count!=before.count+1)goto done;
 uintptr_t added=0;uint64_t added_id=0;int old_matched=0;
 for(int i=0;i<after.count;i++){
  uintptr_t p=((uintptr_t*)after.data)[i];uint64_t id=0;
  if(!deploy_unit_id(image,p,&id,readable)||*(uint32_t*)(p+0x1d8)!=tag)goto done;
  for(int j=0;j<i;j++)if(((uintptr_t*)after.data)[j]==p)goto done;
  int old=0;for(int j=0;j<before.count;j++)if(ids[j]==id){old=1;old_matched++;break;}
  if(!old){if(added)goto done;added=p;added_id=id;}
 }
 if(!added||old_matched!=before.count||!readable((void*)templ,0x260)||
    *(uintptr_t*)templ!=image+0x294f5b0||*(uint32_t*)(templ+0x1ec)!=tag||
    !deploy_member(country+0x1b8,templ,readable)||*(uintptr_t*)(added+0x3b8)!=templ)goto done;
 uintptr_t location=*(uintptr_t*)(added+0x1f0);
 if(!readable((void*)location,0xa8)||*(int32_t*)(location+0xa4)!=province||
    !deploy_resources_match(eq,equipment.count,added+0x350,24,readable)||
    !deploy_resources_match(men,manpower.count,added+0x3e0,8,readable))goto done;
 memcpy(out->line_id,line_id,8);memcpy(out->unit_id,&added_id,8);out->verified=1;out->reason=NULL;
 done:free(ids);free(eq);free(men);DEPLOY_DESTROY(image+0x22d200,command);return out->reason;
}
#endif
