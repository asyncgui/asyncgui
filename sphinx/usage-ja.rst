==============
Usage |ja|
==============

ここでは ``asyncgui`` とコールバック型APIの繋げ方を見ていきます。

schedと繋ぐ
===================

:mod:`sched` はタイマー機能のみを提供する非常に簡素なモジュールなので試すにはうってつけでしょう。
まずはこれをそのまま用いて

#. １秒待機
#. ``A`` を出力
#. ２秒待機
#. ``B`` を出力
#. 3秒待機
#. ``C`` を出力

といった処理を書くとどのようになるのか確認しておきます。

.. code-block::

    import sched

    PRIORITY = 0
    s = sched.scheduler()

    def やりたい事():
        def step1():
            print('A')
            s.enter(2, PRIORITY, step2)

        def step2():
            print('B')
            s.enter(3, PRIORITY, step3)

        def step3():
            print('C')

        s.enter(1, PRIORITY, step1)

    やりたい事()
    s.run()

コールバック型のコードはやはり読みづらいですね。
ここでもしかすると「いや :func:`time.sleep` 使えばいいのでは？」といった声が上がるかもしれないので反論しておきます。

「time.sleep 使えばいいのでは？」に対する反論
-----------------------------------------------

確かに ``time.sleep`` を用いれば次のように書けます。

.. code-block::

    from time import sleep

    def やりたい事():
        sleep(1)
        print('A')
        sleep(2)
        print('B')
        sleep(3)
        print('C')

    やりたい事()

しかしこれは ``やりたい事`` が一つしか無いとき限定であり複数あると話が変わってきます。
``time.sleep`` のやり方では複数のスレッドを建てないと複数の事ができないのに対し ``sched`` を用いたやり方はスレッドは一つで足ります。
具体的にはコードの最後の部分で

.. code-block::

    # あくまで一例
    やりたい事()
    やりたい事()
    s.run()

という風に ``やりたい事`` を複数回呼ぶだけです。なので ``time.sleep`` に ``sched`` の代わりは務まらないと言えます。

APIの姿を決める
---------------------

それではこれから糊を作っていくのですが先ずはいま繋げようとしているコールバック型APIである :meth:`sched.scheduler.enter`
を ``asyncgui`` からどのような形で利用したいかを考えないといけません。
これは即ち ``enter()`` のasync/await版がどうあるべきかを考える事です。

ここで先程出てきた ``time.sleep`` の例を思い出して欲しいのですが 確か以下のようなコードでした。

.. code-block::

    from time import sleep

    def やりたい事():
        sleep(1)
        print('A')
        sleep(2)
        print('B')
        sleep(3)
        print('C')

このやり方はスレッドを占有するという短所がある反面、コードがすこぶる読みやすいという利点を持っています。
きっと ``enter()`` のasync/await版もこのように読みやすいと使う側は嬉しいんじゃないでしょうか？
具体的には以下の感じです。

.. code-block::

    async def やりたい事():
        await sleep(1)
        print('A')
        await sleep(2)
        print('B')
        await sleep(3)
        print('C')

これが実現すれば ``time.sleep`` の物とほぼ同等の読みやすさを保った上でスレッドを占有しないという良いとこ取りができた事になります [#obtain_cancellation]_ 。
なのでこの様な姿を目指す事にしましょう。

``await sleep(1)`` という使い方をするという事は ``sleep`` は :class:`collections.abc.Awaitable` を返す :class:`collections.abc.Callable`
でないといけません。
その条件を満たす実装方法は幾つか有るのですが、とりあえずその一つであるasync関数 [#async_func_mitasu]_ から考えてみます。

.. code-block::

    async def sleep(duration):
        ...

こう書きたいところなのですが ``enter()`` はインスタンスメソッドなのでインスタンスを渡さないと呼びようがありませんし、
このメソッドは ``priority`` という引数も取るのでそれも渡してあげた方が良いと思います。

.. code-block::

    async def sleep(scheduler, priority, duration):
        ...

というわけでこの姿を目指して実装にとりかかりましょう。

.. そもそもコールバック型のコードが読みづらいのはコードが細切れになってしまうからです。
   本来は一つの関数に纏めるべき処理であったとしてもその中に「〇秒経ってから〇〇する」や「〇〇が起こった時に〇〇する」のような"待ち"があると
   関数をそこで分割せざるを得ません。
   しかし処理の進行を一時停止できるasync/awaitの世界では話が変わってきます。
   "待ち"が必要な時には一時停止して文字通り待てばいいだけなのですから。

実装
----

コールバック型のAPIをasync/awaitの世界と繋ぐにはコールバック関数が呼ばれた時に処理が再開するように仕組んだ上で処理を停止させる必要があります。
難しそうに聞こえますが :class:`asyncio.Event` や :class:`trio.Event` を使った事があればピンと来るんじゃないでしょうか？

.. code-block::

    import asyncio

    async def 糊():
        e = asyncio.Event()

        # コールバック関数が呼ばれた時に処理が再開するように仕組む
        コールバック関数を登録(lambda *args, **kwargs: e.set())

        # 処理を停止する
        await e.wait()

    async def 利用者():
        print('A')
        await 糊()
        print('B')

このように ``糊`` を介する事で ``利用者`` 側のコードは読みやすさを保った状態でコールバック型のAPIを使えるようになります。
そして同等の機能は ``asyncgui`` にもあります。

.. code-block::

    import asyncgui

    async def 糊():
        e = asyncgui.Event()
        コールバック関数を登録(e.set)  # A
        await e.wait()

``asyncgui`` の場合は :meth:`asyncgui.Event.set` がどんな引数でも受け取れるようになっているのでlambdaを挟まなくて済むのがちょっとした売りです(A行)。
とはいえこれが繋げ方の本筋というわけではありません。 ``asyncgui`` にはこういった用途の為により特化された物があります。

.. code-block::

    import asyncgui

    async def 糊():
        sig = asyncgui.ISignal()
        コールバック関数を登録(sig.set)
        await sig.wait()

``Event`` というのは複数のタスクが ``await Event.wait()`` を同時に呼んでも良い様になっています。
しかし今回のような使われ方では絶対に一つのタスクからしか呼ばれません。
であればそれ専用の物があってもいいのでは？と思って :class:`asyncgui.ISignal` を作りました。
``ISignal`` は同時に複数のタスクが ``await sig.wait()`` しようとすると例外を起こしてそれを許しません。
その代わり ``Event`` のように複数のタスクを保持する為の ``list`` を持たずに済んでいます。
せっかくなのでこれ用いて ``sleep`` を実装していきましょう。

.. code-block::

    import asyncgui

    async def sleep(scheduler, priority, duration):
        sig = asyncgui.ISignal()
        scheduler.enter(duration, priority, sig.set)
        await sig.wait()

これでめでたく以下のように分かりやすく ``やりたい事`` が書けるようになりました...

.. code-block::

    import functools
    import sched
    import asyncgui

    async def sleep(...):
        省略

    def main():
        s = sched.scheduler()
        asyncgui.start(やりたい事(s))
        s.run()

    async def やりたい事(s: sched.scheduler):
        slp = functools.partial(sleep, s, 0)
        await slp(1)
        print('A')
        await slp(2)
        print('B')
        await slp(3)
        print('C')

    main()

と言いたい所なのですがもう一つやっておきたい事があり、それは中断への対応です。
最低限の対応は ``ISignal`` が行っているので ``sleep`` 内で行うことは必須ではないのですがやっておく方がより良いです。
(参考: :ref:`dealing-with-cancellation`)

.. code-block::

    import asyncgui

    async def sleep(scheduler, priority, duration):
        sig = asyncgui.ISignal()
        event = scheduler.enter(duration, priority, sig.set)
        try:
            await sig.wait()
        except asyncgui.Cancelled:
            scheduler.cancel(event)
            raise

これで完璧に ``sched`` を ``asyncgui`` と繋ぐ事に成功しました。
一度繋ぐ事ができれば ``asyncgui`` の持つ強力な :doc:`structured-concurrency-ja` の恩恵を受けられます。

.. code-block::

    import functools
    import sched
    import asyncgui
    import string

    async def sleep(scheduler, priority, duration):
        省略

    def main():
        s = sched.scheduler()
        asyncgui.start(アルファベットと数字のどちらが先に出力し終わるかの競争(s))
        s.run()

    async def アルファベットと数字のどちらが先に出力し終わるかの競争(s: sched.scheduler):
        slp = functools.partial(sleep, s, 0)

        tasks = await asyncgui.wait_any(
            一文字づつ間を置いて出力(slp, string.ascii_lowercase),
            一文字づつ間を置いて出力(slp, string.digits),
        )
        if tasks[0].finished:
            print("\nアルファベットが先に終わりました")
        else:
            print("\n数字が先に終わりました")

    async def 一文字づつ間を置いて出力(slp, msg, *, interval=0.1):
        for c in msg:
            print(c, end=' ')
            await slp(interval)

    main()

::

    a 0 b 1 c 2 d 3 e 4 f 5 g 6 h 7 i 8 j 9 k 
    数字が先に終わりました


機能拡張
========

ただ実際に上で作った物を用いて何かのプログラムを作ろうとするとまだ不便な気がします。
:mod:`sched` がタイマー機能しか持たない事を考えると「何時間毎に何かを行う」や「この日時になったら何かを行う」といった目的に利用される事が思い浮かぶのですが、
その"何か"は何である事が多いでしょうか？
私はファイルシステムやネットワークとのやりとりが多い気がします。
ところが ``sched`` は :mod:`asyncio` や :mod:`trio` のように入出力機能を備えていません。
ということは現状 :func:`open` や :mod:`requests` のような同期APIに頼るしか無いことになります。

(...執筆中)


.. [#obtain_cancellation] 加えて強力な中断能力も手に入ります。
.. [#async_func_mitasu] async関数は関数なので勿論 ``Callable`` ですし戻り値は必ず ``Awaitable`` の一種である ``Coroutine`` なので条件を満たします。
