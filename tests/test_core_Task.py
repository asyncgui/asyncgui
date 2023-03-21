import pytest


def test_task_state_ended():
    from asyncgui import TaskState as TS
    assert TS.ENDED is (TS.CANCELLED | TS.FINISHED)


def test_the_state_and_the_result():
    import asyncgui as ag
    TS = ag.TaskState

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
    assert task.state is TS.FINISHED
    assert task._exception is None
    assert task.finished
    assert not task.cancelled
    assert task.result == 'result'


def test_the_state_and_the_result__ver_cancel():
    import asyncgui as ag
    TS = ag.TaskState

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
    assert not task.finished
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception():
    '''例外が自然発生した場合'''
    import asyncgui as ag
    TS = ag.TaskState

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
    assert not task.finished
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception_2():
    '''coro.throw()によって例外を起こした場合'''
    import asyncgui as ag
    TS = ag.TaskState

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
    assert not task.finished
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
    assert task.state is ag.TaskState.FINISHED
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
    assert task.state is ag.TaskState.FINISHED


@pytest.mark.parametrize('do_suppress', (True, False, ), )
def test_suppress_exception(do_suppress):
    import asyncgui as ag

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
    assert task.state is ag.TaskState.CANCELLED


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
    assert task.finished


def test_weakref():
    import weakref
    import asyncgui as ag

    task = ag.Task(ag.sleep_forever())
    weakref.ref(task)
    task.cancel()
