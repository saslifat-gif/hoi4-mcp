"""Strict installed-script parser reused from the HOI4 information reader."""
import re
TOKEN=re.compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|[{}]|\?=|[<>=!]+|[^\s{}<>=!"#]+')
class ScriptError(ValueError):pass

def scalar(nodes, key):
    values = [n['value'] for n in nodes if n['key'] == key and n['children'] is None]
    if len(values) > 1:
        raise ValueError('Duplicate field: ' + key)
    return values[0] if values else None

def parse_script(text):
    tokens=[]
    pos=0
    for m in TOKEN.finditer(text):
        if m.start()!=pos:raise ScriptError('Unrecognized script character at '+str(pos))
        pos=m.end();v=m.group()
        if v.isspace() or v.startswith('#'):continue
        tokens.append((v,m.start(),m.end()))
    if pos!=len(text):raise ScriptError('Incomplete tokenization')
    def atom(v):
        return v[1:-1] if v.startswith('"') else v
    def block(i,depth=0):
        if depth>128:raise ScriptError('Nesting limit')
        nodes=[]
        while i<len(tokens) and tokens[i][0]!='}':
            v,start,end=tokens[i]
            if v=='{':
                children,i=block(i+1,depth+1)
                if i>=len(tokens) or tokens[i][0]!='}':raise ScriptError('Unclosed anonymous block')
                nodes.append({'key':None,'operator':None,'value':None,'children':children,
                              'start':start,'end':tokens[i][2]})
                i+=1
                continue
            i+=1;op=None;value=atom(v);children=None
            if i<len(tokens) and tokens[i][0] in ('=','>','<','>=','<=','!=','==','?='):
                op=tokens[i][0];i+=1
                if i>=len(tokens):raise ScriptError('Missing value')
                v2,_,end=tokens[i];i+=1
                if v2=='{':
                    children,i=block(i,depth+1)
                    if i>=len(tokens) or tokens[i][0]!='}':raise ScriptError('Unclosed block')
                    end=tokens[i][2];i+=1;value=None
                elif v2=='}':raise ScriptError('Missing assignment value')
                else:value=atom(v2)
            nodes.append({'key':atom(v) if op else None,'operator':op,'value':value,
                          'children':children,'start':start,'end':end})
        return nodes,i
    nodes,i=block(0)
    if i!=len(tokens):raise ScriptError('Unmatched closing brace')
    return nodes
