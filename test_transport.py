"""HTTP error-body fixtures; no real bridge or gameplay execution."""
import io,unittest
from urllib.error import HTTPError
from unittest.mock import Mock,patch
from transport import BridgeClient

class TransportTests(unittest.TestCase):
 def client(self,body):
  client=BridgeClient('http://127.0.0.1:18768',token='fixture')
  client.opener=Mock()
  client.opener.open.side_effect=HTTPError(client.url,409,'Conflict',{},io.BytesIO(body))
  return client
 def test_json_error_preserved_without_retry(self):
  client=self.client(b'{"error":"Previous command is unresolved"}')
  with self.assertRaisesRegex(RuntimeError,'Previous command is unresolved'):client.call('/submit',{})
  client.opener.open.assert_called_once()
 def test_plain_error_body_reports_http_status(self):
  with self.assertRaisesRegex(RuntimeError,'HTTP 409'):self.client(b'<html>Error</html>').call('/submit',{})
 def test_unexpected_decode_failure_is_not_hidden(self):
  with patch('transport.json.load',side_effect=RuntimeError('reader failed')):
   with self.assertRaisesRegex(RuntimeError,'reader failed'):self.client(b'{}').call('/submit',{})

if __name__=='__main__':unittest.main()
