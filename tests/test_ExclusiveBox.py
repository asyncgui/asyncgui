import pytest


def test_put_get():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        box.put(None, python='awesome')
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    task = ag.start(async_fn())
    assert task.finished


def test_update_get():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        box.put_or_update(None, python='awesome')
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


    box = ag.ExclusiveBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put(None, python='awesome')
    assert task.finished


def test_get_update():
    import asyncgui as ag

    async def async_fn(box):
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    box = ag.ExclusiveBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put_or_update(None, python='awesome')
    assert task.finished


def test_put_put():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        box.put(None)
        box.put(None)

    task = ag.start(async_fn())
    assert task.finished


def test_get_get():
    import asyncgui as ag

    box = ag.ExclusiveBox()
    ag.start(box.get())
    with pytest.raises(ag.InvalidStateError):
        ag.start(box.get())


def test_put_get_put():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        box.put(None, python='awesome')
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }
        box.put(None, python='awesome')

    task = ag.start(async_fn())
    assert task.finished


def test_put_get_update_get():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        box.put(1)
        args, kwargs = await box.get()
        assert args == (1, )
        assert kwargs == {}
        box.update(2)
        args, kwargs = await box.get()
        assert args == (2, )
        assert kwargs == {}

    task = ag.start(async_fn())
    assert task.finished


def test_put_get_get():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        box.put(None, python='awesome')
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

    box = ag.ExclusiveBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put(None, python='awesome')
    assert task.finished


def test_get_put_put():
    import asyncgui as ag

    async def async_fn(box):
        args, kwargs = await box.get()
        assert args == (None, )
        assert kwargs == {'python': 'awesome', }

    box = ag.ExclusiveBox()
    task = ag.start(async_fn(box))
    assert task.state is ag.TaskState.STARTED
    box.put(None, python='awesome')
    assert task.finished
    box.put(None, python='awesome')


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
    box = ag.ExclusiveBox()
    task = ag.start(async_fn(ctx, box))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    box.put(None, python='awesome')
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED


def test_is_empty():
    import asyncgui as ag

    async def async_fn():
        box = ag.ExclusiveBox()
        assert box.is_empty
        box.put(None)
        assert not box.is_empty
        box.clear()
        assert box.is_empty

    task = ag.start(async_fn())
    assert task.finished
