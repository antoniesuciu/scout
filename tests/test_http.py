import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from scout import app as scout


class HTTPTests(unittest.TestCase):
    def request(self, method, path, body='', headers=None):
        # Exercise the real HTTP parser and handler with an in-memory transport.
        import io
        payload = body.encode()
        h = {'Host': scout.HOSTS[0], 'Content-Length': str(len(payload)), **(headers or {})}
        raw = (f'{method} {path} HTTP/1.0\r\n' + ''.join(f'{k}: {v}\r\n' for k,v in h.items()) + '\r\n').encode() + payload
        class Transport:
            def __init__(self):
                self.output = io.BytesIO()
            def makefile(self, *args):
                return io.BytesIO(raw)
            def sendall(self, data):
                self.output.write(data)
        transport = Transport()
        scout.Handler(transport, ('127.0.0.1', 12345), None)
        head, content = transport.output.getvalue().split(b'\r\n\r\n', 1)
        return int(head.split()[1]), content

    def test_local_page_and_state(self):
        status, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'<title>scout</title>', body)
        status, body = self.request('GET', '/api/state')
        self.assertEqual(status, 200)
        self.assertIn('videos', json.loads(body))

    def test_wrong_host_and_content_type_are_forbidden(self):
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('POST', '/api/session', '{}', {'Content-Type': 'text/plain'})[0], 403)

    def test_traversal_is_refused(self):
        self.assertEqual(self.request('GET', '/file/transcripts/../../settings.json')[0], 404)

    def test_bad_bodies_never_start_a_job(self):
        for body in ('[]', 'null', '{', '{"ids": ["x"], "engine": [], "language": "en"}'):
            with patch.object(scout, 'start') as start:
                self.assertEqual(self.request('POST', '/api/run', body, {'Content-Type': 'application/json'})[0], 400)
                start.assert_not_called()

    def test_pasted_local_url_cannot_start_a_downloader(self):
        with patch.object(scout, 'start') as start:
            self.assertEqual(self.request('POST', '/api/add', '{"url":"http://localhost/private"}', {'Content-Type': 'application/json'})[0], 400)
            start.assert_not_called()
