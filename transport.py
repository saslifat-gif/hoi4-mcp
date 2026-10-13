import json
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


class BridgeClient:
    def __init__(self, url, token=None, *, token_file=None):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('Bridge URL must be loopback HTTP; use an SSH tunnel for remote Windows')
        if token_file is not None and token is not None:
            raise ValueError('Use a token or token_file, not both')
        self.token_file = Path(token_file) if token_file is not None else None
        if self.token_file is None and (not token or any(c.isspace() for c in token)):
            raise ValueError('Invalid bridge token')
        self.url = url.rstrip('/')
        self.token = token
        self.opener = build_opener(ProxyHandler({}))

    def call(self, path, payload):
        token = self.token
        if self.token_file is not None:
            try:
                token = self.token_file.read_text(encoding='utf-8-sig').strip()
            except (OSError, UnicodeError) as exc:
                raise RuntimeError('Bridge credential unavailable; no request submitted.') from exc
            if not token or any(c.isspace() for c in token):
                raise RuntimeError('Bridge credential invalid; no request submitted.')
        request = Request(self.url + path, json.dumps(payload).encode(),
                          {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                          method='POST')
        try:
            with self.opener.open(request, timeout=15) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                error = json.load(exc).get('error', f'HTTP {exc.code}')
            except (json.JSONDecodeError, UnicodeError):
                error = f'HTTP {exc.code}'
            raise RuntimeError(error) from exc
        except (URLError, TimeoutError, OSError) as exc:
            if path.startswith('/info/'):
                raise RuntimeError('Code-side read unavailable or timed out; no gameplay command was submitted.') from exc
            raise RuntimeError('Bridge unavailable or response uncertain. Do not automatically retry commands; '
                               'reconnect and observe first.') from exc
