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
