import asyncio
from .connection import ESLConnectionOut, ESLConnectionIn
from .log import aioesl_log


class Client:

    def __init__(self, loop, client_ip, client_port, password=None, reconnect=False, retries=0, retry_sleep=30):
        self._loop = loop
        self.conn = ESLConnectionOut(self._loop, client_ip, client_port, password=password,
                                     reconnect=reconnect, retries=retries, retry_sleep=retry_sleep)
        self.client_ip = client_ip
        self.client_port = client_port
        self.password = password

    async def connect(self):
        await self.conn.open_connection()

    def ready(self):
        return self.conn.ready()

    def set_handler(self, event, handler):
        self.conn.set_handler(event, handler)

    def pop_handler(self, event):
        assert isinstance(event, str), "event mast be str type."
        self.conn.pop_handler(event)

    # syntactic sugar
    def __getattr__(self, attr):
        if not self.conn.check_cmd(attr):
            raise AttributeError(attr)
        attr = self.conn.get_cmd(attr)
        def wrapper(*args, **kw):
            return attr(*args, **kw)
        return wrapper


class ClientSession:
    def __init__(self, loop, reader, writer, client_connected_cb):
        self._loop = loop
        self._reader = reader
        self._writer = writer

        self.host, self.port = self._writer.get_extra_info('peername')
        self.conn = ESLConnectionIn(self._loop, self.host, self.port)

        self._client_connected_cb = client_connected_cb

    @property
    def peer(self):
        return "%s:%s" % (self.host, self.port)

    async def start(self):
        aioesl_log.info("Incoming connection from %s" % self.peer)
        await self._client_connected_cb(self)

    def set_handler(self, event, handler):
        self.conn.set_handler(event, handler)

    def pop_handler(self, event):
        assert isinstance(event, str), "event mast be str type."
        self.conn.pop_handler(event)


class Server:

    def __init__(self, loop, ip, port, client_connected_cb):
        self._loop = loop
        self.server_ip = ip
        self.server_port = port
        self.app = None
        self.connections = []
        self._client_connected_cb = client_connected_cb

    @property
    def server_link(self):
        return "%s:%s" % (self.server_ip, self.server_port)

    async def start(self):
        self.app = await asyncio.start_server(client_connected_cb=self.start_client_session,
                                              host=self.server_ip,
                                              port=self.server_port,
                                              loop=self._loop)
        aioesl_log.info("Server started at %s" % self.server_link)

    async def start_client_session(self, reader, writer):
        cs = ClientSession(self._loop, reader, writer, self._client_connected_cb)
        self.connections.append(cs)
        asyncio.ensure_future(cs.start())
