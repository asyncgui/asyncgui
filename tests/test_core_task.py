import pytest
import asyncgui as ag
TS = ag.TaskState


def test_task_state_ended():
    assert TS.ENDED is (TS.CANCELLED | TS.DONE)


def test_the_state_and_the_result():
    task_state = 'A'
    async def async_fn():
        nonlocal task_state
        task_state = 'B'
        await ag.sleep_forever()
        task_state = 'C'
        return 'result'

    task = ag.Task(async_fn())
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(StopIteration):
        root_coro.send(None)
    assert task.state is TS.DONE
    assert task._exception is None
    assert task.done
    assert not task.cancelled
    assert task.result == 'result'


def test_the_state_and_the_result__ver_cancel():
    task_state = 'A'
    async def async_fn():
        nonlocal task_state
        task_state = 'B'
        await ag.sleep_forever()
        task_state = 'C'
        return 'result'

    task = ag.Task(async_fn(), name='pytest')
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    root_coro.close()
    assert task.state is TS.CANCELLED
    assert task._exception is None
    assert not task.done
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception():
    '''例外が自然発生した場合'''
    task_state = 'A'
    async def async_fn():
        nonlocal task_state
        task_state = 'B'
        await ag.sleep_forever()
        task_state = 'C'
        raise ZeroDivisionError
        return 'result'

    task = ag.Task(async_fn(), name='pytest')
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        root_coro.send(None)
    assert task.state is TS.CANCELLED
    assert task._exception is None
    assert task_state == 'C'
    assert not task.done
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception_2():
    '''coro.throw()によって例外を起こした場合'''
    task_state = 'A'
    async def async_fn():
        nonlocal task_state
        task_state = 'B'
        await ag.sleep_forever()
        task_state = 'C'
        return 'result'

    task = ag.Task(async_fn(), name='pytest')
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        root_coro.throw(ZeroDivisionError)
    assert task.state is TS.CANCELLED
    assert task._exception is None
    assert task_state == 'B'
    assert not task.done
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_throw_exc_to_unstarted_task():
    import asyncgui as ag
    task = ag.Task(ag.sleep_forever(), name='pytest')
    assert task.state is ag.TaskState.CREATED
    with pytest.raises(ag.InvalidStateError):
        task._throw_exc(ZeroDivisionError)
    task.cancel()  # to avoid RuntimeWarning: coroutine 'xxx' was never awaited


def test_throw_exc_to_cancelled_task():
    import asyncgui as ag
    task = ag.start(ag.Event().wait())
    assert task.state is ag.TaskState.STARTED
    task.cancel()
    assert task.state is ag.TaskState.CANCELLED
    with pytest.raises(ag.InvalidStateError):
        task._throw_exc(ZeroDivisionError)


def test_throw_exc_to_finished_task():
    import asyncgui as ag
    e = ag.Event()
    task = ag.start(e.wait())
    assert task.state is ag.TaskState.STARTED
    e.set()
    assert task.state is ag.TaskState.DONE
    with pytest.raises(ag.InvalidStateError):
        task._throw_exc(ZeroDivisionError)


def test_throw_exc_to_started_task_and_get_caught():
    import asyncgui as ag
    async def async_fn():
        try:
            await ag.sleep_forever()
        except ZeroDivisionError:
            pass
        else:
            assert False
    task = ag.start(async_fn())
    assert task.state is ag.TaskState.STARTED
    task._throw_exc(ZeroDivisionError)
    assert task.state is ag.TaskState.DONE


@pytest.mark.parametrize('do_suppress', (True, False, ), )
def test_suppress_exception(do_suppress):
    async def async_fn():
        raise ZeroDivisionError
    task = ag.Task(async_fn(), name='pytest')
    task._suppresses_exception = do_suppress
    if do_suppress:
        ag.start(task)
        assert type(task._exception) is ZeroDivisionError
    else:
        with pytest.raises(ZeroDivisionError):
            ag.start(task)
        assert task._exception is None
    assert task.state is TS.CANCELLED


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
    task._step_coro()
    assert task.cancelled
    assert task._cancel_protection == 0


def test_cancel_self():
    import asyncgui as ag

    async def async_fn():
        assert not task._is_cancellable
        task.cancel()
        assert task._cancel_called
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    task = ag.Task(async_fn())
    ag.start(task)
    assert task.cancelled
    assert task._exception is None


def test_cancel_without_start():
    from inspect import getcoroutinestate, CORO_CLOSED
    import asyncgui as ag
    task = ag.Task(ag.sleep_forever())
    task.cancel()
    assert task.cancelled
    assert task._exception is None
    assert getcoroutinestate(task.root_coro) == CORO_CLOSED


def test_try_to_cancel_self_but_no_opportunity_for_that():
    import asyncgui as ag

    async def async_fn():
        assert not task._is_cancellable
        task.cancel()

    task = ag.Task(async_fn())
    ag.start(task)
    assert task.done


def test_weakref():
    import weakref
    import asyncgui as ag
    task = ag.Task(ag.sleep_forever())
    weakref.ref(task)
    task.cancel()
