import pytest


def test_aclosing():
    import asyncgui as ag
    agen_closed = False

    async def agen_func():
        try:
            for i in range(10):
                yield i
        finally:
            nonlocal agen_closed;agen_closed = True

    async def async_fn():
        async with ag.aclosing(agen_func()) as agen:
            async for i in agen:
                if i > 1:
                    break
            assert not agen_closed
        assert agen_closed

    task = ag.start(async_fn())
    assert task.done


def test_dummy_task():
    from asyncgui import dummy_task
    assert dummy_task.cancelled


@pytest.mark.parametrize('call_cancel', (True, False))
@pytest.mark.parametrize('protect', (True, False))
def test_checkpoint(call_cancel, protect):
    import asyncgui as ag

    async def async_func(ctx):
        if call_cancel:
            ctx['task'].cancel()
        if protect:
            async with ag.cancel_protection():
                await ag.checkpoint()
        else:
            await ag.checkpoint()

    ctx = {}
    ctx['task'] = task = ag.Task(async_func(ctx))
    ag.start(task)
    if (not protect) and call_cancel:
        assert task.cancelled
    else:
        assert task.done


def test_sleep_forever():
    import asyncgui as ag

    async def main():
        args, kwargs = await ag.sleep_forever()
        assert args == (1, 2, )
        assert kwargs == {'python': 'awesome', 'rust': 'awesome', }

    task = ag.start(main())
    assert not task.done
    task._step(1, 2, python='awesome', rust='awesome')
    assert task.done


def test_cancel_protection():
    import asyncgui as ag

    async def async_fn(e):
        async with ag.cancel_protection():
            await e.wait()
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    e = ag.Event()
    task = ag.Task(async_fn(e))
    ag.start(task)
    task.cancel()
    assert task._cancel_protection == 1
    assert not task.cancelled
    assert not task._is_cancellable
    e.set()
    assert task._cancel_protection == 0
    assert task.cancelled


def test_nested_cancel_protection():
    import asyncgui as ag

    async def outer_fn(e):
        async with ag.cancel_protection():
            await inner_fn(e)
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    async def inner_fn(e):
        assert task._cancel_protection == 1
        async with ag.cancel_protection():
            assert task._cancel_protection == 2
            await e.wait()
        assert task._cancel_protection == 1

    e = ag.Event()
    task = ag.Task(outer_fn(e))
    assert task._cancel_protection == 0
    ag.start(task)
    assert task._cancel_protection == 2
    task.cancel()
    assert not task.cancelled
    assert not task._is_cancellable
    e.set()
    assert task._cancel_protection == 0
    assert task.cancelled


def test_cancel_protected_self():
    import asyncgui as ag

    async def async_fn():
        task = await ag.get_current_task()
        async with ag.cancel_protection():
            task.cancel()
            await ag.sleep_forever()
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    task = ag.Task(async_fn())
    ag.start(task)
    assert not task.cancelled
    assert not task._is_cancellable
    assert task._cancel_protection == 1
    task._step()
    assert task.cancelled
    assert task._cancel_protection == 0
