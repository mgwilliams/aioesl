import asyncio
import logging
from aioesl.application import Server

import os
# os.environ['PYTHONASYNCIODEBUG'] = '1'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-.1s | %(name)s | %(message)s', datefmt='%d.%m.%y %H:%M:%S')
logger = logging.getLogger("app")


class ESLServer:
    def __init__(self, **kwargs):
        self.server = Server(loop=loop, ip=kwargs["ip"], port=kwargs["port"])
        self.server.set_handler("new_connection", self.new_connection)

    async def new_connection(self, data):
        print(data)

async def main(loop, **kwargs):
    app = ESLServer(loop=loop, ip=kwargs["ip"], port=kwargs["port"])
    await app.server.start()

    # await srv.close_all()

loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop, ip="0.0.0.0", port=8021))
loop.run_forever()
loop.close()
