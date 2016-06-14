import asyncio
from .streams import start_server, open_connection
from .connection import SessionBase
from .protocol import ESLCommands
from .log import aioesl_log
import traceback
import sys


class Client(SessionBase):

    def __init__(self, loop, **kwargs):
        super().__init__(loop, **kwargs)

        self._password = kwargs.get("password", "ClueCon")
        self._reconnect = kwargs.get("reconnect", False)
        self._retries = kwargs.get("retries", 5)
        self._retry_sleep = kwargs.get("retry_sleep", 30)

        assert isinstance(self._host, str), "host mast be str type"
        assert isinstance(self._port, int), "port mast be int type"
        assert isinstance(self._reconnect, bool), "retries mast be bool type"
        assert isinstance(self._retries, int), "retries mast be int type"
        assert isinstance(self._retry_sleep, int), "retry_sleep mast be int type"

        self._cur_retry = 0

    async def open_connection(self):
        if self._reader is not None:
            raise "Reader is started!"

        try:
            self.li("Connecting. %s retry." % self._cur_retry)
            self._reader, self._writer = await open_connection(self._host, self._port, loop=self._loop)

            self.li("Connected.")
            self._parser.set_reader(self._reader)
            self.set_writer(self._writer)
            self._data_reader = asyncio.ensure_future(self._parser.read_from_connection())
            if self._password is None:
                self.set_connect_waiter(True)

        except OSError:
            self.le("Connect call failed %s" % self.peer)
            asyncio.ensure_future(self.reconnect())

    async def reconnect(self):
        if self._reconnect:
            self._cur_retry += 1
            if self._retries == 0 or self._retries >= self._cur_retry:
                aioesl_log.info("Reconnecting to %s at %s" % (self.peer, self._retry_sleep))
                self._closing = False
                self._connect_waiter = asyncio.Future()
                self._protocol._closing = False
                await asyncio.sleep(self._retry_sleep)
                await self.connect()
            else:
                aioesl_log.error("Max retry. Stop connection.")


class Server:

    def __init__(self, loop, ip, port, **kwargs):
        self._loop = loop
        self.server_ip = ip
        self.server_port = port
        self.app = None
        self.sessions = []
        self._session_connected_cb = kwargs.get("session_connected_cb")
        self._event_handler_log = kwargs.get("event_handler_log", False)

    @property
    def server_link(self):
        return "%s:%s" % (self.server_ip, self.server_port)

    async def start(self):
        self.app = await start_server(client_connected_cb=self._start_client_session,
                                      host=self.server_ip, port=self.server_port,
                                      loop=self._loop,
                                      )
        aioesl_log.info("Server started at %s" % self.server_link)

    async def _start_client_session(self, reader, writer, protocol=None):
        try:
            session = Session(self._loop,
                              reader=reader,
                              writer=writer,
                              protocol=protocol,
                              destroy_session=self.destroy_session,
                              event_handler_log=self._event_handler_log)
            self.sessions.append(session)
            await session.start(session_connected_cb=self._session_connected_cb)
        except Exception as error:
            aioesl_log.exception(error)

    def destroy_session(self, session):
        if session in self.sessions:
            self.sessions.remove(session)


class Session(SessionBase):

    def __init__(self, loop, **kwargs):
        super().__init__(loop, **kwargs)
        self.destroy_session = kwargs.get("destroy_session")

    async def start(self, session_connected_cb=None):
        self._data_reader = asyncio.ensure_future(self._parser.read_from_connection())
        self.li("Connected.")
        res = await self.connect()
        if session_connected_cb is not None:
            cb = session_connected_cb(self, res)
            if asyncio.iscoroutine(cb):
                await cb

    async def _close_handler(self, ev):
        await super()._close_handler(ev=ev)
        self.destroy_session(self)
        del self


