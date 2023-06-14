import pytest


def test_set_wait():
    import asyncgui as ag

    sig = ag.ISignal()
    sig.set()
    task = ag.start(sig.wait())
    assert task.finished


def test_wait_set():
    import asyncgui as ag

    sig = ag.ISignal()
    task = ag.start(sig.wait())
    assert not task.finished
    sig.set()
    assert task.finished


def test_set_set():
    import asyncgui as ag

    sig = ag.ISignal()
    sig.set()
    sig.set()


def test_wait_wait_set():
    import asyncgui as ag

    sig = ag.ISignal()
    task = ag.start(sig.wait())
    with pytest.raises(ag.InvalidStateError):
        ag.start(sig.wait())
    assert not task.finished
    sig.set()
    assert task.finished

def test_set_wait_wait():
    import asyncgui as ag

    sig = ag.ISignal()
    sig.set()
    task = ag.start(sig.wait())
    assert task.finished
    task = ag.start(sig.wait())
    assert task.finished


def test_wait_set_wait():
    import asyncgui as ag

    sig = ag.ISignal()
    task = ag.start(sig.wait())
    assert not task.finished
    sig.set()
    assert task.finished
    task = ag.start(sig.wait())
    assert task.finished


def test_wait_set_set():
    import asyncgui as ag

    sig = ag.ISignal()
    task = ag.start(sig.wait())
    assert not task.finished
    sig.set()
    assert task.finished
    sig.set()


def test_cancel():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx, sig):
        async with ag.open_cancel_scope() as scope:
            ctx['scope'] = scope
            await sig.wait()
            pytest.fail()
        await ag.sleep_forever()

    ctx = {}
    sig = ag.ISignal()
    task = ag.start(async_fn(ctx, sig))
    assert task.state is TS.STARTED
    ctx['scope'].cancel()
    assert task.state is TS.STARTED
    sig.set()
    assert task.state is TS.STARTED
    task._step()
    assert task.state is TS.FINISHED
