def test_background_task_gracefully_ends():
    import asyncgui as ag

    async def async_fn():
        from asyncgui.structured_concurrency import run_and_cancelling
        TS = ag.TaskState
        bg_e = ag.Event()
        bg_task = ag.Task(bg_e.wait())
        with run_and_cancelling(bg_task):
            assert bg_task.state is TS.STARTED
            bg_e.set()
            assert bg_task.state is TS.DONE

    main_task = ag.start(async_fn())
    assert main_task.done


def test_background_task_gets_cancelled():
    import asyncgui as ag

    async def async_fn():
        from asyncgui.structured_concurrency import run_and_cancelling
        TS = ag.TaskState
        bg_task = ag.Task(ag.Event().wait())
        with run_and_cancelling(bg_task):
            assert bg_task.state is TS.STARTED
        assert bg_task.state is TS.CANCELLED

    main_task = ag.start(async_fn())
    assert main_task.done
