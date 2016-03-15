#!/usr/bin/env python3.5
import asyncio
from aioesl import EventProtocol


class ESLOut(EventProtocol):

    def __init__(self, **kwargs):
        EventProtocol.__init__(self, **kwargs)
        self.password = kwargs.get("password")

    async def auth_request(self, ev):
        # Auth if need
        await self.auth(self.password)
        # get status
        res1 = await self.api("status")
        data = res1.get("DataResponse")
        if data is None:
            print ("Error")
        else:
            for row in data.split("\n"):
                print(row)

async def run_client(loop):
    ip = "192.168.87.100"
    esl = ESLOut(loop=loop, password="ClueCon", ip=ip)
    try:
        await loop.create_connection(lambda: esl, ip, 8021)
    except OSError:
        print("Can not connect ESL to %s:%s" % (ip, 8021))
        # try to reconnect
        asyncio.ensure_future(esl.retry_connect(ip=ip, port=8021))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(run_client(loop))
    loop.run_forever()
    loop.close()



