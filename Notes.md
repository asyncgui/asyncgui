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

独自例外を用いようがcoroがGCによって捨てられる時には `GeneratorExit` が起きてしまうので利用者は次のようにして両方の例外に備えないといけない。

```python
def async_func():
    try:
        ...
    except (GeneratorExit, 独自例外):
        中断時に行いたい処理
        raise
```

ただこのやり方だと利用者が片方の例外を書き忘れる怖れがあって危険だと思う。
じゃあcoroへの参照(実際にはcoroを包んでいるTaskへの参照)を何らかの方法で保持してGCに捨てられないようにして `GeneratorExit` が起こらないようにしたらどうかという話になりますが、良い方法を思いつかないので独自例外は用いない方向でいく事にする。
