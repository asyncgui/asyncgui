import pytest
import asyncgui as ag
TS = ag.TaskState


def test_task_state_ended():
    assert TS.ENDED is (TS.CANCELLED | TS.DONE)


def test_the_state_and_the_result():
    job_state = 'A'
    async def job():
        nonlocal job_state
        job_state = 'B'
        await ag.sleep_forever()
        job_state = 'C'
        return 'result'

    task = ag.Task(job())
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert job_state == 'B'
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
    job_state = 'A'
    async def job():
        nonlocal job_state
        job_state = 'B'
        await ag.sleep_forever()
        job_state = 'C'
        return 'result'

    task = ag.Task(job(), name='pytest')
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert job_state == 'B'
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
    job_state = 'A'
    async def job():
        nonlocal job_state
        job_state = 'B'
        await ag.sleep_forever()
        job_state = 'C'
        raise ZeroDivisionError
        return 'result'

    task = ag.Task(job(), name='pytest')
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert job_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        root_coro.send(None)
    assert task.state is TS.CANCELLED
    assert task._exception is None
    job_state = 'C'
    assert not task.done
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


def test_the_state_and_the_result__ver_uncaught_exception_2():
    '''coro.throw()によって例外を起こした場合'''
    job_state = 'A'
    async def job():
        nonlocal job_state
        job_state = 'B'
        await ag.sleep_forever()
        job_state = 'C'
        return 'result'

    task = ag.Task(job(), name='pytest')
    root_coro = task.root_coro
    assert task.state is TS.CREATED
    assert task._exception is None
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert task._exception is None
    assert job_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        root_coro.throw(ZeroDivisionError)
    assert task.state is TS.CANCELLED
    assert task._exception is None
    job_state = 'B'
    assert not task.done
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


@pytest.mark.parametrize('do_suppress', (True, False, ), )
def test_suppress_exception(do_suppress):
    async def job():
        raise ZeroDivisionError
    task = ag.Task(job(), name='pytest')
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


def test_try_to_cancel_self_but_no_opportunity_for_that():
    import asyncgui as ag

    async def async_fn():
        assert not task._is_cancellable
        task.cancel()

    task = ag.Task(async_fn())
    ag.start(task)
    assert task.done
