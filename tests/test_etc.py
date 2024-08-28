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


def test_dummy_task():
    from asyncgui import dummy_task
    assert dummy_task.cancelled


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
    assert task._cancel_disabled == 1
    assert not task.cancelled
    assert not task._is_cancellable
    e.fire()
    assert task._cancel_disabled == 0
    assert task.cancelled


def test_disable_cancellation__ver_nested():
    import asyncgui as ag

    async def outer_fn(e):
        async with ag.disable_cancellation():
            await inner_fn(e)
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    async def inner_fn(e):
        assert task._cancel_disabled == 1
        async with ag.disable_cancellation():
            assert task._cancel_disabled == 2
            await e.wait()
        assert task._cancel_disabled == 1

    e = ag.Event()
    task = ag.Task(outer_fn(e))
    assert task._cancel_disabled == 0
    ag.start(task)
    assert task._cancel_disabled == 2
    task.cancel()
    assert not task.cancelled
    assert not task._is_cancellable
    e.fire()
    assert task._cancel_disabled == 0
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
    assert task._cancel_disabled == 1
    task._step()
    assert task.cancelled
    assert task._cancel_disabled == 0
