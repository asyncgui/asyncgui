from contextlib import nullcontext
import pytest
import asyncgui as ag


async def producer_marked_as_bomb(e: ag.Event):
    async with ag.move_on_when(e.wait()):
        for i in range(10):
            yield i


@pytest.mark.parametrize("safe", [True, pytest.param(False, marks=pytest.mark.xfail)])
def test_consumer_suspends_in_the_middle_of_iteration_1(safe):
    async def consumer():
        agen = producer_marked_as_bomb(e)
        async with ag.safe_cleanup(agen) if safe else nullcontext():
            async for i in agen:
                await ag.sleep_forever()
    e = ag.Event()
    task = ag.start(consumer())
    e.fire()
    assert task.finished


@pytest.mark.parametrize("safe", [True, pytest.param(False, marks=pytest.mark.xfail)])
def test_consumer_suspends_in_the_middle_of_iteration_2(safe):
    async def consumer():
        agen = producer_marked_as_bomb(e)
        async with ag.safe_cleanup(agen) if safe else nullcontext():
            async for i in agen:
                async with ag.move_on_when(e.wait()):
                    await ag.sleep_forever()
    e = ag.Event()
    task = ag.start(consumer())
    e.fire()
    assert task.finished


@pytest.mark.parametrize("safe", [True, pytest.param(False, marks=pytest.mark.xfail)])
def test_consumer_suspends_in_the_middle_of_iteration_3(safe):
    async def consumer():
        agen = producer_marked_as_bomb(e)
        async with ag.safe_cleanup(agen) if safe else nullcontext():
            async for i in agen:
                async with ag.move_on_when(ag.sleep_forever()):
                    await ag.sleep_forever()
    e = ag.Event()
    task = ag.start(consumer())
    e.fire()
    assert task.finished


@pytest.mark.parametrize("safe", [True, pytest.param(False, marks=pytest.mark.xfail)])
def test_consumer_suspends_in_the_middle_of_iteration_4(safe):
    async def consumer():
        agen = producer_marked_as_bomb(e)
        async with ag.safe_cleanup(agen) if safe else nullcontext():
            async with ag.move_on_when(e2.wait()):
                async for i in agen:
                    await ag.sleep_forever()
    e = ag.Event()
    e2 = ag.Event()
    task = ag.start(consumer())
    e2.fire()
    assert task.finished
