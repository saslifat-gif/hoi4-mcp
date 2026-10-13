"""Real MCP/HTTP transport with a simulated engine; not live gameplay proof."""
import asyncio
from http.server import HTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from direct_controller import DirectController, render_effect, render_hook
from direct_bridge import make_direct_handler, CommandHTTPServer
from transport import BridgeClient

SID='b'*32; CID='a'*32
CAT={'equipment':{'infantry_equipment_1':{'factory_kind':'military','base_active':False,
                                        'unlock_technologies_any':['infantry_weapons']}}}


def unpack(r):
    assert not r.isError, str(r)
    return json.loads(r.content[0].text)


async def roundtrip():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);effect=root/'effect.txt';hook=root/'hook.txt';log=root/'game.log'
        effect.write_text(render_effect('GER',[],SID,CAT));hook.write_text(render_hook('GER',SID,CID))
        log.write_text(f'CODEX_COMMAND_SESSION|{SID}|READY|country=GER\n')
        c=DirectController(effect,log,root/'ledger.json',hook_path=hook,session_id=SID,catalog=CAT)
        token=root/'token';token.write_text('simulated-protocol-token')
        http=HTTPServer(('127.0.0.1',0),make_direct_handler(c,token.read_text()))
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{http.server_port}'
        try:
            with unittest.TestCase().assertRaisesRegex(RuntimeError,'Unauthorized'):
                BridgeClient(url,token='wrong').call('/status',{})
            p=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('direct_mcp_server.py')),
                                     '--url',url,'--token-file',str(token)])
            async with stdio_client(p) as (read,write):
                async with ClientSession(read,write) as s:
                    await s.initialize();tools=(await s.list_tools()).tools
                    assert {t.name for t in tools}=={'hoi4_status','hoi4_arm','hoi4_snapshot','hoi4_construct','hoi4_produce','hoi4_receipt','hoi4_deliver'}
                    assert not unpack(await s.call_tool('hoi4_status',{}))['armed']
                    assert (await s.call_tool('hoi4_produce',{'request_id':CID,'equipment':'infantry_equipment_1'})).isError
                    assert unpack(await s.call_tool('hoi4_arm',{'enabled':True}))['armed']
                    args={'request_id':CID,'equipment':'infantry_equipment_1','factories':2}
                    submitted=unpack(await s.call_tool('hoi4_produce',args))
                    assert submitted['status']=='queued' and not submitted['engine_acknowledged']
                    before=(effect.read_bytes(),hook.read_bytes())
                    assert unpack(await s.call_tool('hoi4_produce',args))['status']=='pending'
                    assert before==(effect.read_bytes(),hook.read_bytes())
                    client=BridgeClient(url,token_file=token)
                    with unittest.TestCase().assertRaisesRegex(RuntimeError,'Unsupported'):
                        client.call('/submit',{'request_id':'c'*32,'command':{'kind':'keys','keys':['space']}})
                    assert len(c.state['commands'])==1
                    log.write_text(log.read_text()+f'[12:00:00][1936.01.02.24] CODEX_COMMAND|{SID}|{CID}|ACK|kind=produce|stage=effect_ran|available_military_factories=4\n')
                    receipt=unpack(await s.call_tool('hoi4_receipt',{'command_id':CID}))
                    assert receipt['engine_acknowledged'] and not receipt['gameplay_outcome_verified']
                    assert unpack(await s.call_tool('hoi4_deliver',{'command_id':CID}))['status']=='acknowledged'
                    assert before==(effect.read_bytes(),hook.read_bytes())
                    assert not unpack(await s.call_tool('hoi4_arm',{'enabled':False}))['armed']
            return {'mcp_transport':'real stdio','http_transport':'real authenticated loopback',
                    'engine':'simulated log fixture','tool_count':7,'live_gameplay_verified':False,
                    'keyboard_mouse_fallback':False}
        finally:
            http.shutdown();http.server_close();thread.join()


class Protocol(unittest.TestCase):
    def test_command_port_rejects_competing_listener(self):
        first=CommandHTTPServer(('127.0.0.1',0),make_direct_handler(None,'fixture'))
        try:
            with self.assertRaises(OSError):
                CommandHTTPServer(first.server_address,make_direct_handler(None,'other'))
        finally:
            first.server_close()

    def test_stdio_authentication_semantics_and_receipt_boundary(self):
        print(json.dumps(asyncio.run(roundtrip())))


if __name__=='__main__':unittest.main()
