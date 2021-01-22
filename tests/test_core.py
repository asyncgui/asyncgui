import pytest


def test_get_step_coro():
    import asyncgui as ag
    done = False
    async def job():
        from asyncgui._core import get_step_coro
        step_coro = await get_step_coro()
        assert callable(step_coro)
        nonlocal done;done = True
    ag.start(job())
    assert done


def test__get_current_task__without_task():
    import asyncgui as ag
    done = False
    async def job():
        assert await ag.get_current_task() is None
        nonlocal done;done = True
    ag.start(job())
    assert done


def test__get_current_task():
    import asyncgui as ag
    done = False
    async def job():
        assert await ag.get_current_task() is task
        nonlocal done;done = True
    task = ag.Task(job())
    ag.start(task)
    assert done


def test_gather():
    import asyncgui as ag
    from asyncgui._core import _gather
    events = [ag.Event() for __ in range(3)]
    async def _test():
        tasks = await _gather(
            (event.wait() for event in events),
            n=2,
        )
        assert tasks[0].done
        assert not tasks[1].done
        assert tasks[2].done
        nonlocal done;done = True
    done = False
    ag.start(_test())
    assert not done
    events[0].set()
    assert not done
    events[0].set()
    assert not done
    events[2].set()
    assert done


class Test_or_:
    def test_normal(self):
        import asyncgui as ag
        events = [ag.Event() for __ in range(3)]
        async def _test():
            tasks = await ag.unstructured_or(*(
                event.wait() for event in events))
            assert not tasks[0].done
            assert tasks[1].done
            assert not tasks[2].done
            nonlocal done;done = True
        done = False
        ag.start(_test())
        assert not done
        events[1].set()
        assert done

    @pytest.mark.parametrize("n_do_nothing", range(1, 4))
    def test_some_tasks_immediately_end(self, n_do_nothing):
        '''github issue #3'''
        import asyncgui as ag
        async def do_nothing():
            pass
        async def _test():
            tasks = await ag.unstructured_or(
                *(do_nothing() for __ in range(n_do_nothing)),
                *(ag.Event().wait() for __ in range(3 - n_do_nothing)),
            )
            for task in tasks[:n_do_nothing]:
                assert task.done
            for task in tasks[n_do_nothing:]:
                assert not task.done
            nonlocal done; done = True
        done = False
        ag.start(_test())
        assert done

    def test_zero_task(self):
        import asyncgui as ag
        async def _test():
            tasks = await ag.unstructured_or()
            nonlocal done;done = True
        done = False
        ag.start(_test())
        assert done


class Test_and_:
    def test_normal(self):
        import asyncgui as ag
        events = [ag.Event() for __ in range(3)]
        async def _test():
            tasks = await ag.unstructured_and(*(
                event.wait() for event in events))
            assert tasks[0].done
            assert tasks[1].done
            assert tasks[2].done
            nonlocal done;done = True
        done = False
        ag.start(_test())
        assert not done
        events[1].set()
        assert not done
        events[0].set()
        assert not done
        events[2].set()
        assert done

    @pytest.mark.parametrize("n_coros", range(1, 4))
    def test_all_tasks_immediately_end(self, n_coros):
        '''github issue #3'''
        import asyncgui as ag
        async def do_nothing():
            pass
        async def _test():
            tasks = await ag.unstructured_and(*(
                do_nothing() for __ in range(n_coros)))
            for task in tasks:
                assert task.done
            nonlocal done; done = True
        done = False
        ag.start(_test())
        assert done

    def test_zero_task(self):
        import asyncgui as ag
        async def _test():
            tasks = await ag.unstructured_and()
            nonlocal done;done = True
        done = False
        ag.start(_test())
        assert done


def test_aclosing():
    import asyncgui as ag
    done = False
    agen_closed = False
    async def agen_func():
        try:
            for i in range(10):
                yield i
        finally:
            nonlocal agen_closed;agen_closed = True
    async def job():
        async with ag.aclosing(agen_func()) as agen:
            async for i in agen:
                if i > 1:
                    break
            assert not agen_closed
        assert agen_closed
        nonlocal done;done = True
    ag.start(job())
    assert done
