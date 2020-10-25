import pytest
pytest.importorskip('trio')


@pytest.mark.trio
async def test_return_value(nursery):
    import trio
    import asyncgui as ag
    from asyncgui.adaptor.to_trio import awaitable_to_coro

    async def ag_func(arg, *, kwarg):
        # ensure this function to be asyncgui-flavored
        e = ag.Event();e.set()
        await e.wait()

        assert arg == 'arg'
        assert kwarg == 'kwarg'
        return 'return_value'

    r = await awaitable_to_coro(ag_func('arg', kwarg='kwarg'))
    assert r == 'return_value'
