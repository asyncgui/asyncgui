def test_bg_finishes_before_fg_ends():
    import asyncgui as ag

    async def async_fn():
        TS = ag.TaskState
        bg_task = ag.Task(ag.sleep_forever())
        with ag.run_and_cancelling(bg_task):
            assert bg_task.state is TS.STARTED
            bg_task._step()
            assert bg_task.state is TS.FINISHED

    fg_task = ag.start(async_fn())
    assert fg_task.finished


def test_fg_finishes_before_bg_ends():
    import asyncgui as ag

    async def async_fn():
        TS = ag.TaskState
        bg_task = ag.Task(ag.sleep_forever())
        with ag.run_and_cancelling(bg_task):
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.CANCELLED

    fg_task = ag.start(async_fn())
    assert fg_task.finished
