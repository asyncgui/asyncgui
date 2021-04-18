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
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert job_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(StopIteration):
        root_coro.send(None)
    assert task.state is TS.DONE
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
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert job_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    root_coro.close()
    assert task.state is TS.CANCELLED
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
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert job_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        root_coro.send(None)
    assert task.state is TS.CANCELLED
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
    assert job_state == 'A'
    with pytest.raises(ag.InvalidStateError):
        task.result

    ag.start(task)
    assert task.state is TS.STARTED
    assert job_state == 'B'
    with pytest.raises(ag.InvalidStateError):
        task.result

    with pytest.raises(ZeroDivisionError):
        root_coro.throw(ZeroDivisionError)
    assert task.state is TS.CANCELLED
    job_state = 'B'
    assert not task.done
    assert task.cancelled
    with pytest.raises(ag.InvalidStateError):
        task.result


@pytest.mark.parametrize(
    'wait_for, should_raise', [
        (TS.CREATED, True, ),
        (TS.STARTED, True, ),
        (TS.DONE, False, ),
        (TS.CANCELLED, False, ),
        (TS.ENDED, False, ),
        (TS.ENDED | TS.STARTED, True, ),
        (TS.DONE | TS.STARTED, True, ),
    ])
def test_various_wait_flag(wait_for, should_raise):
    task = ag.Task(ag.sleep_forever())
    ag.start(task)  # just for suppressing a warning
    coro = task.wait(wait_for)
    if should_raise:
        with pytest.raises(ValueError):
            coro.send(None)
    else:
        coro.send(None)


@pytest.mark.parametrize(
    'wait_for, expected',[
        (TS.DONE, TS.STARTED, ),
        (TS.CANCELLED, TS.DONE, ),
        (TS.ENDED, TS.DONE, ),
    ])
def test_wait_for_an_already_cancelled_task(wait_for, expected):
    task1 = ag.Task(ag.sleep_forever())
    ag.start(task1)
    task1.cancel()
    assert task1.cancelled
    task2 = ag.Task(task1.wait(wait_for))
    ag.start(task2)
    assert task2.state is expected


@pytest.mark.parametrize(
    'wait_for, expected',[
        (TS.DONE, TS.DONE, ),
        (TS.CANCELLED, TS.STARTED, ),
        (TS.ENDED, TS.DONE, ),
    ])
def test_wait_for_an_already_finished_task(wait_for, expected):
    task1 = ag.Task(ag.sleep_forever())
    ag.start(task1)
    with pytest.raises(StopIteration):
        task1.root_coro.send(None)
    assert task1.done
    task2 = ag.Task(task1.wait(wait_for))
    ag.start(task2)
    assert task2.state is expected


def test_cancel_the_waiter_before_the_awaited():
    task1 = ag.Task(ag.sleep_forever())
    task2 = ag.Task(task1.wait())
    ag.start(task1)
    ag.start(task2)
    task2.cancel()
    assert task1.state is TS.STARTED
    assert task2.state is TS.CANCELLED
    with pytest.raises(StopIteration):
        task1.root_coro.send(None)
    assert task1.state is TS.DONE
    assert task2.state is TS.CANCELLED


@pytest.mark.parametrize(
    'wait_for_a, expected_a',[
        (TS.DONE, TS.DONE, ),
        (TS.CANCELLED, TS.STARTED, ),
        (TS.ENDED, TS.DONE, ),
    ])
@pytest.mark.parametrize(
    'wait_for_b, expected_b',[
        (TS.DONE, TS.DONE, ),
        (TS.CANCELLED, TS.STARTED, ),
        (TS.ENDED, TS.DONE, ),
    ])
def test_multiple_tasks_wait_for_the_same_task_to_complete(
        wait_for_a, expected_a, wait_for_b, expected_b, ):
    task1 = ag.Task(ag.sleep_forever())
    task2a = ag.Task(task1.wait(wait_for_a))
    task2b = ag.Task(task1.wait(wait_for_b))
    ag.start(task1)
    ag.start(task2a)
    ag.start(task2b)
    with pytest.raises(StopIteration):
        task1.root_coro.send(None)
    assert task2a.state is expected_a
    assert task2b.state is expected_b


@pytest.mark.parametrize(
    'wait_for_a, expected_a',[
        (TS.DONE, TS.STARTED, ),
        (TS.CANCELLED, TS.DONE, ),
        (TS.ENDED, TS.DONE, ),
    ])
@pytest.mark.parametrize(
    'wait_for_b, expected_b',[
        (TS.DONE, TS.STARTED, ),
        (TS.CANCELLED, TS.DONE, ),
        (TS.ENDED, TS.DONE, ),
    ])
def test_multiple_tasks_wait_for_the_same_task_to_be_cancelled(
        wait_for_a, expected_a, wait_for_b, expected_b, ):
    task1 = ag.Task(ag.sleep_forever())
    task2a = ag.Task(task1.wait(wait_for_a))
    task2b = ag.Task(task1.wait(wait_for_b))
    ag.start(task1)
    ag.start(task2a)
    ag.start(task2b)
    task1.cancel()
    assert task2a.state is expected_a
    assert task2b.state is expected_b


def test_safe_cancel():
    import asyncgui as ag

    async def job1(e):
        await e.wait()
        assert not task1.is_cancellable
        assert not task2.is_cancellable
        task1.safe_cancel()
        task2.safe_cancel()
        await ag.sleep_forever()

    async def job2(e):
        assert task1.is_cancellable
        assert not task2.is_cancellable
        e.set()
        await ag.sleep_forever()

    e = ag.Event()
    task1 = ag.Task(job1(e))
    task2 = ag.Task(job2(e))
    ag.start(task1)
    ag.start(task2)
    assert task1.cancelled
    assert task2.cancelled
