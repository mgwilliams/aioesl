import asyncio
import uuid
import errno
from socket import error as SocketError
from urllib.parse import unquote
from .log import aioesl_log
from libs.aioesl.aioesl.common import SESSION_STATUS_CLOSING, SESSION_STATUS_CLOSED

import traceback
import sys

from concurrent.futures._base import CancelledError


class EventParser:

    def __init__(self, **kwargs):
        self.loop = kwargs.get("loop")
        self.reader = kwargs.get("reader")
        self.last_line = [1, 2]
        self.ev = {}
        self.session = kwargs.get("session")
        self.peername = None
        self.readline_process = None

    def set_reader(self, reader):
        self.reader = reader

    async def read_from_connection(self):
        if self.reader is not None:
            self.peername = self.reader._transport.get_extra_info('peername')

        while self.reader is not None and not self.reader.at_eof():
            try:
                line = await self.reader.readline()
                if self.session.status in [SESSION_STATUS_CLOSED, SESSION_STATUS_CLOSING]:
                    # self.session.li(">>>>>>>>>>>>>>>>>>>")
                    break

                if line == b'':
                    await self.session.close_handler(ev={})
                    break

                self.last_line = [self.last_line[-1], line]
                if line == b"\n" and self.ev != {}:
                    self.dispatch_event()
                else:
                    ev_attr = self.parse_ev_attr(line.decode())
                    if "Content-Length" in ev_attr.keys():
                        raw_lenght = int(ev_attr["Content-Length"])
                        content_type = await self.reader.readline()
                        self.ev.update(self.parse_ev_attr(content_type.decode()))
                        self.ev.update({"Content-Length": raw_lenght})

                        data = await self.reader.readexactly(raw_lenght)
                        data = data.decode()
                        if self.ev.get("Content-Type") == "text/event-plain":
                            self.get_plain_body(data)
                        else:
                            if data.startswith("Event-Name"):
                                self.get_plain_body(data)
                            elif data.startswith("-E"):
                                self.ev.update({"ErrorResponse": data})
                            else:
                                self.ev.update({"DataResponse": data})

                        self.dispatch_event()
                    else:
                        self.ev.update(ev_attr)

            except SocketError as e:
                aioesl_log.exception("read_from_connection")
                if e.errno != errno.ECONNRESET:
                    self.session.lw("read_from_connection SocketError")
                    if not self.reader.at_eof():
                        self.reader.feed_eof()

                else:
                    self.session.lw("SocketError Разрыв соединения")
                    if self.reader is not None and not self.reader.at_eof():
                        self.reader.feed_eof()

            except CancelledError:
                if self.session.status not in [SESSION_STATUS_CLOSING, SESSION_STATUS_CLOSED]:
                    self.session.lw("Close connection %s by Cancelled!" % str(self.peername))
                    if self.reader is not None and not self.reader.at_eof():
                        self.reader.feed_eof()

            except:
                self.session.log_exc("read_from_connection")
                if self.reader is not None and not self.reader.at_eof():
                    self.reader.feed_eof()

    def dispatch_event(self):
        ev = self.ev.copy()
        self.ev = {}
        self.session.dispatch_event(ev)

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

    def get_plain_body(self, data):
        out = {}
        for line in data.split("\n"):
            out.update(self.parse_ev_attr(line))

        if out != {}:
            self.ev.update(out)
