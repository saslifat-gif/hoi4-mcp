/* Simulated memory and callbacks only; does not load HOI4 or call its engine. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static uintptr_t image,country,manager,category,group,old_idea,new_idea,array,command,resources;
static int intents,validations,executions,persist,allow,pay,replace;
static int64_t old_cost,new_cost;
static uintptr_t factory(uintptr_t);
static unsigned char validate(uintptr_t,uintptr_t,void*);
static void execute(uintptr_t,uintptr_t),cost(uintptr_t,uintptr_t,int64_t*,uintptr_t),value(uintptr_t,int64_t*,uintptr_t);
static uintptr_t resource_manager(uintptr_t,uintptr_t);
#define POLITICS_FACTORY(fn) factory(fn)
#define POLITICS_VALIDATE(fn,cmd,error) validate((fn),(cmd),(error))
#define POLITICS_EXECUTE(fn,cmd) execute((fn),(cmd))
#define LAW_COST(fn,m,out,idea) cost((fn),(m),(out),(idea))
#define LAW_RESOURCE_MANAGER(fn,c) resource_manager((fn),(c))
#define LAW_RESOURCE_VALUE(fn,out,p) value((fn),(out),(p))
#include "native_law.h"
static int readable(const void *p,size_t n){uintptr_t a=(uintptr_t)p;return a>=image&&n<=0x3330000&&a-image<=0x3330000-n;}
static int name(uintptr_t p,size_t offset,char *out,size_t n){assert(n==160);strcpy(out,(char*)(p+offset));return 1;}
static int intent(const char *rid){assert(!strcmp(rid,"law-request"));intents++;return persist;}
static uintptr_t factory(uintptr_t fn){assert(fn==image+0x114f850&&intents==1);*(unsigned char*)(command+0x40)=1;return command;}
static unsigned char validate(uintptr_t fn,uintptr_t cmd,void *err){assert(fn==image+0x1165bf0&&cmd==command&&!err&&intents==2);validations++;return (unsigned char)allow;}
static int64_t *balance(void){int r=*(int*)(category+0x78);return (int64_t*)(r<2?manager+0xe0:resources+0x10+(r-2)*0x18);}
static void execute(uintptr_t fn,uintptr_t cmd){
 assert(fn==image+0x1159b70&&cmd==command&&validations==1);executions++;
 if(replace)((uintptr_t*)array)[0]=new_idea;
 int64_t charge=old_cost+new_cost;
 if(pay&&charge>0)*balance()-=charge;
 if(!pay||charge<=0)*(unsigned char*)(cmd+0x40)=0;
}
static void cost(uintptr_t fn,uintptr_t m,int64_t *out,uintptr_t idea){
 assert(m==manager&&intents==1&&!validations);
 if(fn==image+0xba9410){assert(idea==old_idea);*out=old_cost;}
 else{assert(fn==image+0xba92b0&&idea==new_idea);*out=new_cost;}
}
static uintptr_t resource_manager(uintptr_t fn,uintptr_t c){assert(fn==image+0x6cf690&&c==country);return resources;}
static void value(uintptr_t fn,int64_t *out,uintptr_t p){assert(fn==image+0x24ed580&&p==(uintptr_t)balance());*out=*(int64_t*)p;}
static void reset(int resource){
 memset((void*)image,0,0x3330000);intents=validations=executions=0;persist=allow=pay=replace=1;old_cost=-100000;new_cost=15000000;
 country=image+0x1000;manager=image+0x3000;category=image+0x4000;group=image+0x5000;old_idea=image+0x6000;new_idea=image+0x8000;array=image+0xa000;command=image+0xb000;resources=image+0xc000;
 *(uint32_t*)(country+8)=1;*(uintptr_t*)(country+0xf90)=manager;
 *(uintptr_t*)category=image+0x2981648;*(int*)(category+0x78)=resource;
 *(uintptr_t*)group=image+0x2946650;strcpy((char*)(group+0x38),"trade_laws");*(unsigned char*)(group+0x58)=1;*(uintptr_t*)(group+0x60)=category;
 *(uintptr_t*)old_idea=*(uintptr_t*)new_idea=image+0x29815e0;*(uintptr_t*)(old_idea+16)=*(uintptr_t*)(new_idea+16)=image+0x2981630;
 *(uintptr_t*)(old_idea+0xaa0)=*(uintptr_t*)(new_idea+0xaa0)=group;
 strcpy((char*)(old_idea+24),"limited_exports");strcpy((char*)(new_idea+24),"free_trade");
 *(uintptr_t*)(manager+0x50)=array;*(int*)(manager+0x58)=2;*(int*)(manager+0x5c)=1;((uintptr_t*)array)[0]=old_idea;
 *(uintptr_t*)command=image+0x29958a0;*(uintptr_t*)(image+0x29958a0+72)=image+0x1165bf0;*(uintptr_t*)(image+0x29958a0+80)=image+0x1159b70;
 uintptr_t db=image+0xd000,items=image+0xe000,null=image+0xf000;
 *(uintptr_t*)(image+0x332ef30)=db;*(uintptr_t*)db=image+0x293c2b0;*(uintptr_t*)(db+0x68)=items;*(int*)(db+0x70)=*(int*)(db+0x74)=3;
 ((uintptr_t*)items)[0]=null;((uintptr_t*)items)[1]=old_idea;((uintptr_t*)items)[2]=new_idea;*(uintptr_t*)null=image+0x293c510;*(uintptr_t*)(null+16)=image+0x293c560;
 *balance()=20000000;
}
static enum politics_result run(struct law_outcome *out){return law_replace(image,country,1,"trade_laws","free_trade","law-request",readable,name,intent,out);}
int main(void){
 image=(uintptr_t)calloc(1,0x3330000);assert(image);struct law_outcome out;
 for(int resource=0;resource<=4;resource++){
  reset(resource);assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&executions==1);
  assert(out.resource==resource&&out.cost==14900000&&out.before==20000000&&out.after==5100000);
  assert(*(uint32_t*)(command+0x28)==1&&*(uintptr_t*)(command+0x30)==old_idea&&*(uintptr_t*)(command+0x38)==new_idea);
 }
 reset(0);allow=0;assert(run(&out)==POLITICS_RULES_REJECTED&&!out.verified&&!executions&&*balance()==20000000);
 reset(0);persist=0;assert(run(&out)==POLITICS_INTENT_FAILED&&!out.verified&&!validations&&!executions);
 reset(0);pay=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&executions==1);
 reset(0);replace=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&executions==1);
 reset(0);old_cost=new_cost=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.before==out.after);
 reset(0);*(unsigned char*)(group+0x58)=0;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!intents&&!executions);
 reset(0);strcpy((char*)(group+0x38),"economy");assert(run(&out)==POLITICS_BAD_ARGUMENT&&!intents);
 reset(0);((uintptr_t*)array)[0]=new_idea;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"already_selected")&&!intents);
 reset(0);*(int*)(manager+0x5c)=2;((uintptr_t*)array)[1]=new_idea;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"ambiguous_current_law")&&!intents);
 reset(0);*(int*)(category+0x78)=42;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"unsupported_cost_resource")&&!intents);
 reset(0);old_cost=INT64_MAX;new_cost=1;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!executions);
 free((void*)image);return 0;
}
