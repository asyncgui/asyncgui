import pytest


def test_get_then_put():
    import asyncgui as ag
    TS = ag.TaskState
    b = ag.Box()
    t1 = ag.start(b.get())
    t2 = ag.start(b.get())
    assert t1.state is TS.STARTED
    assert t2.state is TS.STARTED
    b.put(7, crow='raven')
    assert t1.result == ((7, ), {'crow': 'raven', })
    assert t2.result == ((7, ), {'crow': 'raven', })


def test_put_then_get():
    import asyncgui as ag
    TS = ag.TaskState
    b = ag.Box()
    b.put(7, crow='raven')
    t1 = ag.start(b.get())
    t2 = ag.start(b.get())
    assert t1.state is TS.FINISHED
    assert t2.state is TS.FINISHED
    assert t1.result == ((7, ), {'crow': 'raven', })
    assert t2.result == ((7, ), {'crow': 'raven', })


def test_clear():
    import asyncgui as ag
    b1 = ag.Box()
    b2 = ag.Box()

    async def async_fn():
        assert (await b1.get()) == ((7, ), {'crow': 'raven', })
        assert (await b2.get()) == ((6, ), {'crocodile': 'alligator', })
        assert (await b1.get()) == ((5, ), {'toad': 'frog', })

    task = ag.start(async_fn())
    b1.put(7, crow='raven')
    b1.clear()
    b2.put(6, crocodile='alligator')
    b1.put(5, toad='frog')
    assert task.finished


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, b):
        async with ag.open_cancel_scope() as scope:
            ctx['scope'] = scope
            await b.get()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    b = ag.Box()
    task = ag.start(async_fn(ctx, b))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    b.put()
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED


def test_complicated_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn_1(ctx, b):
        await b.get()
        ctx['scope'].cancel()

    async def async_fn_2(ctx, b):
        async with ag.open_cancel_scope() as scope:
            ctx['scope'] = scope
            await b.get()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    b = ag.Box()
    t1 = ag.start(async_fn_1(ctx, b))
    t2 = ag.start(async_fn_2(ctx, b))
    assert b._waiting_tasks == [t1, t2, ]
    assert t2.state is TS.STARTED
    b.put()
    assert t1.state is TS.FINISHED
    assert t2.state is TS.STARTED
    assert b._waiting_tasks == []
    t2._step()
    assert t2.state is TS.FINISHED
