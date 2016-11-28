import asyncio
from .streams import start_server, open_connection
from .connection import SessionBase
from .log import aioesl_log

list_outbounds = []


class Client(SessionBase):

    def __init__(self, loop, **kwargs):
        super().__init__(loop, **kwargs)

        self._reconnect = kwargs.get("reconnect", False)
        self._retries = kwargs.get("retries", 5)
        self._retry_sleep = kwargs.get("retry_sleep", 30)

        assert isinstance(self._host, str), "host mast be str type"
        assert isinstance(self._port, int), "port mast be int type"
        assert isinstance(self._reconnect, bool), "retries mast be bool type"
        assert isinstance(self._retries, int), "retries mast be int type"
        assert isinstance(self._retry_sleep, int), "retry_sleep mast be int type"

        self._cur_retry = 0
        self.cb_on_connected = kwargs.get("cb_on_connected")

    async def open_connection(self):
        if self._reader is not None:
            raise "Reader is started!"

        try:
            if self.debug:
                self.li("Connecting. %s retry." % self._cur_retry)
            self._reader, self._writer = await open_connection(self._host, self._port, loop=self._loop)
            self._parser.set_reader(self._reader)
            self.set_writer(self._writer)
            self._data_reader = asyncio.ensure_future(self._parser.read_from_connection())

            list_outbounds.append(self)
            if self.debug:
                self.log_debug("Добавил в список подключений %s" % str(self))

            if self.password is None:
                self.set_connect_waiter(True)

            await self.ready()
            if self.cb_on_connected is not None:
                asyncio.ensure_future(self.cb_on_connected)
        except OSError as err:
            self.le("Ошибка установки подлючения OSError %s." % err.errno)
            asyncio.ensure_future(self.reconnect())

    async def _close_handler(self, **kwargs):
        await super()._close_handler(**kwargs)
        if self._data_reader is not None:
            self._data_reader.cancel()

        if kwargs.get("status") != "AuthFailed" and not self._closing:
            await self.reconnect()

        if self in list_outbounds:
            list_outbounds.remove(self)
        if self.debug:
            self.log_debug("Удалил из списка подключений %s" % str(self))

    async def reconnect(self):
        if self._reconnect:
            self._cur_retry += 1
            if self._retries == 0 or self._retries >= self._cur_retry:
                self.li("Reconnecting at %s" % self._retry_sleep)
                self._closing = False
                self._connect_waiter = asyncio.Future()
                await asyncio.sleep(self._retry_sleep)
                await self.open_connection()
                # await self.ready()
            else:
                aioesl_log.error("Max retry. Stop connection.")

    def shutdown(self):

        def ok():
            self.li("Подключение выключено.")
        self._closing = True
        ex = asyncio.ensure_future(self.exit())
        cp = asyncio.ensure_future(self._close_handler())
        cp.add_done_callback(ok)
        ex.add_done_callback(self._close_handler)


class Server:

    def __init__(self, loop, ip, port, **kwargs):
        self._loop = loop
        self.server_ip = ip
        self.server_port = int(port)
        self.app = None
        self.session_factory = kwargs.get("session_factory", Session)
        self.sessions = []
        self._session_connected_cb = kwargs.get("session_connected_cb")
        self._session_destroy_cb = kwargs.get("session_destroy_cb")
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
            session = self.session_factory(self._loop,
                              reader=reader,
                              writer=writer,
                              protocol=protocol,
                              destroy_session=self.destroy_session,
                              event_handler_log=self._event_handler_log)
            self.sessions.append(session)
            await session.start(session_connected_cb=self._session_connected_cb)
        except Exception as error:
            aioesl_log.exception(error)
            self.destroy_session(session)

    def destroy_session(self, session):
        if session in self.sessions:
            self.sessions.remove(session)

        if self._session_destroy_cb is not None:
            cb = self._session_destroy_cb(self)
            if asyncio.iscoroutine(cb):
                asyncio.ensure_future(cb)


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


