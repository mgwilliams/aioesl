import asyncio
import errno
from socket import error as SocketError
from urllib.parse import unquote
from .log import aioesl_log

import traceback
import sys


from concurrent.futures._base import CancelledError


class EventParser:

    def __init__(self, **kwargs):
        self._reader = kwargs.get("reader")
        self.last_line = [1, 2]
        self._ev = {}
        self.dispatch_event_cb = kwargs.get("dispatch_event_cb")

    def set_reader(self, reader):
        self._reader = reader

    async def read_from_connection(self):
        while self._reader is not None and not self._reader.at_eof():
            try:
                # print(self._reader._transport, "parser 22", str(self._reader.__dict__))
                line = await self._reader.readline()
                self.last_line = [self.last_line[-1], line]
                if line == b"\n" and self._ev != {}:
                    self.dispatch_event()
                else:
                    ev_attr = self.parse_ev_attr(line.decode())
                    if "Content-Length" in ev_attr.keys():
                        raw_lenght = int(ev_attr["Content-Length"])
                        content_type = await self._reader.readline()
                        self._ev.update(self.parse_ev_attr(content_type.decode()))
                        self._ev.update({"Content-Length": raw_lenght})

                        data = await self._reader.readexactly(raw_lenght)
                        data = data.decode()
                        if self._ev.get("Content-Type") == "text/event-plain":
                            self._get_plain_body(data)
                        else:
                            if data.startswith("Event-Name"):
                                self._get_plain_body(data)
                            elif data.startswith("-E"):
                                self._ev.update({"ErrorResponse": data})
                            else:
                                self._ev.update({"DataResponse": data})

                        self.dispatch_event()
                    else:
                        self._ev.update(ev_attr)

            except SocketError as e:
                if e.errno != errno.ECONNRESET:
                    aioesl_log.exception("read_from_connection SocketError")
                    self._reader.feed_eof()
                else:
                    aioesl_log.exception("SocketError Разрыв соединения")
                    self._reader.feed_eof()
                # res = self._reader.feed_eof()
                # if asyncio.coroutines.iscoroutine(res):
                #     await res
            except CancelledError:
                aioesl_log.debug("Close connection %s!" % self._reader._transport.get_extra_info('peername'))
                # self._reader._waiter.cancel()
                self._reader.feed_eof()
            except:
                aioesl_log.exception("read_from_connection")
                self._reader.feed_eof()
                # res = self._reader.feed_eof()
                # self._reader.
                # res = self._reader._close_handler(ev={})
                # if asyncio.coroutines.iscoroutine(res):
                #     await res

    def dispatch_event(self):
        ev = self._ev.copy()
        self._ev = {}
        self.dispatch_event_cb(ev)

    def parse_ev_attr(self, line):
        if line == "\n":
            return {}
        elif ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = unquote(v.strip())
            return {k: v}
        else:
            return {}

    def _get_plain_body(self, data):
        out = {}
        for line in data.split("\n"):
            out.update(self.parse_ev_attr(line))

        if out != {}:
            self._ev.update(out)
