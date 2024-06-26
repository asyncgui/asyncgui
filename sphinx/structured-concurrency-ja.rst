===========================
Structured Concurrency |ja|
===========================

ここでは `structured concurrency`_ (`構造化された並行性`_) 関連のAPIについて解説していきます。
``構造化された並行性`` が何であるか また何故素晴らしいのかはここでは触れませんので
興味がある人は `Notes on structured concurrency`_ (`不完全な和訳`_) を読んでください。


wait_any
--------

おそらく最も需要があるのはこの機能になると思います。これは複数のタスクを同時に走らせその **いずれか** が完了するまで待ちます。
そしてそれが起こり次第 残りのタスクを中断させます。

.. code-block::

    await wait_any(async_fn1(), async_fn2(), async_fn3())

どのタスクが完了/中断したのか、完了した物の戻り値は何か等は全て戻り値から判別可能です。

.. code-block::

    tasks = await wait_any(async_fn1(), async_fn2(), async_fn3())

    while t, idx in zip(tasks, "123"):
        if t.finished:
            print(f"async_fn{idx}()の戻り値 :", t.result)
        else:
            print(f"async_fn{idx}()は中断されました")

必ず一つだけタスクが完了しているとは限らない事に注意して下さい。全てのタスクが中断されることもあれば複数のタスクが完了することもあります。
そうなる理由としては タスクに中断に対する保護がかけられている や 中断する暇も無く完了してしまう が挙げられますが、
ほとんどの場合 気にしなくて良いでしょう。


wait_all
--------

こちらは全てのタスクが完了/中断するまで待ちます。

.. code-block::

    tasks = await wait_all(async_fn1(), async_fn2(), async_fn3())

どのタスクが完了/中断したのか、完了した物の戻り値は何か等の調べ方は全て ``wait_any`` と同じです。


好きなだけ入れ子に
------------------

``wait_all`` と ``wait_any`` は共に :class:`typing.Awaitable` を返すので当然それを ``wait_all`` や ``wait_any``
の引数に渡すことも可能です。

.. code-block::

    # async_fn1が完了し なおかつ async_fn2かasync_fn3のいずれかが完了するまで待つ
    tasks = await wait_all(
        async_fn1(),
        wait_any(
            async_fn2(),
            async_fn3(),
        ),
    )

.. figure:: ./figure/nested-tasks.*

ただ階層深くにあるタスクを触るまでが面倒くさくなるのが難点です。

.. code-block::

    flattened_tasks = (tasks[0], *tasks[1].result, )

    for t, idx in zip(flattened_tasks, "123"):
        if t.finished:
            print(f"async_fn{idx}()の戻り値 :", t.result)
        else:
            print(f"async_fn{idx}()は中断されました")

入れ子が深くなればなるほど階層深くにあるtaskを触るための式が ``tasks[i].result[j].result[k].result`` といった具合に長くなる
わけですが、このような書き方を好まないのであれば以下の様に :class:`asyncgui.Task` のインスタンスを自ら作って渡せば後は階層には触らずに
タスクの結果を知ることも出来ます。

.. code-block::

    await wait_all(
        async_fn1(),
        wait_any(
            task2 := Task(async_fn2()),  # 自ら作って渡す
            async_fn3(),
        ),
    )
    if tasks2.finished:
        print("async_fn2()の戻り値: ", tasks2.result)
    else:
        print("async_fn2()は中断されました")


wait_any_cm, wait_all_cm
------------------------

``wait_any`` を用いて二つのタスクを並行させるコードは

.. code-block::

    async def async_fn1():
        # async_fn1 の中身

    async def main():
        await wait_any(async_fn1(), async_fn2())

``wait_any_cm`` を用いて以下の様に書くこともできます。

.. code-block::

    async def main():
        async with wait_any_cm(async_fn2()) as task2:
            # async_fn1 の中身

この様に関数の中身をwithブロック内に移す事で関数を一つ減らす事に成功しました。
この機能は ``async_fn1()`` 内で ``main()`` 内のローカル変数をたくさん読み書きしたい時に特に活きるでしょう。
例えば次のコードを見て下さい。

.. code-block::

    async def main():
        var1 = ...
        var2 = ...

        async def async_fn1():
            nonlocal var1, var2
            var1 = ...
            var2 = ...

        await wait_any(async_fn1(), async_fn2())

``async_fn1()`` 内で ``main()`` 内のローカル変数を触りたいが為にこのようにインナー関数として実装したわけですが、
このようなコードは読みにくいだけでなく ``nonlocal`` の書き忘れによるバグを引き起こす可能性も孕んでいます。
これを ``wait_any_cm`` を用いて書き直すとどうなるかというと

.. code-block::

    async def main():
        var1 = ...
        var2 = ...
        async with wait_any_cm(async_fn2()) as task2:
            var1 = ...
            var2 = ...

この様にスッキリします。

.. note::

    この設計は trio_ と trio-util_ から学びました。
    trio というのはまさに `構造化された並行性`_ を具現化したようなライブラリで、その優れた設計は :mod:`asyncio` にも影響を与えるほどです。
    個人的には厳格過ぎて扱いづらいなと感じているのですが それはきっと私が大規模なプログラムを作ったことがないからでしょう。

後このコンテキストマネージャー型のAPIは :class:`typing.Awaitable` を一つしか受け取れないので並行させられるタスクの数に限界があるように
見えますが、先に述べたように入れ子にできるのでその限界は実質無いような物です。

.. code-block::

    async def main():
        async with wait_any_cm(wait_any(...)):
            ...


run_as_daemon
-------------

これまで解説してきたAPIはどれも並行させたタスク達の関係が対等でした。
``wait_any_cm`` を例に挙げるならwithブロック内のコードと ``wait_any_cm`` に渡したタスクのどちらが完了した場合でももう片方を中断させるの
でした。
しかし時には対等ではない関係も必要となります。

.. code-block::

    async with run_as_daemon(async_fn()) as daemon_task:
        ...

このコードではwithブロック内が先に完了した場合は ``async_fn()`` は中断させられますが、 ``async_fn()`` が先に完了しても何も起きず
withブロック内の完了を待つだけです。例えるなら非daemonスレッドとdaemonスレッドの関係です。withブロック内のコードが非daemonで
``async_fn()`` がdaemonになっていると考えて下さい。

.. note::

    これは :func:`trio_util.run_and_cancelling` に相当する機能です。

run_as_main
-----------

これは ``run_as_daemon`` の逆でwithブロック内がdaemonとなります。

.. code-block::

    async with run_as_main(async_fn()) as primary_task:
        ...

すなわちwithブロック内が先に完了した場合は ``async_fn()`` の完了を待つ事になり、
``async_fn()`` が先に完了した場合はwithブロック内が中断されます。


open_nursery
------------

:func:`trio.open_nursery` を真似たものです。
このAPIの利は並行させたいタスクをあらかじめ用意しなくて良い事です。
``nursery`` が開いている限りは後からいくらでも ``nursery.start()`` でタスクを加えられます。

.. code-block::

    async with open_nursery() as nursery:
        while True:
            touch = await 画面に指が触れられるのを待つ
            nursery.start(指に沿って線を引く(touch))

但しタスクの戻り値を得る方法は無いので別の形で値を受け渡してください。

.. seealso:: :class:`asyncgui.Nursery`, `Trio関連の日本語記事`_


例外処理
--------

ここのAPI全てに共通しているのが例外の運ばれ方です。
並行させているタスクの内どれか一つで例外が起きると他のタスクは中断され例外は呼び出し元に運ばれます。
この時 中断された他のタスクがその中断過程で更に例外を起こすかもしれないので例外は複数同時に起こりえます。
このため ``asyncgui`` は例外を運ぶために Python3.11 より登場した :exc:`ExceptionGroup` を用います
(3.11未満のPythonが使われていた場合は exceptiongroup_ を用います)。
これはたとえ例外が一つしか起こらなかった場合でもです。

.. tabs::

    .. group-tab:: 3.11以上

        .. code-block::

            try:
                await wait_any(...)
            except* Exception as excgroup:
                for exc in excgroup.exceptions:
                    print('例外が起きました:', type(exc))
                

    .. group-tab:: 3.11未満

        .. code-block::

            import exceptiongroup

            def error_handler(excgroup):
                for exc in excgroup.exceptions:
                    print('例外が起きました:', type(exc))

            with exceptiongroup.catch({Exception: error_handler, }):
                await wait_any(...)


.. _structured concurrency: https://en.wikipedia.org/wiki/Structured_concurrency
.. _構造化された並行性: https://ja.wikipedia.org/wiki/%E6%A7%8B%E9%80%A0%E5%8C%96%E3%81%95%E3%82%8C%E3%81%9F%E4%B8%A6%E8%A1%8C%E6%80%A7
.. _trio: https://trio.readthedocs.io/
.. _trio-util: https://trio-util.readthedocs.io/
.. _Notes on structured concurrency: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
.. _不完全な和訳: https://qiita.com/gotta_dive_into_python/items/6feb3224a5fa572f1e19
.. _Trio関連の日本語記事: https://qiita.com/tags/trio
.. _exceptiongroup: https://github.com/agronholm/exceptiongroup
