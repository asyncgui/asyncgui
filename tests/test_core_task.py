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


def test_the_state_and_the_result__ver_uncaught_exception2():
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


def test_safe_cancel():
    import asyncgui as ag

    async def job1(e):
        await e.wait()
        assert not task1._is_cancellable
        assert not task2._is_cancellable
        task1.safe_cancel()
        task2.safe_cancel()
        await ag.sleep_forever()

    async def job2(e):
        assert task1._is_cancellable
        assert not task2._is_cancellable
        e.set()
        await ag.sleep_forever()

    e = ag.Event()
    task1 = ag.Task(job1(e))
    task2 = ag.Task(job2(e))
    ag.start(task1)
    ag.start(task2)
    assert task1.cancelled
    assert task2.cancelled
