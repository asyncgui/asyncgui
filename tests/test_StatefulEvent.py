import pytest


def test_wait_then_fire():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.StatefulEvent()
    t1 = ag.start(e.wait())
    t2 = ag.start(e.wait())
    assert t1.state is TS.STARTED
    assert t2.state is TS.STARTED
    e.fire(7, crow='raven')
    assert t1.result == ((7, ), {'crow': 'raven', })
    assert t2.result == ((7, ), {'crow': 'raven', })


def test_fire_then_wait():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.StatefulEvent()
    e.fire(7, crow='raven')
    t1 = ag.start(e.wait())
    t2 = ag.start(e.wait())
    assert t1.state is TS.FINISHED
    assert t2.state is TS.FINISHED
    assert t1.result == ((7, ), {'crow': 'raven', })
    assert t2.result == ((7, ), {'crow': 'raven', })


def test_clear():
    import asyncgui as ag
    e1 = ag.StatefulEvent()
    e2 = ag.StatefulEvent()

    async def async_fn():
        assert (await e1.wait()) == ((7, ), {'crow': 'raven', })
        assert (await e2.wait()) == ((6, ), {'crocodile': 'alligator', })
        assert (await e1.wait()) == ((5, ), {'toad': 'frog', })

    task = ag.start(async_fn())
    e1.fire(7, crow='raven')
    e1.clear()
    e2.fire(6, crocodile='alligator')
    e1.fire(5, toad='frog')
    assert task.finished


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, e):
        with ag.CancelScope(await ag.current_task()) as scope:
            ctx['scope'] = scope
            await e.wait()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    e = ag.StatefulEvent()
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
        with ag.CancelScope(await ag.current_task()) as scope:
            ctx['scope'] = scope
            await e.wait()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    e = ag.StatefulEvent()
    t1 = ag.start(async_fn_1(ctx, e))
    t2 = ag.start(async_fn_2(ctx, e))
    assert e._waiting_tasks == [t1, t2, ]
    assert t2.state is TS.STARTED
    e.fire()
    assert t1.state is TS.FINISHED
    assert t2.state is TS.STARTED
    assert e._waiting_tasks == []
    t2._step()
    assert t2.state is TS.FINISHED


def test_params():
    import asyncgui as ag
    e = ag.StatefulEvent()

    e.fire(1, crow='raven')
    args, kwargs = e.params
    assert args == (1, )
    assert kwargs == {'crow': 'raven', }

    e.refire(2, parasol='umbrella')
    args, kwargs = e.params
    assert args == (2, )
    assert kwargs == {'parasol': 'umbrella', }

    e.clear()
    with pytest.raises(ag.InvalidStateError):
        e.params
