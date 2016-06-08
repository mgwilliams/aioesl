import uuid
import asyncio
import logging
from aioesl.application import Client

import os
# os.environ['PYTHONASYNCIODEBUG'] = '1'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-.1s | %(name)s | %(message)s', datefmt='%d.%m.%y %H:%M:%S')
logger = logging.getLogger("app")


async def on_channelanswer(ev):
    print(ev)

async def main(loop, **kwargs):
    client = Client(loop=loop, host=kwargs["host"], port=kwargs["port"], password=kwargs["password"],
                    reconnect=kwargs["reconnect"], max_retry=kwargs["max_retry"], retry_time=kwargs["retry_time"])
    client.handler_log = True
    await client.make_connection()
    if await client.authenticated:
        res = await client.api("status")
        print(res)
        # res = await client.eventplain("CHANNEL_ANSWER")
        # print(res)
        # client.set_handler("on_channelanswer", on_channelanswer)

        _uuid = uuid.uuid4()
        orig_vars = "origination_caller_id_name=Test," \
                    "origination_caller_id_number={id}," \
                    "sip_h_X-toll_allow=0187," \
                    "execute_on_answer='socket 172.16.10.2:8021 async full'," \
                    "sip_h_X-originate_retry_sleep_ms=50," \
                    "sip_h_X-originate_retries=10," \
                    "sip_h_X-b_context=1506193.runtel.ru".format(uuid=_uuid,
                                                         id="89081435926"
                                                         )
        cmd = "originate {%s}sofia/internal/a7247c84-9ea8-4045-8533-1c57def114b3_9081435926@1506193.runtel.ru &wait_for_answer()" % (orig_vars)
        print(cmd)
        res = await client.api(cmd)
        print(res)

    await client.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop, host="37.18.2.22", port=8021, password="ClueCon",
                             reconnect=True, max_retry=1, retry_time=5))
loop.run_forever()
loop.close()
