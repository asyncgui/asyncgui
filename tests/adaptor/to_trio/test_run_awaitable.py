import pytest
pytest.importorskip('trio')


@pytest.mark.trio
async def test_return_value(nursery):
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import run_awaitable

    async def ag_func():
        # ensure this function to be asyncgui-flavored
        e = ag.Event();e.set()
        await e.wait()

        return 'return_value'

    await run_awaitable(ag_func()) == 'return_value'


@pytest.mark.trio
async def test_nursery_start(nursery):
    from inspect import getcoroutinestate, CORO_SUSPENDED, CORO_CLOSED
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import run_awaitable

    ag_event = ag.Event()
    trio_event = trio.Event()
    async def ag_func():
        await ag_event.wait()
        trio_event.set()
    ag_coro = ag_func()

    with trio.fail_after(1):
        ag_wrapper_coro = await nursery.start(run_awaitable, ag_coro)
        assert ag_wrapper_coro.cr_await is ag_coro
        assert getcoroutinestate(ag_wrapper_coro) == CORO_SUSPENDED
        assert getcoroutinestate(ag_coro) == CORO_SUSPENDED
        ag_event.set()
        assert getcoroutinestate(ag_wrapper_coro) == CORO_CLOSED
        assert getcoroutinestate(ag_coro) == CORO_CLOSED
        await trio_event.wait()


@pytest.mark.trio
async def test_nursery_start_soon(nursery):
    from inspect import (
        getcoroutinestate, CORO_CREATED, CORO_SUSPENDED, CORO_CLOSED,
    )
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import run_awaitable

    ag_event = ag.Event()
    trio_event1 = trio.Event()
    trio_event2 = trio.Event()
    async def ag_func():
        trio_event1.set()
        await ag_event.wait()
        trio_event2.set()
    ag_coro = ag_func()

    with trio.fail_after(1):
        nursery.start_soon(run_awaitable, ag_coro)
        assert getcoroutinestate(ag_coro) == CORO_CREATED
        await trio_event1.wait()
        assert getcoroutinestate(ag_coro) == CORO_SUSPENDED
        ag_event.set()
        assert getcoroutinestate(ag_coro) == CORO_CLOSED
        await trio_event2.wait()


@pytest.mark.trio
async def test_cancel_from_trio(nursery):
    from inspect import getcoroutinestate, CORO_SUSPENDED, CORO_CLOSED
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import run_awaitable

    ag_event = ag.Event()
    trio_event = trio.Event()
    cancel_scope = None
    async def trio_func(*, task_status):
        nonlocal cancel_scope; cancel_scope = trio.CancelScope()
        with cancel_scope:
            await run_awaitable(ag_event.wait(), task_status=task_status)
        trio_event.set()

    with trio.fail_after(1):
        ag_wrapper_coro = await nursery.start(trio_func)
        cancel_scope.cancel()
        assert getcoroutinestate(ag_wrapper_coro) == CORO_SUSPENDED
        await trio_event.wait()
        assert getcoroutinestate(ag_wrapper_coro) == CORO_CLOSED
        assert not ag_event.is_set()


@pytest.mark.trio
async def test_cancel_from_asyncgui(nursery):
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import run_awaitable

    ag_event = ag.Event()
    trio_event = trio.Event()
    async def trio_func(*, task_status):
        with pytest.raises(ag.exceptions.CancelledError):
            await run_awaitable(ag_event.wait(), task_status=task_status)
        trio_event.set()

    with trio.fail_after(1):
        ag_wrapper_coro = await nursery.start(trio_func)
        ag_wrapper_coro.close()
        await trio_event.wait()
        assert not ag_event.is_set()


@pytest.mark.trio
async def test_exception_propagation(nursery):
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import run_awaitable

    trio_event = trio.Event()
    async def ag_func():
        # ensure this function to be asyncgui-flavored
        e = ag.Event();e.set()
        await e.wait()

        raise ZeroDivisionError
    async def trio_func(*, task_status):
        with pytest.raises(ZeroDivisionError):
            await run_awaitable(ag_func(), task_status=task_status)
        trio_event.set()

    with trio.fail_after(1):
        await nursery.start(trio_func)
        await trio_event.wait()
