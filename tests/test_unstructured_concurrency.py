import pytest


def test_gather():
    import asyncgui as ag
    from asyncgui.unstructured_concurrency import _gather
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
        from asyncgui.unstructured_concurrency import or_
        events = [ag.Event() for __ in range(3)]
        async def _test():
            tasks = await or_(*(event.wait() for event in events))
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
        from asyncgui.unstructured_concurrency import or_
        async def do_nothing():
            pass
        async def _test():
            tasks = await or_(
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
        from asyncgui.unstructured_concurrency import or_
        async def _test():
            tasks = await or_()
            nonlocal done;done = True
        done = False
        ag.start(_test())
        assert done


class Test_and_:
    def test_normal(self):
        import asyncgui as ag
        from asyncgui.unstructured_concurrency import and_
        events = [ag.Event() for __ in range(3)]
        async def _test():
            tasks = await and_(*(event.wait() for event in events))
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
        from asyncgui.unstructured_concurrency import and_
        async def do_nothing():
            pass
        async def _test():
            tasks = await and_(*(do_nothing() for __ in range(n_coros)))
            for task in tasks:
                assert task.done
            nonlocal done; done = True
        done = False
        ag.start(_test())
        assert done

    def test_zero_task(self):
        import asyncgui as ag
        from asyncgui.unstructured_concurrency import and_
        async def _test():
            tasks = await and_()
            nonlocal done;done = True
        done = False
        ag.start(_test())
        assert done
