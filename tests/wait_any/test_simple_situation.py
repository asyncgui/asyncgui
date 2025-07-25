import pytest


async def finish_immediately(e=None):
    pass


async def fail_immediately(e=None):
    raise ZeroDivisionError


async def finish_soon(e):
    await e.wait()


async def fail_soon(e):
    await e.wait()
    raise ZeroDivisionError


async def fail_on_cancel(e=None):
    import asyncgui as ag
    try:
        await ag.sleep_forever()
    finally:
        raise ZeroDivisionError


def test_no_child():
    import asyncgui as ag

    async def main():
        tasks = await ag.wait_any()
        assert len(tasks) == 0

    main_task = ag.start(main())
    assert main_task.finished


def test_one_child_finishes_immediately():
    import asyncgui as ag

    async def main():
        tasks = await ag.wait_any(finish_immediately())
        assert [True, ] == [task.finished for task in tasks]

    main_task = ag.start(main())
    assert main_task.finished


def test_multiple_children_finish_immediately():
    import asyncgui as ag

    async def main():
        tasks = await ag.wait_any(finish_immediately(), finish_immediately())
        assert [True, True, ] == [task.finished for task in tasks]

    main_task = ag.start(main())
    assert main_task.finished


def test_one_child_fails_immediately():
    import asyncgui as ag

    async def main():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_any(fail_immediately())
        child_exceptions = excinfo.value.exceptions
        assert len(child_exceptions) == 1
        assert type(child_exceptions[0]) is ZeroDivisionError

    main_task = ag.start(main())
    assert main_task.finished


def test_multiple_children_fail_immediately():
    import asyncgui as ag

    async def main():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_any(fail_immediately(), fail_immediately())
        assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]

    main_task = ag.start(main())
    assert main_task.finished


def test_one_child_finishes_soon():
    import asyncgui as ag

    async def main(e):
        tasks = await ag.wait_any(finish_soon(e))
        assert [True, ] == [task.finished for task in tasks]

    e = ag.StatefulEvent()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.fire()
    assert main_task.finished


def test_multiple_children_finish_soon():
    import asyncgui as ag
    TS = ag.TaskState

    async def main(e):
        tasks = await ag.wait_any(finish_soon(e), finish_soon(e))
        assert [TS.FINISHED, TS.CANCELLED] == [task.state for task in tasks]

    e = ag.StatefulEvent()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.fire()
    assert main_task.finished


def test_one_child_fails_soon():
    import asyncgui as ag

    async def main(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_any(fail_soon(e))
        child_exceptions = excinfo.value.exceptions
        assert len(child_exceptions) == 1
        assert type(child_exceptions[0]) is ZeroDivisionError

    e = ag.StatefulEvent()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.fire()
    assert main_task.finished


def test_multiple_children_fail_soon():
    '''
    ２つの例外が起こるように思えるが、１つ目の子で例外が起こるや否や２つ目
    は即中断されるため、２つ目では例外は起こらない
    '''
    import asyncgui as ag

    async def main(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_any(fail_soon(e), fail_soon(e))
        child_exceptions = excinfo.value.exceptions
        assert len(child_exceptions) == 1
        assert type(child_exceptions[0]) is ZeroDivisionError

    e = ag.StatefulEvent()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.fire()
    assert main_task.finished


def test_multiple_children_fail():
    '''
    １つ目の子で例外が起こる事で２つ目が中断される。その時２つ目でも例外が
    起きるため２つ例外が湧く。
    '''
    import asyncgui as ag

    async def main(e):
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_any(fail_soon(e), fail_on_cancel())
        assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]

    e = ag.StatefulEvent()
    main_task = ag.start(main(e))
    assert not main_task.finished
    e.fire()
    assert main_task.finished


def test_cancel_all_children():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        tasks = await ag.wait_any(child1, child2)
        for task in tasks:
            assert task.cancelled

    child1 = ag.Task(ag.sleep_forever())
    child2 = ag.Task(ag.sleep_forever())
    main_task = ag.start(main())
    assert main_task.state is TS.STARTED
    child1.cancel()
    assert main_task.state is TS.STARTED
    child2.cancel()
    assert main_task.state is TS.FINISHED


def test_必ず例外を起こす子_を複数持つ親を中断():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        with pytest.raises(ag.ExceptionGroup) as excinfo:
            await ag.wait_any(fail_on_cancel(), fail_on_cancel())
        assert [ZeroDivisionError, ZeroDivisionError] == [type(e) for e in excinfo.value.exceptions]
        await ag.sleep_forever()
        pytest.fail("Failed to cancel")

    main_task = ag.start(main())
    assert main_task.state is TS.STARTED
    main_task.cancel()
    assert main_task.state is TS.CANCELLED


def test_必ず例外を起こす子_を複数持つ親を中断_2():
    import asyncgui as ag
    TS = ag.TaskState

    async def main():
        await ag.wait_any(fail_on_cancel(), fail_on_cancel())
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
        await ag.wait_any(ag.sleep_forever())
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
        await ag.wait_any(ag.sleep_forever(), ag.sleep_forever())
        pytest.fail()

    main_task = ag.Task(main())
    ag.start(main_task)
    assert main_task.state is TS.STARTED
    main_task.cancel()
    assert main_task.state is TS.CANCELLED


def test_no_errors_on_GeneratorExit():
    import asyncgui as ag

    async def main():
        try:
            await ag.wait_any(ag.sleep_forever())
        except GeneratorExit:
            nonlocal caught; caught = True
            raise

    caught = False
    task = ag.start(main())
    task.root_coro.close()
    assert caught
    assert task.cancelled


def test_error_on_scoped_cancel():
    import asyncgui as ag

    async def main():
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
            with pytest.raises(ag.ExceptionGroup) as exc_info:
                scope.cancel()
                await ag.wait_any(fail_on_cancel())
            assert [ZeroDivisionError, ] == [type(e) for e in exc_info.value.exceptions]
            await ag.sleep_forever()
            pytest.fail()

    task = ag.start(main())
    assert task.finished


def test_no_errors_on_scoped_cancel():
    import asyncgui as ag

    async def main():
        task = await ag.current_task()
        with task._open_cancel_scope() as scope:
            scope.cancel()
            await ag.wait_any(ag.sleep_forever())
            pytest.fail()

    task = ag.start(main())
    assert task.finished
