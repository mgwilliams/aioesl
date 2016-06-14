import asyncio
from .streams import open_connection
from .protocol import ESLProtocol
from .parser import EventParser
from .log import aioesl_log


class ESLConnectionBase:

    def __init__(self, loop, host, port, **kwargs):
        self.host = host
        self.port = port
        assert isinstance(self.host, str), "host mast be str type"
        assert isinstance(self.port, int), "port mast be int type"
        self._loop = loop
        self._reader = kwargs.get("reader")
        self._writer = kwargs.get("writer")
        self._connect_waiter = asyncio.Future()
        self._protocol = ESLProtocol(password=kwargs.get("password"),
                                     open_handler=self.open_handler, close_handler=self.close_handler,
                                     set_connect_waiter=self.set_connect_waiter)
        self._parser = EventParser(protocol=self._protocol)
        self._data_reader = None

        self._valid_commands = ["api", "exit"]

    @property
    def peer(self):
        return "%s:%s" % (self.host, self.port)

    def ready(self):
        return self._connect_waiter

    def set_connect_waiter(self, res):
        self._connect_waiter.set_result(res)

    def set_handler(self, event, handler):
        assert isinstance(event, str), "event mast be str type."
        self._protocol.event_handlers[event] = handler

    def pop_handler(self, event):
        assert isinstance(event, str), "event mast be str type."
        self._protocol.event_handlers.pop(event)

    def check_cmd(self, cmd):
        if cmd in self._valid_commands:
            return True
        return False

    def get_cmd(self, attr):
        if attr not in self._valid_commands or not hasattr(self._protocol, attr):
            raise AttributeError(attr)
        return getattr(self._protocol, attr)

    async def close_handler(self, ev):
        self._reader.feed_eof()
        self._writer.close()
        self._writer = None
        self._reader = None
        self._data_reader.cancel()
        self._data_reader = None
        self._parser.set_reader(self._data_reader)
        self._protocol.reset()
        aioesl_log.warning("Connection %s closed" % self.peer)

    async def open_handler(self, ev):
        pass


class ESLConnectionOut(ESLConnectionBase):

    def __init__(self, loop, host, port, **kwargs):
        super().__init__(loop, host, port, **kwargs)
        self.password = kwargs.get("password")
        self._reconnect = kwargs.get("reconnect")
        self._retries = kwargs.get("retries")
        self._retry_sleep = kwargs.get("retry_sleep")

        assert isinstance(self._reconnect, bool), "retries mast be bool type"
        assert isinstance(self._retries, int), "retries mast be int type"
        assert isinstance(self._retry_sleep, int), "retry_sleep mast be int type"

        self._cur_retry = 1
        self._closing = False

    @property
    def peer(self):
        return "%s:%s" % (self.host, self.port)

    async def open_connection(self):

        if self._reader is not None:
            raise "Reader is started!"
        try:
            aioesl_log.error("Connecting to %s. %s retry." % (self.peer, self._cur_retry))
            self._reader, self._writer = await open_connection(
                self.host, self.port, loop=self._loop)

            aioesl_log.error("Connected to %s." % self.peer)
            self._parser.set_reader(self._reader)
            self._protocol.set_writer(self._writer)
            self._data_reader = asyncio.ensure_future(self._parser.read_from_connection())
            if self.password is None:
                self.set_connect_waiter(True)

        except OSError:
            aioesl_log.error("Connect call failed %s" % self.peer)
            asyncio.ensure_future(self.reconnect())

    async def open_handler(self, ev):
        if self._connect_waiter.done():
            if self._connect_waiter.result():
                self._cur_retry = 1
            else:
                pass
                # print()

    async def close_handler(self, ev):
        await super().close_handler(ev)
        if not self._closing and not self._protocol._closing:
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
                await self.open_connection()
            else:
                aioesl_log.error("Max retry. Stop connection.")


class ESLConnectionIn(ESLConnectionBase):

    def __init__(self, loop, host, port, **kwargs):
        super().__init__(loop, host, port, **kwargs)
        self._parser.set_reader(self._reader)
        self._protocol.set_writer(self._writer)
        self._data_reader = asyncio.ensure_future(self._parser.read_from_connection())

