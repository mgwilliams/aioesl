import asyncio
import logging
from .protocol import EventProtocol

log_srv = logging.getLogger("aioesl SRV")
log_cli = logging.getLogger("aioesl CLI")

class Server(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self._is_server = True


def get_server(loop, ip, port):
    assert int(port), "Порт должен быть integer"
    esl = loop.create_server(Server(loop=loop), ip, port)
    ok = asyncio.ensure_future(esl)
    ok.add_done_callback(lambda res: print("Server started"))
    return ok


class Client(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self.host = kwargs.get("host")
        self.port = kwargs.get("port", 8021)
        self.connection_timeout = kwargs.get("connection_timeout", 10)

    def make_connection(self):
        future = asyncio.Future()

        async def connect():
            try:
                await self._loop.create_connection(lambda: self, self.host, self.port)
                print(11)
                future.set_result(True)
            except OSError:
                log_cli.info("Can not connect to %s:%s" % (self.host, self.port))
                await reconnect()

        async def reconnect():
            if self.check_retry():
                await asyncio.sleep(self.retry_time)
                await self.make_connection()
            else:
                future.set_result(False)

        async def timer():
            try:
                await asyncio.wait_for(connect(), timeout=self.connection_timeout)
            except asyncio.futures.TimeoutError:
                log_cli.info("Connect timeout to %s:%s" % (self.host, self.port))
                await reconnect()

        assert self.host is not None, "Host can not be None"
        assert isinstance(self.port, int), "Port can not be None"
        assert isinstance(self.reconnect, bool), "reconnect is Boolean"
        assert isinstance(self.retry_time, int), "retry_time is int"
        asyncio.ensure_future(timer())
        return future


