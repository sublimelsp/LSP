from __future__ import annotations
import asyncio
from threading import Thread
from typing import Awaitable
from ..plugin.core.logging import debug

__loop: asyncio.AbstractEventLoop | None = None
__thread: Thread | None = None
__active_tasks: set[asyncio.Task] = set()


def run_future(future: Awaitable):
    global __loop, __active_tasks
    if __loop:
        task = asyncio.ensure_future(future, loop=__loop)
        __active_tasks.add(task)
        task.add_done_callback(__active_tasks.discard)  # Remove once done
        __loop.call_soon_threadsafe(lambda: task)


def setup_event_loop():
    debug('loop: starting')
    global __loop
    global __thread
    if __loop:
        debug('loop: already created')
        return
    __loop = asyncio.new_event_loop()
    __thread = Thread(target=__loop.run_forever)
    __thread.start()
    debug("loop: started")


def shutdown_event_loop():
    debug("loop: stopping")
    global __loop
    global __thread

    if not __loop:
        debug('no loop to shutdown.')

    def __shutdown():
        for task in asyncio.all_tasks():
            task.cancel()
        asyncio.get_event_loop().stop()

    if __loop and __thread:
        __loop.call_soon_threadsafe(__shutdown)
        __thread.join()
        __loop.run_until_complete(__loop.shutdown_asyncgens())
        __loop.close()
    __loop = None
    __thread = None
    debug("loop: stopped")
