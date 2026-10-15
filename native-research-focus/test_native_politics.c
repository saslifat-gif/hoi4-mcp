/* Native invocation is simulated. No HOI4 process or game memory is accessed. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static int sequence,allow=1,persist=1;
static uintptr_t expected_validate,expected_execute,expected_command;
static void *expected_error;
static uintptr_t expected_factory,factory_object,resolved_object;
static uint32_t handle[2]={51,1};
static uintptr_t fake_factory(uintptr_t fn){assert(sequence++==1&&fn==expected_factory);return factory_object;}
static uintptr_t fake_resolve(uintptr_t fn,const uint32_t *id){assert(fn==expected_validate&&id==handle);return resolved_object;}
#define POLITICS_FACTORY(fn) fake_factory(fn)
#define POLITICS_RESOLVE(fn,id) fake_resolve((fn),(id))
static unsigned char fake_validate(uintptr_t fn,uintptr_t command,void *error){
 assert(sequence++==1&&fn==expected_validate&&command==expected_command&&error==expected_error);return (unsigned char)allow;
}
static void fake_execute(uintptr_t fn,uintptr_t command){assert(sequence++==2&&fn==expected_execute&&command==expected_command);}
#define POLITICS_VALIDATE(fn,cmd,error) fake_validate((fn),(cmd),(error))
#define POLITICS_EXECUTE(fn,cmd) fake_execute((fn),(cmd))
#include "native_politics.h"
static unsigned char *image_memory;
static uintptr_t command[12];static unsigned char error[1];
static int readable(const void *p,size_t n){
 uintptr_t address=(uintptr_t)p,base=(uintptr_t)image_memory;
 return (address>=base&&address+n<=base+0x3330000)||(p==(void*)command&&n<=sizeof command)||(p==handle&&n==8)||(p==error&&n==1);
}
static int intent(const char *rid){assert(sequence++==0&&!strcmp(rid,"existing-request"));return persist;}
static enum politics_result run(void){return politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,error,"existing-request",readable,intent);}
#include "native_name.h"
static void set_name(uintptr_t idea,const char *name){
 size_t n=strlen(name);assert(n<64);strcpy((char*)(idea+0x100),name);
 *(uintptr_t*)(idea+24)=idea+0x100;*(uint64_t*)(idea+40)=n;*(uint64_t*)(idea+48)=63;
}
int main(void){
 image_memory=calloc(1,0x3330000);assert(image_memory);expected_command=(uintptr_t)command;expected_error=error;
 for(size_t i=0;i<sizeof politics_methods/sizeof *politics_methods;i++){
  uintptr_t vt=(uintptr_t)image_memory+politics_methods[i].vtable;command[0]=vt;
  expected_validate=*(uintptr_t*)(vt+72)=(uintptr_t)image_memory+politics_methods[i].validate;
  expected_execute=*(uintptr_t*)(vt+80)=(uintptr_t)image_memory+politics_methods[i].execute;
  expected_factory=(uintptr_t)image_memory+politics_methods[i].factory;factory_object=(uintptr_t)command;
  uintptr_t built=0;sequence=0;
  assert(politics_construct_default((uintptr_t)image_memory,politics_methods[i].vtable,"existing-request",readable,intent,&built)==POLITICS_OBJECT_CONSTRUCTED&&built==(uintptr_t)command&&sequence==2);
  sequence=0;persist=0;assert(politics_construct_default((uintptr_t)image_memory,politics_methods[i].vtable,"existing-request",readable,intent,&built)==POLITICS_INTENT_FAILED&&built==0&&sequence==1);persist=1;
  sequence=0;factory_object=0;assert(politics_construct_default((uintptr_t)image_memory,politics_methods[i].vtable,"existing-request",readable,intent,&built)==POLITICS_FACTORY_FAILED&&built==0);factory_object=(uintptr_t)command;
  if(politics_methods[i].vtable==0x2995328||politics_methods[i].vtable==0x29958a0||politics_methods[i].vtable==0x2996908){
   int replace=politics_methods[i].vtable==0x29958a0;sequence=0;
   assert(politics_construct_tagged((uintptr_t)image_memory,politics_methods[i].vtable,1,0x1234,replace?0x5678:0,"existing-request",readable,intent,&built)==POLITICS_OBJECT_CONSTRUCTED);
   assert(*(uint32_t*)(built+0x28)==1&&*(uintptr_t*)(built+0x30)==0x1234);
   if(replace)assert(*(uintptr_t*)(built+0x38)==0x5678);
   sequence=0;assert(politics_construct_tagged((uintptr_t)image_memory,politics_methods[i].vtable,0,0x1234,0,"existing-request",readable,intent,&built)==POLITICS_BAD_ARGUMENT&&sequence==0);
  }
  sequence=0;expected_error=NULL;
  enum politics_result without_error=politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,NULL,"existing-request",readable,intent);
  if(politics_methods[i].vtable==0x29958a0||politics_methods[i].vtable==0x2995580||politics_methods[i].vtable==0x2996908){
   assert(without_error==POLITICS_EXECUTION_RETURNED&&sequence==3);
   sequence=0;allow=0;
   assert(politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,NULL,"existing-request",readable,intent)==POLITICS_RULES_REJECTED&&sequence==2);allow=1;
   sequence=0;persist=0;
   assert(politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,NULL,"existing-request",readable,intent)==POLITICS_INTENT_FAILED&&sequence==1);persist=1;
   sequence=0;*(uintptr_t*)(vt+72)=0;
   assert(politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,NULL,"existing-request",readable,intent)==POLITICS_BINDING_CHANGED&&sequence==0);
   *(uintptr_t*)(vt+72)=expected_validate;
  }else assert(without_error==POLITICS_BINDING_CHANGED&&sequence==0);
  sequence=0;
  assert(politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,(void*)1,"existing-request",readable,intent)==POLITICS_BINDING_CHANGED&&sequence==0);
  expected_error=error;
  sequence=0;assert(run()==POLITICS_EXECUTION_RETURNED&&sequence==3);
  sequence=0;persist=0;assert(run()==POLITICS_INTENT_FAILED&&sequence==1);persist=1;
  sequence=0;allow=0;assert(run()==POLITICS_RULES_REJECTED&&sequence==2);allow=1;
  sequence=0;*(uintptr_t*)(vt+80)=0;assert(run()==POLITICS_BINDING_CHANGED&&sequence==0);
 }
 sequence=0;command[0]=1;assert(run()==POLITICS_UNSUPPORTED&&sequence==0);
 assert(politics_execute_resolved((uintptr_t)image_memory,0,error,"existing-request",readable,intent)==POLITICS_BINDING_CHANGED);
 assert(politics_execute_resolved((uintptr_t)image_memory,(uintptr_t)command,NULL,"existing-request",readable,intent)==POLITICS_UNSUPPORTED);
 memcpy((unsigned char*)command+8,handle,8);resolved_object=(uintptr_t)command;expected_validate=(uintptr_t)image_memory+0x221f310;
 assert(politics_bind_native_handle((uintptr_t)image_memory,handle,(uintptr_t)command,readable)==(uintptr_t)command);
 assert(politics_bind_native_handle((uintptr_t)image_memory,handle,(uintptr_t)command+8,readable)==0);
 ((uint32_t*)((unsigned char*)command+8))[1]=2;
 assert(politics_bind_native_handle((uintptr_t)image_memory,handle,(uintptr_t)command,readable)==0);
 uintptr_t image=(uintptr_t)image_memory,db=image+0x1000,array=image+0x2000,null=image+0x3000,first=image+0x4000,second=image+0x5000;
 *(uintptr_t*)(image+0x332ef30)=db;*(uintptr_t*)db=image+0x293c2b0;*(uintptr_t*)(db+0x68)=array;*(int*)(db+0x70)=*(int*)(db+0x74)=3;
 ((uintptr_t*)array)[0]=null;((uintptr_t*)array)[1]=first;((uintptr_t*)array)[2]=second;
 *(uintptr_t*)null=image+0x293c510;*(uintptr_t*)(null+16)=image+0x293c560;
 *(uintptr_t*)first=*(uintptr_t*)second=image+0x29815e0;*(uintptr_t*)(first+16)=*(uintptr_t*)(second+16)=image+0x2981630;
 set_name(first,"limited_exports");set_name(second,"free_trade");
 assert(politics_resolve_idea(image,"free_trade",readable,native_name)==second);
 assert(politics_resolve_idea(image,"missing",readable,native_name)==0);
 uintptr_t unrelated=image+0x6000;*(uintptr_t*)unrelated=image+0x29815e0;*(uintptr_t*)(unrelated+16)=image+0x2981630;
 ((uintptr_t*)array)[3]=unrelated;*(int*)(db+0x70)=*(int*)(db+0x74)=4;
 set_name(unrelated,"AST_vickers-ruwolt_organization_idea");
 assert(politics_resolve_idea(image,"free_trade",readable,native_name)==second);
 set_name(unrelated,"AST_curtiss-wright_organization_idea");
 assert(politics_resolve_idea(image,"free_trade",readable,native_name)==second);
 set_name(unrelated,"invalid|wire");assert(politics_resolve_idea(image,"free_trade",readable,native_name)==0);
 *(int*)(db+0x70)=*(int*)(db+0x74)=3;

 set_name(first,"free_trade");assert(politics_resolve_idea(image,"free_trade",readable,native_name)==0);
 set_name(first,"limited_exports");*(uintptr_t*)(second+16)=0;assert(politics_resolve_idea(image,"free_trade",readable,native_name)==0);
 *(uintptr_t*)(second+16)=image+0x2981630;*(uintptr_t*)null=0;assert(politics_resolve_idea(image,"free_trade",readable,native_name)==0);
 free(image_memory);return 0;
}
