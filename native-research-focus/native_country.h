#ifndef HOI4_NATIVE_COUNTRY_H
#define HOI4_NATIVE_COUNTRY_H
/* A session's country is configuration, never inferred from opaque native IDs. */
static char country_code[4];
static int load_country_code(void){
 wchar_t file[MAX_PATH];path(file,L"country-code.txt");
 HANDLE f=CreateFileW(file,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(f==INVALID_HANDLE_VALUE)return 0;
 char text[4];DWORD got=0;BOOL ok=ReadFile(f,text,sizeof text,&got,NULL);CloseHandle(f);
 if(!ok||got!=3||(memcmp(text,"GER",3)&&memcmp(text,"ITA",3)))return 0;
 memcpy(country_code,text,3);country_code[3]=0;return 1;
}
#endif
