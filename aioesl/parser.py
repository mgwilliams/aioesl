import asyncio
from urllib.parse import unquote
from .log import aioesl_log

class EventParser:
    def __init__(self, protocol):
        self._reader = None
        self.last_line = [1, 2]
        self._ev = {}
        self.protocol = protocol

    def set_reader(self, reader):
        self._reader = reader

    async def read_from_connection(self):
        while self._reader is not None:
            try:
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
            except Exception as e:
                print(e)

    def dispatch_event(self):
        ev = self._ev.copy()
        self._ev = {}
        self.protocol.process_event(ev)

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
