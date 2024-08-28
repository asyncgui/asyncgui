'''
親がa,b,cの３つの子を持っていて、bが'Box.put()'を呼んだことでaが再開し、
aがそこでbに中断をかけた状況のtest。
'''
import pytest


async def child_a(ctx):
    from inspect import getcoroutinestate, CORO_RUNNING
    import asyncgui as ag
    await ctx['e_begin'].get()
    await ctx['e'].get()
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
        task_a = await ag.current_task()
        task_a.cancel()
        await ag.sleep_forever()
    else:
        pytest.fail(f"Invalid value: {what}")


async def child_b(ctx):
    import asyncgui as ag
    try:
        await ctx['e_begin'].get()
        ctx['e'].put()
    finally:
        if ctx['should_b_fail']:
            raise ZeroDivisionError


async def child_c(ctx):
    import asyncgui as ag
    try:
        await ctx['e_begin'].get()
    finally:
        if ctx['should_c_fail']:
            raise ZeroDivisionError


p = pytest.mark.parametrize
@p('starts_immediately', (True, False, ))
@p('what_a_should_do', 'nothing suspend fail cancel_self'.split())
@p('should_b_fail', (True, False, ))
@p('should_c_fail', (True, False, ))
def test_complicated_case(starts_immediately, what_a_should_do, should_b_fail, should_c_fail):
    import asyncgui as ag

    ctx = {
        'e_begin': ag.Box(),
        'e': ag.Box(),
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
        task_a = ag.Task(child_a(ctx))
        task_b = ctx['task_b'] = ag.Task(child_b(ctx))
        task_c = ag.Task(child_c(ctx))
        if n_exceptions:
            with pytest.raises(ag.ExceptionGroup) as excinfo:
                await ag.wait_any(task_a, task_b, task_c)
            assert [ZeroDivisionError, ] * n_exceptions == [type(e) for e in excinfo.value.exceptions]
        else:
            await ag.wait_any(task_a, task_b, task_c)

    if starts_immediately:
        ctx['e_begin'].put()
    main_task = ag.start(main(ctx))
    if not starts_immediately:
        ctx['e_begin'].put()
    assert main_task.finished
