"""Build-pinned event identity and global-alert cache reads; no native invocation."""
import struct
from runtime_gui import GuiSnapshotChanged,native_markup

OWNER_LAYOUTS={'.?AVCWorldTensionPopUpWindow@@':(56,0x2a133d8,0x2a13478,0x570),
               '.?AVCEventWindow@@':(56,0x29a4818,0x29a4878,0x50),
               '.?AVCGlobalAlertIcon@@':(40,0x29468f8,0x2946920,0x38)}
SIGNATURES={0x1238fe0:'488bc4488958104889701855574156488da848ffffff4881eca00100000f2970',
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
 signature(0xb0cc50);signature(0xb0ab70)
 manager=pointer(owner+0x30);alert=struct.unpack('<I',read(owner+0x48,4))[0];context=pointer(owner+0x558)
 if alert>81:return {'status':'unsupported_alert_kind','native_alert_kind':alert}
 # The native tooltip lookup uses this vector, stride and three-part context key.
 table=manager+24*(alert+0xf0e);array,capacity,count=struct.unpack('<QII',read(table,16))
 if count>capacity or capacity>1000:raise RuntimeError('Native alert cache extent invalid')
 matches=[]
 for i in range(count):
  entry=array+i*0x468;key=struct.unpack('<4Q',read(entry+0x438,32))
  if key[0]==0 and key[1]==0 and key[3]==context:matches.append(entry)
 if len(matches)!=1:
  verify();return {'status':'cache_missing' if not matches else 'cache_ambiguous','native_alert_kind':alert}
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
 return {'status':'native_cached_text','native_alert_kind':alert,'fields':fields,
         'runtime_binding_verified':True,'buffer_freshness_verified':False,
         'buffer_last_update_unix':None,'complete_message_coverage':False,'atomic_game_frame':False}
