import pytest


def test_wait():
    import asyncgui as ag

    c = ag.Counter()
    task = ag.start(c.wait_for_zero())
    assert task.finished


def test_decr_decr():
    import asyncgui as ag

    c = ag.Counter()
    with pytest.raises(AssertionError):
        c.decrease()
    with pytest.raises(AssertionError):
        c.decrease()
    assert c._value == 0


def test_incr_wait_decr():
    import asyncgui as ag

    c = ag.Counter()
    c.increase()
    task = ag.start(c.wait_for_zero())
    assert not task.finished
    c.decrease()
    assert task.finished


def test_incr_decr_wait():
    import asyncgui as ag

    c = ag.Counter()
    c.increase()
    c.decrease()
    task = ag.start(c.wait_for_zero())
    assert task.finished


def test_incr_decr_incr_wait_decr():
    import asyncgui as ag

    c = ag.Counter()
    c.increase()
    c.decrease()
    c.increase()
    task = ag.start(c.wait_for_zero())
    assert not task.finished
    c.decrease()
    assert task.finished


def test_is_not_zero():
    import asyncgui as ag

    c = ag.Counter()
    assert not c.is_not_zero
    c.increase()
    assert c.is_not_zero
    c.decrease()
    assert not c.is_not_zero


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, c):
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
            ctx['scope'] = scope
            await c.wait_for_zero()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    c = ag.Counter()
    c.increase()
    task = ag.start(async_fn(ctx, c))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    c.decrease()
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED


def test_boolean_conversion():
    import asyncgui as ag

    c = ag.Counter()
    with pytest.raises(NotImplementedError):
        if c:
            pass
    with pytest.raises(NotImplementedError):
        if not c:
            pass
    with pytest.raises(NotImplementedError):
        bool(c)
