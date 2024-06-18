'''
例外が起きる状況のテストは全て test_wait_xxx_cm.py に任せてあるので、ここではそれ以外の状況のみをテストする。
'''

import pytest


def test_bg_finishes_immediately():
    import asyncgui as ag
    TS = ag.TaskState

    async def finish_imm():
        pass

    async def async_fn():
        async with ag.wait_all_cm(finish_imm()) as bg_task:
            assert bg_task.state is TS.FINISHED
            await ag.sleep_forever()

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.wait_all_cm(ag.sleep_forever()) as bg_task:
            assert bg_task.state is TS.STARTED
            bg_task._step()
            assert bg_task.state is TS.FINISHED
            await ag.sleep_forever()
        assert bg_task.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.wait_all_cm(e.wait()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_fn():
        await e.wait()
        fg_task._step()

    async def async_fn(e):
        async with ag.wait_all_cm(bg_fn()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn(e))
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.wait_all_cm(e.wait()) as bg_task:
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.FINISHED
        

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_protected():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.wait_all_cm(e.wait()) as bg_task:
            async with ag.disable_cancellation():
                await ag.sleep_forever()
            assert bg_task.state is TS.FINISHED
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_protected():
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_func():
        async with ag.disable_cancellation():
            await e.wait()

    async def async_fn():
        async with ag.wait_all_cm(bg_func()) as bg_task:
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED
