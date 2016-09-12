import asyncio
from .protocol import ESLCommands
from .parser import EventParser
from .log import aioesl_log, LogBase


class SessionBase(ESLCommands):

    def __init__(self, loop, **kwargs):
        self._loop = loop
        self._host, self._port = kwargs.get("host"), kwargs.get("port")
        self._reader = kwargs.get("reader")
        self._data_reader = None
        self._connect_waiter = asyncio.Future()
        self._parser = EventParser(reader=self._reader, dispatch_event_cb=self.dispatch_event)
        self._closing = False
        super().__init__(loop, **kwargs)
        if self._writer is not None:
            self._host, self._port = self._writer.transport.get_extra_info('peername')

    @property
    def peer(self):
        return "%s:%s" % (self._host, self._port)

    def ready(self):
        return self._connect_waiter

    def set_connect_waiter(self, res):
        self._connect_waiter.set_result(res)

    #@todo Проверить, зачем этот тут нужно!
    async def _open_handler(self, **kwargs):
        if kwargs.get("auth"):
            self._connect_waiter.set_result(True)

    async def _close_handler(self, ev):
        self._reader.feed_eof()
        self._writer.close()
        self._writer = None
        self._reader = None
        # self._data_reader.cancel()
        self._data_reader = None
        self._parser.set_reader(self._reader)
        self.reset()
        self.li("Connection closed.")
