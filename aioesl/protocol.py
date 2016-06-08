import asyncio
from collections import deque
from .log import aioesl_log


class ESLProtocol:
    def __init__(self, password, set_connect_waiter, open_handler, close_handler):
        self._writer = None
        self._ev_queue = deque()
        self._set_connect_waiter = set_connect_waiter
        self.password = password
        self.event_handlers = {}
        self._open_handler = open_handler
        self._close_handler = close_handler

        self._closing = False
        self._close = False

    def reset(self):
        self._ev_queue = deque()

    @property
    def closing(self):
        return self._closing

    def set_writer(self, writer):
        self._writer = writer

    # ======= SEND COMMAND TO ESL

    def _write(self, s):
        if self._writer is not None:
            self._writer.write(s.encode())

    def _send(self, cmd):
        self._write(cmd + "\n\n")

    def _send_msg(self, name, arg=None, uuid="", lock=False):
        self._write("sendmsg %s\ncall-command: execute\n" % uuid)
        self._write("execute-app-name: %s\n" % name)
        if arg:
            self._write("execute-app-arg: %s\n" % arg)
        if lock is True:
            self._write("event-lock: true\n")
        self._write("\n\n")

    def _raw_send(self, stuff):
        self._write(stuff)

    def _protocol_send(self, name, args=""):
        if self._writer is not None:
            future = asyncio.Future()
            self._send("%s %s" % (name, args))
            self._ev_queue.append((name, future))
            return future
        else:
            return self.err_response("ESL not connected to %s cmd %s %s" % (self.peer, name, args))

    def _protocol_send_msg(self, name, args=None, uuid="", lock=False):
        if self._writer is not None:
            future = asyncio.Future()
            self._send_msg(name, args, uuid, lock)
            self._ev_queue.append((name, future))
            return future
        else:
            return self.err_response("ESL not status to %s cmd %s %s" % (self.ip, name, args))

    def _protocol_send_raw(self, name, args=""):
        if self._writer is not None:
            future = asyncio.Future()
            self._raw_send("%s %s" % (name, args))
            self._ev_queue.append((name, future))
            return future
        else:
            return self.err_response("ESL not status to %s cmd %s %s" % (self.ip, name, args))

    # END SEND COMMAND TO ESL

    # CONTENT TYPE PROCESSING

    def process_event(self, ev):
        ct = ev.get("Content-Type", None)
        if ct is None:
            return self.unknown_content_type(ct, ev)

        method_name = "_%s" % ct.lower().replace("/", "_").replace("-", "_")
        method = getattr(self, method_name, None)
        if callable(method):
            asyncio.ensure_future(method(ev))
        else:
            return self.unknown_content_type(ct, ev)

    async def _auth_request(self, ev):
        if self.password is None:
            aioesl_log.warning("Server auth required, but password not set.")
            return
        res = await self.auth()
        if isinstance(res, dict) and res.get("Reply-Text") == "+OK accepted":
            self._set_connect_waiter(True)
        else:
            aioesl_log.warning("Auth failed.")
            self._set_connect_waiter(False)

        await self._open_handler(ev)

    async def _api_response(self, ev):
        cmd, future = self._ev_queue.popleft()
        if cmd == "api":
            future.set_result(ev)
        else:
            aioesl_log.error("apiResponse on '%s': out of sync?" % cmd)

    async def _command_reply(self, ev):
        cmd, future = self._ev_queue.popleft()
        if ev.get("Reply-Text").startswith("+OK"):
            future.set_result(ev)

        elif ev.get("Reply-Text").startswith("-ERR"):
            future.set_result(ev)

        elif cmd == "auth":
            print("password error")
        else:
            pass

    async def _plain_event(self, ev):
        name = ev.get("Event-Name")
        if name is not None:
            evname = "on_" + name.lower().replace("_", "")
            if evname in self.handlers.keys():
                asyncio.ensure_future(self.handlers[evname](ev))
            else:
                if self.handler_log:
                    aioesl_log.error("Handler for %s not set" % evname)
        else:
            aioesl_log.error("Не могу получить метод. Не установлен Event_Name")

    async def _text_disconnect_notice(self, ev):
        aioesl_log.warning(ev.get("DataResponse", "Error!!!").replace("\n", " "))
        await self._close_handler(ev)

        # aioesl_log.warning("нужно повесить хендлер для выключения")

    async def _rude_rejection(self, ev):
        aioesl_log.warning(ev.get("DataResponse"))

    # END CONTENT TYPE PROCESSING

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
        return self._protocol_send_msg("event", args, lock=True)

    def connect(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Outbound#Using_Netcat"
        return self._protocol_send("connect")

    def api(self, args):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#api"
        return self._protocol_send("api", args)

    def sendevent(self, name, args=dict(), body=None):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#sendevent"
        parsed_args = [name]
        for k, v in args.iteritems():
            parsed_args.append('%s: %s' % (k, v))
        parsed_args.append('')
        if body:
            parsed_args.append(body)
        else:
            parsed_args.append('')
        return self._protocol_send_raw("sendevent", '\n'.join(parsed_args))

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

    def myevents(self):
        "Please refer to http://wiki.freeswitch.org/wiki/Event_Socket#event"
        return self._protocol_send("myevents")

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
        return self._protocol_send_msg("read", args, lock=True)

    def bind_meta_app(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_bind_meta_app

        >>> bind_meta_app("2 ab s record_session::/tmp/dump.gsm")
        """
        return self._protocol_send_msg("bind_meta_app", args, lock=True)

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

    def set(self, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Misc._Dialplan_Tools_set

        >>> set("ringback=${us-ring}")
        """
        return self._protocol_send_msg("set", args, lock=True)

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

    def playback(self, filename, terminators=None, lock=True):
        """Please refer to http://wiki.freeswitch.org/wiki/Mod_playback

        The optional argument `terminators` may contain a string with
        the characters that will terminate the playback.

        >>> playback("/tmp/dump.gsm", terminators="#8")

        In this case, the audio playback is automatically terminated
        by pressing either '#' or '8'.
        """
        asyncio.ensure_future(self.set("playback_terminators=%s" % terminators or "none"))
        return self._protocol_send_msg("playback", filename, lock=lock)

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

    def execute(self, command, args):
        """Please refer to http://wiki.freeswitch.org/wiki/Event_Socket_Library#execute

        >>> execute('voicemail', 'default $${domain} 1000')
        """
        return self._protocol_send_msg(command, args, lock=True)

    def play_and_get_digits(self, args):
        """Please refer to https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+play+and+get+digits

        >>> play_and_get_digits("2 5 3 7000 # $${base_dir}/sounds/en/us/callie/conference/8000/conf-pin.wav /invalid.wav foobar \d+")
        """
        return self._protocol_send_msg("play_and_get_digits", args, lock=True)

    def displace_session(self, params):
        return self._protocol_send_msg("displace_session", params, lock=True)

    # API ShortCats

    def uuid_getvar(self, uuid, varname):
        """
        Please refer to https://freeswitch.org/confluence/display/FREESWITCH/mod_commands
        :param args: [channel_uuid, var_name]
        :param lock:
        :return: Fuature
        """
        args = "%s %s %s" % ("uuid_getvar", uuid, varname)
        return self.api(args=args)

    def uuid_displace(self, uuid=None, action="start", file="$", limit="60", mux=""):
        """
        >>> uuid_displace <uuid> [start|stop] <file> [<limit>] [mux]
        :param uuid:
        :param action:
        :param file:
        :param limit:
        :param mux:
        :return:
        """

        params = "uuid_displace {uuid} {action} {file} {limit} {mux}".format(
            uuid=uuid, action=action, file=file, limit=limit, mux=mux)
        print(params)
        return self.api(params)