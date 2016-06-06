import asyncio
import logging
from aioesl.application import get_server

logger = logging.getLogger("aioesl SRV")

async def main(loop, **kwargs):
    # logger.info(kwargs)
    print(kwargs)
    srv = await get_server(loop, kwargs["ip"], kwargs["port"])
    print(await srv.api("status"))


loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop, ip="0.0.0.0", port=1234, login="", password=""))