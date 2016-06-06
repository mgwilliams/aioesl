#!/usr/bin/env python3.5
import asyncio
from aioesl import EventProtocol


class ESLOut(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)

    async def auth_request(self, ev):
        res = await self.auth(self.esl_password)
        # logger.debug(res)
        # res1 = await self.eventplain("ANSWER")
        # logger.debug(res1)


class ESLIn(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self._is_server = True

def run_server(loop):
    esl = loop.create_server(lambda: ESLIn(loop=loop), "0.0.0.0", 5678)
    ok = asyncio.ensure_future(esl)
    ok.add_done_callback(lambda res: print("Server started"))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    run_server(loop)
    loop.run_forever()
    loop.close()



