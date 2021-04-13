import pytest


def test_concurrency():
    import asyncgui as ag
    from asyncgui.testing.scheduler import open_scheduler

    state = 'started'
    done1 = False
    done2 = False

    async def state_changer(sleep):
        nonlocal state
        await sleep(0.1)
        state = 'A'
        await sleep(0.1)
        state = 'B'
        await sleep(0.1)
        state = 'C'
        nonlocal done1; done1 = True

    async def state_watcher(sleep):
        await sleep(0.05)
        assert state == 'started'
        await sleep(0.1)
        assert state == 'A'
        await sleep(0.1)
        assert state == 'B'
        await sleep(0.1)
        assert state == 'C'
        nonlocal done2; done2 = True


    with open_scheduler() as (schedulr, sleep):
        ag.start(state_changer(sleep))
        ag.start(state_watcher(sleep))
    assert done1
    assert done2
