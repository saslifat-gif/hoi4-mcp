/* Native registry names include shipped hyphenated organization IDs. */
static int native_name(uintptr_t object,size_t offset,char *out,size_t cap){
 unsigned char *s=(unsigned char*)(object+offset);if(!readable(s,32))return 0;
 uint64_t n=*(uint64_t*)(s+16),c=*(uint64_t*)(s+24);
 if(!n||n>=cap||n>c||c>65536)return 0;
 const char *v=c>15?*(const char**)s:(const char*)s;
 if(!readable(v,n+1)||v[n])return 0;
 for(size_t i=0;i<n;i++)if(!((v[i]>='a'&&v[i]<='z')||(v[i]>='A'&&v[i]<='Z')||(v[i]>='0'&&v[i]<='9')||v[i]=='_'||v[i]=='-'||v[i]=='.'))return 0;
 memcpy(out,v,n);out[n]=0;return 1;
}
