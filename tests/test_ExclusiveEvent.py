import pytest


def test_wait_fire_wait():
    import asyncgui as ag

    async def async_fn():
        args, kwargs = await e.wait()
        assert args == (1, )
        assert kwargs == {'one': 'ONE', }

    e = ag.ExclusiveEvent()
    task = ag.start(async_fn())
    assert not task.finished
    e.fire(1, one='ONE')
    assert task.finished


def test_fire_wait_fire():
    import asyncgui as ag

    async def async_fn():
        args, kwargs = await e.wait()
        assert args == (2, )
        assert kwargs == {'two': 'TWO', }

    e = ag.ExclusiveEvent()
    e.fire(1, one='ONE')
    task = ag.start(async_fn())
    assert not task.finished
    e.fire(2, two='TWO')
    assert task.finished


def test_fire_fire():
    import asyncgui as ag

    e = ag.ExclusiveEvent()
    e.fire(None)
    e.fire(None)


def test_wait_wait():
    import asyncgui as ag

    e = ag.ExclusiveEvent()
    ag.start(e.wait())
    with pytest.raises(ag.InvalidStateError):
        ag.start(e.wait())


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx):
        with ag.CancelScope(await ag.current_task()) as scope:
            ctx['scope'] = scope
            await e.wait()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    e = ag.ExclusiveEvent()
    task = ag.start(async_fn(ctx))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    e.fire(None, python='awesome')
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED
