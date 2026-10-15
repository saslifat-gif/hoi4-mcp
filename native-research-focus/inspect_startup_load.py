"""Read-only startup argument and world-state probe for an owned game process."""
import argparse,hashlib,json,struct
from pathlib import Path
from direct_process import process_identity
from runtime_gui import WindowsProcess,NativeGuiReader
from country_binding import read_country_binding
from military_reader import read_unit_ids
p=argparse.ArgumentParser();p.add_argument('--pid',required=True,type=int);p.add_argument('--game-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();exe=a.game_root/'hoi4.exe';ident=process_identity(a.pid);process=WindowsProcess(ident,exe)
try:
 r=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest());world=struct.unpack('<Q',r.read(r.base+0x332f260,8))[0];owner=struct.unpack('<Q',r.read(r.base+0x332f698,8))[0]
 result={'process_identity':ident,'world':hex(world),'owner':hex(owner),'start_save':r._string(r.base+0x3085090),'start_tag':r._string(r.base+0x3085070),'process_writes':False,'native_calls':False}
 if world:
  result.update(native_tick=struct.unpack('<i',r.read(world+0x468,4))[0],startup_gate_byte=r.read(world+0x979,1)[0],player_fields_hex=r.read(world+0x520,8).hex())
  country=read_country_binding(r,world,'GER');result['country']=country;units=read_unit_ids(r,country['country_id'],world);result['unit_count']=units['count'];result['unit_ids']=[u['unit_id'] for u in units['units']]
 process.guard();a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:process.close()
