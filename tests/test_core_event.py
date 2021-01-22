import pytest


def test_multiple_tasks():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()
    task1 = ag.start(e.wait())
    task2 = ag.start(e.wait())
    assert task1.state == TS.STARTED
    assert task2.state == TS.STARTED
    e.set()
    assert task1.state == TS.DONE
    assert task2.state == TS.DONE


def test_set_before_task_starts():
    import asyncgui as ag
    e = ag.Event()
    e.set()
    async def _task():
        await e.wait()
        nonlocal done; done = True
    done = False
    ag.start(_task())
    assert done


def test_clear():
    import asyncgui as ag
    e1 = ag.Event()
    e2 = ag.Event()
    async def _task():
        nonlocal task_state
        task_state = 'A'
        await e1.wait()
        task_state = 'B'
        await e2.wait()
        task_state = 'C'
        await e1.wait()
        task_state = 'D'
    task_state = None
    ag.start(_task())
    assert task_state == 'A'
    e1.set()
    assert task_state == 'B'
    e1.clear()
    e2.set()
    assert task_state == 'C'
    e1.set()
    assert task_state == 'D'


def test_pass_argument():
    import asyncgui as ag
    e = ag.Event()
    async def task(e):
        assert await e.wait() == ((1, 2, ), {'python': 'awesome', }, )
        nonlocal done; done = True
    done = False
    ag.start(task(e))
    assert not done
    e.set(1, 2, python='awesome')
    assert done
    done = False
    ag.start(task(e))
    assert done


def test_reset_argument_while_resuming_awaited_coroutines():
    import asyncgui as ag
    e = ag.Event()

    async def task1(e):
        assert await e.wait() == (('A', ), {}, )
        e.clear()
        e.set('B')
        nonlocal done1; done1 = True

    async def task2(e):
        assert await e.wait() == (('A', ), {}, )
        assert await e.wait() == (('B', ), {}, )
        nonlocal done2; done2 = True

    done1 = False
    done2 = False
    ag.start(task1(e))
    ag.start(task2(e))
    assert not done1
    assert not done2
    e.set('A')
    assert done1
    assert done2


def test_callback():
    import asyncgui as ag
    e = ag.Event()

    def callback(*args, **kwargs):
        assert args == (1, 2, )
        assert kwargs == {'python': 'awesome', }
        nonlocal done; done = True

    # set after a callback is registered
    done = False
    e.add_callback(callback)
    assert not done
    e.set(1, 2, python='awesome')
    assert done
    e.clear()

    # set before a callback is registered
    done = False
    e.set(1, 2, python='awesome')
    assert not done
    e.add_callback(callback)
    assert done


def test_regular_gen():
    import asyncgui as ag

    def regular_gen():
        yield 1

    with pytest.raises(ValueError):
        ag.start(regular_gen())
