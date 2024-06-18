import pytest


def test_wait_then_set():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()
    task1 = ag.start(e.wait())
    task2 = ag.start(e.wait())
    assert task1.state is TS.STARTED
    assert task2.state is TS.STARTED
    e.set()
    assert task1.state is TS.FINISHED
    assert task2.state is TS.FINISHED


def test_set_then_wait():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()
    e.set()
    task1 = ag.start(e.wait())
    task2 = ag.start(e.wait())
    assert task1.state is TS.FINISHED
    assert task2.state is TS.FINISHED


def test_clear():
    import asyncgui as ag
    e1 = ag.Event()
    e2 = ag.Event()

    async def main():
        nonlocal task_state
        task_state = 'A'
        await e1.wait()
        task_state = 'B'
        await e2.wait()
        task_state = 'C'
        await e1.wait()
        task_state = 'D'

    task_state = None
    ag.start(main())
    assert task_state == 'A'
    e1.set()
    assert task_state == 'B'
    e1.clear()
    assert task_state == 'B'
    e2.set()
    assert task_state == 'C'
    e1.set()
    assert task_state == 'D'


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, e):
        async with ag.open_cancel_scope() as scope:
            ctx['scope'] = scope
            await e.wait()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    e = ag.Event()
    task = ag.start(async_fn(ctx, e))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    e.set()
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED


def test_complicated_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn_1(ctx, e):
        await e.wait()
        ctx['scope'].cancel()

    async def async_fn_2(ctx, e):
        async with ag.open_cancel_scope() as scope:
            ctx['scope'] = scope
            await e.wait()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    e = ag.Event()
    task1 = ag.start(async_fn_1(ctx, e))
    task2 = ag.start(async_fn_2(ctx, e))
    assert e._waiting_tasks == [task1, task2, ]
    assert task2.state is TS.STARTED
    e.set()
    assert task1.state is TS.FINISHED
    assert task2.state is TS.STARTED
    assert e._waiting_tasks == []
    task2._step()
    assert task2.state is TS.FINISHED
