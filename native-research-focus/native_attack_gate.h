#ifndef HOI4_NATIVE_ATTACK_GATE_H
#define HOI4_NATIVE_ATTACK_GATE_H
/* Semantic hostile attack preflight for the existing ordinary CMoveCommand.
 * No command construction, state writes, declaration of war or readiness bypass.
 * Caller still invokes whole native move validator and owns durable intent. */
#include <stdint.h>
#include <stddef.h>
#ifndef ATTACK_RESOLVE
#define ATTACK_RESOLVE(fn,id) ((uintptr_t(*)(const uint32_t*))(fn))(id)
#define ATTACK_PROVINCE(fn,w,id) ((uintptr_t(*)(uintptr_t,int32_t))(fn))(w,id)
#define ATTACK_COUNTRY(fn,tag) ((uintptr_t(*)(const uint32_t*))(fn))(tag)
#define ATTACK_COUNTRY_INDEX(fn,tag) ((uint32_t(*)(const uint32_t*))(fn))(tag)
#define ATTACK_AT_WAR(fn,c,tag) ((unsigned char(*)(uintptr_t,const uint32_t*))(fn))(c,tag)
#endif
static const char *combat_attack_preflight(uintptr_t image,uintptr_t world,uintptr_t country,
 uint32_t tag,const uint32_t unit_id[2],int32_t province,int(*readable)(const void*,size_t),
 uintptr_t *unit_out,uintptr_t *province_out){
 *unit_out=*province_out=0;
 if(!tag||!unit_id||!unit_id[0]||!unit_id[1]||province<1)return "invalid_attack_arguments";
 if(!readable((void*)country,0x2a0)||*(uintptr_t*)country!=image+0x27e7360||
    *(uint32_t*)(country+8)!=tag)return "attack_country_binding_changed";
 uintptr_t object=ATTACK_RESOLVE(image+0x221f310,unit_id);
 if(object<0x10)return "attack_unit_binding_changed";
 uintptr_t unit=object-0x10;
 if(!readable((void*)unit,0x310)||*(uintptr_t*)unit!=image+0x295a2b0||
    *(uintptr_t*)object!=image+0x295a490||
    *(uint32_t*)(unit+0x18)!=unit_id[0]||*(uint32_t*)(unit+0x1c)!=unit_id[1]||
    *(uint32_t*)(unit+0x1d8)!=tag||
    *(uint32_t*)(unit+0x1e0)!=tag)return "attack_unit_binding_changed";
 uintptr_t units=*(uintptr_t*)(country+0x290);int32_t cap=*(int32_t*)(country+0x298),count=*(int32_t*)(country+0x29c);
 if(count<0||count>cap||cap>100000||(count&&!readable((void*)units,(size_t)count*8)))return "attack_unit_binding_changed";
 int found=0;for(int32_t i=0;i<count;i++)if(((uintptr_t*)units)[i]==unit)found++;
 if(found!=1)return "attack_unit_binding_changed";
 uintptr_t target=ATTACK_PROVINCE(image+0x1ca1b0,world+8,province);
 if(!readable((void*)target,0x18c)||*(int32_t*)(target+0xa4)!=province)return "invalid_attack_province";
 uint32_t target_tag=*(uint32_t*)(target+0x188);
 if(!target_tag||target_tag==tag)return "attack_destination_not_foreign_controlled";
 uintptr_t other=ATTACK_COUNTRY(image+0xbb48f0,&target_tag);
 if(!readable((void*)other,0x10)||*(uintptr_t*)other!=image+0x27e7360||
    *(uint32_t*)(other+8)!=target_tag)return "attack_enemy_country_binding_changed";
 uint32_t source[2]={tag,ATTACK_COUNTRY_INDEX(image+0xbb5490,&tag)};
 /* Exact native predicate also used by unit conflict eligibility c01660 and
  * ordinary movement/update paths. The war already exists; nothing creates it. */
 if(!ATTACK_AT_WAR(image+0x700570,other,source))return "attack_requires_existing_native_war";
 *unit_out=unit;*province_out=target;return NULL;
}
#endif
