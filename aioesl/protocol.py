import os
import asyncio
import time
import json

from collections import deque
from .log import aioesl_log, LogBase

LINE_DELIMITER = "\n"
CMD_DELIMITER = "\n\n"


class ESLCommands(LogBase):

    def __init__(self, loop, **kwargs):
        super().__init__(loop, **kwargs)
        self._writer = kwargs.get("writer")
        self._ev_queue = deque()
        self.password = kwargs.get("password")
        self.event_handlers = {}
        self.event_handler_log = kwargs.get("event_handler_log", False)
        self._closing = False
        self._close = False
        self.uuid = None

        self._timeout = 300 # Ожидаем ответа от клиента/сервера 5 минут. Потом убиваем соединение.

    def set_handler(self, event, handler):
        assert isinstance(event, str), "event mast be str type."
        event = str(event.split(" ")[0]).upper()
        self.event_handlers[event] = handler

    def pop_handler(self, event):
        assert isinstance(event, str), "event mast be str type."
        event = event.split(" ")[0]
        assert event in self.event_handlers.keys(), "Event handler not found."
        self.event_handlers.pop(event)

    async def _open_handler(self, **kwargs):
        pass

    async def _close_handler(self, **kwargs):
        pass

    @property
    def peer(self):
        pass

    def reset(self):
        self._ev_queue = deque()

    @property
    def closing(self):
        return self._closing

    @property
    def closed(self):
        return True if self._writer is None else False

    def set_writer(self, writer):
        self._writer = writer

    # ======= SEND COMMAND TO ESL

    async def _check_timeout(self, f):
        await asyncio.sleep(self._timeout)
        if f.done() or self.closing:
            return
        else:
            try:
                if len(self._ev_queue) > 0:
                    self._ev_queue.popleft()
            except:
                # self.lw()
                self.log_exc("_check_timeout Очередь пуста. F = %s" % str(f))

            f.set_result({'Content-Type': 'Error/response', 'ErrorResponse': "TimeOut"})
            res = self._close_handler(ev={})
            if asyncio.coroutines.iscoroutine(res):
                await res

    async def _writeln(self, ln=[]):

        try:
            if self._writer is None:
                await self._close_handler(ev={})
                return
            ln.append(CMD_DELIMITER)
            out = b"".join([s.encode() for s in ln])
            # self.li("-----------\n%s----------" % out.decode())
            try:
                # self.ld(out)
                self._write(out)
                await self._writer.drain()
            except:
                aioesl_log.exception("_writeln  1")
                await self._close_handler(ev={})
        except:
            aioesl_log.exception("_writeln  2")
            await self._close_handler(ev={})

    def _write(self, data):
        # self.li(data)
        self._writer.write(data)

    def _protocol_send(self, name, args=""):
            if self._writer is not None:
                future = asyncio.Future()
                time_future = asyncio.ensure_future(self._check_timeout(future))
                cmd = "%s %s" % (name, args)
                asyncio.ensure_future(self._writeln(ln=[cmd]))
                self._ev_queue.append((name, future, time_future))
                return future
            else:
                return self.err_response("ESL not connected to %s cmd %s %s" % (self.peer, name, args))

    def _protocol_send_msg(self, name, args=None, uuid=None, lock=False):
        if self._writer is not None:
            uuid = uuid or self.uuid or ""
            future = asyncio.Future()
            time_future = asyncio.ensure_future(self._check_timeout(future))
            cmd = ["SendMsg %s" % uuid, LINE_DELIMITER,
                   "call-command: execute", LINE_DELIMITER,
                   "execute-app-name: %s" % name,
                   ]
            if args:
                cmd.extend([LINE_DELIMITER, "execute-app-arg: %s" % args])
            if lock:
                cmd.extend([LINE_DELIMITER, "event-lock: true"])

            # self.ld(cmd)
            asyncio.ensure_future(self._writeln(ln=cmd))
            self._ev_queue.append((name, future, time_future))
            return future
        else:
            return self.err_response("ESL not status to %s cmd %s %s" % (self.peer, name, args))

    def _protocol_send_raw(self, name, headers="", body=""):
        if self._writer is not None:
            future = asyncio.Future()
            time_future = asyncio.ensure_future(self._check_timeout(future))
            headers = "%s %s" % (name, headers)

            if body != "":
                headers += LINE_DELIMITER
                headers += "Content-Length: %s" % len(body.encode())
                headers += CMD_DELIMITER
                body += LINE_DELIMITER

            ev = (headers + body + CMD_DELIMITER)  # ev is encoded
            # aioesl_log.debug("======\n%s========" % ev)

            self._write(ev.encode())
            self._ev_queue.append((name, future, time_future))

            return future
        else:
            return self.err_response("ESL not status to %s cmd %s %s" % (self.ip, name, headers))

    # CONTENT TYPE PROCESSING

    def unknown_content_type(self, ct, ev):
        self.le("Unknown context type %s" % ct)

    def err_response(self, text):
        aioesl_log.error(text)
        future = asyncio.Future()
        future.set_result({'Content-Type': 'Error/response', 'ErrorResponse': text})
        return future

    def dispatch_event(self, ev):
        # self.ld(ev)
        ct = ev.get("Content-Type", None)
        if ct is None:
            return self.unknown_content_type(ct, ev)

        method_name = "_%s" % ct.lower().replace("/", "_").replace("-", "_")
        method = getattr(self, method_name, None)
        if callable(method):
            try:
                asyncio.ensure_future(method(ev))
            except:
                aioesl_log.exception("dispatch_event")
        else:
            return self.unknown_content_type(method_name, ev)

    async def _text_rude_rejection(self, ev):
        if ev.get("DataResponse") == "Access Denied, go away.\n":
            aioesl_log.warn("[ %s ] %s" % (self.peer, ev.get("DataResponse")))
            self._closing = True
            await self._close_handler(ev=ev, status="AuthFailed")
        else:
            aioesl_log.info(str(ev))

    async def _auth_request(self, ev):
        if self.password is None:
            self.le("Server auth required, but password not set.")
            return
        res = await self.auth()
        if isinstance(res, dict) and res.get("Reply-Text") == "+OK accepted":
            await self._open_handler(auth=True)
        else:
            self.le("Auth failed.")
            await self._open_handler(auth=False)

    async def _api_response(self, ev):
        cmd, future, time_future = self._ev_queue.popleft()
        time_future.cancel()
        if cmd == "api":
            future.set_result(ev)
        else:
            aioesl_log.error("apiResponse on '%s': out of sync?" % cmd)

    async def _command_reply(self, ev):
        try:
            cmd, future, time_future = self._ev_queue.popleft()
            ev["app-name"] = cmd
            time_future.cancel()
            # if ev.get('Reply-Text') == "+OK":
            #     pass

            if ev.get("Reply-Text").startswith("+OK"):
                future.set_result(ev)

            elif ev.get("Reply-Text").startswith("-ERR"):
                future.set_result(ev)

            elif cmd == "auth":
                aioesl_log.error("password error")
            else:
                pass
        except:
            aioesl_log.exception(ev)

    async def _text_event_plain(self, ev):
        name = ev.get("Event-Name")
        if name is not None:
            if name in self.event_handlers.keys():
                method = self.event_handlers[name]
            elif "ALL" in self.event_handlers.keys():
                method = self.event_handlers["ALL"]
            else:
                if self.event_handler_log:
                    aioesl_log.error("Handler for %s not set" % name)
                return
            try:
                m = method(self, ev)
                if asyncio.iscoroutine(m):
                    await m
            except Exception as error:
                aioesl_log.exception(error)
        else:
            aioesl_log.error("Не могу получить метод.")

    async def _text_disconnect_notice(self, ev):
        # self.li("_text_disconnect_notice %s" % ev)
        self.log_debug(ev.get("DataResponse", "Error!!!").replace("\n", " "))
        self._closing = True
        res = self._close_handler(ev={})
        if asyncio.coroutines.iscoroutine(res):
            await res
        # aioesl_log.warning("нужно повесить хендлер для выключения")

    async def _rude_rejection(self, ev):
        aioesl_log.warning(ev.get("DataResponse"))

    # EVENT SOCKET COMMANDS

    def auth(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#auth
        This method is allowed only for Inbound connections."""
        return self._protocol_send("auth", self.password)

    def eventplain(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#event"
        return self._protocol_send('event plain', args)

    def event(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#event"
        return self._protocol_send('event', args)

    def noevents(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#noevents"
        return self._protocol_send('noevents', args)

    def connect(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Outbound#Using_Netcat"
        return self._protocol_send("connect")

    def api(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#api"
        return self._protocol_send("api", args)

    def sendevent(self, name, args=None, body=None):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#sendevent"
        if args is None:
            args = dict()

        parsed_args = [name]
        for k, v in args.items():
            parsed_args.append('%s: %s' % (k, v))

        if body is None:
            parsed_body = None
        else:
            parsed_body = []
            if isinstance(body, dict):
                for k, v in body.items():
                    parsed_body.append('%s: %s' % (k, v))
            else:
                parsed_body = "%s"

        return self._protocol_send_raw(name="sendevent",
                                       headers='\n'.join(parsed_args),
                                       body='\n'.join(parsed_body))

    def bgapi(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#bgapi"
        return self._protocol_send("bgapi", args)

    def exit(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#exit"
        self._closing = True
        return self._protocol_send("exit")

    def linger(self, args=None):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#event"
        return self._protocol_send("linger", args)

    def filter(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#filter

        The user might pass any number of values to filter an event for. But, from the point
        filter() is used, just the filtered events will come to the app - this is where this
        function differs from event().

        >>> filter('Event-Name MYEVENT')
        >>> filter('Unique-ID 4f37c5eb-1937-45c6-b808-6fba2ffadb63')
        """
        return self._protocol_send('filter', args)

    def filter_delete(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#filter_delete

        >>> filter_delete('Event-Name MYEVENT')
        """
        return self._protocol_send('filter delete', args)

    def verbose_events(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_verbose_events

        >>> verbose_events()
        """
        return self._protocol_send_msg('verbose_events', lock=True)

    def myevents(self, uuid=None, msg_type="plain"):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#event"
        uuid = uuid or self.uuid or ""
        return self._protocol_send("myevents", "%s %s" % (msg_type, uuid))

    def answer(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Outbound#Using_Netcat"
        return self._protocol_send_msg("answer", lock=True)

    def pre_answer(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Outbound#Using_Netcat"
        return self._protocol_send_msg("pre_answer", lock=True)

    def bridge(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Outbound

        >>> bridge("{ignore_early_media=true}sofia/gateway/myGW/177808")
        """
        return self._protocol_send_msg("bridge", args, lock=True)

    def hangup(self, reason=""):
        """Hangup may be used by both Inbound and Outbound connections.

        When used by Inbound connections, you may add the extra `reason`
        argument. Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#hangup
        for details.

        When used by Outbound connections, the `reason` argument must be ignored.

        Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Outbound for
        details.
        """
        return self._protocol_send_msg("hangup", reason, lock=True)

    def sched_api(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Mod_commands#sched_api"
        return self._protocol_send_msg("sched_api", args, lock=True)

    def ring_ready(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_ring_ready"
        return self._protocol_send_msg("ring_ready")

    def record_session(self, filename):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_record_session

        >>> record_session("/tmp/dump.gsm")
        """
        return self._protocol_send_msg("record_session", filename, lock=True)

    def read(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_read

        >>> read("0 10 $${base_dir}/sounds/en/us/callie/conference/8000/conf-pin.wav res 10000 #")
        """
        # asyncio.ensure_future(self.set("read_terminator_used=''", lock=False))
        return self._protocol_send_msg("read", args, lock=False)

    def bind_meta_app(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_bind_meta_app

        >>> bind_meta_app("2 ab s record_session::/tmp/dump.gsm")
        """
        return self._protocol_send_msg("bind_meta_app", args, lock=True)

    def bind_digit_action(self, args):
        """Please refer to https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+bind_digit_action

        >>> bind_digit_action("my_digits,11,exec:execute_extension,att_xfer XML default,both,self")
        """
        return self._protocol_send_msg("bind_digit_action", args, lock=True)

    def wait_for_silence(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_wait_for_silence

        >>> wait_for_silence("200 15 10 5000")
        """
        return self._protocol_send_msg("wait_for_silence", args, lock=True)

    def sleep(self, milliseconds):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_sleep

        >>> sleep(5000)
        >>> sleep("5000")
        """
        return self._protocol_send_msg("sleep", milliseconds, lock=True)

    def vmd(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_vmd

        >>> vmd("start")
        >>> vmd("stop")
        """
        return self._protocol_send_msg("vmd", args, lock=True)

    def set(self, args, lock=True):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_set

        >>> set("ringback=${us-ring}")
        """
        return self._protocol_send_msg("set", args, lock=lock)

    def set_global(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_set_global

        >>> set_global("global_var=value")
        """
        return self._protocol_send_msg("set_global", args, lock=True)

    def unset(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_unset

        >>> unset("ringback")
        """
        return self._protocol_send_msg("unset", args, lock=True)

    def start_dtmf(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_start_dtmf

        >>> start_dtmf()
        """
        return self._protocol_send_msg("start_dtmf", lock=True)

    def stop_dtmf(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_stop_dtmf

        >>> stop_dtmf()
        """
        return self._protocol_send_msg("stop_dtmf", lock=True)

    def start_dtmf_generate(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_start_dtmf_generate

        >>> start_dtmf_generate()
        """
        return self._protocol_send_msg("start_dtmf_generate", "true", lock=True)

    def stop_dtmf_generate(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_stop_dtmf_generate

        >>> stop_dtmf_generate()
        """
        return self._protocol_send_msg("stop_dtmf_generate", lock=True)

    def queue_dtmf(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_queue_dtmf

        Enqueue each received dtmf, that'll be sent once the call is bridged.

        >>> queue_dtmf("0123456789")
        """
        return self._protocol_send_msg("queue_dtmf", args, lock=True)

    def flush_dtmf(self):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_flush_dtmf

        >>> flush_dtmf()
        """
        return self._protocol_send_msg("flush_dtmf", lock=True)

    def play_fsv(self, filename):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_fsv

        >>> play_fsv("/tmp/video.fsv")
        """
        return self._protocol_send_msg("play_fsv", filename, lock=True)

    def record_fsv(self, filename):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_fsv

        >>> record_fsv("/tmp/video.fsv")
        """
        return self._protocol_send_msg("record_fsv", filename, lock=True)

    def record(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_record

        >>> record("/tmp/tmp.wav 20 200")
        """
        return self._protocol_send_msg("record", args, lock=True)

    def playback(self, filename, uuid="", terminators=None, lock=True):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_playback

        The optional argument `terminators` may contain a string with
        the characters that will terminate the playback.

        >>> playback("/tmp/dump.gsm", terminators="#8")

        In this case, the audio playback is automatically terminated
        by pressing either '#' or '8'.
        """
        asyncio.ensure_future(self.set("playback_terminators=%s" % terminators or "none"))
        return self._protocol_send_msg("playback", filename, uuid=uuid, lock=lock)

    def transfer(self, args):
        """Please refer to https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+transfer

        >>> transfer("3222 XML default")
        """
        return self._protocol_send_msg("transfer", args, lock=True)

    def execute_extension(self, args):
        """Please refer to https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+execute_extension
        >>> execute_extension("3222 XML default")
        """
        return self._protocol_send_msg("execute_extension", args, lock=True)

    def conference(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_conference#API_Reference

        >>> conference("myconf")
        """
        return self._protocol_send_msg("conference", args, lock=True)

    def att_xfer(self, url):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_att_xfer

        >>> att_xfer("user/1001")
        """
        return self._protocol_send_msg("att_xfer", url, lock=True)

    def send_break(self):
        return self._protocol_send_msg("break", lock=True)

    def endless_playback(self, filename):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_endless_playback

        >>> endless_playback("/tmp/dump.gsm")
        """
        return self._protocol_send_msg("endless_playback", filename, lock=True)

    def execute(self, command, args, uuid=""):
        """Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Library#execute

        >>> execute('voicemail', 'default $${domain} 1000')
        """
        return self._protocol_send_msg(command, args, uuid=uuid, lock=True)

    def play_and_get_digits(self, args):
        """Please refer to https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+play+and+get+digits

        >>> play_and_get_digits("2 5 3 7000 # $${base_dir}/sounds/en/us/callie/conference/8000/conf-pin.wav /invalid.wav foobar \d+")
        """
        return self._protocol_send_msg("play_and_get_digits", args, lock=True)

    def displace_session(self, params):
        return self._protocol_send_msg("displace_session", params, lock=True)


    # shortcats

    def json(self, cmd, format=None, data=None):
        """
        Please refer to  https://freeswitch.org/confluence/display/FREESWITCH/mod_callcenter
        json {"command": "callcenter_config", "format": "pretty", "data": {"arguments":"agent list"}}
        :return:
        """
        _ = '"command": "%s"' % cmd
        if format is not None:
            _ += ', "format": "%s"' % format
        if data is not None:
            _ += ', "data": %s' % json.dumps(data)

        return self.api('json {%s}' % _)

    def callcenter(self, args, lock=True):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_set

        >>> callcenter("queue_name")
        """
        return self._protocol_send_msg("callcenter", args, lock=lock)
