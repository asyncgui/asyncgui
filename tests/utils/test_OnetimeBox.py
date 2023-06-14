import pytest


def test_put_get():
    import asyncgui as ag

    async def async_fn():
        box = ag.OnetimeBox()
        box.put_nowait(None, python='awesome')
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    task = ag.start(async_fn())
    assert task.finished


def test_get_put():
    import asyncgui as ag

    async def async_fn(box):
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }


    box = ag.OnetimeBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put_nowait(None, python='awesome')
    assert task.finished


def test_put_put():
    import asyncgui as ag

    async def async_fn():
        box = ag.OnetimeBox()
        box.put_nowait(None)
        box.put_nowait(None)

    task = ag.start(async_fn())
    assert task.finished


def test_get_get():
    import asyncgui as ag

    box = ag.OnetimeBox()
    ag.start(box.get())
    with pytest.raises(ag.InvalidStateError):
        ag.start(box.get())


def test_put_get_put():
    import asyncgui as ag

    async def async_fn():
        box = ag.OnetimeBox()
        box.put_nowait(None, python='awesome')
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }
        box.put_nowait(None, python='awesome')

    task = ag.start(async_fn())
    assert task.finished


def test_put_get_get():
    import asyncgui as ag

    async def async_fn():
        box = ag.OnetimeBox()
        box.put_nowait(None, python='awesome')
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    task = ag.start(async_fn())
    assert task.finished


def test_get_put_get():
    import asyncgui as ag

    async def async_fn(box):
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    box = ag.OnetimeBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put_nowait(None, python='awesome')
    assert task.finished


def test_get_put_put():
    import asyncgui as ag

    async def async_fn(box):
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    box = ag.OnetimeBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put_nowait(None, python='awesome')
    assert task.finished
    box.put_nowait(None, python='awesome')


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, box):
        async with ag.open_cancel_scope() as scope:
            ctx['scope'] = scope
            await box.get()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    box = ag.OnetimeBox()
    task = ag.start(async_fn(ctx, box))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    box.put_nowait(None, python='awesome')
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED
