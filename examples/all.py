import asyncio
import logging
from aioesl.application import Client
from aioesl.application import Server

from aioesl.log import aioesl_log


async def client_connected_cb(session):
    print(session.__dict__)

async def show_connections(srv):
    print(srv.connections)
    await asyncio.sleep(2)
    asyncio.ensure_future(show_connections(srv))

async def main():
    clnt = Client(loop=loop, client_ip='37.18.2.22', client_port=8021, password="ClueCon", reconnect=True, retries=3)
    await clnt.connect()
    if await clnt.ready():
        res = await clnt.api("status")
        print(res)
        await clnt.exit()
    #
    # srv = Server(loop, "0.0.0.0", 4567, client_connected_cb=client_connected_cb)
    # await srv.start()
    # print(srv.app)
    # asyncio.ensure_future(show_connections(srv))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-.1s | %(name)s | %(message)s', datefmt='%d.%m.%y %H:%M:%S')
logger = logging.getLogger("app")

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_forever()
loop.close()
