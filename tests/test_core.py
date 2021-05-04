import pytest


@pytest.mark.parametrize('raw', (True, False))
def test__get_step_coro(raw):
    import asyncgui as ag
    done = False

    async def job():
        step_coro = await ag.get_step_coro()
        assert callable(step_coro)
        nonlocal done;done = True

    if raw:
        ag.raw_start(job())
    else:
        ag.start(job())
    assert done


@pytest.mark.parametrize('raw', (True, False))
def test__get_current_task(raw):
    import asyncgui as ag
    done = False

    async def job():
        task = await ag.get_current_task()
        assert (task is None) if raw else isinstance(task, ag.Task)
        nonlocal done;done = True

    if raw:
        ag.raw_start(job())
    else:
        ag.start(job())
    assert done


def test_aclosing():
    import asyncgui as ag
    agen_closed = False

    async def agen_func():
        try:
            for i in range(10):
                yield i
        finally:
            nonlocal agen_closed;agen_closed = True

    async def job():
        async with ag.aclosing(agen_func()) as agen:
            async for i in agen:
                if i > 1:
                    break
            assert not agen_closed
        assert agen_closed

    task = ag.start(job())
    assert task.done
