import pytest


def test_wait():
    import asyncgui as ag

    tc = ag.TaskCounter()
    task = ag.start(tc.to_be_zero())
    assert task.finished


def test_decr_decr():
    import asyncgui as ag

    tc = ag.TaskCounter()
    with pytest.raises(AssertionError):
        tc.decrease()
    with pytest.raises(AssertionError):
        tc.decrease()
    assert tc._n_children == 0


def test_incr_wait_decr():
    import asyncgui as ag

    tc = ag.TaskCounter()
    tc.increase()
    task = ag.start(tc.to_be_zero())
    assert not task.finished
    tc.decrease()
    assert task.finished


def test_incr_decr_wait():
    import asyncgui as ag

    tc = ag.TaskCounter()
    tc.increase()
    tc.decrease()
    task = ag.start(tc.to_be_zero())
    assert task.finished


def test_incr_decr_incr_wait_decr():
    import asyncgui as ag

    tc = ag.TaskCounter()
    tc.increase()
    tc.decrease()
    tc.increase()
    task = ag.start(tc.to_be_zero())
    assert not task.finished
    tc.decrease()
    assert task.finished


def test_boolean():
    import asyncgui as ag

    tc = ag.TaskCounter()
    assert not tc
    tc.increase()
    assert tc
    tc.decrease()
    assert not tc


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, tc):
        with ag.CancelScope(await ag.current_task()) as scope:
            ctx['scope'] = scope
            await tc.to_be_zero()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    tc = ag.TaskCounter()
    tc.increase()
    task = ag.start(async_fn(ctx, tc))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    tc.decrease()
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED
