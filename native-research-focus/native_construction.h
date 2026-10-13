/* The same queued totals and limits used by ordinary native construction. */
static uintptr_t building_defs[3];
static const char *building_ids[3]={"industrial_complex","arms_factory","dockyard"};
static unsigned construction_attempts;
static int initialize_buildings(void){
 uintptr_t registry=*(uintptr_t*)(image+0x332ee28);
 if(!readable((void*)registry,0x50))return 0;
 int n=*(int*)(registry+0x4c);uintptr_t list=*(uintptr_t*)(registry+0x40);
 if(n<1||n>128||!readable((void*)list,n*8))return 0;
 for(int i=0;i<n;i++){
  uintptr_t d=*(uintptr_t*)(list+i*8);char id[160];
  if(!readable((void*)d,0x440)||!native_name(d,0x270,id,sizeof id))continue;
  for(int k=0;k<3;k++)if(!strcmp(id,building_ids[k])){if(building_defs[k])return 0;building_defs[k]=d;}
 }
 for(int k=0;k<3;k++)if(!building_defs[k]||!*(unsigned char*)(building_defs[k]+0x20))return 0;
 return 1;
}
static uintptr_t state_holder(uintptr_t world,int state){
 if(!readable((void*)world,0x528))return 0;
 int n=*(int*)(world+0x2d4);uintptr_t list=*(uintptr_t*)(world+0x2c8);
 if(n<1||n>10000||state<1||state>=n||!readable((void*)list,n*8))return 0;
 uintptr_t s=*(uintptr_t*)(list+state*8);
 if(!readable((void*)s,0x1a0)||*(int*)(s+0x58)!=state||(*(unsigned char*)(s+0x188)&1)||*(int*)(s+0x18c)!=state)return 0;
 return s+0x120;
}
static int queue_capacity(uintptr_t holder,int k,int *built,int *total,int *limit){
 uintptr_t d=building_defs[k];int index=*(int*)(d+0x2e0),n=*(int*)(holder+0x2c);
 uintptr_t slots=*(uintptr_t*)(holder+0x20),entries=*(uintptr_t*)(holder+0x38);
 if(n<1||n>128||index<0||index>=n||!readable((void*)slots,n*4))return 0;
 int j=*(int*)(slots+index*4);uintptr_t b=0;
 if(j!=-1){
  /* The slot map indexes the building pointer array, never guessed offsets. */
  int count=*(int*)(holder+0x44);
  if(count<1||count>128||j<0||j>=count||!readable((void*)entries,count*8))return 0;
  b=*(uintptr_t*)(entries+j*8);if(!readable((void*)b,0x48))return 0;
 }
 *built=b?*(short*)(b+0x40):0;
 if(b){
  int c1=*(int*)(b+0x1c),c2=*(int*)(b+0x34);
  if(c1<0||c1>10000||c2<0||c2>10000|| (c1&&!readable((void*)*(uintptr_t*)(b+0x10),c1*8))||(c2&&!readable((void*)*(uintptr_t*)(b+0x28),c2*8)))return 0;
  *total=((int(*)(void*))(image+0x10db9f0))((void*)b);
 }else *total=0;
 *limit=((int(*)(void*,void*,int,void*))(image+0x1173020))((void*)holder,(void*)d,*total,NULL);
 return *built>=0&&*total>=*built&&*total<=10000&&*limit>=0&&*limit<=10000;
}
static void construct_args(unsigned char *cmd,uint32_t tag,int state,int k,int levels){
 memset(cmd,0,0x50);*(uintptr_t*)cmd=image+0x2994770;*(int*)(cmd+0xc)=-1;*(uint32_t*)(cmd+0x14)=0xffff0000;
 *(uint32_t*)(cmd+0x28)=tag;*(uintptr_t*)(cmd+0x30)=image+0x2971f30;
 *(int*)(cmd+0x38)=state;*(int*)(cmd+0x3c)=*(int*)(building_defs[k]+8);
 *(int*)(cmd+0x48)=levels; /* mode 0: ordinary queue insertion */
}
static int capture_capacity(char *b,size_t cap,size_t *used,uintptr_t world,uint32_t tag){
 int n=*(int*)(world+0x2d4);uintptr_t list=*(uintptr_t*)(world+0x2c8);int rows=0,states=0;
 if(n<1||n>10000||!readable((void*)list,n*8))return 0;
 if(!append(b,cap,used,",\"construction_capacity\":["))return 0;
 for(int state=1;state<n;state++){
  uintptr_t object=*(uintptr_t*)(list+state*8);
  if(!object)continue;
  if(!readable((void*)object,0x1a0))return 0;
  if(*(uint32_t*)(object+0xcc)!=tag)continue;
  uintptr_t holder=state_holder(world,state);if(!holder)return 0;
  for(int k=0;k<3;k++){
   int built,total,limit;if(!queue_capacity(holder,k,&built,&total,&limit))return 0;
   int remaining=limit>total?limit-total:0;
   if(!append(b,cap,used,"%s{\"state_id\":%d,\"building\":\"%s\",\"built\":%d,\"built_and_queued\":%d,\"queued\":%d,\"queue_adjusted_limit\":%d,\"remaining\":%d}",rows?",":"",state,building_ids[k],built,total,total-built,limit,remaining))return 0;
   rows++;
  }
  states++;
 }
 return append(b,cap,used,"],\"construction_state_count\":%d",states);
}
static int construction_receipt(const char *rid,const char *status,const char *reason,int state,int k,int levels,int before,int after,int remaining){
 wchar_t file[80];swprintf(file,80,L"construction-%hs.json",rid);char b[1200];
 snprintf(b,sizeof b,"{\"session_id\":\"%s\",\"command_id\":\"%s\",\"status\":\"%s\",\"data\":{\"kind\":\"construct\",\"reason\":\"%s\",\"state_id\":%d,\"building\":\"%s\",\"levels\":%d,\"before_built_and_queued\":%d,\"after_built_and_queued\":%d,\"remaining_before\":%d},\"engine_acknowledged\":true,\"gameplay_outcome_verified\":%s,\"acknowledgment_scope\":\"native_construction_queue\",\"pid\":%lu,\"world\":\"0x%llx\",\"uses_mouse_or_keyboard\":false}",sid,rid,status,reason,state,k>=0?building_ids[k]:"unknown",levels,before,after,remaining,!strcmp(status,"acknowledged")?"true":"false",(unsigned long)GetCurrentProcessId(),(unsigned long long)bound_world);return write_atomic(file,b);
}
static void construct_native(void *scope,const char *payload){
 char rid[33],building[64],extra;int state,levels,k=-1;
 if(sscanf(payload,"%32[a-f0-9]|state=%d|building=%63[A-Za-z0-9_]|levels=%d%c",rid,&state,building,&levels,&extra)!=4||!hex_id(rid))return;
 for(int i=0;i<3;i++)if(!strcmp(building,building_ids[i]))k=i;
 if(k<0||levels<1||levels>5)return;
 wchar_t file[80],full[MAX_PATH];swprintf(file,80,L"construction-%hs.json",rid);path(full,file);
 if(GetFileAttributesW(full)!=INVALID_FILE_ATTRIBUTES)return;
 const uint32_t *tag=((const uint32_t*(*)(void*))(image+0x537fb0))(scope);
 uintptr_t world=*(uintptr_t*)(image+0x332f260);
 if(GetCurrentThreadId()!=expected_thread||!readable(tag,4)||!*tag||(bound_world&&bound_world!=world))return;
 bound_world=world;uintptr_t holder=state_holder(world,state);int built,total,limit;
 if(!holder||!queue_capacity(holder,k,&built,&total,&limit)){construction_receipt(rid,"rejected","capacity_unavailable",state,k,levels,0,0,0);return;}
 int remaining=limit>total?limit-total:0;
 if(levels>remaining||construction_attempts>=64){construction_receipt(rid,"rejected","insufficient_queued_capacity",state,k,levels,total,total,remaining);return;}
 __declspec(align(16)) unsigned char cmd[0x50];construct_args(cmd,*tag,state,k,levels);
 if(!((unsigned char(*)(void*,void*))(image+0x11616f0))(cmd,NULL)){construction_receipt(rid,"rejected","native_rules_rejected",state,k,levels,total,total,remaining);return;}
 if(!construction_receipt(rid,"delivery_uncertain","execution_intent",state,k,levels,total,total,remaining))return;construction_attempts++;
 __try{
  ((void(*)(void*))(image+0x1150fb0))(cmd);
  int b2,t2,l2;if(!queue_capacity(holder,k,&b2,&t2,&l2)||t2!=total+levels){construction_receipt(rid,"delivery_uncertain","queue_postcondition_failed",state,k,levels,total,-1,remaining);return;}
  construction_receipt(rid,"acknowledged","ordinary_native_queue_insertion",state,k,levels,total,t2,remaining);
 }__except(EXCEPTION_EXECUTE_HANDLER){construction_receipt(rid,"delivery_uncertain","native_execution_exception",state,k,levels,total,-1,remaining);}
}
