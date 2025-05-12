import pytest


def test_no_cancel():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
            assert scope._depth == 1
            assert not scope.cancel_called
            assert not scope.closed
            assert task._current_depth == 1
            assert task._requested_cancel_level is None
        assert scope._depth == 1
        assert not scope.cancel_called
        assert scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_cancel():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
            assert scope._depth == 1
            assert not scope.cancel_called
            assert not scope.closed
            assert task._current_depth == 1
            assert task._requested_cancel_level is None
            scope.cancel()
            assert scope._depth == 1
            assert scope.cancel_called
            assert not scope.closed
            assert task._current_depth == 1
            assert task._requested_cancel_level == 1

            await ag.sleep_forever()
            pytest.fail("Failed to cancel")
        assert scope._depth == 1
        assert scope.cancel_called
        assert scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_cancel_neither():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as o_scope:  # o_ -> outer
            assert o_scope._depth == 1
            assert not o_scope.cancel_called
            assert not o_scope.closed
            assert task._current_depth == 1
            assert task._requested_cancel_level is None
            with task._open_cancel_scope() as i_scope:  # i_ -> inner
                assert i_scope._depth == 2
                assert not i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert not o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level is None
            assert i_scope._depth == 2
            assert not i_scope.cancel_called
            assert i_scope.closed
            assert o_scope._depth == 1
            assert not o_scope.cancel_called
            assert not o_scope.closed
            assert task._current_depth == 1
            assert task._requested_cancel_level is None
        assert i_scope._depth == 2
        assert not i_scope.cancel_called
        assert i_scope.closed
        assert o_scope._depth == 1
        assert not o_scope.cancel_called
        assert o_scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_cancel_inner():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as o_scope:
            with task._open_cancel_scope() as i_scope:
                i_scope.cancel()
                assert i_scope._depth == 2
                assert i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert not o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level == 2

                await ag.sleep_forever()
                pytest.fail("Failed to cancel")
            assert i_scope._depth == 2
            assert i_scope.cancel_called
            assert i_scope.closed
            assert o_scope._depth == 1
            assert not o_scope.cancel_called
            assert not o_scope.closed
            assert task._current_depth == 1
            assert task._requested_cancel_level is None
        assert i_scope._depth == 2
        assert i_scope.cancel_called
        assert i_scope.closed
        assert o_scope._depth == 1
        assert not o_scope.cancel_called
        assert o_scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_cancel_outer():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as o_scope:
            with task._open_cancel_scope() as i_scope:
                o_scope.cancel()
                assert i_scope._depth == 2
                assert not i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level == 1

                await ag.sleep_forever()
                pytest.fail("Failed to cancel")
            pytest.fail("Failed to cancel")
        assert i_scope._depth == 2
        assert not i_scope.cancel_called
        assert i_scope.closed
        assert o_scope._depth == 1
        assert o_scope.cancel_called
        assert o_scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_cancel_inner_first():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as o_scope:
            with task._open_cancel_scope() as i_scope:
                i_scope.cancel()
                assert i_scope._depth == 2
                assert i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert not o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level == 2
                o_scope.cancel()
                assert i_scope._depth == 2
                assert i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level == 1

                await ag.sleep_forever()
                pytest.fail("Failed to cancel")
            pytest.fail("Failed to cancel")
        assert i_scope._depth == 2
        assert i_scope.cancel_called
        assert i_scope.closed
        assert o_scope._depth == 1
        assert o_scope.cancel_called
        assert o_scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_cancel_outer_first():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as o_scope:
            with task._open_cancel_scope() as i_scope:
                o_scope.cancel()
                assert i_scope._depth == 2
                assert not i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level == 1
                i_scope.cancel()
                assert i_scope._depth == 2
                assert i_scope.cancel_called
                assert not i_scope.closed
                assert o_scope._depth == 1
                assert o_scope.cancel_called
                assert not o_scope.closed
                assert task._current_depth == 2
                assert task._requested_cancel_level == 1

                await ag.sleep_forever()
                pytest.fail("Failed to cancel")
            pytest.fail("Failed to cancel")
        assert i_scope._depth == 2
        assert i_scope.cancel_called
        assert i_scope.closed
        assert o_scope._depth == 1
        assert o_scope.cancel_called
        assert o_scope.closed
        assert task._current_depth == 0
        assert task._requested_cancel_level is None

    task = ag.start(async_fn())
    assert task.finished


def test_reuse_the_internal_one():
    import asyncgui as ag

    async def async_fn():
        task = await ag.current_task()
        scope = task._open_cancel_scope()
        with scope:
            pass
        with pytest.raises(Exception):
            with scope:
                pass

    task = ag.start(async_fn())
    assert task.finished


@pytest.mark.parametrize('inside', (True, False, ))
@pytest.mark.parametrize('outside', (True, False, ))
def test_cancel_does_not_affect_the_next_scope(inside, outside):
    import asyncgui as ag

    if not (inside or outside):
        return

    async def async_fn():
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
            if inside: scope.cancel()
        if outside: scope.cancel()
        with task._open_cancel_scope() as scope:
            await ag.sleep_forever()

    task = ag.start(async_fn())
    assert task.state is ag.TaskState.STARTED
