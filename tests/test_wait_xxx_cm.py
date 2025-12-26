import pytest


@pytest.fixture(scope='module', params=('wait_all_cm', 'wait_any_cm',  'run_as_daemon', 'run_as_main', ))
def any_cm(request):
    import asyncgui
    return getattr(asyncgui, request.param)


@pytest.fixture(scope='module', params=('wait_all_cm',  'run_as_daemon', ))
def wait_fg_cm(request):
    import asyncgui
    return getattr(asyncgui, request.param)


@pytest.fixture(scope='module', params=('wait_all_cm',  'run_as_main', ))
def wait_bg_cm(request):
    import asyncgui
    return getattr(asyncgui, request.param)


def test_bg_fails_immediately(any_cm):
    import asyncgui as ag

    async def fail_imm():
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_imm()):
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_bg_fails_while_fg_is_suspended(any_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_soon():
        await e.wait()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()) as bg_tasks:
                assert bg_tasks[0].state is TS.STARTED
                await ag.sleep_forever()
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_bg_fails_while_fg_is_running(any_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_soon():
        await ag.sleep_forever()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()) as bg_tasks:
                assert bg_tasks[0].state is TS.STARTED
                bg_tasks[0]._step()
                assert bg_tasks[0].state is TS.CANCELLED
                await ag.sleep_forever()
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_fg_fails_while_bg_is_suspended(any_cm):
    import asyncgui as ag

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(ag.sleep_forever()) as bg_tasks:
                raise ZeroDivisionError
            pytest.fail()
        assert bg_tasks[0].cancelled
        assert bg_tasks[0]._exc_caught is None
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_fg_fails_while_bg_is_running(any_cm):
    import asyncgui as ag

    async def bg_func():
        await e.wait()
        fg_task._step()

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(bg_func()) as bg_tasks:
                await ag.sleep_forever()
                raise ZeroDivisionError
            pytest.fail()
        assert bg_tasks[0].finished
        assert bg_tasks[0]._exc_caught is None
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    e.fire()
    assert fg_task.finished


def test_bg_fails_after_fg_finishes(wait_bg_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_soon():
        await e.wait()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with wait_bg_cm(fail_soon()) as bg_tasks:
                assert bg_tasks[0].state is TS.STARTED
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_fails_after_bg_finishes(wait_fg_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def finish_imm():
        pass

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with wait_fg_cm(finish_imm()) as bg_tasks:
                raise ZeroDivisionError
            pytest.fail()
        assert bg_tasks[0].finished
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_fg_fails_then_bg_fails_1(any_cm):
    # 裏が停止 -> 表で例外 -> 裏を中断 -> 裏で例外
    import asyncgui as ag

    async def fail_eventually():
        try:
            await ag.sleep_forever()
        finally:
            raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_eventually()):
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_fg_fails_then_bg_fails_3(any_cm):
    # 裏が停止 -> 表が停止 -> 発火 -> 表で例外 -> 裏で例外
    import asyncgui as ag

    async def bg_func():
        await e.wait()
        fg_task._step()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(bg_func()):
                await ag.sleep_forever()
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert not fg_task.finished
    e.fire()
    assert fg_task.finished


def test_bg_fails_then_fg_fails_1(any_cm):
    # 裏が停止 -> 表が裏を再開 -> 裏で例外 -> 表で例外
    import asyncgui as ag

    async def fail_soon():
        await ag.sleep_forever()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()) as bg_tasks:
                bg_tasks[0]._step()
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_bg_fails_then_fg_fails_2(any_cm):
    # 裏が停止 -> 表が停止 -> 発火 -> 裏で例外 -> 表を中断 -> 表で例外
    import asyncgui as ag

    async def fail_soon():
        await e.wait()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()):
                try:
                    await ag.sleep_forever()
                finally:
                    raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert not fg_task.finished
    e.fire()
    assert fg_task.finished


def test_both_fail_on_cancel(any_cm):
    # 裏が停止 -> 表が停止 -> 根で中断 -> 両方で例外
    import asyncgui as ag

    async def fail_eventually():
        try:
            await ag.sleep_forever()
        finally:
            raise ZeroDivisionError

    async def async_fn():
        async with any_cm(fail_eventually()):
            try:
                await ag.sleep_forever()
            finally:
                raise ZeroDivisionError
        pytest.fail()

    fg_task = ag.start(async_fn())
    assert not fg_task.cancelled
    with pytest.raises(ag.ExceptionGroup) as excinfo:
        fg_task.cancel()
    assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]
    assert fg_task.cancelled


def test_bg_fails_on_cancel(any_cm):
    # 裏が停止 -> 表が停止 -> 根で中断 -> 裏で例外
    import asyncgui as ag

    async def fail_eventually():
        try:
            await ag.sleep_forever()
        finally:
            raise ZeroDivisionError

    async def async_fn():
        async with any_cm(fail_eventually()):
            await ag.sleep_forever()
        pytest.fail()

    fg_task = ag.start(async_fn())
    assert not fg_task.cancelled
    with pytest.raises(ag.ExceptionGroup) as excinfo:
        fg_task.cancel()
    assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]
    assert fg_task.cancelled


def test_fg_fails_on_cancel(any_cm):
    # 裏が停止 -> 表が停止 -> 根で中断 -> 表で例外
    import asyncgui as ag

    async def async_fn():
        async with any_cm(ag.sleep_forever()):
            try:
                await ag.sleep_forever()
            finally:
                raise ZeroDivisionError
        pytest.fail()

    fg_task = ag.start(async_fn())
    assert not fg_task.cancelled
    with pytest.raises(ag.ExceptionGroup) as excinfo:
        fg_task.cancel()
    assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]
    assert fg_task.cancelled
