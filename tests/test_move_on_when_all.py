'''
例外が起きる状況のテストは全て test_wait_xxx_cm.py に任せてあるので、ここではそれ以外の状況のみをテストする。
'''


def test_bg_finishes_immediately():
    import asyncgui as ag
    TS = ag.TaskState

    async def finish_imm():
        pass

    async def async_fn():
        async with ag.move_on_when_all(finish_imm()) as bg_tasks:
            assert bg_tasks[0].state is TS.FINISHED
            await ag.sleep_forever()

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.move_on_when_all(ag.sleep_forever()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
            bg_tasks[0]._step()
            assert bg_tasks[0].state is TS.FINISHED
            await ag.sleep_forever()
        assert bg_tasks[0].state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_finishes_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.move_on_when_all(e.wait()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
            await ag.sleep_forever()
            assert bg_tasks[0].state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_running():
    import asyncgui as ag
    TS = ag.TaskState

    async def bg_fn():
        await e.wait()
        fg_task._step()

    async def async_fn():
        async with ag.move_on_when_all(bg_fn()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
            await ag.sleep_forever()
            assert bg_tasks[0].state is TS.STARTED
        assert bg_tasks[0].state is TS.FINISHED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_bg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.move_on_when_all(e.wait()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
        assert bg_tasks[0].state is TS.CANCELLED

    e = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.FINISHED


def test_bg_tasks_finishes_one_by_one_while_fg_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.move_on_when_all(e1.wait(), e2.wait()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
            assert bg_tasks[1].state is TS.STARTED
            await ag.sleep_forever()
        assert bg_tasks[0].state is TS.FINISHED
        assert bg_tasks[1].state is TS.FINISHED

    e1 = ag.Event()
    e2 = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e1.fire()
    assert fg_task.state is TS.STARTED
    e2.fire()
    assert fg_task.state is TS.FINISHED


def test_fg_finishes_while_one_of_bg_tasks_is_suspended():
    import asyncgui as ag
    TS = ag.TaskState

    async def async_fn():
        async with ag.move_on_when_all(e1.wait(), ag.sleep_forever()) as bg_tasks:
            assert bg_tasks[0].state is TS.STARTED
            assert bg_tasks[1].state is TS.STARTED
            await e2.wait()
        assert bg_tasks[0].state is TS.FINISHED
        assert bg_tasks[1].state is TS.CANCELLED

    e1 = ag.Event()
    e2 = ag.Event()
    fg_task = ag.start(async_fn())
    assert fg_task.state is TS.STARTED
    e1.fire()
    assert fg_task.state is TS.STARTED
    e2.fire()
    assert fg_task.state is TS.FINISHED
