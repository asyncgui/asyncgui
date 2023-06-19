import pytest


@pytest.fixture(scope='module', params=('wait_all_cm', 'wait_any_cm',  'run_as_secondary', 'run_as_primary', ))
def any_cm(request):
    import asyncgui
    return getattr(asyncgui, request.param)


@pytest.fixture(scope='module', params=('wait_any_cm',  'run_as_secondary', ))
def fg_primary_cm(request):
    import asyncgui
    return getattr(asyncgui, request.param)


@pytest.fixture(scope='module', params=('wait_any_cm',  'run_as_primary', ))
def bg_primary_cm(request):
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
            async with any_cm(fail_soon()) as bg_task:
                assert bg_task.state is TS.STARTED
                await ag.sleep_forever()
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED


def test_bg_fails_while_fg_is_running(any_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_soon():
        await ag.sleep_forever()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()) as bg_task:
                assert bg_task.state is TS.STARTED
                bg_task._step()
                assert bg_task.state is TS.CANCELLED
                await ag.sleep_forever()
                pytest.fail()
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_fg_fails_while_bg_is_suspended(any_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(ag.sleep_forever()) as bg_task:
                raise ZeroDivisionError
            pytest.fail()
        assert bg_task.cancelled
        assert bg_task._exc_caught is None
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
            async with any_cm(bg_func()) as bg_task:
                await ag.sleep_forever()
                raise ZeroDivisionError
            pytest.fail()
        assert bg_task.finished
        assert bg_task._exc_caught is None
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    e.set()
    assert fg_task.finished


def test_bg_fails_after_fg_finishes(any_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def fail_soon():
        async with ag.disable_cancellation():
            await e.wait()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()) as bg_task:
                assert bg_task.state is TS.STARTED
            pytest.fail()
        assert [ZeroDivisionError, ] == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.set()
    assert fg_task.state is TS.FINISHED


def test_fg_fails_after_bg_finishes(any_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def finish_imm():
        pass

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(finish_imm()) as bg_task:
                raise ZeroDivisionError
            pytest.fail()
        assert bg_task.finished
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


def test_fg_fails_then_bg_fails_2(any_cm):
    # 裏が停止 -> 表で例外 -> 裏は保護下 -> 発火 -> 裏で例外
    import asyncgui as ag

    async def bg_func():
        async with ag.disable_cancellation():
            await e.wait()
            raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(bg_func()):
                raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert not fg_task.finished
    e.set()
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
    e.set()
    assert fg_task.finished


def test_bg_fails_then_fg_fails_1(any_cm):
    # 裏が停止 -> 表が裏を再開 -> 裏で例外 -> 表で例外
    import asyncgui as ag

    async def fail_soon():
        await ag.sleep_forever()
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_soon()) as bg_task:
                bg_task._step()
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
    e.set()
    assert fg_task.finished


def test_bg_fails_then_fg_fails_3(any_cm):
    # 裏で例外 -> 表は保護下 -> 根で表を再開 -> 表で例外
    import asyncgui as ag

    async def fail_imm():
        raise ZeroDivisionError

    async def async_fn():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            async with any_cm(fail_imm()):
                async with ag.disable_cancellation():
                    await ag.sleep_forever()
                    raise ZeroDivisionError
            pytest.fail()
        assert [ZeroDivisionError, ] * 2 == [type(exc) for exc in excinfo.value.exceptions]

    fg_task = ag.start(async_fn())
    assert not fg_task.finished
    fg_task._step()
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


def test_disable_cancellation_1(fg_primary_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_func(ctx):
        ctx['bg_task'] = await ag.current_task()
        await ag.sleep_forever()
        ctx['fg_task'].cancel()
        await ag.sleep_forever()

    async def async_fn(ctx):
        ctx['fg_task'] = await ag.current_task()
        async with fg_primary_cm(bg_func(ctx)) as bg_task:
            async with ag.disable_cancellation():
                await ag.sleep_forever()
            assert bg_task.state is TS.STARTED
        pytest.fail()

    ctx = {}
    fg_task = ag.start(async_fn(ctx))
    bg_task = ctx['bg_task']
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.STARTED
    bg_task._step()
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.CANCELLED
    assert bg_task.state is TS.CANCELLED


def test_disable_cancellation_2(fg_primary_cm):
    # 1とは違い中断保護を fg_primary_cm の外側で行う
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_func(ctx):
        ctx['bg_task'] = await ag.current_task()
        await ag.sleep_forever()
        ctx['fg_task'].cancel()
        await ag.sleep_forever()

    async def async_fn(ctx):
        ctx['fg_task'] = await ag.current_task()
        async with ag.disable_cancellation():
            async with fg_primary_cm(bg_func(ctx)) as bg_task:
                await ag.sleep_forever()
            assert bg_task.state is TS.CANCELLED
        assert bg_task.state is TS.CANCELLED

    ctx = {}
    fg_task = ag.start(async_fn(ctx))
    bg_task = ctx['bg_task']
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.STARTED
    bg_task._step()
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.FINISHED
    assert bg_task.state is TS.CANCELLED


def test_disable_cancellation_3(bg_primary_cm):
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_func(ctx):
        ctx['bg_task'] = await ag.current_task()
        await ag.sleep_forever()
        ctx['scope'].cancel()
        await ag.sleep_forever()

    async def async_fn(ctx):
        ctx['fg_task'] = await ag.current_task()
        async with bg_primary_cm(bg_func(ctx)) as bg_task:
            async with ag.open_cancel_scope() as scope:
                ctx['scope'] = scope
                async with ag.disable_cancellation():
                    assert bg_task.state is TS.STARTED
                    bg_task._step()
                    assert bg_task.state is TS.STARTED
                    await ag.sleep_forever()
                await ag.sleep_forever()
                pytest.fail()
            await ag.sleep_forever()
            pytest.fail()

    ctx = {}
    fg_task = ag.start(async_fn(ctx))
    bg_task = ctx['bg_task']
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.STARTED
    fg_task._step()
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.STARTED
    bg_task._step()
    assert fg_task.state is TS.FINISHED
    assert bg_task.state is TS.FINISHED


def test_disable_cancellation_4(bg_primary_cm):
    # 3とは違い中断保護を bg_primary_cm の外側で行う
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_func(ctx):
        ctx['bg_task'] = await ag.current_task()
        await ag.sleep_forever()
        ctx['fg_task'].cancel()

    async def async_fn(ctx):
        ctx['fg_task'] = await ag.current_task()
        async with ag.disable_cancellation():
            async with bg_primary_cm(bg_func(ctx)) as bg_task:
                assert bg_task.state is TS.STARTED
                bg_task._step()
                assert bg_task.state is TS.FINISHED
                await ag.sleep_forever()
            assert bg_task.state is TS.FINISHED

    ctx = {}
    fg_task = ag.start(async_fn(ctx))
    bg_task = ctx['bg_task']
    assert fg_task.state is TS.STARTED
    assert bg_task.state is TS.FINISHED
    fg_task._step()
    assert fg_task.state is TS.FINISHED
    assert bg_task.state is TS.FINISHED
