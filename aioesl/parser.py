import asyncio
import uuid
import errno
from socket import error as SocketError
from urllib.parse import unquote
from .log import aioesl_log

import traceback
import sys

from concurrent.futures._base import CancelledError


class EventParser:

    def __init__(self, **kwargs):
        self._connection_uuid = str(uuid.uuid4())
        self._reader = kwargs.get("reader")
        self.last_line = [1, 2]
        self._ev = {}
        self.dispatch_event_cb = kwargs.get("dispatch_event_cb")
        self.make_close = kwargs.get("make_close")
        self.closing_flag = kwargs.get("closing_flag")
        self.peername = None

    def set_reader(self, reader):
        self._reader = reader

    async def read_from_connection(self):
        if self._reader is not None:
            self.peername = self._reader._transport.get_extra_info('peername')

        while self._reader is not None and not self._reader.at_eof():
            try:
                line = await self._reader.readline()
                # aioesl_log.debug("%s %s %s" % (self._connection_uuid, self.peername, line))

                if line == b'' and not self.closing_flag():
                    aioesl_log.error("NULLDATA read_from_connection %s" % self.closing_flag)
                    await self.make_close(ev={})
                    break

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
                aioesl_log.exception("read_from_connection")
                if e.errno != errno.ECONNRESET:
                    aioesl_log.error("read_from_connection SocketError")
                    self._reader.feed_eof()
                else:
                    aioesl_log.error("SocketError Разрыв соединения")
                    self._reader.feed_eof()
                # res = self._reader.feed_eof()
                # if asyncio.coroutines.iscoroutine(res):
                #     await res
            except CancelledError:
                aioesl_log.exception("read_from_connection")
                aioesl_log.debug("Close connection %s!" % str(self.peername))
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
