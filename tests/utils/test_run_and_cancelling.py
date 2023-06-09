import pytest


def test_bg_finishes_immediately():
    import asyncgui as ag
    TS = ag.TaskState

    async def do_nothing():
        pass

    async def async_fn():
        async with ag.run_and_cancelling(do_nothing()) as bg_task:
            assert bg_task.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_and_cancelling(ag.sleep_forever()) as bg_task:
            assert bg_task.state is TS.STARTED
            bg_task._step()
            assert bg_task.state is TS.FINISHED
        assert bg_task.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_and_cancelling(e.wait()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.FINISHED
        assert bg_task.state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED


@pytest.mark.parametrize('bg_cancel', (True, False, ))
def test_fg_finishes_while_bg_is_running(bg_cancel):
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_fn():
        await e.wait()
        fg_task._step()
        if bg_cancel:
            await ag.sleep_forever()

    async def async_fn(e):
        async with ag.run_and_cancelling(bg_fn()) as bg_task:
            assert bg_task.state is TS.STARTED
            await ag.sleep_forever()
            assert bg_task.state is TS.STARTED
        assert bg_task.state is (TS.CANCELLED if bg_cancel else TS.FINISHED)

    e = ag.Event()
    fg_task = ag.start(async_fn(e))
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.run_and_cancelling(ag.sleep_forever()) as bg_task:
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.CANCELLED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_fails_immediately():
    import asyncgui as ag

    async def fails_imm():
        raise ZeroDivisionError

    async def async_fn():
        bg_task = ag.Task(fails_imm())
        with pytest.raises(ZeroDivisionError):
            async with ag.run_and_cancelling(bg_task):
                pytest.fail()
            pytest.fail()
        assert type(bg_task._exc_caught) is ZeroDivisionError

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_bg_fails_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def fails_soon(e):
        await e.wait()
        raise ZeroDivisionError

    async def async_fn(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(fails_soon(e)) as bg_task:
                assert bg_task.state is TS.STARTED
                await ag.sleep_forever()
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn(e))
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED


def test_bg_fails_while_fg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def fails_soon():
        await ag.sleep_forever()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(fails_soon()) as bg_task:
                assert bg_task.state is TS.STARTED
                bg_task._step()
                assert bg_task.state is TS.CANCELLED
                assert type(bg_task._exc_caught) is ZeroDivisionError
                await ag.sleep_forever()
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_fg_fails_while_bg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(ag.sleep_forever()) as bg_task:
                raise ZeroDivisionError
            pytest.fail()
        assert bg_task.cancelled
        assert bg_task._exc_caught is None
        assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_fg_fails_and_bg_fails():
    import asyncgui as ag

    async def bg_func():
        await e.wait()
        fg_task._step()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(bg_func()):
                await ag.sleep_forever()
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(e) for e in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    e.set()
    assert fg_task.finished


def test_bg_fails_and_fg_fails():
    import asyncgui as ag

    async def bg_func():
        await ag.sleep_forever()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(bg_func()) as bg_task:
                bg_task._step()
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(e) for e in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_fg_fails_and_bg_fails_on_cancel():
    import asyncgui as ag

    async def fails_eventually():
        try:
            await ag.sleep_forever()
        finally:
            raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(fails_eventually()):
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(e) for e in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_bg_fails_and_fg_fails_on_cancel():
    import asyncgui as ag

    async def bg_func():
        await e.wait()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(bg_func()):
                try:
                    await ag.sleep_forever()
                finally:
                    raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(e) for e in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    e.set()
    assert fg_task.finished


def test_bg_fails_after_fg_finishes():
    import asyncgui as ag

    async def bg_func():
        await e.wait()
        fg_task._step()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(bg_func()):
                await ag.sleep_forever()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    e.set()
    assert fg_task.finished


def test_fg_fails_after_bg_finishes():
    import asyncgui as ag

    async def async_fn():
        fg_task = await ag.current_task()
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with ag.run_and_cancelling(ag.sleep_forever()) as bg_task:
                bg_task._step()
                assert bg_task.finished
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(e) for e in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished
