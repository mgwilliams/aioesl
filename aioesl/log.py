import logging
from logging import Logger, setLoggerClass, getLoggerClass, NOTSET, addLevelName

DEBUG_LEVEL1_NUM = 9
DEBUG_LEVEL2_NUM = 8
DEBUG_LEVEL3_NUM = 7
DEBUG_LEVEL4_NUM = 6
DEBUG_LEVEL5_NUM = 5

logLevelToName = {
    logging.CRITICAL: 'CRITICAL',
    logging.ERROR: 'ERROR',
    logging.WARNING: 'WARNING',
    logging.INFO: 'INFO',
    logging.DEBUG: 'DEBUG',
    logging.NOTSET: 'NOTSET',
    DEBUG_LEVEL1_NUM: "DEBUG1",
    DEBUG_LEVEL2_NUM: "DEBUG2",
    DEBUG_LEVEL3_NUM: "DEBUG3",
    DEBUG_LEVEL4_NUM: "DEBUG4",
    DEBUG_LEVEL5_NUM: "DEBUG5"
}

addLevelName(DEBUG_LEVEL1_NUM, "DEBUG1")
addLevelName(DEBUG_LEVEL2_NUM, "DEBUG2")
addLevelName(DEBUG_LEVEL3_NUM, "DEBUG3")
addLevelName(DEBUG_LEVEL4_NUM, "DEBUG4")
addLevelName(DEBUG_LEVEL5_NUM, "DEBUG5")


class ESLLogger(getLoggerClass()):
    def __init__(self, name, level=NOTSET):
        super().__init__(name, level)

        logging.addLevelName(DEBUG_LEVEL1_NUM, "DEBUG1")
        logging.addLevelName(DEBUG_LEVEL2_NUM, "DEBUG2")
        logging.addLevelName(DEBUG_LEVEL3_NUM, "DEBUG3")
        logging.addLevelName(DEBUG_LEVEL4_NUM, "DEBUG4")
        logging.addLevelName(DEBUG_LEVEL5_NUM, "DEBUG5")

    def debug1(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG_LEVEL1_NUM):
            self._log(DEBUG_LEVEL1_NUM, msg, args, **kwargs)

    def debug2(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG_LEVEL2_NUM):
            self._log(DEBUG_LEVEL2_NUM, msg, args, **kwargs)

    def debug3(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG_LEVEL3_NUM):
            self._log(DEBUG_LEVEL3_NUM, msg, args, **kwargs)

    def debug4(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG_LEVEL4_NUM):
            self._log(DEBUG_LEVEL4_NUM, msg, args, **kwargs)

    def debug5(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG_LEVEL5_NUM):
            self._log(DEBUG_LEVEL5_NUM, msg, args, **kwargs)

setLoggerClass(ESLLogger)
aioesl_log = logging.getLogger("aioesl")


class LogBase:

    def __init__(self, *args, **kwargs):
        # self.debug = kwargs.get("debug", False)
        pass

    @property
    def peer(self):
        pass

    @property
    def log_prefix(self):
        return "[0x%x %s]" % (id(self), self.peer)

    def li(self, m):
        aioesl_log.info("%s %s" % (self.log_prefix, m))

    def le(self, m):
        aioesl_log.error("%s %s" % (self.log_prefix, m))

    def lw(self, m):
        aioesl_log.warning("%s %s" % (self.log_prefix, m))

    def ld(self, m):
        aioesl_log.debug("%s %s" % (self.log_prefix, m))

    def ld1(self, m):
        aioesl_log.debug1("%s %s" % (self.log_prefix, m))

    def ld2(self, m):
        aioesl_log.debug2("%s %s" % (self.log_prefix, m))

    def ld3(self, m):
        aioesl_log.debug3("%s %s" % (self.log_prefix, m))

    def ld4(self, m):
        aioesl_log.debug4("%s %s" % (self.log_prefix, m))

    def ld5(self, m):
        aioesl_log.debug5("%s %s" % (self.log_prefix, m))

    def log_exc(self, m):
        aioesl_log.exception("%s %s" % (self.log_prefix, m))
