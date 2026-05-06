from contextlib import asynccontextmanager
from asyncgui import open_nursery


async def wait_any(*args):
    async with open_nursery() as nursery:
        tasks = [nursery.start(arg, close_on_finish=True) for arg in args]
    return tasks


async def wait_all(*args):
    async with open_nursery() as nursery:
        tasks = [nursery.start(arg) for arg in args]
    return tasks


@asynccontextmanager
async def move_on_when(arg):
    async with open_nursery() as nursery:
        task = nursery.start(arg, daemon=True, close_on_finish=True)
        yield task


@asynccontextmanager
async def run_as_daemon(arg):
    async with open_nursery() as nursery:
        task = nursery.start(arg, daemon=True)
        yield task
