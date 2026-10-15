/* Simulated memory/native callbacks; no game or Windows execution. */
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "native_tooltip_query.h"
static uintptr_t image,owner,root,core,target,definition,registry,other;
static int intents,elections,updates,permit_intent,on_ui,is_paused,skip_elect,empty,change_binding;
static int queried,destroyed,bad_text,bad_return;static uintptr_t output;
static int readable(const void *p,size_t n){uintptr_t a=(uintptr_t)p;return (a>=image&&n<=0x3460000&&a-image<=0x3460000-n)||(output&&a>=output&&n<=0x420&&a-output<=0x420-n);}
static void text(uintptr_t a,const char*s){size_t n=strlen(s);assert(n<=15);memset((void*)a,0,32);memcpy((void*)a,s,n);*(size_t*)(a+16)=n;*(size_t*)(a+24)=15;}
static int gate_ui(uintptr_t p){assert(p==owner);return on_ui;}
static int gate_pause(uintptr_t p){assert(p==owner);return is_paused;}
static int intent(const char*id){assert(!strcmp(id,"tooltip-request"));intents++;return permit_intent;}
static uintptr_t query(uintptr_t fn,uintptr_t o,uintptr_t out,uintptr_t widget,unsigned char secondary){
 assert(fn==image+0x163bb80&&o==owner&&widget==target&&!secondary&&intents==1);queried++;output=out;
 memset((void*)out,0,0x420);text(out,empty?"":"Native title");text(out+32,empty?"":"Body £test£");text(out+64,"");
 *(uintptr_t*)(owner+0x728)=widget;
 if(bad_text)*(size_t*)(out+16)=99999;
 if(change_binding)*(uintptr_t*)(target+96)=other;
 return bad_return?out+32:out;
}
static void destroy(uintptr_t fn,uintptr_t p){assert(fn==image+0x14d0d0&&p==output&&queried==1&&!destroyed);destroyed++;}
static struct TooltipQueryCalls calls={readable,gate_pause,gate_ui,intent,query,destroy};
static struct TooltipSelector selector={"test.gui","entry"};
static void setup(void){
 queried=destroyed=bad_text=bad_return=0;output=0;
 memset((void*)image,0,0x3460000);owner=image+0x1000;root=image+0x3000;core=image+0x5000;
 target=image+0x6000;definition=image+0x7000;registry=image+0x8000;other=image+0x9000;
 intents=elections=updates=skip_elect=empty=change_binding=0;permit_intent=on_ui=is_paused=1;
 *(uintptr_t*)(image+0x332f408)=image+0xa000;*(unsigned char*)(image+0xa000+0x188)=1;
 unsigned char gate_global[]={0x48,0x8b,0x05,0x21,0x4e,0x13,0x03,0xc3};memcpy((void*)(image+0x1fa5e0),gate_global,sizeof gate_global);
 unsigned char gate_field[]={0x48,0x8d,0x81,0x78,0x01,0x00,0x00,0xc3};memcpy((void*)(image+0x1fae70),gate_field,sizeof gate_field);
 *(uintptr_t*)(image+0x332f698)=owner;*(uintptr_t*)owner=image+0x2968ff0;
 *(uintptr_t*)(owner+0x4e8)=core;*(uintptr_t*)(owner+0x4f8)=root;
 *(uintptr_t*)(image+0x34531e0)=root;*(uintptr_t*)root=image+0x294a688;
 *(uintptr_t*)(root+264)=registry;*(unsigned*)(root+272)=*(unsigned*)(root+276)=1;
 *(uintptr_t*)registry=target;*(uintptr_t*)(root+0x140)=other;
 *(uintptr_t*)core=image+0x2b421d8;*(uintptr_t*)(core+104)=root;text(core+0x130,"");
 *(uintptr_t*)target=image+0x2b468c8;*(uintptr_t*)(target+104)=root;*(uintptr_t*)(target+96)=definition;
 *(int*)(target+0x58)=4;*(unsigned char*)(target+117)=8;text(definition+40,"entry");text(definition+72,"test.gui");
 text(owner+0x58,"");text(owner+0x480,"");text(owner+0x4a0,"");
 *(uintptr_t*)(image+0x2b468c8)=image+0x22ae010;
 *(uintptr_t*)(image+0x2b468c8+120)=image+0x22a4440;*(uintptr_t*)(image+0x2b468c8+128)=image+0x22a4080;
 unsigned char a[]={0x44,0x8b,0x49,0x58,0x44,0x0f,0xb6,0x41,0x75,0x41,0x83,0xf9,0xff,0x74,0x2b};memcpy((void*)(image+0x22ae010),a,sizeof a);
 unsigned char b[]={0x48,0x8b,0xc4,0x48,0x89,0x58,0x08,0x88,0x50,0x10,0x55,0x56,0x57,0x41,0x54};memcpy((void*)(image+0x2a44a0),b,sizeof b);
 *(uintptr_t*)(image+0x2968ff0+0x3a0)=image+0x163bb80;
 *(uintptr_t*)(image+0x2b468c8+0x230)=image+0x6773a0;
 unsigned char g[]={0x48,0x89,0x5c,0x24,8,0x48,0x89,0x6c,0x24,0x18,0x48,0x89,0x74,0x24,0x20,0x48};memcpy((void*)(image+0x163bb80),g,sizeof g);
 unsigned char d[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0x51,0x58,0x48,0x8b,0xd9,0x48,0x83,0xfa};memcpy((void*)(image+0x14d0d0),d,sizeof d);
 unsigned char og[]={0x48,0x8b,0x41,0x50,0xc3};memcpy((void*)(image+0x6773a0),og,sizeof og);
}

static int run(struct TooltipQueryOutcome*out){return tooltip_query(image,owner,&selector,"tooltip-request",&calls,out);}
static void button(void){
 uintptr_t vt=image+0x2b472e8;*(uintptr_t*)target=vt;
 *(uintptr_t*)vt=image+0x22d17d0;*(uintptr_t*)(vt+120)=image+0x22a4440;
 *(uintptr_t*)(vt+128)=image+0x22a4080;*(uintptr_t*)(vt+0x230)=image+0x6773a0;
}
int main(void){image=(uintptr_t)calloc(1,0x3460000);assert(image);struct TooltipQueryOutcome out;int cases=0;
 setup();button();assert(run(&out)&&out.nonempty&&queried==1&&destroyed==1);assert(!tooltip_supported_widget(image,target,root,readable));cases++;
 setup();button();*(uintptr_t*)(image+0x2b472e8+0x230)=0;assert(!run(&out)&&!intents&&!queried);cases++;
 setup();button();*(uintptr_t*)(target+104)=other;assert(!run(&out)&&!intents&&!queried);cases++;
 setup();assert(run(&out)&&out.nonempty&&out.attempted&&out.returned&&out.destroyed&&destroyed==1&&queried==1);assert(!strcmp(out.title,"Native title")&&out.owner_target_after==target&&*(uintptr_t*)(root+0x140)==other);cases++;
 setup();empty=1;assert(run(&out)&&!out.nonempty&&destroyed==1&&!strcmp(out.reason,"native_tooltip_result_empty"));cases++;
 setup();bad_text=1;assert(!run(&out)&&destroyed==1&&!strcmp(out.reason,"tooltip_result_unreadable"));cases++;
 setup();bad_return=1;assert(!run(&out)&&destroyed==1);cases++;
 setup();change_binding=1;assert(!run(&out)&&destroyed==1&&!strcmp(out.reason,"tooltip_binding_changed"));cases++;
 setup();on_ui=0;assert(!run(&out)&&!intents&&!queried);cases++;
 setup();is_paused=0;assert(!run(&out)&&!intents);cases++;
 setup();permit_intent=0;assert(!run(&out)&&intents==1&&!queried&&!destroyed);cases++;
 setup();*(uintptr_t*)(image+0x2968ff0+0x3a0)=0;assert(!run(&out)&&!intents);cases++;
 setup();*(uintptr_t*)(image+0x2b468c8+0x230)=0;assert(!run(&out)&&!intents);cases++;
 setup();text(definition+72,"other.gui");assert(!run(&out)&&!intents);cases++;
 setup();*(unsigned char*)(target+117)=0;assert(!run(&out)&&!intents);cases++;
 setup();*(uintptr_t*)(target+0x50)=other;*(uintptr_t*)other=image+0xb000;*(uintptr_t*)(image+0xb000)=image+0xc000;assert(run(&out)&&out.tooltip_owner==other&&out.tooltip_method==image+0xc000);cases++;
 setup();*(uintptr_t*)(target+0x50)=other;*(uintptr_t*)other=image+0xb000;*(uintptr_t*)(image+0xb000)=image+0x332f698;assert(!run(&out)&&!intents);cases++;
 setup();*(unsigned char*)(image+0x163bb80)=0xcc;assert(!run(&out)&&!intents);cases++;
 printf("%d simulated explicit native tooltip query scenarios passed\n",cases);free((void*)image);return 0;}
