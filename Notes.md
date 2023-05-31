# coroの各状態で各methodを呼び出した時に起こる事

*検証環境 CPython3.9.7*

### CORO_CREATED

- `.send()` None以外を送ると `TypeError: can't send non-None value to a just-started coroutine` が起こり、状態はCORO_CREATEDのまま。
- `.throw()` 投げた例外がそのまま湧き、状態がCORO_CLOSEDになる。
- `.close()` 状態がCORO_CLOSEDになる。

### CORO_SUSPENDED

- `.send()` 特に氣になったこと無し。
- `.throw()` 同上。
- `.close()` 同上。

### CORO_CLOSED

- `.send()` `RuntimeError: cannot reuse already awaited coroutine` が起こり、状態はCORO_CLOSEDのまま。
- `.throw()` 同上。
- `.close()` 状態はCORO_CLOSEDのまま。

### CORO_RUNNING

- `.send()` `ValueError: coroutine already executing` が起こり、状態がCORO_CLOSEDになる。
- `.throw()` 同上。
- `.close()` 同上。

## 結果を見て思うこと

起こる例外は全て `TypeError`, `RuntimeError`, `ValueError` といった一般的な物でありcoro専用の物ではないので、これらの例外を捕まえた側のコードがその原因を知るのは容易ではない。なのでlibrary側はこれらの例外がそもそも起きない様に立ち回る必要があると思う。

# 中断を表す独自例外を用いるか否か

独自例外を用いていようがcoroがGCによって捨てられる時には `GeneratorExit` が起きてしまうので利用者はそれから逃れる事は出来ない。結果次のようにして両方の例外に備えないといけない。

```python
def async_func():
    try:
        ...
    except (GeneratorExit, 独自例外):
        中断時に行いたい処理
        raise
```

ただこのやり方だと利用者が片方の例外を書き忘れる怖れがあって危険だと思う。
ではcoroへの参照(実際にはcoroを包んでいるTaskへの参照)を何らかの方法で保持してGCに捨てられないようにしたらどうかという話になりますが、良い方法を思いつかないので独自例外は用いない方向でいく事にする。

### 追記(2023/05/22)

両方の例外を含んだtupleを用意してやれば利用者側が書き忘れる可能性は低いだろう。

```python

Cancelled = (GeneratorExit, 独自例外, )

def async_func():
    try:
        ...
    except Cancelled:
        中断時に行いたい処理
        raise
```

# coro.send()で例外が起きなかった場合でも状態がCORO_CLOSEDになる事がある

`investigation/current_task_enlarges_the_call_stack.py` を実行して分かる通り `current_task()` だけを `await` しているとcall stackは肥っていく。
この時どうやら `Task._step()` が入れ子になって呼び出されているようである。
結果的に内側の `Task._step()` が `StopIteration` を受け取った場合は外側の　`Task._step()` では例外が起こらないのにcoroの状態が `CORO_CLOSED` に変わっている。
この事は `Task._throw_exc()` と `asyncgui.start()` にも言える。
なので `Task._actual_cancel()` を呼ぶ前にはcoroの状態が `CORO_SUSPENDED` であるかの確認が必要と思う。

# 中断scopeが連続した場合の懸念

```python
async def async_fn():
    with open_cancel_scope() as scope1:
        scope1.cancel()
    with open_cancel_scope() as scope2:
        await ...
```

scope1とscope2は深さが同じであるため`scope1.cancel()`はscope2を中断させてしまう。
これを防ぐためにはcontextmanager側が中断を取り消す必要がありそう。

# ExceptionGroupを用いればcoroを閉じた時に発生した例外を外に運べるか？

無理そう。

```python
# 環境 CPython 3.11.0

from types import coroutine


@coroutine
def sleep_forever():
    yield


async def error_on_cleanup():
    try:
        await sleep_forever()
    except GeneratorExit as e:
        raise BaseExceptionGroup("error_on_cleanup", [e, ZeroDivisionError()])


async def no_error_on_cleanup():
    await sleep_forever()


async def outer(async_fn):
    try:
        await async_fn()
    except* GeneratorExit as e:
        print("except* GeneratorExit:", repr(e))
        # raise e.exceptions[0]
        raise
    except* ZeroDivisionError as e:
        print("except* ZeroDivisionError:", repr(e))
    assert False


def main():
    coro = outer(error_on_cleanup)
    coro.send(None)
    coro.close()

    # coro = outer(no_error_on_cleanup)
    # coro.send(None)
    # coro.close()

main()
```
