'''
Pythonのcoro周りの挙動が変わりないかを確かめるだけのテスト。
'''

from inspect import getcoroutinestate, CORO_CLOSED, CORO_CREATED, CORO_SUSPENDED, CORO_RUNNING
import types
import pytest
from contextlib import nullcontext

p = pytest.mark.parametrize


@types.coroutine
def sleep_forever(_f=lambda: None):
    yield _f


async def await_n_times(n):
    for __ in range(n):
        await sleep_forever()


class Test_CORO_CREATED:
    @p('n, state', [(0, CORO_CLOSED), (1, CORO_SUSPENDED)])
    def test_send_None(self, n, state):
        coro = await_n_times(n)
        with pytest.raises(StopIteration) if n == 0 else nullcontext():
            coro.send(None)
        assert getcoroutinestate(coro) == state

    @p("n", [0, 1])
    def test_send_non_None(self, n):
        coro = await_n_times(n)
        with pytest.raises(TypeError):
            coro.send("non-None")
        assert getcoroutinestate(coro) == CORO_CREATED
        coro.close()  # to avoid RuntimeWarning: coroutine 'do_nothing' was never awaited

    @p("n", [0, 1])
    def test_throw(self, n):
        coro = await_n_times(n)
        with pytest.raises(ZeroDivisionError):
            coro.throw(ZeroDivisionError)
        assert getcoroutinestate(coro) == CORO_CLOSED

    @p("n", [0, 1])
    def test_close(self, n):
        coro = await_n_times(n)
        coro.close()
        assert getcoroutinestate(coro) == CORO_CLOSED


class Test_CORO_SUSPENDED:
    @p('n, state', [(1, CORO_CLOSED), (2, CORO_SUSPENDED)])
    @p('value', [None, 'non-None'])
    def test_send(self, n, state, value):
        coro = await_n_times(n)
        coro.send(None)
        assert getcoroutinestate(coro) == CORO_SUSPENDED
        with pytest.raises(StopIteration) if n == 1 else nullcontext():
            coro.send(value)
        assert getcoroutinestate(coro) == state

    @p('n', [1, 2])
    def test_throw(self, n):
        coro = await_n_times(n)
        coro.send(None)
        assert getcoroutinestate(coro) == CORO_SUSPENDED
        with pytest.raises(ZeroDivisionError):
            coro.throw(ZeroDivisionError)
        assert getcoroutinestate(coro) == CORO_CLOSED

    @p('n, state', [(1, CORO_CLOSED), (2, CORO_SUSPENDED)])
    def test_throw_and_caught(self, n, state):
        async def await_n_times(n):
            assert n >= 1
            try:
                await sleep_forever()
            except ZeroDivisionError:
                pass
            for __ in range(n - 1):
                await sleep_forever()

        coro = await_n_times(n)
        coro.send(None)
        assert getcoroutinestate(coro) == CORO_SUSPENDED
        with pytest.raises(StopIteration) if n == 1 else nullcontext():
            coro.throw(ZeroDivisionError)
        assert getcoroutinestate(coro) == state

    @p('n', [1, 2])
    def test_close(self, n):
        coro = await_n_times(n)
        coro.send(None)
        assert getcoroutinestate(coro) == CORO_SUSPENDED
        coro.close()
        assert getcoroutinestate(coro) == CORO_CLOSED


class Test_CORO_CLOSED:
    @pytest.fixture()
    def coro(self):
        coro = await_n_times(0)
        try:
            coro.send(None)
        except StopIteration:
            pass
        assert getcoroutinestate(coro) == CORO_CLOSED
        return coro

    @p('value', [None, 'non-None'])
    def test_send(self, coro, value):
        with pytest.raises(RuntimeError):
            coro.send(value)
        assert getcoroutinestate(coro) == CORO_CLOSED

    def test_throw(self, coro):
        with pytest.raises(RuntimeError):
            coro.throw(ZeroDivisionError)
        assert getcoroutinestate(coro) == CORO_CLOSED

    def test_close(self, coro):
        coro.close()
        assert getcoroutinestate(coro) == CORO_CLOSED


class Test_CORO_RUNNING:
    def test_send(self):
        async def async_fn():
            nonlocal called; called = True
            assert getcoroutinestate(coro) == CORO_RUNNING
            coro.send(None)

        called = False
        coro = async_fn()
        with pytest.raises(ValueError):
            coro.send(None)
        assert getcoroutinestate(coro) == CORO_CLOSED
        assert called

    def test_throw(self):
        async def async_fn():
            nonlocal called; called = True
            assert getcoroutinestate(coro) == CORO_RUNNING
            coro.throw(ZeroDivisionError)

        called = False
        coro = async_fn()
        with pytest.raises(ValueError):
            coro.send(None)
        assert getcoroutinestate(coro) == CORO_CLOSED
        assert called

    def test_close(self):
        async def async_fn():
            nonlocal called; called = True
            assert getcoroutinestate(coro) == CORO_RUNNING
            coro.close()

        called = False
        coro = async_fn()
        with pytest.raises(ValueError):
            coro.send(None)
        assert getcoroutinestate(coro) == CORO_CLOSED
        assert called


def test_GeneratorExit_occurs_when_a_coroutine_gets_garbage_collected():
    async def async_fn():
        try:
            await sleep_forever()
        except GeneratorExit as e:
            nonlocal occurred; occurred = True
            assert not e.args  # これは本来は別のテストであるべきだがコードのかぶりが多いのでここで行う。
            raise

    occurred = False
    coro = async_fn()
    coro.send(None)
    assert not occurred
    del coro
    assert occurred
