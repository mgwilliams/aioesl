import asyncio
from .log import aioesl_log


class Protocol(asyncio.Protocol):

    def __init__(self, loop=None, client_connected_cb=None, client_disconnected_cb=None):
        self._loop = loop
        self._stream_reader = asyncio.StreamReader(loop=self._loop)
        self._stream_writer = None
        self._client_connected_cb = client_connected_cb
        self._client_disconnected_cb = client_disconnected_cb

    def connection_made(self, transport):
        print("Protocol connection_made")
        self._stream_reader.set_transport(transport)
        if self._client_connected_cb is not None:
            self._stream_writer = asyncio.StreamWriter(transport, self,
                                               self._stream_reader,
                                               self._loop)
            res = self._client_connected_cb()
            if asyncio.coroutines.iscoroutine(res):
                self._loop.create_task(res)

    def connection_lost(self, exc):
        print("Protocol connection_lost")
        # print(self._client_disconnected_cb)
        # res = self._client_disconnect_cb()
        # if asyncio.coroutines.iscoroutine(res):
        #     self._loop.create_task(res)
        #
        # if exc is None:
        #     self._stream_reader.feed_eof()
        # else:
        #     self._stream_reader.set_exception(exc)

    def data_received(self, data):
        # self._stream_reader.feed_data(data)
        pass

    def eof_received(self):
        self._stream_reader.feed_eof()
        # return True
        pass

class Connection:

    def __init__(self, **kwargs):
        self._loop = kwargs.get("loop")
        self._protocol = Protocol(loop=self._loop,
                                  client_connected_cb=self._client_connected_cb,
                                  client_disconnected_cb=self._client_disconnected_cb
                                  )
        self._cbs = {}
        self._set_cbs(kwargs)
        self._commands = None

    @property
    def protocol(self):
        return self._protocol

    def _set_cbs(self, kw):
        self._cbs["client_connected"] = kw.get("client_connected_cb")
        self._cbs["client_disconnected"] = kw.get("client_disconnect_cb")

    def _client_connected_cb(self):
        print("Connection _client_connected_cb")
        if self._cbs.get("client_connected") is not None:
            self._cbs["client_connected"]()

    def _client_disconnected_cb(self, exc=None):
        print("Connection _client_disconnected_cb")
        if self._cbs.get("client_disconnected") is not None:
            self._cbs["client_disconnected"]()


class Server:

    def __init__(self, ip, port, loop, handler=None):
        self._loop = loop
        self._server_ip = ip
        self._server_port = port
        self._server = None
        self._connections = []
        self._session_handler = handler

    def _remove_connection(self, connect):
        aioesl_log.info("client done: %s" % connect)
        if connect in self._connections:
            self._connections.remove(connect)

    @property
    def peer(self):
        return "%s:%s" % (self._server_ip, self._server_port)

    async def start(self):
        def factory():
            connect = Connection(loop=self._loop, client_disconnect_cb=self._remove_connection)
            self._connections.append(connect)
            return connect.protocol

        self._server = await self._loop.create_server(factory,
                                                      self._server_ip,
                                                      self._server_port)
        aioesl_log.info("Server started %s" % self.peer)

    def stop(self):
        """
        Stops the TCP server, i.e. closes the listening socket(s).
        This method runs the loop until the server sockets are closed.
        """
        if self.server is not None:
            self.server.close()
            self._loop.run_until_complete(self.server.wait_closed())
            self.server = None
