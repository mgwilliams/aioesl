import logging

aioesl_log = logging.getLogger("aioesl")


class LogBase:

    def __init__(self, *args, **kwargs):
        self.debug = kwargs.get("debug", False)

    @property
    def peer(self):
        pass

    def li(self, m):
        aioesl_log.info("[{host}] {msg}".format(host=self.peer, msg=m))

    def le(self, m):
        aioesl_log.error("[{host}] {msg}".format(host=self.peer, msg=m))

    def lw(self, m):
        aioesl_log.warning("[{host}] {msg}".format(host=self.peer, msg=m))

    def ld(self, m):
        aioesl_log.debug("[{host}] {msg}".format(host=self.peer, msg=m))

    def log_debug(self, m):
        if self.debug:
            aioesl_log.debug("[{host}] {msg}".format(host=self.peer, msg=m))

    def log_exc(self, m):
        aioesl_log.exception("[{host}] {msg}".format(host=self.peer, msg=m))
