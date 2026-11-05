"""Bounded local Uvicorn host for actual socket-based acceptance tests."""

import socket
import asyncio
import sys
import threading
import time
import uvicorn


class LiveServer:
    def __init__(self, app):
        self.listener=socket.socket()
        self.listener.bind(('127.0.0.1',0))
        self.endpoint=f'http://127.0.0.1:{self.listener.getsockname()[1]}'
        self.server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='off',timeout_keep_alive=1,timeout_graceful_shutdown=2))
        self.worker=threading.Thread(target=self._serve,daemon=True)

    def _serve(self):
        # Embedded Windows test servers must drain reset connections before joining.
        factory=asyncio.SelectorEventLoop if sys.platform=='win32' else asyncio.new_event_loop
        with asyncio.Runner(loop_factory=factory) as runner:
            runner.run(self.server.serve(sockets=[self.listener]))

    def start(self):
        self.worker.start();deadline=time.monotonic()+5
        while not self.server.started and self.worker.is_alive() and time.monotonic()<deadline:time.sleep(.01)
        if not self.server.started:
            self.close();raise RuntimeError('local test server did not start')
        return self

    def close(self):
        self.server.should_exit=True;self.worker.join(5);self.listener.close()
        if self.worker.is_alive():raise RuntimeError('local test server did not stop')
