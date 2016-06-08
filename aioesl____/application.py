import asyncio
import logging
from .protocol import EventProtocol
from aioredis import Redis

log_srv = logging.getLogger("aioesl SRV")
log_cli = logging.getLogger("aioesl CLI")


class Server(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self.mode = "Server"

    def cd_connection_made(self):
        log_srv.info("Incoming connection from %s:%s" % (self.peer, self.port))
        self.host = self.peer
        self.peers["%s:%s" % (self.host, self.port)] = self
        asyncio.ensure_future(self.start_server())

    peers = {}
    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self.mode = "Server"
        self.ip = kwargs.get("ip", "0.0.0.0")
        self.port = kwargs.get("port", "4567")
        self.handlers["new_connection"] = self.new_connection

    @property
    def peer_info(self):
        return "%s:%s" % (self.transport.get_extra_info("peername"))

    async def start(self):
        assert self.ip is not None, "IP can not be None"
        assert isinstance(self.port, int), "Port can not be None"
        await self._loop.create_server(lambda: self, self.ip, self.port)
        log_srv.info("Server started %s:%s" % (self.ip, self.port))

    async def cb_connection_made(self):
        log_cli.info("Incomming connection from %s" % self.peer_info)
        self.peers[self.peer_info] = self
        await self.handlers["new_connection"](await self.connect())

    async def cb_connection_lost(self, exc):
        print("!!!!!!!!!!exc", exc)
        self.peers.pop(self.peer_info)

    async def close_all(self):
        for p in self.peers:
            await self.close(p)

    async def close(self, peer):
        peer.status = 'close'

    async def new_connection(self):
        pass


class Client(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self.mode = "Client"

        self.host = kwargs.get("host")
        self.port = kwargs.get("port", 8021)
        self.auth_password = kwargs.get("password", "ClueCon")

        self.connection_timeout = kwargs.get("connection_timeout", 10)

        self._auth_success = False
        self.reconnect = kwargs.get("reconnect", False)
        self.retry_time = kwargs.get("retry_time", 120)
        self.max_retry = kwargs.get("max_retry", -1)
        self.count_retry = 0

        self.authenticated = asyncio.Future()

    @property
    def peer_info(self):
        return "%s:%s" % (self.transport.get_extra_info("peername"))


    def make_connection(self):
        future = asyncio.Future()

        async def connect():
            try:
                await self._loop.create_connection(lambda: self, self.host, self.port)
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

    async def auth_request(self, ev):
        res = await self.auth(self.auth_password)
        if res.get('Reply-Text') == '+OK accepted':
            self.authenticated.set_result(True)
            self.max_retry = 0

    async def on_disconnect(self, ev):
        self._authenticated = asyncio.Future()

    async def on_rude_rejection(self, ev):
        log_cli.warning("Host %s. %s " % (
            str(self.transport.get_extra_info("peername")[0]),
            ev["DataResponse"].replace("\n", "")))

        asyncio.ensure_future(self.retry_connect())

    async def cb_connection_made(self):
        pass
        # log_cli.info("Outgoing connection to %s:%s" % (self.peer, self.port))

    async def cb_connection_lost(self, exc):
        log_cli.warning("Host %s. Connection lost. " % (self.peer))
        if self.status != 'close':
            asyncio.ensure_future(self.retry_connect())

    def check_retry(self):
        if self.reconnect and self.count_retry < self.max_retry:
            return True
        return False

    async def retry_connect(self):
        if self.check_retry():
            if self.max_retry > 0:
                self.count_retry += 1
            await asyncio.sleep(self.retry_time)
            log_cli.info("Start connection to %s:%s" % (self.peer, self.port))
            await self.make_connection()
        else:
            log_cli.info("Max count retry to %s:%s. Trying connection stopped." % (self.peer, self.port))
            self.authenticated.set_result(False)

    async def close(self):
        self.status = 'close'
        self.reconnect = False
        self.authenticated.cancel()

        if self.transport is not None:
            self.transport.close()
