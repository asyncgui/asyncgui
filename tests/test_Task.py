import sys
import pytest


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
    assert task.state is TS.CREATED
    assert task._exc_caught is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exc_caught is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(StopIteration):
        task.root_coro.send(None)
    assert task.state is TS.FINISHED
    assert task._exc_caught is None
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

    task = ag.Task(async_fn())
    assert task.state is TS.CREATED
    assert task._exc_caught is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exc_caught is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    task.cancel()
    assert task.state is TS.CANCELLED
    assert task._exc_caught is None
    assert not task.finished
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception():
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

    task = ag.Task(async_fn())
    assert task.state is TS.CREATED
    assert task._exc_caught is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exc_caught is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        task.root_coro.send(None)
    assert task.state is TS.CANCELLED
    assert type(task._exc_caught) is ZeroDivisionError
    assert task_state == 'C'
    assert not task.finished
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception_2():
    '''Task._throw_exc()によって例外を起こした場合'''
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
    assert task.state is TS.CREATED
    assert task._exc_caught is None
    assert task_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exc_caught is None
    assert task_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        task._throw_exc(ZeroDivisionError)
    assert task.state is TS.CANCELLED
    assert type(task._exc_caught) is ZeroDivisionError
    assert task_state == 'B'
    assert not task.finished
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_throw_exc_to_unstarted_task():
    import asyncgui as ag
    TS = ag.TaskState

    task = ag.Task(ag.sleep_forever())
    assert task.state is TS.CREATED
    with pytest.raises(ag.InvalidStateError):
        task._throw_exc(ZeroDivisionError)
    assert task.state is TS.CREATED
    assert task._exc_caught is None
    task.cancel()  # to avoid RuntimeWarning: coroutine 'xxx' was never awaited
    assert task.state is TS.CANCELLED
    assert task._exc_caught is None


def test_throw_exc_to_cancelled_task():
    import asyncgui as ag
    TS = ag.TaskState

    task = ag.start(ag.sleep_forever())
    assert task.state is TS.STARTED
    task.cancel()
    assert task.state is TS.CANCELLED
    assert task._exc_caught is None
    with pytest.raises(ag.InvalidStateError):
        task._throw_exc(ZeroDivisionError)
    assert task.state is TS.CANCELLED
    assert task._exc_caught is None


def test_throw_exc_to_finished_task():
    import asyncgui as ag

    async def async_func():
        pass

    task = ag.start(async_func())
    assert task.finished
    with pytest.raises(ag.InvalidStateError):
        task._throw_exc(ZeroDivisionError)
    assert task.finished
    assert task._exc_caught is None


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
    assert task._exc_caught is None
    task._throw_exc(ZeroDivisionError)
    assert task.state is ag.TaskState.FINISHED
    assert task._exc_caught is None


@pytest.mark.parametrize('do_suppress', (True, False, ), )
def test_suppress_exception(do_suppress):
    from contextlib import nullcontext
    import asyncgui as ag

    async def async_fn():
        raise ZeroDivisionError

    task = ag.Task(async_fn())
    task._suppresses_exc = do_suppress
    with nullcontext() if do_suppress else pytest.raises(ZeroDivisionError):
        ag.start(task)
    assert type(task._exc_caught) is ZeroDivisionError
    assert task.state is ag.TaskState.CANCELLED


def test_cancel_self():
    import asyncgui as ag

    async def async_fn():
        assert not task._is_cancellable
        task.cancel()
        assert task._cancel_requested
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    task = ag.Task(async_fn())
    ag.start(task)
    assert task.cancelled
    assert task._exc_caught is None


def test_cancel_without_starting_it():
    import asyncgui as ag

    task = ag.Task(ag.sleep_forever())
    task.cancel()
    assert task._cancel_requested
    assert task.cancelled
    assert task._exc_caught is None


def test_try_to_cancel_self_but_no_opportunity_for_that():
    import asyncgui as ag

    async def async_fn():
        assert not task._is_cancellable
        task.cancel()

    task = ag.Task(async_fn())
    ag.start(task)
    assert task.finished


@pytest.mark.skipif(sys.implementation.name == "pypy", reason="Couldn't figure out how to prevent weakrefs from being created")
def test_making_a_weakref_should_raise_an_exception():
    import weakref
    import asyncgui as ag
    with pytest.raises(Exception):
        weakref.ref(ag.dummy_task)
