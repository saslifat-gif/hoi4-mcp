#include <assert.h>
#include "native_unit_payload.h"
int main(void){
 const char *sid="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",*rid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
 uint32_t ids[64][2];char text[2048];snprintf(text,sizeof text,"%s|%s|52:1,52:2",sid,rid);
 assert(unit_payload_parse(text,sid,rid,2,ids)&&ids[0][0]==52&&ids[1][1]==2);
 assert(!unit_payload_parse(text,sid,rid,1,ids));assert(!unit_payload_parse(text,sid,rid,3,ids));assert(!unit_payload_parse(text,rid,sid,2,ids));
 const char *bad[]={"52:1,52:1","052:1","-52:1","52:0","52:4294967296","52:1|extra","52:1,","52:1\n"};
 for(unsigned i=0;i<sizeof bad/sizeof *bad;i++){snprintf(text,sizeof text,"%s|%s|%s",sid,rid,bad[i]);assert(!unit_payload_parse(text,sid,rid,i==0?2:1,ids));}
 int used=snprintf(text,sizeof text,"%s|%s|",sid,rid);
 for(unsigned i=0;i<64;i++)used+=snprintf(text+used,sizeof text-(size_t)used,"%s4294967295:%u",i?",":"",i+1);
 assert(unit_payload_parse(text,sid,rid,64,ids)&&ids[63][0]==UINT32_MAX&&ids[63][1]==64);
 assert(!unit_payload_parse(text,sid,rid,65,ids));return 0;
}
