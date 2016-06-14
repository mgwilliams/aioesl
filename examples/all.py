import uuid
import asyncio
import logging
from aioesl.application import Client, Server
from aioesl.helpers import print_event
from aioesl.log import aioesl_log

import os
# os.environ['PYTHONASYNCIODEBUG'] = '1'


def on_hangup(session, ev):
    print("on_hangup>>>>>", ev)
    # print_event(event=ev, filter="Time", print_func=aioesl_log.info)
    # print_event(event=ev, filter="0404", print_func=aioesl_log.info)
    # tt = int((int(ev.get("Event-Date-Timestamp"))-int(ev.get("Caller-Channel-Created-Time")))/1000000)
    # print_event(event=ev, filter="6800404", print_func=aioesl_log.info)
    # if ev.get("variable_user_state") is not None:
    #     print_event(event=ev, filter="6800404", print_func=aioesl_log.info)
    #     print("tt>", tt)
    #     print("variable_user_state", ev.get("variable_user_state"))


def on_answer(session, ev):
    print("on_answer>>>>>", ev)

def on_state(session, ev):
    print("on_state>>>>>",ev)

async def session_handler(session, data):

    _waiter = asyncio.Future()

    # await session.answer()
    # print_event(data)
    # call_uuid = data.get("variable_call_uuid")
    # res = await session.api("uuid_dump %s" % data.get("variable_call_uuid"))
    # print_event(event=res, filter=None, print_func=aioesl_log.info)
    #
    # res = await session.api("uuid_transfer %s playback(${hold_music})" % data.get("variable_call_uuid"))
    # print(res)
    # await session.myevents()
    # session.set_handler("CHANNEL_ANSWER", on_answer)
    # session.set_handler("CHANNEL_HANGUP", on_hangup)
    # session.set_handler("CHANNEL_STATE", on_state)
    # res = await session.myevents()
    # print(res)
    res = await session.event("plain ALL")
    print(res)

    print(">>>>>1")
    await _waiter
    print(">>>>>2")

    # await session.filter("Event-Name CHANNEL_ANSWER")
    # await session.filter("Unique-ID %s" % call_uuid)
    # await session.filter("Unique-ID %s" % data.get("Unique-ID"))
    #
    await session.api("uuid_setvar %s user_state %s" % (data.get("variable_call_uuid"), "Hello"))
    await session.playback("file_string://https://tlk.runtel.ru/media/cdc4b2ad-eada-4a74-8def-c7d5c15138a3/a6d57c7d-083f-4fa3-84c5-13e0e8b2d9e7.wav", lock=True)
    #
    # await session.playback("${hold_music}", lock=False)
    # await session.api("uuid_broadcast {uuid} {file} aleg".format(
    #     uuid=data.get("Unique-ID"),
    #     file="file_string://https://tlk.runtel.ru/media/cdc4b2ad-eada-4a74-8def-c7d5c15138a3/a6d57c7d-083f-4fa3-84c5-13e0e8b2d9e7.wav")
    # )
    # # await session.api("uuid_setvar %s user_state %s" % (data.get("Unique-ID"), "Hello"))
    # await asyncio.sleep(30)
    # await session.api("uuid_setver %s user_state %s" % (data.get("variable_call_uuid"), "Wait"))
    # await asyncio.sleep(20)
    # await session.api("uuid_broadcast {uuid} {file} aleg".format(
    #     uuid=data.get("Unique-ID"),
    #     file="file_string://https://tlk.runtel.ru/media/cdc4b2ad-eada-4a74-8def-c7d5c15138a3/61e8ec53-c4cc-42f5-8c91-ed20f17fbdf4.wav")
    # )
    # await session.api("uuid_setver %s user_state %s" % (data.get("variable_call_uuid"), "HangUp"))
    # await asyncio.sleep(5)
    # await session.hangup()
    # await asyncio.sleep(1)
    # await session.exit()

async def show_connections(srv):
    print("Current sessions:", len(srv.sessions))
    await asyncio.sleep(2)
    asyncio.ensure_future(show_connections(srv))

async def make_call(phone):

    async def on_answer(session, ev):
        print(123)

    async def on_hangup(session, ev):
        print(321)
        if not answer_waiter.done():
            answer_waiter.set_result("123123")

    _uuid = uuid.uuid4()
    # "execute_on_answer='socket 172.16.10.2:4888 async full'," \
    orig_vars = "origination_caller_id_name=Test," \
                "origination_caller_id_number=TEST," \
                "sip_h_X-toll_allow=9330," \
                "execute_on_answer='\'playback:/tmp/123.wav,hangup\' inline'," \
                "sip_h_X-originate_retry_sleep_ms=50," \
                "sip_h_X-originate_retries=10," \
                "sip_h_X-b_context=1506193.runtel.ru".format(uuid=_uuid, id=phone)
    # cmd = "originate {%s}sofia/internal/a7247c84-9ea8-4045-8533-1c57def114b3_%s@1506193.runtel.ru &wait_for_answer()" % (
    cmd = "originate {%s}sofia/internal/a7247c84-9ea8-4045-8533-1c57def114b3_%s@1506193.runtel.ru &wait_for_answer()" % (
    # cmd = "originate {%s}sofia/internal/a7247c84-9ea8-4045-8533-1c57def114b3_%s@1506193.runtel.ru &playback(${hold_music})" % (
    # cmd = "originate {%s}sofia/internal/a7247c84-9ea8-4045-8533-1c57def114b3_%s@1506193.runtel.ru &socket(172.16.10.2:4888 async full)" % (
    orig_vars, phone)
    answer_waiter = asyncio.Future()
    esl = Client(loop=loop, host='37.18.2.22', port=8021,
                 password="ClueCon", reconnect=True, retries=3, retry_sleep=10)
    await esl.open_connection()
    if await esl.ready():
        try:
            await esl.api(cmd)
            await esl.exit()
        except Exception as error:
            aioesl_log.exception(error)

async def main():
    srv = Server(loop=loop,
                 ip="172.16.10.2",
                 port=4888,
                 session_connected_cb=session_handler,
                 event_handler_log=True)
    await srv.start()
    asyncio.ensure_future(show_connections(srv))

    phones = [
    "9042129658",
    "9805536332",
    "9056550417",
    "9290114882",
    "9050498638"]

    total = len(phones)
    current = 1
    for phone in phones:
        print("Total: %s, current %s" % (total, current))
        await make_call(phone)
        await asyncio.sleep(10)
        current +=1


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-.1s | %(name)s | %(message)s', datefmt='%d.%m.%y %H:%M:%S')
logger = logging.getLogger("app")

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_forever()
loop.close()
