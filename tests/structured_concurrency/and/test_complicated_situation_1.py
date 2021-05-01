'''
親がa,b,cの３つの子を持っていて、bが'Event.set()'を呼んだことでaが再開し、
aがそこでbに中断をかけた状況のtest。
'''
import pytest


async def child_a(ctx):
    from inspect import getcoroutinestate, CORO_RUNNING
    import asyncgui as ag
    await ctx['e_begin'].wait()
    await ctx['e'].wait()
    task_b = ctx['task_b']
    assert getcoroutinestate(task_b.root_coro) == CORO_RUNNING
    task_b.cancel()
    what = ctx['what_a_should_do']
    if what == 'nothing':
        return
    elif what == 'suspend':
        await ag.sleep_forever()
    elif what == 'fail':
        raise ZeroDivisionError
    elif what == 'cancel_self':
        task_a = await ag.get_current_task()
        task_a.cancel()
        await ag.sleep_forever()
    else:
        pytest.fail(f"Invalid value: {what}")


async def child_b(ctx):
    import asyncgui as ag
    try:
        await ctx['e_begin'].wait()
        ctx['e'].set()
    finally:
        if ctx['should_b_fail']:
            raise ZeroDivisionError


async def child_c(ctx):
    import asyncgui as ag
    try:
        await ctx['e_begin'].wait()
    finally:
        if ctx['should_c_fail']:
            raise ZeroDivisionError


p = pytest.mark.parametrize
@p('starts_immediately', (True, False, ))
@p('what_a_should_do', 'nothing suspend fail cancel_self'.split())
@p('should_b_fail', (True, False, ))
@p('should_c_fail', (True, False, ))
def test_complicated_case(
    starts_immediately, what_a_should_do, should_b_fail, should_c_fail,
):
    import asyncgui as ag
    TS = ag.TaskState

    ctx = {
        'e_begin': ag.Event(),
        'e': ag.Event(),
        'what_a_should_do': what_a_should_do,
        'should_b_fail': should_b_fail,
        'should_c_fail': should_c_fail,
    }
    n_exceptions = 0
    if what_a_should_do == 'fail':
        n_exceptions += 1
    if should_b_fail:
        n_exceptions += 1
    if should_c_fail:
        n_exceptions += 1

    async def main(ctx):
        from asyncgui.structured_concurrency import and_
        task_a = ag.Task(child_a(ctx))
        task_b = ctx['task_b'] = ag.Task(child_b(ctx))
        task_c = ag.Task(child_c(ctx))
        if n_exceptions == 1:
            with pytest.raises(ZeroDivisionError):
                await and_(task_a, task_b, task_c)
        elif n_exceptions:
            with pytest.raises(ag.MultiError) as excinfo:
                await and_(task_a, task_b, task_c)
            assert [ZeroDivisionError, ] * n_exceptions == \
                [type(e) for e in excinfo.value.exceptions]
        else:
            await and_(task_a, task_b, task_c)

    if starts_immediately:
        ctx['e_begin'].set()
    main_task = ag.start(main(ctx))
    if not starts_immediately:
        ctx['e_begin'].set()
    if should_c_fail or should_b_fail or what_a_should_do != 'suspend':
        assert main_task.state is TS.DONE
    else:
        assert main_task.state is TS.STARTED
