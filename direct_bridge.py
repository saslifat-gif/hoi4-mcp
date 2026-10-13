"""Keyboard-free service; may run over SSH because it uses only files and logs."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import socket
import sys
from direct_controller import DirectController
from direct_process import process_identity
from bind_session import verify_sources


class CommandHTTPServer(HTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        # Windows SO_REUSEADDR can permit competing listeners and credentials.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_direct_handler(controller, token):
    import hmac
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, value):
            body = json.dumps(value).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.connection.settimeout(5)
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                return self.reply(401, {'error': 'Unauthorized'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('Invalid request length')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('Request must be an object')
                if self.path == '/status': result = controller.status()
                elif self.path == '/arm': result = controller.arm(payload.get('enabled'))
                elif self.path == '/submit': result = controller.submit(payload.get('command'),payload.get('request_id'))
                elif self.path == '/deliver': result = controller.deliver(payload.get('command_id'))
                elif self.path == '/receipt': result = controller.receipt(payload.get('command_id'))
                else: return self.reply(404, {'error': 'Unknown direct endpoint'})
                self.reply(200, result)
            except (ValueError, TypeError, AttributeError) as exc:
                self.reply(400, {'error': str(exc)})
            except Exception as exc:
                self.reply(409, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session-file', required=True)
    parser.add_argument('--port', type=int, default=18768)
    parser.add_argument('--token-file', default=str(Path(__file__).with_name('.commands-token')))
    args = parser.parse_args()
    config = json.loads(Path(args.session_file).read_text(encoding='utf-8-sig'))
    expected = config['process_identity']
    if not isinstance(expected,dict):
        raise RuntimeError('Bind the prepared game session first')
    catalog=verify_sources(config)
    def guard():
        if process_identity(expected['pid']) != expected:
            raise RuntimeError('Bound game process changed; no command submitted')
        verify_sources(config)
    guard()
    controller = DirectController(config['effect_path'], config['log_path'], config['state_path'], config['country'], guard, config['hook_path'],config['session_id'],catalog)
    token = secrets.token_urlsafe(32)
    server = CommandHTTPServer(('127.0.0.1', args.port), make_direct_handler(controller, token))
    Path(args.token_file).write_text(token)
    print(f'Direct HOI4 bridge listening on loopback {args.port}; no input APIs loaded', file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.arm(False)
        server.server_close()

if __name__ == '__main__': main()
