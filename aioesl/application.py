import asyncio
from .streams import start_server, open_connection
# from .connection import SessionBase
from .session import Session
from libs.aioesl.aioesl.common import *
from .log import aioesl_log

list_outbounds = []
list_inbound = []


class OutboundSession(Session):

    def __init__(self, loop, **kwargs):
        super().__init__(loop, **kwargs)
        self.direction = SESSION_DIRECTION_OUTBOUND
        self.reconnect = kwargs.get("reconnect", False)
        self.retries = kwargs.get("retries", 5)
        self.retry_sleep = kwargs.get("retry_sleep", 30)

        assert isinstance(self.host, str), "host mast be str type"
        assert isinstance(self.port, int), "port mast be int type"
        assert isinstance(self.reconnect, bool), "retries mast be bool type"
        assert isinstance(self.retries, int), "retries mast be int type"
        assert isinstance(self.retry_sleep, int), "retry_sleep mast be int type"

        self.cur_retry = 0
        self.cb_on_connected = kwargs.get("cb_on_connected")
        self.cb_on_disconnect = kwargs.get("cb_on_disconnect")

    def __repr__(self):
        return "<%s at 0x%x>" % ("OutboundSession", id(self))

    async def run_cb_on_disconnect(self):
        self.ld("Запускаю коллбек дисконнекта")
        cb = self.cb_on_disconnect()
        if asyncio.iscoroutine(cb):
            await cb

    async def open_connection(self):
        self.status = SESSION_STATUS_NEW
        if self.reader is not None:
            self.lw("Повтоная попытка установки исходящего соединения")
        try:
            self.ld4("Новое исходящее подключение %s. Попытка %s" % (str(self), self.cur_retry))
            self.parser.reader, self.writer = await open_connection(self.host, self.port, loop=self.loop)
            if self.data_reader is None:
                self.data_reader = asyncio.ensure_future(self.parser.read_from_connection())

            if self not in list_outbounds:
                list_outbounds.append(self)
                self.ld1("Добавил в список подключений %s" % str(self))
                self.ld2("Всего исходящих подключений: %s" % len(list_outbounds))
                self.ld2("Текущие подключения \n %s" % list_outbounds)

            if self.password is None:
                self.ready.set_result(True)

            await self.ready

            self.ld2("Авторизация пройдена")
            if self.cb_on_connected is not None:
                await self.cb_on_connected()

        except OSError as err:
            self.le("Ошибка установки подлючения OSError %s." % err.errno)
            self.close()
        except:
            self.log_exc("open_connection")
            self.close()

    async def application_close_handler(self, **kwargs):
        self.data_reader = None

        if self.reconnect and self.status != SESSION_STATUS_RECONNETING:
            self.status = SESSION_STATUS_RECONNETING
            if self.retries == 0 or self.retries < self.cur_retry:
                self.lw("Переподключаем ESL соединение")
                await self.reconnection()
                return
            else:
                if len(list_outbounds) > 100:
                    self.lw("Закрываю исходящее соединение.")
                self.ld3("Закрываю исходящее соединение.")

        self.status = SESSION_STATUS_CLOSED
        if self in list_outbounds:
            list_outbounds.remove(self)
            self.ld3("Удаляю исходящее подключение %s" % str(self))

        if self.cb_on_disconnect is not None:
            asyncio.ensure_future(self.run_cb_on_disconnect())

    async def reconnection(self):
        self.cur_retry += 1
        self.ready = asyncio.Future()
        self.li("Следующая попытка подключения через %s секунд" % self.retry_sleep)
        if self.cb_on_disconnect is not None:
            asyncio.ensure_future(self.run_cb_on_disconnect())
        await asyncio.sleep(self.retry_sleep)
        await self.open_connection()

    # def shutdown(self):
    #
    #     def ok(_):
    #         self.ld3("Подключение выключено.")
    #
    #     self.ld("shutdown RUN!")
    #     self.closing = True
    #     ex = asyncio.ensure_future(self.exit())
    #     cp = asyncio.ensure_future(self.close_handler())
    #     cp.add_done_callback(ok)
    #     ex.add_done_callback(self.close_handler)


class Server:

    def __init__(self, loop, ip, port, **kwargs):
        self._loop = loop
        self.server_ip = ip
        self.server_port = int(port)
        self.app = None
        self.session_factory = kwargs.get("session_factory", InboundSession)
        self.sessions = list_inbound
        self.session_connected_cb = kwargs.get("session_connected_cb")
        self.session_destroy_cb = kwargs.get("session_destroy_cb")
        self.event_handler_log = kwargs.get("event_handler_log", False)

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
        host, port = writer.transport.get_extra_info('peername')
        session = self.session_factory(self._loop,
                                       reader=reader,
                                       writer=writer,
                                       protocol=protocol,
                                       destroy_session=self.destroy_session,
                                       event_handler_log=self.event_handler_log,
                                       direction=SESSION_DIRECTION_INBOUND,
                                       host=host,
                                       port=port)
        self.sessions.append(session)
        try:
            session.ld3("Входящее подключение")
            await session.start(session_connected_cb=self.session_connected_cb)
        except GeneratorExit:
            aioesl_log.error("Завершаю работу подключения c ошибкой GeneratorExit")
        except Exception as error:
            aioesl_log.exception(error)
        finally:
            session.ld3("Текущий статус активна %s" % session.connected)

            if session.connected:
                await session.exit()

            session.close()
            await self.destroy_session(session)

    async def destroy_session(self, session):
        if session in self.sessions:
            session = self.sessions.remove(session)
            if self.session_destroy_cb is not None:
                cb = self.session_destroy_cb(session)
                if asyncio.iscoroutine(cb):
                    asyncio.ensure_future(cb)
            if session is not None:
                session.ld3("Завершена сервераная сессия")
                del session


class InboundSession(Session):

    def __init__(self, loop, **kwargs):
        super().__init__(loop, **kwargs)
        self.destroy_session = kwargs.get("destroy_session")

    def __repr__(self):
        return "<%s at 0x%x>" % ("InboundSession", id(self))

    async def start(self, session_connected_cb=None):
        self.data_reader = asyncio.ensure_future(self.parser.read_from_connection())
        self.ld3("Новое входящее подключение %s." % str(self))
        res = await self.connect()
        self.ld3("Текущее состояние подключения: %s" % self.status)
        if session_connected_cb is not None:
            cb = session_connected_cb(self, res)
            if asyncio.iscoroutine(cb):
                await cb

