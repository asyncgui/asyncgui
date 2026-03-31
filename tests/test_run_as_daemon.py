'''
例外が起きる状況のテストは全て test_wait_xxx_cm.py に任せてあるので、ここではそれ以外の状況のみをテストする。
'''

import pytest


def test_bg_finishes_immediately():
    import asyncgui as ag

    async def finish_imm():
        pass

    async def async_fn():
        async with ag.run_as_daemon(finish_imm()) as bg_task:
            assert bg_task.finished

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_bg_finishes_while_fg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_daemon(ag.sleep_forever()) as bg_task:
            assert bg_task.state is TS.STARTED
            bg_task._step()
            assert bg_task.state is TS.FINISHED
        assert bg_task.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_daemon(e.wait()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.FINISHED
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED


@pytest.mark.parametrize('bg_cancel', (True, False, ))
def test_fg_finishes_while_bg_is_running(bg_cancel):
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_fn():
        await e.wait()
        fg_task._step()
        if bg_cancel:
            await ag.sleep_forever()

    async def async_fn(e):
        async with ag.run_as_daemon(bg_fn()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.STARTED
        assert bg_task.state is (TS.CANCELLED if bg_cancel else TS.FINISHED)

    e = ag.Event()
    fg_task = ag.start(async_fn(e))
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_daemon(ag.sleep_forever()) as bg_task:
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.CANCELLED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED
