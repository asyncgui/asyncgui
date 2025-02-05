'''
wait_any()が入れ子になっていて なおかつ幾つか中断から護られた子が
ある状況のtest
'''
import pytest


async def protected(e):
    import asyncgui
    async with asyncgui.disable_cancellation():
        await e.wait()


async def main(e1, e2):
    from asyncgui import wait_any
    await wait_any(
        e1.wait(), protected(e1), e2.wait(), protected(e2),
        wait_any(
            e1.wait(), protected(e1), e2.wait(), protected(e2),
        ),
    )


p = pytest.mark.parametrize
@p('set_immediately_1', (True, False, ))
@p('set_immediately_2', (True, False, ))
def test_nested(set_immediately_1, set_immediately_2):
    import asyncgui as ag
    TS = ag.TaskState

    e1 = ag.StatefulEvent()
    e2 = ag.StatefulEvent()
    if set_immediately_1:
        e1.fire()
    if set_immediately_2:
        e2.fire()

    main_task = ag.Task(main(e1, e2))
    ag.start(main_task)
    main_task.cancel()
    if set_immediately_1 and set_immediately_2:
        # 中断の機会を与えられずに終わる為 FINISHED
        assert main_task.state is TS.FINISHED
        return
    assert main_task.state is TS.STARTED
    if set_immediately_1 or set_immediately_2:
        e1.fire()
        e2.fire()
        assert main_task.state is TS.CANCELLED
        return
    e1.fire()
    assert main_task.state is TS.STARTED
    e2.fire()
    assert main_task.state is TS.CANCELLED
