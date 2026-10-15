/* Simulation only: all native engine calls below are fakes. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static uintptr_t image,country,manager,group,child,target,old,created,command;
static int calls,allocations,constructions,validations,executions,destructions,allow,fail_intent,broken_outcome,use_existing,wrong_name,keep_old_member;
static uintptr_t resolve(uintptr_t,const uint32_t*),allocate(uintptr_t,size_t),construct(uintptr_t,uintptr_t,const void*,uintptr_t,const void*),destroy(uintptr_t,uintptr_t);
static unsigned char validate(uintptr_t,uintptr_t);
static void execute(uintptr_t,uintptr_t);
#define THEATER_RESOLVE(fn,id) resolve(fn,id)
#define THEATER_ALLOC(fn,n) allocate(fn,n)
#define THEATER_CONSTRUCT(fn,c,v,t,n) construct(fn,c,v,t,n)
#define THEATER_VALIDATE(fn,c) validate(fn,c)
#define THEATER_EXECUTE(fn,c) execute(fn,c)
#define THEATER_DESTROY(fn,c) destroy(fn,c)
#include "native_theater.h"
static int readable(const void *p,size_t n){uintptr_t a=(uintptr_t)p;return a>=image&&n<=0x3330000&&a-image<=0x3330000-n;}
static void vector(uintptr_t where,uintptr_t array,int n){*(uintptr_t*)where=array;*(int*)(where+8)=8;*(int*)(where+12)=n;}
static void string(uintptr_t where,const char *s){
 size_t n=strlen(s);memset((void*)where,0,32);*(uint64_t*)(where+16)=n;*(uint64_t*)(where+24)=n>15?n:15;
 if(n>15){*(uintptr_t*)where=where+0x100;strcpy((char*)(where+0x100),s);}else strcpy((char*)where,s);
}
static int read_name(uintptr_t object,size_t offset,char *out,size_t cap){
 uintptr_t s=object+offset;size_t n=*(uint64_t*)(s+16);if(n>=cap)return 0;
 uintptr_t data=*(uint64_t*)(s+24)>15?*(uintptr_t*)s:s;memcpy(out,(void*)data,n);out[n]=0;return 1;
}
static uintptr_t resolve(uintptr_t fn,const uint32_t *id){
 assert(fn==image+0x221f310);
 uintptr_t all[]={group,child,target,old,created};
 for(size_t i=0;i<sizeof all/sizeof *all;i++)if(!memcmp(id,(void*)(all[i]+8),8))return all[i];
 return 0;
}
static int intent(const char *rid){assert(!strcmp(rid,"theater-request"));calls++;return calls!=fail_intent&&calls<=2;}
static uintptr_t allocate(uintptr_t fn,size_t size){assert(fn==image+0x21c9af0&&size==0x68&&calls==1);allocations++;return command;}
static uintptr_t construct(uintptr_t fn,uintptr_t c,const void *v,uintptr_t t,const void *n){
 assert(fn==image+0x1a7d110&&c==command&&allocations==1);constructions++;
 const struct theater_vector *vec=v;const struct theater_string *text=n;
 *(uintptr_t*)c=image+0x2a326d0;
 if(t)memcpy((void*)(c+0x28),(void*)(t+8),8);
 vector(c+0x30,image+0x16000,vec->count);
 for(int i=0;i<vec->count;i++)memcpy((void*)(image+0x16000+i*8),(void*)(((uintptr_t*)vec->data)[i]+8),8);
 char copied[160];const char *src=text->capacity>15?(const char*)text->data.pointer:text->data.text;
 memcpy(copied,src,text->length);copied[text->length]=0;string(c+0x48,copied);return c;
}
static unsigned char validate(uintptr_t fn,uintptr_t c){
 assert(fn==image+0x1a7fb40&&c==command&&calls==2&&constructions==1);validations++;
 assert(*(int*)(c+0x3c)>=1);return (unsigned char)allow;
}
static void move(uintptr_t g,uintptr_t to){
 *(uintptr_t*)(g+0x180)=to;uintptr_t members=*(uintptr_t*)(to+0x48);int n=*(int*)(to+0x54);
 ((uintptr_t*)members)[n]=g;*(int*)(to+0x54)=n+1;
}
static void execute(uintptr_t fn,uintptr_t c){
 assert(fn==image+0x1a7e8c0&&c==command&&validations==1);executions++;
 uintptr_t chosen=use_existing?target:resolve(image+0x221f310,(uint32_t*)(c+0x28));
 if(!chosen)chosen=created;
 if(chosen==created){((uintptr_t*)(image+0x15000))[2]=created;*(int*)(manager+0xd4)=3;}
 if(broken_outcome==1)return;
 *(int*)(old+0x54)=keep_old_member?1:0;
 if(broken_outcome==2){*(uintptr_t*)(group+0x180)=chosen;return;}
 move(group,chosen);
 if(*(unsigned char*)(group+0x39))move(child,chosen);
 if(broken_outcome==3)((uintptr_t*)*(uintptr_t*)(chosen+0x48))[0]=child;
 char name[160];assert(read_name(c,0x48,name,sizeof name));if(name[0])string(chosen+0x28,wrong_name?"wrong":name);
}
static uintptr_t destroy(uintptr_t fn,uintptr_t c){assert(fn==image+0x1a7dc20&&c==command);destructions++;return c;}
static void reset(void){
 memset((void*)image,0,0x3330000);calls=allocations=constructions=validations=executions=destructions=fail_intent=broken_outcome=use_existing=wrong_name=keep_old_member=0;allow=1;
 country=image+0x1000;manager=image+0x3000;group=image+0x5000;child=image+0x6000;target=image+0x8000;old=image+0xa000;created=image+0xc000;command=image+0xe000;
 *(uintptr_t*)country=image+0x27e7360;*(uint32_t*)(country+8)=67;
 vector(country+0x168,image+0x10000,1);*(uintptr_t*)(image+0x10000)=manager;
 *(uintptr_t*)manager=image+0x2975a48;*(uint32_t*)(manager+0x48)=67;
 vector(manager+0xb0,image+0x14000,2);((uintptr_t*)(image+0x14000))[0]=group;((uintptr_t*)(image+0x14000))[1]=child;
 vector(manager+0xc8,image+0x15000,2);((uintptr_t*)(image+0x15000))[0]=old;((uintptr_t*)(image+0x15000))[1]=target;
 uintptr_t gs[]={group,child};
 for(int i=0;i<2;i++){
  uintptr_t g=gs[i];*(uintptr_t*)g=image+0x29522b0;*(uint32_t*)(g+8)=0x35;*(uint32_t*)(g+12)=(uint32_t)(i+1);*(unsigned char*)(g+0x10)=1;
  *(uint32_t*)(g+0x3c)=67;*(uintptr_t*)(g+0x40)=manager;*(uintptr_t*)(g+0x180)=old;
 }
 uintptr_t ts[]={old,target,created};
 for(int i=0;i<3;i++){
  uintptr_t t=ts[i];*(uintptr_t*)t=image+0x29e5c50;*(uint32_t*)(t+8)=0x44;*(uint32_t*)(t+12)=(uint32_t)(i+1);*(uintptr_t*)(t+0x18)=manager;
  vector(t+0x48,image+0x18000+(uintptr_t)i*0x100,0);string(t+0x28,"");
 }
 *(int*)(old+0x54)=1;*(uintptr_t*)(image+0x18000)=group;
 uintptr_t vt=image+0x2a326d0;*(uintptr_t*)vt=image+0x1a7dc20;*(uintptr_t*)(vt+72)=image+0x1a7fb40;*(uintptr_t*)(vt+80)=image+0x1a7e8c0;
}
static enum theater_result run(int assign,const char *name,struct theater_outcome *out){
 const uint32_t ids[1][2]={{0x35,1}};uint32_t tid[2]={0x44,2};
 return theater_change(image,country,67,ids,1,assign?tid:NULL,name,"theater-request",readable,read_name,intent,out);
}
int main(void){
 image=(uintptr_t)calloc(1,0x3330000);assert(image);struct theater_outcome out;
 reset();assert(run(0,"new theater",&out)==THEATER_EXECUTION_RETURNED&&out.verified&&out.target_id[0]==68&&out.target_id[1]==3&&destructions==1);
 reset();assert(run(0,"a long native theater name",&out)==THEATER_EXECUTION_RETURNED&&out.verified);
 reset();assert(run(1,"",&out)==THEATER_EXECUTION_RETURNED&&out.verified&&out.target_id[1]==2);
 reset();allow=0;assert(run(0,"",&out)==THEATER_RULES_REJECTED&&!out.verified&&!executions&&destructions==1);
 for(int i=1;i<=2;i++){reset();fail_intent=i;assert(run(0,"",&out)==THEATER_INTENT_FAILED&&!executions&&destructions==(i==2));}
 for(int i=1;i<=3;i++){reset();broken_outcome=i;assert(run(0,"",&out)==THEATER_EXECUTION_RETURNED&&!out.verified&&destructions==1);}
 reset();keep_old_member=1;assert(run(0,"",&out)==THEATER_EXECUTION_RETURNED&&!out.verified);
 reset();wrong_name=1;assert(run(0,"expected",&out)==THEATER_EXECUTION_RETURNED&&!out.verified);
 reset();use_existing=1;assert(run(0,"",&out)==THEATER_EXECUTION_RETURNED&&!out.verified);
 reset();*(uintptr_t*)group=image+0x295a490;assert(run(0,"",&out)==THEATER_BINDING_CHANGED&&!calls);
 reset();*(uint32_t*)(group+0x3c)=68;assert(run(0,"",&out)==THEATER_BINDING_CHANGED&&!calls);
 reset();*(uint32_t*)(manager+0x48)=68;assert(run(0,"",&out)==THEATER_BINDING_CHANGED&&!calls);
 reset();*(uintptr_t*)(target+0x18)=manager+16;assert(run(1,"",&out)==THEATER_BINDING_CHANGED&&!calls);
 reset();*(uintptr_t*)(group+0x180)=target;assert(run(1,"",&out)==THEATER_BAD_ARGUMENT&&!strcmp(out.reason,"already_assigned")&&!calls);
 reset();const uint32_t duplicate[2][2]={{53,1},{53,1}};assert(theater_change(image,country,67,duplicate,2,NULL,"","theater-request",readable,read_name,intent,&out)==THEATER_BAD_ARGUMENT&&!calls);
 reset();*(uintptr_t*)group=image+0x2952348;*(unsigned char*)(group+0x39)=1;vector(group+0x230,image+0x1d000,1);*(uintptr_t*)(image+0x1d000)=child;
 assert(run(0,"",&out)==THEATER_EXECUTION_RETURNED&&out.verified&&out.affected_groups==2);
 reset();assert(run(0,"",&out)==THEATER_EXECUTION_RETURNED&&out.verified);assert(run(0,"",&out)==THEATER_INTENT_FAILED&&executions==1);
 reset();*(uint32_t*)(group+8)=6000;*(uint32_t*)(target+8)=6001;
 const uint32_t dynamic_ids[1][2]={{6000,1}},dynamic_target[2]={6001,2};
 assert(theater_change(image,country,67,dynamic_ids,1,dynamic_target,"","theater-request",readable,read_name,intent,&out)==THEATER_EXECUTION_RETURNED&&out.verified);
 free((void*)image);return 0;
}
