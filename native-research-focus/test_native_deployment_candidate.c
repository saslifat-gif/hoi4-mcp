#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static uintptr_t test_resolve(uintptr_t,const uint32_t*);
static int test_ready(uintptr_t,uintptr_t);
static uintptr_t test_alloc(uintptr_t,size_t),test_ctor(uintptr_t,uintptr_t,uintptr_t),test_destroy(uintptr_t,uintptr_t);
static int test_validate(uintptr_t,uintptr_t);
static int test_queue_ready(uintptr_t,uintptr_t,uintptr_t);
static uintptr_t test_location_ctor(uintptr_t,uintptr_t,uintptr_t,int32_t);
static uintptr_t test_queue_ctor(uintptr_t,uintptr_t,uintptr_t);
#define DEPLOY_RESOLVE(f,i) test_resolve(f,i)
#define DEPLOY_READY(f,l) test_ready(f,l)
#define DEPLOY_ALLOC(f,n) test_alloc(f,n)
#define DEPLOY_CTOR(f,c,l) test_ctor(f,c,l)
#define DEPLOY_VALIDATE(f,c) test_validate(f,c)
#define DEPLOY_DESTROY(f,c) test_destroy(f,c)
#define DEPLOY_QUEUE_READY(f,m,t) test_queue_ready(f,m,t)
#define DEPLOY_QUEUE_CTOR(f,c,t) test_queue_ctor(f,c,t)
#define DEPLOY_LOCATION_CTOR(f,c,v,p) test_location_ctor(f,c,v,p)
static void test_execute(uintptr_t,uintptr_t);
#define DEPLOY_EXECUTE(f,c) test_execute(f,c)
#include "native_deployment_execute.h"
static unsigned char country[0x1000],manager[0x120],line[0x40],conveyor[0xa0],entry[0xd0],templ[0x260];
static uintptr_t conveyors[2],lines[2],units[1];static unsigned char unit[0x688],location[0x200],equipment_rows[24],manpower_rows[8];
static uint32_t unit_id[2]={51,99};
static uint32_t id[2]={73,9}, template_id[2]={52,3};static uintptr_t templates[1];static int executed_mode,intents;static int ready=1,valid=1,allocations,destroyed;static uintptr_t image=0x140000000;
static void q(void*p,size_t o,uintptr_t v){memcpy((char*)p+o,&v,8);}
static void i(void*p,size_t o,uint32_t v){memcpy((char*)p+o,&v,4);}
static int readable(const void*p,size_t n){return p&&n<0x100000;}
static uintptr_t test_resolve(uintptr_t f,const uint32_t*p){assert(f==image+0x221f310);return p[0]==unit_id[0]&&p[1]==unit_id[1]?(uintptr_t)unit+0x10:p[0]==71&&p[1]==1?(uintptr_t)conveyor:p[0]==template_id[0]&&p[1]==template_id[1]?(uintptr_t)templ:p[0]==id[0]&&p[1]==id[1]?(uintptr_t)line:0;}
static int test_ready(uintptr_t f,uintptr_t l){assert(f==image+0xce7d50&&l==(uintptr_t)line);return ready;}
static uintptr_t test_alloc(uintptr_t f,size_t n){assert(f==image+0x21c9af0&&(n==0x30||n==0x38));allocations++;return (uintptr_t)calloc(1,n);}
static uintptr_t test_ctor(uintptr_t f,uintptr_t c,uintptr_t l){assert(f==image+0x1ba1460&&l==(uintptr_t)line);q((void*)c,0,image+0x2a48de8);memcpy((void*)(c+0x28),id,8);return c;}
static int test_validate(uintptr_t f,uintptr_t c){assert((f==image+0x1162ce0||f==image+0x1ba3c10)&&c);return valid;}
static uintptr_t test_destroy(uintptr_t f,uintptr_t c){assert(f==image+0x22d200||f==image+0xdb4550);destroyed++;free((void*)c);return 0;}
static int test_queue_ready(uintptr_t f,uintptr_t m,uintptr_t t){assert(f==image+0xd0e740&&m==(uintptr_t)manager&&t==(uintptr_t)templ+0x18);return ready;}
static uintptr_t test_queue_ctor(uintptr_t f,uintptr_t c,uintptr_t t){assert(f==image+0x1ba11b0&&t==(uintptr_t)templ);q((void*)c,0,image+0x2a483c0);memcpy((void*)(c+0x28),template_id,8);i((void*)c,0x30,0);return c;}
static uintptr_t test_location_ctor(uintptr_t f,uintptr_t c,uintptr_t v,int32_t p){assert(f==image+0x1ba17e0&&v==(uintptr_t)conveyor);q((void*)c,0,image+0x2a48618);memcpy((void*)(c+0x28),conveyor+8,8);i((void*)c,0x30,(uint32_t)p);return c;}
static void test_execute(uintptr_t f,uintptr_t c){if(f==image+0x1ba3270){
 i(country,0x29c,1);q(unit,0,image+0x295a2b0);q(unit,0x10,image+0x295a490);i(unit,0x18,unit_id[0]);i(unit,0x1c,unit_id[1]);
 i(unit,0x1d8,1);q(unit,0x3b8,(uintptr_t)templ);q(unit,0x1f0,(uintptr_t)location);i(location,0xa4,123);
 q(unit,0x350,(uintptr_t)equipment_rows);i(unit,0x358,1);i(unit,0x35c,1);
 q(unit,0x3e0,(uintptr_t)manpower_rows);i(unit,0x3e8,1);i(unit,0x3ec,1);
 if(executed_mode==1)i(location,0xa4,124);if(executed_mode==2)i(manpower_rows,4,50);
 if(executed_mode==4)i(country,0x29c,0);memset(line,0,sizeof line);memset(entry,0,sizeof entry);return;}
 if(f==image+0x1ba3510){if(executed_mode!=2)memcpy(conveyor+0x4c,(void*)(c+0x30),4);return;}assert(f==image+0x1ba3060&&c);i(manager,0x54,1);if(executed_mode==1)q(line,0x38,(uintptr_t)manager);if(executed_mode==2)i(manager,0x54,0);}
static int test_intent(const char *rid){assert(!strcmp(rid,"req-1"));intents++;return executed_mode!=3||intents<2;}
static void fixture(void){
 memset(country,0,sizeof country);memset(manager,0,sizeof manager);memset(line,0,sizeof line);memset(conveyor,0,sizeof conveyor);memset(entry,0,sizeof entry);memset(templ,0,sizeof templ);
 q(country,0,image+0x27e7360);i(country,8,1);q(country,0xf70,(uintptr_t)manager);q(manager,0,image+0x295fc38);
 q(line,0,image+0x295e0a8);memcpy(line+8,id,8);q(line,0x38,(uintptr_t)conveyor);q(line,0x30,(uintptr_t)entry);
 q(conveyor,0,image+0x295e100);q(conveyor,0x20,(uintptr_t)templ);i(templ,0x1ec,1);
 q(entry,0,image+0x295e020);q(entry,0xb8,(uintptr_t)line);
 conveyors[0]=(uintptr_t)conveyor;lines[0]=(uintptr_t)line;
 q(manager,0x48,(uintptr_t)conveyors);i(manager,0x50,2);i(manager,0x54,1);
 q(conveyor,0x78,(uintptr_t)lines);i(conveyor,0x80,2);i(conveyor,0x84,1);
 q(manager,0x118,(uintptr_t)country);q(templ,0,image+0x294f5b0);memcpy(templ+8,template_id,8);
 templates[0]=(uintptr_t)templ;q(country,0x1b8,(uintptr_t)templates);i(country,0x1c0,1);i(country,0x1c4,1);
 i(conveyor,8,71);i(conveyor,12,1);executed_mode=intents=0;
 memset(unit,0,sizeof unit);memset(location,0,sizeof location);memset(equipment_rows,0,sizeof equipment_rows);memset(manpower_rows,0,sizeof manpower_rows);
 units[0]=(uintptr_t)unit;q(country,0x290,(uintptr_t)units);i(country,0x298,1);i(country,0x29c,0);
 q(entry,0x28,(uintptr_t)equipment_rows);i(entry,0x30,1);i(entry,0x34,1);q(equipment_rows,0,0x777);q(equipment_rows,16,300);
 q(entry,0x78,(uintptr_t)manpower_rows);i(entry,0x80,1);i(entry,0x84,1);i(manpower_rows,0,1);i(manpower_rows,4,900);i(conveyor,0x4c,123);
 ready=valid=1;allocations=destroyed=0;
}
int main(void){
 uintptr_t c;const char*err;
 fixture();assert(!deployment_prepare_line(image,(uintptr_t)country,1,id,readable,&c));assert(c&&allocations==1);test_destroy(image+0x22d200,c);
 fixture();ready=0;err=deployment_prepare_line(image,(uintptr_t)country,1,id,readable,&c);assert(!strcmp(err,"deployment_native_rules_rejected")&&!c&&!allocations);
 fixture();i(templ,0x1ec,2);assert(deployment_prepare_line(image,(uintptr_t)country,1,id,readable,&c)&&!allocations);
 fixture();lines[1]=(uintptr_t)line;i(conveyor,0x84,2);assert(deployment_prepare_line(image,(uintptr_t)country,1,id,readable,&c)&&!allocations);
 fixture();q(entry,0xb8,(uintptr_t)conveyor);assert(deployment_prepare_line(image,(uintptr_t)country,1,id,readable,&c)&&!allocations);
 fixture();valid=0;assert(deployment_prepare_line(image,(uintptr_t)country,1,id,readable,&c)&&!c&&destroyed==1);
 fixture();assert(!deployment_prepare_queue(image,(uintptr_t)country,1,template_id,readable,&c));assert(c);test_destroy(image+0xdb4550,c);
 fixture();ready=0;assert(deployment_prepare_queue(image,(uintptr_t)country,1,template_id,readable,&c)&&!allocations);
 fixture();q(manager,0x118,(uintptr_t)line);assert(deployment_prepare_queue(image,(uintptr_t)country,1,template_id,readable,&c)&&!allocations);
 fixture();i(country,0x1c4,0);assert(deployment_prepare_queue(image,(uintptr_t)country,1,template_id,readable,&c)&&!allocations);
 struct deployment_outcome out;
 fixture();i(manager,0x54,0);assert(!deployment_create_queue(image,(uintptr_t)country,1,template_id,"req-1",readable,test_intent,&out));assert(out.executed&&out.verified&&out.conveyor_id[0]==71&&out.line_id[0]==73&&intents==2&&destroyed==1);
 fixture();i(manager,0x54,0);executed_mode=1;assert(deployment_create_queue(image,(uintptr_t)country,1,template_id,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified&&destroyed==1);
 fixture();i(manager,0x54,0);executed_mode=2;assert(deployment_create_queue(image,(uintptr_t)country,1,template_id,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified);
 fixture();i(manager,0x54,0);executed_mode=3;assert(deployment_create_queue(image,(uintptr_t)country,1,template_id,"req-1",readable,test_intent,&out));assert(!out.executed&&!out.verified&&destroyed==1);
 fixture();assert(deployment_create_queue(image,(uintptr_t)country,1,template_id,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified);
 uint32_t conveyor_id[2]={71,1};
 fixture();assert(!deployment_set_location(image,(uintptr_t)country,1,conveyor_id,123,"req-1",readable,test_intent,&out));assert(out.executed&&out.verified&&*(int32_t*)(conveyor+0x4c)==123&&intents==2);
 fixture();valid=0;assert(deployment_set_location(image,(uintptr_t)country,1,conveyor_id,123,"req-1",readable,test_intent,&out));assert(!out.executed&&!out.verified&&destroyed==1);
 fixture();executed_mode=2;assert(deployment_set_location(image,(uintptr_t)country,1,conveyor_id,124,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified);
 fixture();assert(deployment_set_location(image,(uintptr_t)country,1,conveyor_id,0,"req-1",readable,test_intent,&out));assert(!out.executed&&!allocations);
 fixture();assert(!deployment_deploy_line(image,(uintptr_t)country,1,id,"req-1",readable,test_intent,&out));assert(out.executed&&out.verified&&out.unit_id[0]==51&&out.unit_id[1]==99&&destroyed==1);
 fixture();executed_mode=1;assert(deployment_deploy_line(image,(uintptr_t)country,1,id,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified);
 fixture();executed_mode=2;assert(deployment_deploy_line(image,(uintptr_t)country,1,id,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified);
 fixture();executed_mode=4;assert(deployment_deploy_line(image,(uintptr_t)country,1,id,"req-1",readable,test_intent,&out));assert(out.executed&&!out.verified);
 fixture();unit_id[0]=4713;unit_id[1]=3966;assert(!deployment_deploy_line(image,(uintptr_t)country,1,id,"req-1",readable,test_intent,&out));assert(out.verified&&out.unit_id[0]==4713&&out.unit_id[1]==3966);
 template_id[0]=4714;template_id[1]=4000;fixture();assert(!deployment_prepare_queue(image,(uintptr_t)country,1,template_id,readable,&c));test_destroy(image+0xdb4550,c);
 return 0;
}
