'''
例外が起きる状況のテストは全て test_wait_xxx_cm.py に任せてあるので、ここではそれ以外の状況のみをテストする。
'''

import pytest

num_bg_tasks = pytest.mark.parametrize('num_bg_tasks', range(3))


@num_bg_tasks
def test_bg_finishes_immediately(num_bg_tasks):
    import asyncgui as ag

    async def finish_imm():
        pass

    async def async_fn():
        async with ag.run_as_daemon(*[finish_imm() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.finished
        for t in bg_tasks:
            assert t.finished

    fg_task = ag.start(async_fn())
    assert fg_task.finished


@num_bg_tasks
def test_bg_finishes_while_fg_is_running(num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()

    async def async_fn():
        async with ag.run_as_daemon(*[e.wait() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
            e.fire()
            for t in bg_tasks:
                assert t.state is TS.FINISHED
        for t in bg_tasks:
            assert t.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


@num_bg_tasks
def test_bg_finishes_while_fg_is_suspended(num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_daemon(*[e.wait() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
            await ag.sleep_forever()
            for t in bg_tasks:
                assert t.state is TS.FINISHED
        for t in bg_tasks:
            assert t.state is TS.FINISHED

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
        async with ag.run_as_daemon(bg_fn()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
            await ag.sleep_forever()
            assert bg_tasks[0].state is TS.STARTED
        assert bg_tasks[0].state is (TS.CANCELLED if bg_cancel else TS.FINISHED)

    e = ag.Event()
    fg_task = ag.start(async_fn(e))
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


@num_bg_tasks
def test_fg_finishes_while_bg_is_suspended(num_bg_tasks):
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_as_daemon(*[ag.sleep_forever() for __ in range(num_bg_tasks)]) as bg_tasks:
            for t in bg_tasks:
                assert t.state is TS.STARTED
        for t in bg_tasks:
            assert t.state is TS.CANCELLED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED
