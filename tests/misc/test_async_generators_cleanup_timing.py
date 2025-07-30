import pytest


def await_(coro, *, max_steps=10):
    coro_send = coro.send
    try:
        for __ in range(max_steps):
            coro_send(None)
    except StopIteration as e:
        return e.value
    pytest.fail(f'coroutine did not finish in {max_steps} steps')


async def feeder(finishing_order):
    try:
        yield 1
        yield 2
    finally:
        finishing_order.append('feeder')


async def light_eater(finishing_order):
    async for __ in feeder(finishing_order):
        break
    finishing_order.append('eater')
    return 'RETURN'


async def big_eater(finishing_order):
    async for __ in feeder(finishing_order):
        pass
    finishing_order.append('eater')
    return 'RETURN'


def test_when_a_partially_consumed_async_generator_is_cleaned_up():
    import sys
    import gc
    finishing_order = []

    assert await_(light_eater(finishing_order)) == 'RETURN'
    if sys.implementation.name == 'cpython':
        assert finishing_order == ['feeder', 'eater']
    else:
        gc.collect()  # Without this, 'feeder' doesn't appear in the finishing_order list on PyPy.
        assert finishing_order == ['eater', 'feeder']


def test_when_a_partially_consumed_async_generator_is_cleaned_up_under_asyncio():
    import asyncio
    finishing_order = []

    assert asyncio.run(light_eater(finishing_order)) == 'RETURN'
    assert finishing_order == ['eater', 'feeder']


def test_when_a_fully_consumed_async_generator_is_cleaned_up():
    finishing_order = []

    assert await_(big_eater(finishing_order)) == 'RETURN'
    assert finishing_order == ['feeder', 'eater']


def test_when_a_fully_consumed_async_generator_is_cleaned_up_under_asyncio():
    import asyncio
    finishing_order = []

    assert asyncio.run(big_eater(finishing_order)) == 'RETURN'
    assert finishing_order == ['feeder', 'eater']
