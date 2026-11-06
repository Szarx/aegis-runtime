"""Optional metadata-only health channel, independent of the Span export queue."""
import json
import threading
import uuid
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class HealthReporter:
    def __init__(self, sdk, endpoint, token, interval):
        url = urlsplit(endpoint)
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
                or url.path != '/v1/health' or url.query or url.fragment or url.port == 0
                or (url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'))):
            raise ValueError('Invalid health endpoint')
        if token is not None and (type(token) is not str or not token or len(token) > 4096
                                  or any(not 33 <= ord(c) <= 126 for c in token)):
            raise ValueError('Invalid health token')
        if type(interval) not in (int, float) or not 1 <= interval <= 30:
            raise ValueError('Health interval must be 1..30 seconds')
        self.instance_id = uuid.uuid4().hex
        self._sdk, self._endpoint, self._token, self._interval = sdk, endpoint, token, interval
        self._stop = threading.Event()
        self._sequence = self._failures = 0
        self._worker = threading.Thread(target=self._run, daemon=True, name='aegis-health')

    def start(self):
        self._worker.start()
        return self.instance_id

    def stop(self):
        self._stop.set()

    def _run(self):
        opener = build_opener(ProxyHandler({}), NoRedirect())
        while True:
            closing = self._stop.is_set()
            self._sequence += 1
            payload = dict(instance_id=self.instance_id, sequence=self._sequence,
                           service_name=self._sdk.service_name, **self._sdk._processor.activity(),
                           diagnostics=self._sdk.diagnostics(), health_failures=self._failures)
            headers = {'Content-Type': 'application/json'}
            if self._token:
                headers['Authorization'] = 'Bearer ' + self._token
            try:
                request = Request(self._endpoint, data=json.dumps(payload).encode(), headers=headers)
                with opener.open(request, timeout=1) as response:
                    if response.status != 200:
                        raise ValueError('Health report rejected')
            except Exception:
                self._failures += 1
            if closing:
                return
            self._stop.wait(self._interval)
