import pytest


def test_multiple_tasks():
    import asyncgui as ag
    TS = ag.TaskState
    e = ag.Event()
    task1 = ag.start(e.wait())
    task2 = ag.start(e.wait())
    assert task1.state is TS.STARTED
    assert task2.state is TS.STARTED
    e.set()
    assert task1.state is TS.FINISHED
    assert task2.state is TS.FINISHED


def test_set_before_task_starts():
    import asyncgui as ag
    e = ag.Event()
    e.set()

    async def main():
        await e.wait()

    task = ag.start(main())
    assert task.finished


def test_clear():
    import asyncgui as ag
    e1 = ag.Event()
    e2 = ag.Event()

    async def main():
        nonlocal task_state
        task_state = 'A'
        await e1.wait()
        task_state = 'B'
        await e2.wait()
        task_state = 'C'
        await e1.wait()
        task_state = 'D'

    task_state = None
    ag.start(main())
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

    async def main(e):
        assert await e.wait() == 'A'

    task = ag.start(main(e))
    assert not task.finished
    e.set('A')
    assert task.finished


def test_reset_value():
    import asyncgui as ag
    e = ag.Event()

    async def async_fn1(e):
        assert await e.wait() == 'A'
        e.clear()
        e.set('B')

    async def async_fn2(e):
        assert await e.wait() == 'A'
        assert await e.wait() == 'B'

    task1 = ag.start(async_fn1(e))
    task2 = ag.start(async_fn2(e))
    assert not task1.finished
    assert not task2.finished
    e.set('A')
    assert task1.finished
    assert task2.finished


def test_regular_gen():
    import asyncgui as ag

    def regular_gen():
        yield 1

    with pytest.raises(ValueError):
        ag.start(regular_gen())


def test_weakref():
    import weakref
    from asyncgui import Event
    e = Event()
    weakref.ref(e)
