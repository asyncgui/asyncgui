import pytest


def test_multiple_tasks():
    import asyncgui as ag
    e = ag.Event()
    async def _task1():
        await e.wait()
        nonlocal task1_done; task1_done = True
    async def _task2():
        await e.wait()
        nonlocal task2_done; task2_done = True
    task1_done = False
    task2_done = False
    ag.start(_task1())
    ag.start(_task2())
    assert not task1_done
    assert not task2_done
    e.set()
    assert task1_done
    assert task2_done


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
