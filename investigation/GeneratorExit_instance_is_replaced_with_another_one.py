'''
A行に代えてB行を用いるとユニットテストが通らなくなる事から分かる通り文字列'Hello'が渡らなくなってしまうようである。
またオブジェクトの id() が異なる事からGeneratorExitのインスタンスのすり替えが起こっているようである。
'''

import types
import pytest


@types.coroutine
def sleep_forever():
    yield lambda: None


async def async_fn():
    try:
        await sleep_forever()
    except BaseException as e:
        print(id(e), 'caught')
        if e.args and (e.args[0] == 'Hello'):
            return
    pytest.fail()


async def wrapper():
    return await async_fn()


@pytest.mark.parametrize('exc_cls', (Exception, BaseException, GeneratorExit))
def test_exc(exc_cls):
    print("\n", exc_cls)
    coro = async_fn()  # A
    # coro = wrapper()  # B
    coro.send(None)
    e = exc_cls('Hello')
    print(id(e), 'about to be thrown')
    try:
        coro.throw(e)
    except StopIteration:
        pass


if __name__ == '__main__':
    pytest.main(['-s', __file__])
