import pytest


async def finish_immediately(e=None):
    pass


async def fail_immediately(e=None):
    raise ZeroDivisionError


async def finish_soon(e):
    await e.get()


async def fail_soon(e):
    await e.get()
    raise ZeroDivisionError


async def fail_on_cancel(e=None):
    import asyncgui as ag
    try:
        await ag.sleep_forever()
    finally:
        raise ZeroDivisionError


async def finish_soon_but_protected(e):
    import asyncgui as ag
    async with ag.disable_cancellation():
        await e.get()


def test_no_child():
    import asyncgui as ag

    async def main():
        tasks = await ag.wait_all()
        assert len(tasks) == 0

    main_task = ag.start(main())
    assert main_task.finished


def test_one_child_finishes_immediately():
    import asyncgui as ag

    async def main():
        tasks = await ag.wait_all(finish_immediately())
        assert [True, ] == [task.finished for task in tasks]

    main_task = ag.start(main())
    assert main_task.finished


def test_multiple_children_finish_immediately():
    import asyncgui as ag

    async def main():
        tasks = await ag.wait_all(finish_immediately(), finish_immediately())
        assert [True, True] == [task.finished for task in tasks]

    main_task = ag.start(main())
    assert main_task.finished


def test_one_child_fails_immediately():
    import asyncgui as ag

    async def main():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_all(fail_immediately())
        child_exceptions = excinfo.value.exceptions
        assert len(child_exceptions) == 1
        assert type(child_exceptions[0]) is ZeroDivisionError

    main_task = ag.start(main())
    assert main_task.finished


def test_multiple_children_fail_immediately():
    import asyncgui as ag

    async def main():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_all(fail_immediately(), fail_immediately())
        assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]

    main_task = ag.start(main())
    assert main_task.finished


def test_one_child_finishes_soon():
    import asyncgui as ag

    async def main(e):
        tasks = await ag.wait_all(finish_soon(e))
        assert [True, ] == [task.finished for task in tasks]

    e = ag.Box()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.put()
    assert main_task.finished


def test_multiple_children_finish_soon():
    import asyncgui as ag

    async def main(e):
        tasks = await ag.wait_all(finish_soon(e), finish_soon(e))
        assert [True, True] == [task.finished for task in tasks]

    e = ag.Box()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.put()
    assert main_task.finished


def test_one_child_fails_soon():
    import asyncgui as ag

    async def main(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_all(fail_soon(e))
        child_exceptions = excinfo.value.exceptions
        assert len(child_exceptions) == 1
        assert type(child_exceptions[0]) is ZeroDivisionError

    e = ag.Box()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.put()
    assert main_task.finished


def test_multiple_children_fail_soon():
    '''
    ２つ例外が起こるように思えるが、１つ目の子で例外が起こるや否や２つ目
    は即中断されるため、２つ目では例外は起こらない
    '''
    import asyncgui as ag

    async def main(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_all(fail_soon(e), fail_soon(e))
        child_exceptions = excinfo.value.exceptions
        assert len(child_exceptions) == 1
        assert type(child_exceptions[0]) is ZeroDivisionError

    e = ag.Box()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.put()
    assert main_task.finished


def test_multiple_children_fail():
    '''
    １つ目の子で例外が起こる事で２つ目が中断される。その時２つ目でも例外が
    起きるため２つの例外が湧く。
    '''
    import asyncgui as ag

    async def main(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_all(fail_soon(e), fail_on_cancel())
        assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]

    e = ag.Box()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.put()
    assert main_task.finished


def test_必ず例外を起こす子_を複数持つ親を中断():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_all(fail_on_cancel(), fail_on_cancel())
        assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    main_task = ag.Task(main())
    ag.start(main_task)
    assert main_task.state is TS.STARTED
    main_task.cancel()
    assert main_task.state is TS.CANCELLED


def test_必ず例外を起こす子_を複数持つ親を中断_2():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        await ag.wait_all(fail_on_cancel(), fail_on_cancel())
        pytest.fail("Failed to cancel")

    main_task = ag.Task(main())
    ag.start(main_task)
    assert main_task.state is TS.STARTED
    with pytest.raises(ag.ExceptionGroup) as excinfo:
        main_task.cancel()
    assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]
    assert main_task.state is TS.CANCELLED


def test_例外を起こさない子_を一つ持つ親を中断():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        await ag.wait_all(ag.sleep_forever())
        pytest.fail()

    main_task = ag.Task(main())
    ag.start(main_task)
    assert main_task.state is TS.STARTED
    main_task.cancel()
    assert main_task.state is TS.CANCELLED


def test_例外を起こさない子_を複数持つ親を中断():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        await ag.wait_all(ag.sleep_forever(), ag.sleep_forever())
        pytest.fail()

    main_task = ag.Task(main())
    ag.start(main_task)
    assert main_task.state is TS.STARTED
    main_task.cancel()
    assert main_task.state is TS.CANCELLED


class Test_disable_cancellation:

    @pytest.mark.parametrize('other_child', (fail_on_cancel, fail_immediately))
    def test_other_child_fails(self, other_child):
        import asyncgui as ag

        async def main(e):
            with pytest.raises(ag.ExceptionGroup) as excinfo:
                await ag.wait_all(finish_soon_but_protected(e), other_child(e))
            child_exceptions = excinfo.value.exceptions
            assert len(child_exceptions) == 1
            assert type(child_exceptions[0]) is ZeroDivisionError

        e = ag.Box()
        main_task = ag.Task(main(e))
        ag.start(main_task)
        assert not main_task.finished
        main_task.cancel()
        assert not main_task.finished
        e.put()
        assert main_task.finished

    @pytest.mark.parametrize('other_child', (fail_soon, finish_immediately, finish_soon, finish_soon_but_protected))
    def test_other_child_does_not_fail(self, other_child):
        import asyncgui as ag

        async def main(e):
            await ag.wait_all(finish_soon_but_protected(e), other_child(e))
            pytest.fail("Failed to cancel")

        e = ag.Box()
        main_task = ag.Task(main(e))
        ag.start(main_task)
        assert not main_task.cancelled
        main_task.cancel()
        assert not main_task.cancelled
        e.put()
        assert main_task.cancelled


def test_no_errors_on_GeneratorExit():
    import asyncgui as ag

    async def main():
        try:
            await ag.wait_all(ag.sleep_forever())
        except GeneratorExit:
            nonlocal caught; caught = True
            raise
        await ag.sleep_forever()

    caught = False
    task = ag.start(main())
    task.root_coro.close()
    assert caught
    assert task.cancelled


def test_error_on_scoped_cancel():
    import asyncgui as ag

    async def main():
        async with ag.open_cancel_scope() as scope:
            with pytest.raises(ag.ExceptionGroup) as exc_info:
                scope.cancel()
                await ag.wait_all(fail_on_cancel())
            assert [ZeroDivisionError, ] == [type(e) for e in exc_info.value.exceptions]
            await ag.sleep_forever()
            pytest.fail()

    task = ag.start(main())
    assert task.finished


def test_no_errors_on_scoped_cancel():
    import asyncgui as ag

    async def main():
        async with ag.open_cancel_scope() as scope:
            scope.cancel()
            await ag.wait_all(ag.sleep_forever())
            pytest.fail()

    task = ag.start(main())
    assert task.finished
