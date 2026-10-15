/* Host simulation: all engine function calls are fakes. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static uintptr_t image,country,manager,u1,u2,child,parent,theater,command,old_group;
static int intents,factories,appends,validations,executions,destructions,fail_intent,allow,broken,factory_fail,append_fail;
static uintptr_t resolve(uintptr_t,const uint32_t*),factory(uintptr_t),append(uintptr_t,uintptr_t,const void*),destroy(uintptr_t,uintptr_t);
static unsigned char validate(uintptr_t,uintptr_t);
static void execute(uintptr_t,uintptr_t);
#define ARMY_RESOLVE(fn,id) resolve(fn,id)
#define ARMY_FACTORY(fn) factory(fn)
#define ARMY_APPEND(fn,out,in) append(fn,out,in)
#define ARMY_VALIDATE(fn,cmd) validate(fn,cmd)
#define ARMY_EXECUTE(fn,cmd) execute(fn,cmd)
#define ARMY_DESTROY(fn,cmd) destroy(fn,cmd)
#include "native_army_group.h"
static int readable(const void *p,size_t n){uintptr_t a=(uintptr_t)p;return a>=image&&n<=0x3340000&&a-image<=0x3340000-n;}
static void vector(uintptr_t at,uintptr_t data,int count){*(uintptr_t*)at=data;*(int*)(at+8)=8;*(int*)(at+12)=count;}
static uintptr_t resolve(uintptr_t fn,const uint32_t *id){
 assert(fn==image+0x221f310);uintptr_t objects[]={manager,u1+16,u2+16,child,parent,theater,old_group};
 for(size_t i=0;i<sizeof objects/sizeof *objects;i++)if(!memcmp(id,(void*)(objects[i]+8),8))return objects[i];return 0;
}
static int intent(const char *rid){assert(!strcmp(rid,"army-request"));intents++;return intents!=fail_intent&&intents<=2;}
static uintptr_t factory(uintptr_t fn){
 assert(fn==image+0x183fa60&&intents==1);factories++;if(factory_fail)return 0;
 *(uintptr_t*)command=image+0x2a0ac88;vector(command+0x30,image+0x20000,0);vector(command+0x48,image+0x21000,0);
 memcpy((void*)(command+0x60),(void*)(image+0x333d528),8);
 *(int*)(command+0x68)=-1;*(int64_t*)(command+0x70)=-100000;*(int64_t*)(command+0x78)=-100000;return command;
}
static uintptr_t append(uintptr_t fn,uintptr_t out,const void *in){
 assert(fn==image+0x1835920&&out==command+0x48&&factories==1);appends++;
 const struct army_vector *v=in;assert(v->count==2);vector(image+0x21000,image+0x22000,2);memcpy((void*)(image+0x22000),(void*)v->data,16);
 if(append_fail)*(uint32_t*)(image+0x22000+4)=99;*(int*)(out+12)=1;return image+0x21000;
}
static unsigned char validate(uintptr_t fn,uintptr_t cmd){
 assert(fn==image+0x184cfc0&&cmd==command&&appends==1&&intents==2);validations++;
 assert(!memcmp((void*)(cmd+0x28),(void*)(manager+8),8));assert(*(int*)(cmd+0x3c)==0&&*(int*)(cmd+0x54)==1);return (unsigned char)allow;
}
static void group_object(uintptr_t g,int is_parent,unsigned id){
 *(uintptr_t*)g=image+(is_parent?0x2952348:0x29522b0);*(uint32_t*)(g+8)=0x35;*(uint32_t*)(g+12)=id;
 *(unsigned char*)(g+0x10)=1;*(unsigned char*)(g+0x39)=(unsigned char)is_parent;*(uint32_t*)(g+0x3c)=67;*(uintptr_t*)(g+0x40)=manager;
}
static void execute(uintptr_t fn,uintptr_t cmd){
 assert(fn==image+0x1842970&&cmd==command&&validations==1);executions++;if(broken==1)return;
 group_object(child,0,1);group_object(parent,1,2);
 vector(manager+0xb0,image+0x18000,2);((uintptr_t*)(image+0x18000))[0]=child;((uintptr_t*)(image+0x18000))[1]=parent;
 vector(manager+0x80,image+0x18100,1);*(uintptr_t*)(image+0x18100)=child;
 vector(manager+0x98,image+0x18200,1);*(uintptr_t*)(image+0x18200)=parent;
 vector(manager+0xc8,image+0x18300,1);*(uintptr_t*)(image+0x18300)=theater;
 *(uintptr_t*)(u1+0xc0)=child;*(uintptr_t*)(u2+0xc0)=broken==2?0:child;
 vector(child+0x50,image+0x18400,2);((uintptr_t*)(image+0x18400))[0]=u1+0xb8;((uintptr_t*)(image+0x18400))[1]=broken==3?u2:u2+0xb8;
 *(uintptr_t*)(child+0x1b8)=parent;
 vector(parent+0x230,image+0x18500,broken==4?0:1);*(uintptr_t*)(image+0x18500)=child;
 *(uintptr_t*)(child+0x180)=theater;*(uintptr_t*)(parent+0x180)=broken==5?0:theater;
 vector(theater+0x48,image+0x18600,2);((uintptr_t*)(image+0x18600))[0]=child;((uintptr_t*)(image+0x18600))[1]=parent;
 if(broken==6)*(uintptr_t*)(child+0x40)=manager+8;
 if(broken==7){
  group_object(old_group,0,3);vector(old_group+0x50,image+0x18700,1);*(uintptr_t*)(image+0x18700)=u1+0xb8;
  ((uintptr_t*)(image+0x18000))[2]=old_group;*(int*)(manager+0xbc)=3;
 }
}
static uintptr_t destroy(uintptr_t fn,uintptr_t c){assert(fn==image+0x183c7b0&&c==command);destructions++;return c;}
static void reset(void){
 memset((void*)image,0,0x3340000);intents=factories=appends=validations=executions=destructions=fail_intent=broken=factory_fail=append_fail=0;allow=1;
 *(uint64_t*)(image+0x333d528)=0xffffffff00000000ULL;
 country=image+0x1000;manager=image+0x3000;u1=image+0x5000;u2=image+0x6000;child=image+0x8000;parent=image+0xa000;theater=image+0xc000;command=image+0xe000;old_group=image+0x10000;
 *(uintptr_t*)country=image+0x27e7360;*(uint32_t*)(country+8)=67;
 vector(country+0x168,image+0x14000,1);*(uintptr_t*)(image+0x14000)=manager;
 vector(country+0x290,image+0x15000,2);((uintptr_t*)(image+0x15000))[0]=u1;((uintptr_t*)(image+0x15000))[1]=u2;
 *(uintptr_t*)manager=image+0x2975a48;*(uint32_t*)(manager+8)=54;*(uint32_t*)(manager+12)=1;*(uint32_t*)(manager+0x48)=67;
 vector(manager+0xb0,image+0x18000,0);
 uintptr_t us[]={u1,u2};for(int i=0;i<2;i++){
  uintptr_t u=us[i];*(uintptr_t*)u=image+0x295a2b0;*(uintptr_t*)(u+0x10)=image+0x295a490;*(uint32_t*)(u+0x18)=51;*(uint32_t*)(u+0x1c)=(uint32_t)i+1;
  *(uintptr_t*)(u+0xb8)=image+0x295a500;*(uint32_t*)(u+0x1d8)=67;
 }
 *(uintptr_t*)theater=image+0x29e5c50;*(uint32_t*)(theater+8)=68;*(uint32_t*)(theater+12)=1;*(uintptr_t*)(theater+0x18)=manager;
 uintptr_t vt=image+0x2a0ac88;*(uintptr_t*)vt=image+0x183c7b0;*(uintptr_t*)(vt+72)=image+0x184cfc0;*(uintptr_t*)(vt+80)=image+0x1842970;
}
static enum army_group_result run(struct army_group_outcome *out){
 const uint32_t units[2][2]={{51,1},{51,2}},manager_id[2]={54,1};
 return army_create_from_units(image,country,67,manager_id,units,2,"army-request",readable,intent,out);
}
int main(void){
 image=(uintptr_t)calloc(1,0x3340000);assert(image);struct army_group_outcome out;
 reset();assert(run(&out)==ARMY_EXECUTION_RETURNED&&out.verified&&out.group_id[0]==53&&out.group_id[1]==1&&out.army_group_id[1]==2&&out.theater_id[0]==68&&out.unit_count==2&&destructions==1);
 reset();allow=0;assert(run(&out)==ARMY_RULES_REJECTED&&!executions&&destructions==1);
 for(int i=1;i<=2;i++){reset();fail_intent=i;assert(run(&out)==ARMY_INTENT_FAILED&&!executions&&destructions==(i==2));}
 for(int i=1;i<=7;i++){reset();broken=i;assert(run(&out)==ARMY_EXECUTION_RETURNED&&!out.verified&&destructions==1);}
 reset();*(uint32_t*)(u1+0x1d8)=68;assert(run(&out)==ARMY_BINDING_CHANGED&&!intents);
 reset();*(uintptr_t*)(u1+0x10)=image+0x2952348;assert(run(&out)==ARMY_BINDING_CHANGED&&!intents);
 reset();*(uintptr_t*)(u1+0xb8)=0;assert(run(&out)==ARMY_BINDING_CHANGED&&!intents);
 reset();*(uint32_t*)(manager+0x48)=68;assert(run(&out)==ARMY_BINDING_CHANGED&&!intents);
 reset();*(int*)(country+0x29c)=3;*(int*)(country+0x298)=2;assert(run(&out)==ARMY_BINDING_CHANGED&&!intents);
 reset();append_fail=1;assert(run(&out)==ARMY_BINDING_CHANGED&&!executions&&destructions==1);
 reset();factory_fail=1;assert(run(&out)==ARMY_ALLOCATION_FAILED&&!executions&&!destructions);
 reset();const uint32_t duplicate[2][2]={{51,1},{51,1}},mid[2]={54,1};assert(army_create_from_units(image,country,67,mid,duplicate,2,"army-request",readable,intent,&out)==ARMY_BAD_ARGUMENT&&!intents);
 reset();assert(run(&out)==ARMY_EXECUTION_RETURNED&&out.verified);assert(run(&out)==ARMY_INTENT_FAILED&&executions==1&&factories==1);
 free((void*)image);return 0;
}
