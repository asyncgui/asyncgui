'''
例外が起きる状況のテストは全て test_wait_xxx_cm.py に任せてあるので、ここではそれ以外の状況のみをテストする。
'''

import pytest

fg_sleep = pytest.mark.parametrize('fg_sleep', (True, False, ), ids=('fg_sleep', ''))
num_bg_tasks = pytest.mark.parametrize('num_bg_tasks', (1, 2, ))


@fg_sleep
@num_bg_tasks
def test_bg_finishes_immediately(fg_sleep, num_bg_tasks):
    import asyncgui as ag

    async def finish_imm():
        pass

    async def async_fn():
        async with ag.run_as_main(*[finish_imm() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.finished
            if fg_sleep:
                await ag.sleep_forever()

    fg_task = ag.start(async_fn())
    assert fg_task.finished


@fg_sleep
@num_bg_tasks
def test_bg_finishes_while_fg_is_running(fg_sleep, num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()

    async def async_fn():
        async with ag.run_as_main(*[e.wait() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
            e.fire()
            for t in bg_tasks:
                assert t.state is TS.FINISHED
            if fg_sleep:
                await ag.sleep_forever()
        for t in bg_tasks:
            assert t.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


@num_bg_tasks
def test_bg_finishes_while_fg_is_suspended(num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_main(*[e.wait() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
            await ag.sleep_forever()
            pytest.fail()
        for t in bg_tasks:
            assert t.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


@num_bg_tasks
def test_fg_finishes_while_bg_is_running(num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_fn():
        await bg_e.wait()
        fg_e.fire()

    async def async_fn():
        async with ag.run_as_main(*[bg_fn() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
            await fg_e.wait()
            for t in bg_tasks:
                assert t.state is TS.STARTED
        for t in bg_tasks:
            assert t.state is TS.FINISHED

    fg_e = ag.Event()
    bg_e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    bg_e.fire()
    assert fg_task.state is TS.FINISHED


@num_bg_tasks
def test_fg_finishes_while_bg_is_suspended(num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_main(*[e.wait() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
        for t in bg_tasks:
            assert t.state is TS.FINISHED
        

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


@num_bg_tasks
def test_bg_gets_cancelled_while_fg_is_suspended(num_bg_tasks):
    # https://github.com/asyncgui/asyncgui/issues/142
    import asyncgui as ag
    TS = ag.TaskState

    exposed_bg_tasks = None

    async def async_fn():
        nonlocal exposed_bg_tasks
        async with ag.run_as_main(*[ag.sleep_forever() for _ in range(num_bg_tasks)]) as bg_tasks:
            exposed_bg_tasks = bg_tasks
            await ag.sleep_forever()
            pytest.fail()

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    for t in exposed_bg_tasks:
        t.cancel()
    assert fg_task.state is TS.FINISHED
