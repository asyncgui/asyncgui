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
