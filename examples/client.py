import asyncio
import logging
from aioesl.application import Client

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-.1s | %(name)s | %(message)s', datefmt='%d.%m.%y %H:%M:%S')
logger = logging.getLogger("app")

async def main(loop, **kwargs):
    client = Client(loop=loop, host=kwargs["host"], port=kwargs["port"], password=kwargs["password"],
                    reconnect=kwargs["reconnect"], max_retry=kwargs["max_retry"], retry_time=kwargs["retry_time"])
    print("0")
    await client.make_connection()
    await client.auth_success()
    print("1")
    if client.connected:
        print("2")
        res = await client.api("status")
        print(res)
        print("3")

loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop, host="37.18.2.22", port=8021, password="ClueCon",
                             reconnect=True, max_retry=5, retry_time=5))
loop.close()
