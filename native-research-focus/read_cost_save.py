"""Read-only cost evidence from a stable plaintext save in a protected session."""
import hashlib, io, json, re, zipfile
from pathlib import Path
from script_parser import parse_script
TOK = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]')
def block(text, start):
    depth = 1
    for m in TOK.finditer(text, start):
        if m.group() == '{': depth += 1
        elif m.group() == '}':
            depth -= 1
            if not depth: return text[start:m.start()]
    raise ValueError('Incomplete native save block')
def child(nodes, key):
    values = [n['children'] for n in nodes if n['key'] == key and n['children'] is not None]
    if len(values) != 1: raise ValueError('Missing/ambiguous save block: ' + key)
    return values[0]
def scalars(nodes): return {n['key']: n['value'] for n in nodes if n['key'] and n['children'] is None}
def read_save(sf, *, retained=False):
    sf = Path(sf); cfg = json.loads(sf.read_text())
    manifest = json.loads((sf.parent/'recovery/manifest.json').read_text())
    save = Path(next(x['path'] for x in manifest if Path(x['path']).name == 'autosave.hoi4'))
    if retained:save=sf.parent/'private-test-autosave.hoi4'
    a=save.stat(); raw=save.read_bytes(); b=save.stat()
    if a.st_mtime < cfg['prepared_unix']:raise ValueError('Save predates the protected test session')
    if (a.st_size,a.st_mtime_ns)!=(b.st_size,b.st_mtime_ns):raise ValueError('Save is still changing')
    digest=hashlib.sha256(raw).hexdigest()
    if raw.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=[x for x in z.namelist() if x in ('gamestate','game_state')]
            if len(names)!=1:raise ValueError('Exactly one archive gamestate is required')
            raw=z.read(names[0])
    if not raw.startswith(b'HOI4txt'):raise ValueError('A native plaintext test save is required')
    text=raw.decode('utf-8-sig')
    top=re.search(r'(?m)^countries\s*=\s*\{',text)
    if top is None:raise ValueError('Native countries block is missing')
    countries=block(text,top.end()); depth=0; prev=0; germany=None
    for m in TOK.finditer(countries):
        if m.group()=='{':
            if depth==0 and re.search(r'\bGER\s*=\s*$',countries[prev:m.start()]):
                germany=block(countries,m.end());break
            depth+=1
        elif m.group()=='}':depth-=1
        prev=m.end()
    if germany is None:raise ValueError('Native Germany block is missing')
    prod=child(parse_script(germany),'production')
    lines=[]; builds=[]
    for n in prod:
        if n['key']=='military_lines':
            line=scalars(n['children']);line['variant']=scalars(child(n['children'],'equipment_variant_index'));lines.append(line)
        if n['key']=='general_lines':
            for item in n['children']:
                if item['key']=='building':
                    entry=scalars(item['children']);entry['building']=scalars(child(item['children'],'building'));builds.append(entry)
    date=re.search(r'(?m)^date\s*=\s*([^\r\n]+)',text)
    return {'save_sha256':digest,'mtime_ns':a.st_mtime_ns,'date':date.group(1) if date else None,
            'production':lines,'construction':builds}
if __name__=='__main__':
    import sys
    out=read_save(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(out,indent=2));print(json.dumps(out))
