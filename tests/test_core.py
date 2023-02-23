import pytest


def test__get_current_task():
    import asyncgui as ag
    done = False

    async def async_fn():
        task = await ag.get_current_task()
        assert isinstance(task, ag.Task)
        nonlocal done;done = True

    ag.start(async_fn())
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
    task._step_coro(1, 2, python='awesome', rust='awesome')
    assert task.done
