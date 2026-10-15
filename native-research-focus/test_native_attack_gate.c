#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
static uintptr_t resolve(uintptr_t,const uint32_t*),test_province(uintptr_t,uintptr_t,int32_t),test_country(uintptr_t,const uint32_t*);
static uint32_t index_test_country(uintptr_t,const uint32_t*);static int at_war(uintptr_t,uintptr_t,const uint32_t*);
#define ATTACK_RESOLVE(f,id) resolve(f,id)
#define ATTACK_PROVINCE(f,w,id) test_province(f,w,id)
#define ATTACK_COUNTRY(f,t) test_country(f,t)
#define ATTACK_COUNTRY_INDEX(f,t) index_test_country(f,t)
#define ATTACK_AT_WAR(f,c,t) at_war(f,c,t)
#include "native_attack_gate.h"
static unsigned char own[0x400],enemy[0x10],army[0x688],target[0x200];static uintptr_t members[2];static uintptr_t image=0x140000000;static int war;static uint32_t unit_id[2]={51,7};
static void q(void*p,size_t o,uintptr_t v){memcpy((char*)p+o,&v,8);}static void i(void*p,size_t o,uint32_t v){memcpy((char*)p+o,&v,4);}
static int readable(const void*p,size_t n){return p&&n<0x100000;}
static uintptr_t resolve(uintptr_t f,const uint32_t*id){assert(f==image+0x221f310);return id[0]==unit_id[0]&&id[1]==unit_id[1]?(uintptr_t)army+0x10:0;}
static uintptr_t test_province(uintptr_t f,uintptr_t w,int32_t p){assert(f==image+0x1ca1b0&&w==0x100008);return p==123?(uintptr_t)target:0;}
static uintptr_t test_country(uintptr_t f,const uint32_t*t){assert(f==image+0xbb48f0);return *t==2?(uintptr_t)enemy:0;}
static uint32_t index_test_country(uintptr_t f,const uint32_t*t){assert(f==image+0xbb5490&&*t==1);return 42;}
static int at_war(uintptr_t f,uintptr_t c,const uint32_t*t){assert(f==image+0x700570&&c==(uintptr_t)enemy&&t[0]==1&&t[1]==42);return war;}
static void fixture(void){memset(own,0,sizeof own);memset(enemy,0,sizeof enemy);memset(army,0,sizeof army);memset(target,0,sizeof target);q(own,0,image+0x27e7360);i(own,8,1);q(enemy,0,image+0x27e7360);i(enemy,8,2);q(army,0,image+0x295a2b0);q(army,0x10,image+0x295a490);i(army,0x18,unit_id[0]);i(army,0x1c,unit_id[1]);i(army,0x1d8,1);i(army,0x1e0,1);members[0]=(uintptr_t)army;q(own,0x290,(uintptr_t)members);i(own,0x298,2);i(own,0x29c,1);i(target,0xa4,123);i(target,0x188,2);war=1;}
int main(void){uint32_t id[2]={51,7};uintptr_t u,p;
 fixture();assert(!combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,123,readable,&u,&p));assert(u==(uintptr_t)army&&p==(uintptr_t)target);
 fixture();war=0;assert(!strcmp(combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,123,readable,&u,&p),"attack_requires_existing_native_war"));assert(!u&&!p);
 fixture();i(target,0x188,1);assert(combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,123,readable,&u,&p));
 fixture();i(army,0x1e0,2);assert(combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,123,readable,&u,&p));
 fixture();members[1]=(uintptr_t)army;i(own,0x29c,2);assert(combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,123,readable,&u,&p));
 fixture();assert(combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,124,readable,&u,&p));
 unit_id[0]=id[0]=4713;unit_id[1]=id[1]=3966;fixture();assert(!combat_attack_preflight(image,0x100000,(uintptr_t)own,1,id,123,readable,&u,&p));
 return 0;}
