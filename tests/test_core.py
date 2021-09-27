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
