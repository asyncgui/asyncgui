import pytest


def test_one_child():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx):
        async with ag.open_nursery() as nursery:
            ctx['nursery'] = nursery
            ctx['child'] = nursery.start(ag.sleep_forever())

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    child = ctx['child']
    assert root.state is TS.STARTED
    assert child.state is TS.STARTED
    assert not nursery.closed
    child._step()
    assert root.state is TS.FINISHED
    assert child.state is TS.FINISHED
    assert nursery.closed


def test_one_daemon():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx):
        async with ag.open_nursery() as nursery:
            ctx['nursery'] = nursery
            ctx['daemon'] = nursery.start(ag.sleep_forever(), daemon=True)
            await ag.sleep_forever()

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    daemon = ctx['daemon']
    assert root.state is TS.STARTED
    assert daemon.state is TS.STARTED
    assert not nursery.closed
    root._step()
    assert root.state is TS.FINISHED
    assert daemon.state is TS.CANCELLED
    assert nursery.closed


def test_finish_a_child_while_a_daemon_is_alive():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx):
        async with ag.open_nursery() as nursery:
            ctx['nursery'] = nursery
            ctx['daemon'] = nursery.start(ag.sleep_forever(), daemon=True)
            ctx['child'] = nursery.start(ag.sleep_forever())

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    daemon = ctx['daemon']
    child = ctx['child']
    assert root.state is TS.STARTED
    assert daemon.state is TS.STARTED
    assert child.state is TS.STARTED
    assert not nursery.closed
    child._step()
    assert root.state is TS.FINISHED
    assert daemon.state is TS.CANCELLED
    assert child.state is TS.FINISHED
    assert nursery.closed


def test_cancel_a_child_while_a_daemon_is_alive():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx):
        async with ag.open_nursery() as nursery:
            ctx['nursery'] = nursery
            ctx['daemon'] = nursery.start(ag.sleep_forever(), daemon=True)
            ctx['child'] = nursery.start(ag.sleep_forever())

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    daemon = ctx['daemon']
    child = ctx['child']
    assert root.state is TS.STARTED
    assert daemon.state is TS.STARTED
    assert child.state is TS.STARTED
    assert not nursery.closed
    child.cancel()
    assert root.state is TS.FINISHED
    assert daemon.state is TS.CANCELLED
    assert child.state is TS.CANCELLED
    assert nursery.closed


def test_finish_a_child_and_a_daemon_fails():
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_eventually():
        try:
            await ag.sleep_forever()
        finally:
            raise ZeroDivisionError

    async def async_fn(ctx):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.open_nursery() as nursery:
                ctx['nursery'] = nursery
                ctx['daemon'] = nursery.start(fail_eventually(), daemon=True)
                ctx['child'] = nursery.start(ag.sleep_forever())
            assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    daemon = ctx['daemon']
    child = ctx['child']
    assert root.state is TS.STARTED
    assert daemon.state is TS.STARTED
    assert child.state is TS.STARTED
    assert not nursery.closed
    child._step()
    assert root.state is TS.FINISHED
    assert daemon.state is TS.CANCELLED
    assert child.state is TS.FINISHED
    assert nursery.closed


def test_finish_a_child_and_a_daemon_immediately_fails():
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_imm():
        raise ZeroDivisionError

    async def do_nothing():
        pass

    async def async_fn(ctx):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.open_nursery() as nursery:
                ctx['nursery'] = nursery
                ctx['daemon'] = nursery.start(fail_imm(), daemon=True)
                ctx['child'] = nursery.start(do_nothing())
                await ag.sleep_forever()
                pytest.fail()
            assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    daemon = ctx['daemon']
    child = ctx['child']
    assert root.state is TS.FINISHED
    assert daemon.state is TS.CANCELLED
    assert child.state is TS.FINISHED
    assert nursery.closed


def test_close_nursery():
    import asyncgui as ag
    TS = ag.TaskState

    async def child2_func(nursery):
        await ag.sleep_forever()
        nursery.close()

    async def async_fn(ctx):
        async with ag.open_nursery() as nursery:
            ctx['nursery'] = nursery
            ctx['child1'] = nursery.start(ag.sleep_forever())
            ctx['child2'] = nursery.start(child2_func(nursery))

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    child1 = ctx['child1']
    child2 = ctx['child2']
    assert root.state is TS.STARTED
    assert child1.state is TS.STARTED
    assert child2.state is TS.STARTED
    assert not nursery.closed
    child2._step()
    assert root.state is TS.FINISHED
    assert child1.state is TS.CANCELLED
    assert child2.state is TS.FINISHED
    assert nursery.closed


def test_two_children():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn(ctx):
        async with ag.open_nursery() as nursery:
            ctx['nursery'] = nursery
            ctx['child1'] = nursery.start(ag.sleep_forever())
            ctx['child2'] = nursery.start(ag.sleep_forever())

    ctx = {}
    root = ag.start(async_fn(ctx))
    nursery = ctx['nursery']
    child1 = ctx['child1']
    child2 = ctx['child2']
    assert root.state is TS.STARTED
    assert child1.state is TS.STARTED
    assert child2.state is TS.STARTED
    assert not nursery.closed
    child1._step()
    assert root.state is TS.STARTED
    assert child1.state is TS.FINISHED
    assert child2.state is TS.STARTED
    assert not nursery.closed
    child2._step()
    assert root.state is TS.FINISHED
    assert child1.state is TS.FINISHED
    assert child2.state is TS.FINISHED
    assert nursery.closed


def test_parent_fails():
    import asyncgui as ag

    async def fail_imm():
        raise ZeroDivisionError

    async def fail_eventually():
        try:
            await ag.sleep_forever()
        finally:
            raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.open_nursery() as nursery:
                nursery.start(fail_imm(), daemon=True)
                nursery.start(fail_eventually(), daemon=True)
                nursery.start(fail_imm())
                nursery.start(fail_eventually())
                raise ZeroDivisionError
        assert [ZeroDivisionError, ] * 5 == [type(e) for e in excinfo.value.exceptions]

    root = ag.start(async_fn())
    assert root.finished


def test_garbage_collection():
    import asyncgui as ag

    async def do_nothing():
        pass

    async def async_fn(ctx):
        async with ag.open_nursery(_gc_in_every=3) as nursery:
            ctx['nursery'] = nursery
            nursery.start(ag.sleep_forever())
            nursery.start(do_nothing())
            nursery.start(ctx['e'].wait())

    ctx = {}
    ctx['e'] = e = ag.Event()
    root = ag.start(async_fn(ctx))
    nursery: ag.Nursery = ctx['nursery']
    assert len(nursery._children) == 3
    nursery.start(do_nothing())  # GC-ed
    assert len(nursery._children) == 3
    nursery.start(do_nothing())
    assert len(nursery._children) == 4
    e.fire()
    nursery.start(do_nothing())
    assert len(nursery._children) == 5
    nursery.start(do_nothing())  # GC-ed
    assert len(nursery._children) == 2
    nursery.close()
    assert root.finished
