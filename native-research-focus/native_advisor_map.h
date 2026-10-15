#ifndef HOI4_NATIVE_ADVISOR_MAP_H
#define HOI4_NATIVE_ADVISOR_MAP_H
/* CCharacter+b0 native role-map key, independent from CAdvisor's script ID+30.
 * Node layout and ordinary f9f700 lookup are pinned to the researched image. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#ifndef ADVISOR_ROLE
#define ADVISOR_ROLE(fn,character,key) ((uintptr_t(*)(uintptr_t,uintptr_t))(fn))(character,key)
#endif
struct advisor_map_snapshot {uintptr_t pointer;unsigned char bytes[0x50];};
static uintptr_t advisor_map_key(uintptr_t image,uintptr_t character,uintptr_t role,
 int(*can_read)(const void*,size_t),int(*read_name)(uintptr_t,size_t,char*,size_t),char key_name[160]){
 if(!can_read((void*)character,0xc0)||*(uintptr_t*)character!=image+0x297ea60||
    !can_read((void*)role,0x58)||*(uintptr_t*)role!=image+0x29a7d60||*(uintptr_t*)(role+0x10)!=character)return 0;
 uintptr_t head=*(uintptr_t*)(character+0xb0);uint64_t count=*(uint64_t*)(character+0xb8);
 if(!count||count>10000||!can_read((void*)head,0x20)||!*(unsigned char*)(head+0x19))return 0;
 unsigned char header[0x20];memcpy(header,(void*)head,sizeof header);
 struct advisor_map_snapshot *seen=calloc((size_t)count,sizeof *seen);
 uintptr_t *stack=calloc((size_t)count,sizeof *stack),key=0;size_t used=0,pending=0;int valid=0;
 if(!seen||!stack)goto done;
 uintptr_t root=*(uintptr_t*)(head+8);
 if(root==head||!can_read((void*)root,0x50)||*(uintptr_t*)(root+8)!=head)goto done;
 stack[pending++]=root;
 while(pending){
  uintptr_t node=stack[--pending];if(used>=count||!can_read((void*)node,0x50)||*(unsigned char*)(node+0x19))goto done;
  for(size_t i=0;i<used;i++)if(seen[i].pointer==node)goto done;
  seen[used].pointer=node;memcpy(seen[used++].bytes,(void*)node,0x50);
  uintptr_t value=*(uintptr_t*)(node+0x48);
  if(value&&(!can_read((void*)value,0x58)||*(uintptr_t*)value!=image+0x29a7d60||*(uintptr_t*)(value+0x10)!=character))goto done;
  if(value==role){
   if(key||!read_name(node,0x20,key_name,160))goto done;
   uint32_t hash=0x811c9dc5;
   for(const unsigned char *p=(const unsigned char*)key_name;*p;p++){
    unsigned char c=*p;if(c>='A'&&c<='Z')c=(unsigned char)(c+32);hash=(hash^c)*0x1000193;
   }
   if(!key_name[0]||hash!=*(uint32_t*)(node+0x40))goto done;
   key=node+0x20;
  }
  for(int branch=0;branch<2;branch++){
   uintptr_t child=*(uintptr_t*)(node+(branch?0x10:0));if(child==head)continue;
   if(pending>=count||!can_read((void*)child,0x50)||*(unsigned char*)(child+0x19)||*(uintptr_t*)(child+8)!=node)goto done;
   stack[pending++]=child;
  }
 }
 if(used!=count||!key||*(uintptr_t*)(character+0xb0)!=head||*(uint64_t*)(character+0xb8)!=count||memcmp(header,(void*)head,sizeof header))goto done;
 for(size_t i=0;i<used;i++)if(!can_read((void*)seen[i].pointer,0x50)||memcmp(seen[i].bytes,(void*)seen[i].pointer,0x50))goto done;
 char current[160];if(!read_name(key,0,current,sizeof current)||strcmp(current,key_name))goto done;
 if(ADVISOR_ROLE(image+0xf9f700,character,key)!=role)goto done;
 /* The native lookup must not have changed the selected ownership/map binding. */
 if(*(uintptr_t*)(character+0xb0)!=head||*(uint64_t*)(character+0xb8)!=count||*(uintptr_t*)(role+0x10)!=character)goto done;
 for(size_t i=0;i<used;i++)if(!can_read((void*)seen[i].pointer,0x50)||memcmp(seen[i].bytes,(void*)seen[i].pointer,0x50))goto done;
 if(!read_name(key,0,current,sizeof current)||strcmp(current,key_name))goto done;
 valid=1;
 done:free(stack);free(seen);return valid?key:0;
}
#endif
