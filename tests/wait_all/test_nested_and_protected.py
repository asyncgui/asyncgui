'''
wait_all()が入れ子になっていて なおかつ幾つか中断から護られた子が
ある状況のtest
'''
import pytest


async def protected(e):
    import asyncgui
    async with asyncgui.disable_cancellation():
        await e.get()


async def main(e1, e2):
    from asyncgui import wait_all
    await wait_all(
        e1.get(), protected(e1), e2.get(), protected(e2),
        wait_all(
            e1.get(), protected(e1), e2.get(), protected(e2),
        ),
    )


p = pytest.mark.parametrize
@p('set_immediately_1', (True, False, ))
@p('set_immediately_2', (True, False, ))
def test_nested(set_immediately_1, set_immediately_2):
    import asyncgui as ag
    TS = ag.TaskState

    e1 = ag.Box()
    e2 = ag.Box()
    if set_immediately_1:
        e1.put()
    if set_immediately_2:
        e2.put()

    main_task = ag.Task(main(e1, e2))
    ag.start(main_task)
    main_task.cancel()
    if set_immediately_1 and set_immediately_2:
        # 中断の機会を与えられずに終わる為 FINISHED
        assert main_task.state is TS.FINISHED
        return
    assert main_task.state is TS.STARTED
    if set_immediately_1 or set_immediately_2:
        e1.put()
        e2.put()
        assert main_task.state is TS.CANCELLED
        return
    e1.put()
    assert main_task.state is TS.STARTED
    e2.put()
    assert main_task.state is TS.CANCELLED
