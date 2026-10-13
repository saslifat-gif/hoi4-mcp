"""Bind the exact selected content; do not assume unknown overlay precedence."""
import hashlib,json,zipfile
from pathlib import Path
from script_parser import parse_script, scalar as field

RELEVANT=('common/units/equipment/','common/technologies/','common/buildings/','common/defines/')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def capture(game_root,user_root,owned_entry=None):
    game=Path(game_root).resolve();user=Path(user_root).resolve()
    selection=json.loads((user/'dlc_load.json').read_text(encoding='utf-8-sig'))
    mods=selection.get('enabled_mods');disabled=selection.get('disabled_dlcs')
    if not isinstance(mods,list) or not isinstance(disabled,list):raise ValueError('Invalid selected content')
    mods=[x for x in mods if x!=owned_entry]
    out={'enabled_mods':mods,'disabled_dlcs':disabled,'descriptors':{},'definition_inventory':[],
         'overlay_definition_files':[],'integrated_descriptor_relocations':[]}
    for prefix in RELEVANT:
        out['definition_inventory'] += sorted(p.relative_to(game).as_posix() for p in (game/prefix).rglob('*.txt'))
    descriptors=[]
    for base in (game/'dlc',game/'integrated_dlc'):
        descriptors += [(p,False) for p in sorted(base.rglob('*.dlc'))]
    for name in mods:
        p=(user/name).resolve()
        if not p.is_relative_to(user):raise ValueError('Mod descriptor escapes user directory')
        descriptors.append((p,True))
    for descriptor,is_mod in descriptors:
        nodes=parse_script(descriptor.read_text(encoding='utf-8-sig'))
        out['descriptors'][str(descriptor)]=digest(descriptor)
        # All installed DLC containers are audited, even if currently disabled.
        if any(n['key']=='replace_path' for n in nodes):
            raise RuntimeError('Content replace_path requires an explicit overlay resolver')
        containers=[field(nodes,k) for k in ('path','archive')];containers=[x for x in containers if x]
        if not containers:raise RuntimeError('Unresolved content container: '+str(descriptor))
        for value in containers:
            root=Path(value)
            if not root.is_absolute():root=(user if is_mod else game)/root
            if not root.exists() and descriptor.is_relative_to(game/'integrated_dlc'):
                candidate=game/'integrated_dlc'/Path(value).name
                if candidate==descriptor.parent:
                    out['integrated_descriptor_relocations'].append(str(descriptor));root=candidate
            if not root.exists():raise RuntimeError('Missing content container: '+str(root))
            files=[root] if root.is_file() else sorted(x for x in root.rglob('*') if x.is_file())
            for path in files:
                if path.suffix.lower()=='.zip':
                    with zipfile.ZipFile(path) as z:
                        names=[n.replace('\\','/').lower() for n in z.namelist()]
                    out['overlay_definition_files'] += [str(path)+':'+n for n in names if n.startswith(RELEVANT)]
                elif path!=root:
                    rel=path.relative_to(root).as_posix().lower()
                    if rel.startswith(RELEVANT):out['overlay_definition_files'].append(str(path))
    if out['overlay_definition_files']:
        raise RuntimeError('Active/installed content overrides need resolution: '+', '.join(out['overlay_definition_files'][:5]))
    out['active_overlay_verified']=True
    return out

def verify(config):
    record=config.get('content_binding')
    if record is None:return # Older sessions retain their explicit unresolved status.
    current=capture(config['game_root'],record['user_root'],record['owned_entry'])
    if current!=record['snapshot']:raise RuntimeError('Selected content or definition inventory changed; prepare a fresh session')
