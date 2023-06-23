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


def test_weakref():
    import weakref
    import asyncgui as ag
    with pytest.raises(Exception):
        weakref.ref(ag.dummy_task)
