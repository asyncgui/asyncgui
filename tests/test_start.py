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


def test__return_value_is_a_Task():
    import asyncgui as ag

    for v in [ag.Task(ag.sleep_forever()), ag.sleep_forever(), async_fn()]:
        r = ag.start(v)
        assert isinstance(r, ag.Task)


def test__already_started():
    import asyncgui as ag
    task1 = ag.start(ag.sleep_forever())
    task2 = ag.start(async_fn())
    for task in (task1, task2):
        with pytest.raises(ValueError):
            ag.start(task)
