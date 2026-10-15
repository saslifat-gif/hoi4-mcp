#ifndef HOI4_NATIVE_ATOMIC_PUBLISH_H
#define HOI4_NATIVE_ATOMIC_PUBLISH_H
/* Windows MoveFileEx rejects replacing an open destination even for a reader
 * sharing DELETE on this host. Retry publication only, never the native action.
 * Receipt polling reproduced ERROR_ACCESS_DENIED; a closed file succeeds. */
static BOOL native_publish_file(const wchar_t *temporary,const wchar_t *destination){
 for(unsigned attempt=0;;attempt++){
  if(MoveFileExW(temporary,destination,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return TRUE;
  DWORD error=GetLastError();
  if(attempt==9||(error!=ERROR_ACCESS_DENIED&&error!=ERROR_SHARING_VIOLATION))return FALSE;
  Sleep(5);
 }
}
#endif
