最惡の状況
=============

こうなると ``consumer`` 側のコードはasync generatorを用いない物よりも読みにくくなってしまう。

.. code-block::

    from contextlib import asynccontextmanager
    from inspect import getasyncgenstate, AGEN_SUSPENDED, AGEN_CLOSED
    import string

    import asyncgui as ag

    @asynccontextmanager
    async def aclosing(agen):
        try:
            yield agen
        finally:
            await agen.aclose()


    @asynccontextmanager
    async def safe_exc_propagation(agen, yielded_values: list):
        try:
            yield
        except BaseException as e:
            if getasyncgenstate(agen) is AGEN_SUSPENDED:
                try:
                    yielded_values.append(await agen.athrow(e))
                except StopAsyncIteration:
                    pass
            else:
                raise


    async def producer(e: ag.Event):
        async with ag.move_on_when(e.wait()):
            for i in range(10):
                yield i
        async with ag.move_on_when(e.wait()):
            for c in string.ascii_lowercase:
                yield c
        async with ag.move_on_when(e.wait()):
            for c in string.ascii_uppercase:
                yield c


    def test_the_worst_scenario():
        async def consumer():
            values = []
            async with aclosing(producer(e)) as agen:
                while getasyncgenstate(agen) is not AGEN_CLOSED:
                    async with safe_exc_propagation(agen, values):
                        async for v in agen:
                            values.append(v)
                            await ag.sleep_forever()
            assert values == [0, 'a', 'b', 'A', 'B']
        e = ag.Event()
        task = ag.start(consumer())
        e.fire()
        assert not task.finished
        e.fire()
        assert not task.finished
        e.fire()
        assert task.finished
