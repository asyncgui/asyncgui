import pytest

async def async_fn():
    pass


def test__unsupported_type():
    import asyncgui as ag

    func = lambda: None
    gen  = (i for i in range(3))

    for v in (func, gen):
        with pytest.raises(ValueError):
            ag.start(v)


def test__return_value():
    import asyncgui as ag

    task = ag.Task(ag.sleep_forever())
    gen_based_coro = ag.sleep_forever()
    coro = async_fn()

    assert ag.start(task) is task
    for v in (gen_based_coro, coro):
        assert isinstance(ag.start(v), ag.Task)


def test__return_value2():
    import asyncgui as ag

    coro = async_fn()
    assert ag.raw_start(coro) is coro


def test__already_started():
    import asyncgui as ag
    task1 = ag.start(ag.sleep_forever())
    task2 = ag.start(async_fn())
    for task in (task1, task2):
        with pytest.raises(ValueError):
            ag.start(task)
