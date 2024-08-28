'''
例外が起きる状況のテストは全て test_wait_xxx_cm.py に任せてあるので、ここではそれ以外の状況のみをテストする。
'''

import pytest

fg_sleep = pytest.mark.parametrize('fg_sleep', (True, False, ), ids=('fg_sleep', ''))

@fg_sleep
def test_bg_finishes_immediately(fg_sleep):
    import asyncgui as ag

    async def finish_imm():
        pass

    async def async_fn():
        async with ag.run_as_main(finish_imm()) as bg_task:
            assert bg_task.finished
            if fg_sleep:
                await ag.sleep_forever()

    fg_task = ag.start(async_fn())
    assert fg_task.finished


@fg_sleep
def test_bg_finishes_while_fg_is_running(fg_sleep):
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_main(ag.sleep_forever()) as bg_task:
            assert bg_task.state is TS.STARTED
            bg_task._step()
            assert bg_task.state is TS.FINISHED
            if fg_sleep:
                await ag.sleep_forever()
        assert bg_task.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_main(e.wait()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            pytest.fail()
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_fn():
        await e.wait()
        fg_task._step()

    async def async_fn():
        async with ag.run_as_main(bg_fn()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_main(e.wait()) as bg_task:
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.FINISHED
        

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_protected():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_main(e.wait()) as bg_task:
            async with ag.disable_cancellation():
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
