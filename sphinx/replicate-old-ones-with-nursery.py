from contextlib import asynccontextmanager
from asyncgui import open_nursery


# Removed in version 0.11.0
@asynccontextmanager
async def move_on_when_any(*args):
    async with open_nursery() as nursery:
        tasks = [nursery.start(arg, daemon=True, close_on_finish=True) for arg in args]
        yield tasks


# Removed in version 0.11.0
@asynccontextmanager
async def run_as_daemons(*args):
    async with open_nursery() as nursery:
        tasks = [nursery.start(arg, daemon=True) for arg in args]
        yield tasks


# Removed in version 0.10.0
@asynccontextmanager
async def run_as_main(arg):
    async with open_nursery() as nursery:
        task = nursery.start(arg, close_on_finish=True)
        yield task


# Removed in version 0.11.0
@asynccontextmanager
async def wait_all_cm(*args):
    async with open_nursery() as nursery:
        tasks = [nursery.start(arg) for arg in args]
        yield tasks
