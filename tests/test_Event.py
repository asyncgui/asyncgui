import pytest


def test_wait_then_fire_then_fire():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()
    task1 = ag.start(e.wait())
    task2 = ag.start(e.wait())
    assert task1.state is TS.STARTED
    assert task2.state is TS.STARTED
    e.fire()
    assert task1.state is TS.FINISHED
    assert task2.state is TS.FINISHED
    e.fire()


def test_fire_then_wait_then_fire():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()
    e.fire()
    task1 = ag.start(e.wait())
    task2 = ag.start(e.wait())
    assert task1.state is TS.STARTED
    assert task2.state is TS.STARTED
    e.fire()
    assert task1.state is TS.FINISHED
    assert task2.state is TS.FINISHED


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, e):
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
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
    e.fire()
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
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
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
    e.fire()
    assert task1.state is TS.FINISHED
    assert task2.state is TS.STARTED
    assert e._waiting_tasks == []
    task2._step()
    assert task2.state is TS.FINISHED


def test_value_passing():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn1(e):
        args, kwargs = await e.wait()
        assert args == (2, )
        assert kwargs == {'crow': 'raven', }

        args, kwargs = await e.wait()
        assert args == (3, )
        assert kwargs == {'toad': 'frog', }

    async def async_fn2(e):
        args, kwargs = await e.wait()
        assert args == (3, )
        assert kwargs == {'toad': 'frog', }

    e = ag.Event()
    e.fire(1, crocodile='alligator')

    task1 = ag.start(async_fn1(e))
    assert task1.state is TS.STARTED

    e.fire(2, crow='raven')
    assert task1.state is TS.STARTED

    task2 = ag.start(async_fn2(e))
    assert task1.state is TS.STARTED
    assert task2.state is TS.STARTED

    e.fire(3, toad='frog')
    assert task1.state is TS.FINISHED
    assert task2.state is TS.FINISHED


def test_weakref():
    import asyncgui as ag
    import weakref
    weakref.ref(ag.Event())
