import pytest


def test_concurrency():
    import asyncgui as ag
    from asyncgui.testing import open_scheduler

    state = 'started'

    async def state_changer(sleep):
        nonlocal state
        await sleep(0.1)
        state = 'A'
        await sleep(0.1)
        state = 'B'
        await sleep(0.1)
        state = 'C'

    async def state_watcher(sleep):
        await sleep(0.05)
        assert state == 'started'
        await sleep(0.1)
        assert state == 'A'
        await sleep(0.1)
        assert state == 'B'
        await sleep(0.1)
        assert state == 'C'


    with open_scheduler() as (schedulr, sleep):
        task1 = ag.start(state_changer(sleep))
        task2 = ag.start(state_watcher(sleep))
    assert task1.done
    assert task2.done
