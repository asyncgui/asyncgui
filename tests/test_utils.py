import pytest


def test_current_task():
    import asyncgui as ag
    finished = False

    async def async_fn():
        task = await ag.current_task()
        assert isinstance(task, ag.Task)
        nonlocal finished;finished = True

    ag.start(async_fn())
    assert finished


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
    assert task.finished


def test_dummy_task():
    from asyncgui import dummy_task
    assert dummy_task.cancelled


@pytest.mark.parametrize('call_cancel', (True, False))
@pytest.mark.parametrize('disable_cancellation', (True, False))
def test_check_cancellation(call_cancel, disable_cancellation):
    import asyncgui as ag

    async def async_func():
        if call_cancel:
            task.cancel()
        if disable_cancellation:
            async with ag.disable_cancellation():
                await ag.check_cancellation()
        else:
            await ag.check_cancellation()

    task = ag.Task(async_func())
    ag.start(task)
    if (not disable_cancellation) and call_cancel:
        assert task.cancelled
    else:
        assert task.finished


def test_sleep_forever():
    import asyncgui as ag

    async def main():
        assert (await ag.sleep_forever()) is None

    task = ag.start(main())
    assert not task.finished
    task._step(1, 2, python='awesome', rust='awesome')
    assert task.finished


def test_disable_cancellation():
    import asyncgui as ag

    async def async_fn(e):
        async with ag.disable_cancellation():
            await e.wait()
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    e = ag.Event()
    task = ag.Task(async_fn(e))
    ag.start(task)
    task.cancel()
    assert task._disable_cancellation == 1
    assert not task.cancelled
    assert not task._is_cancellable
    e.set()
    assert task._disable_cancellation == 0
    assert task.cancelled


def test_disable_cancellation__ver_nested():
    import asyncgui as ag

    async def outer_fn(e):
        async with ag.disable_cancellation():
            await inner_fn(e)
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    async def inner_fn(e):
        assert task._disable_cancellation == 1
        async with ag.disable_cancellation():
            assert task._disable_cancellation == 2
            await e.wait()
        assert task._disable_cancellation == 1

    e = ag.Event()
    task = ag.Task(outer_fn(e))
    assert task._disable_cancellation == 0
    ag.start(task)
    assert task._disable_cancellation == 2
    task.cancel()
    assert not task.cancelled
    assert not task._is_cancellable
    e.set()
    assert task._disable_cancellation == 0
    assert task.cancelled


def test_disable_cancellation__ver_self():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        async with ag.disable_cancellation():
            task.cancel()
            await ag.sleep_forever()
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    task = ag.Task(async_fn())
    ag.start(task)
    assert not task.cancelled
    assert not task._is_cancellable
    assert task._disable_cancellation == 1
    task._step()
    assert task.cancelled
    assert task._disable_cancellation == 0
