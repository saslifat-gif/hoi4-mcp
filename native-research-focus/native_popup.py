"""Build-pinned event identity and global-alert cache reads; no native invocation."""
import struct
from runtime_gui import GuiSnapshotChanged,native_markup
from native_handle import HANDLE_SIGNATURES,resolve_native_handle

NOTIFICATION_OWNERS={'.?AVCExternallyCompletedFocusNotification@NNotification@@':(40,0x29b4378,0x29b43c8,0x50),
                     '.?AVCIdeaExpiredNotification@NNotification@@':(40,0x2a1bcb0,0x2a1bd00,0x50),
                     '.?AVCLegacyMessagePopUpNotification@NNotification@@':(40,0x2a02ea0,0x2a02ef0,0x50)}
OWNER_LAYOUTS={**NOTIFICATION_OWNERS,'.?AVCWorldTensionPopUpWindow@@':(56,0x2a133d8,0x2a13478,0x570),
               '.?AVCEventWindow@@':(56,0x29a4818,0x29a4878,0x50),
               '.?AVCGlobalAlertIcon@@':(40,0x29468f8,0x2946920,0x38),
               '.?AVCRegionAlertEntry@@':(72,0x2a86ec8,0x2a87000,0x40),
               '.?AVCTheaterGroupAlertEntry@@':(72,0x2a86988,0x2a86ac0,0x40)}
SIGNATURES={**HANDLE_SIGNATURES,
            0x1e6acf0:'48895c2410574881ec40040000488bd9498bf84881c114050000833900750a83',0x22a9260:'48895c2410488974241848894c2408574883ec30498bd8488bf2488bf9e83e430400',
            0x1e6aac0:'40534881ec400400004c8b8918050000488d54243033c0498bd8448b8110050000',0x1bbf140:'40534883ec20488bd9e8c2fcffff488b4b504885c97438488b41304883c13080',
            0x1238fe0:'488bc4488958104889701855574156488da848ffffff4881eca00100000f2970',
            0x1239a40:'40534883ec20488bd9488b89581200004883e980488d93500d0000488b01ff50',
            0x1180270:'40534881ec30010000488bd94883c120e8fbe302ff89831804000083bb740300',
            0xb0cc50:'40534881ec40040000488b813005000033d24533c9498bd8448b4120488b4908',
            0xb0ab70:'488bc448895820488950105556574154415541564157488da818f7ffff4881ecb0090000'}

def read_native_popup(reader,gui):
 r=reader;guards=[]
 def read(address,size):
  data=r.read(address,size)
  if data is None:raise RuntimeError('Native popup binding unreadable')
  guards.append((address,data));return data
 def pointer(address):return struct.unpack('<Q',read(address,8))[0]
 def verify():
  if any(r.read(a,len(data))!=data for a,data in guards):raise GuiSnapshotChanged('Native popup binding changed during read')
  r._guard_root()
 def signature(target):
  expected=bytes.fromhex(SIGNATURES[target])
  if read(r.base+target,len(expected))!=expected:raise RuntimeError('Native popup implementation changed')
 header=read(gui,160);parent=struct.unpack_from('<Q',header,80)[0];kind=r.typename(parent)
 if kind not in OWNER_LAYOUTS:return {'status':'unsupported_owner','native_type':kind}
 adjust,main_vt,tooltip_vt,container_offset=OWNER_LAYOUTS[kind];owner=parent-adjust
 if pointer(owner)!=r.base+main_vt or pointer(parent)!=r.base+tooltip_vt:raise RuntimeError('Native popup owner vtable mismatch')
 if pointer(owner+container_offset)+48!=gui:return {'status':'nested_panel','native_type':kind}
 if kind in NOTIFICATION_OWNERS:
  signature(0x1bbf140);verify()
  return {'status':'native_notification','notification_native_type':kind,'runtime_binding_verified':True,
          'binding':'NNotification.notification_entry','physical_visibility_verified':False,'atomic_game_frame':False}
 if kind=='.?AVCEventWindow@@':
  signature(0x1238fe0);signature(0x1239a40);signature(0x1180270)
  event=pointer(owner+0x68)
  if not event:return {'status':'no_current_event'}
  if r.typename(event)!='.?AVCEvent@@' or pointer(event)!=r.base+0x2999be8:raise RuntimeError('Native event type mismatch')
  read(event+0x20,32);value=r._string(event+0x20)
  if value['status']!='read':raise GuiSnapshotChanged('Native event ID unreadable or changed')
  # CEventWindow's option selection iterates CEvent.options and uses each
  # CEventOption.index; its name parser stores the key at +0x178.
  array,capacity,count=struct.unpack('<QII',read(event+0x368,16))
  if count>capacity or capacity>1000:raise RuntimeError('Native event option extent invalid')
  options=[]
  for i in range(count):
   option=pointer(array+i*8)
   if r.typename(option)!='.?AVCEventOption@@' or pointer(option)!=r.base+0x2999b48:raise RuntimeError('Native event option type mismatch')
   read(option+0x178,32);name=r._string(option+0x178)
   if name['status']!='read':raise GuiSnapshotChanged('Native event option ID unreadable or changed')
   index=struct.unpack('<i',read(option+0x1f0,4))[0]
   if index<0 or any(x['native_index']==index for x in options):raise RuntimeError('Native event option index invalid')
   options.append({'native_index':index,'name_key':name['raw_text'],'identity_verified':True,
                   'availability_verified':False,'effects_verified':False})
   if r._string(option+0x178)!=name:raise GuiSnapshotChanged('Native event option ID changed during read')
  verify()
  return {'status':'native_event_id','event_id':value['raw_text'],'event_id_verified':True,
          'binding':'CEventWindow.current_event.CEvent.id','native_options':options,
          'option_identity_scope':'event_definition_not_displayed_choices','atomic_game_frame':False}
 if kind=='.?AVCWorldTensionPopUpWindow@@':
  verify();return {'status':'native_window_state','window':'world_tension','engine_local_shown':bool(header[117]&8),
                   'runtime_binding_verified':True,'physical_visibility_verified':False,'atomic_game_frame':False}
 scope='region' if kind=='.?AVCRegionAlertEntry@@' else 'theater' if kind=='.?AVCTheaterGroupAlertEntry@@' else 'global'
 signature({'region':0x1e6aac0,'theater':0x1e6acf0,'global':0xb0cc50}[scope]);signature(0xb0ab70)
 if scope!='global':
  signature(0x22a9260)
  manager=pointer(pointer(r.base+0x332f6a0)+0x798);alert=struct.unpack('<I',read(owner+0x558,4))[0]
  if scope=='region':
   context=pointer(owner+0x560)
   if context and (pointer(context)!=r.base+0x296d558 or r.typename(context)!='.?AVCStrategicRegion@@'):raise RuntimeError('Native region context type mismatch')
  else:
   signature(0x221f310);signature(0x221d320)
   first,second=struct.unpack('<2I',read(owner+0x55c,8))
   context=resolve_native_handle(r.base,read,first,second)
   if context and (pointer(context)!=r.base+0x29e5c50 or r.typename(context)!='.?AVCTheaterGroup@@'):raise RuntimeError('Native theater context type mismatch')
  expected_key=(context,0,0) if scope=='region' else (0,context,0)
  if not context:
   verify();return {'status':'no_'+scope+'_context','native_alert_kind':alert}
 else:
  manager=pointer(owner+0x30);alert=struct.unpack('<I',read(owner+0x48,4))[0];context=pointer(owner+0x558);expected_key=(0,0,context)
 identity={'native_owner_id':hex(owner),'native_provider_id':hex(parent),'native_context_id':hex(context),'native_alert_kind':alert,'alert_scope':scope}
 if scope=='theater':identity['native_context_handle']=[first,second]
 if alert>81:return {'status':'unsupported_alert_kind',**identity}
 # The native tooltip lookup uses this vector, stride and three-part context key.
 table=manager+24*(alert+0xf0e);array,capacity,count=struct.unpack('<QII',read(table,16))
 if count>capacity or capacity>1000:raise RuntimeError('Native alert cache extent invalid')
 matches=[]
 for i in range(count):
  entry=array+i*0x468;key=struct.unpack('<4Q',read(entry+0x438,32))
  if (key[0],key[1],key[3])==expected_key:matches.append(entry)
 if len(matches)!=1:
  verify();return {'status':'cache_missing' if not matches else 'cache_ambiguous',**identity}
 active=read(matches[0],1)[0]==0
 fields={}
 for label,offset in (('title',8),('body',40)):
  address=matches[0]+offset;read(address,32);value=r._string(address)
  if value['status']!='read':raise GuiSnapshotChanged('Native alert cache text unreadable or changed')
  value['formatted_runs']=native_markup(value['raw_text']);fields[label]=value
 # Re-read payloads as well as headers; heap contents can change without relocation.
 for label,offset in (('title',8),('body',40)):
  final=r._string(matches[0]+offset)
  if final.get('raw_text')!=fields[label]['raw_text'] or final['status']!='read':raise GuiSnapshotChanged('Native alert cache text changed during read')
 verify()
 return {'status':'native_cached_text',**identity,'fields':fields,'native_cache_record_active':active,
         'alert_scope':scope,'runtime_binding_verified':True,'buffer_freshness_verified':False,
         'buffer_last_update_unix':None,'complete_message_coverage':False,'atomic_game_frame':False}
