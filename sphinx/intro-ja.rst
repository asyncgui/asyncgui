=================
Introduction |ja|
=================


既存のライブラリが抱える問題
============================

Pythonには既に幾つかasyncライブラリがあります。
一つはもちろん標準ライブラリの :mod:`asyncio` 。
一つは `構造化された並行性`_ で有名な Trio_ 。
そして ``Trio`` に大きな影響を与えたとみられる Curio_ (ただし今はもう不具合修正を受け付けるのみで機能追加はしない模様)、等々。


それぞれ違いはあると思うのですがどれにも共通して言えるのはGUIプログラムとの相性が悪い事です。
私は何も「GUIライブラリとasyncライブラリはそれぞれがイベントループを持つから同じスレッド内で同居できないよね」と言いたいわけではありません。
実際 PyGame_ の様に利用者側にイベントループの実装を委ねている場合は ``PyGame`` のイベントループをasyncライブラリのいちタスクとして実装してしまえば同居できそうですし、
Kivy_ や BeeWare_ に関しては自身でasyncライブラリに対応してくれてますし、
:mod:`tkinter` や PyQt_ にはそれを可能にする外部ライブラリがあるようです。
仮にそのどれにも当てはまらなかったとしても ``Trio`` には `guest mode`_ という「他のイベントループの邪魔をせずに動作するモード」があるため
同居の問題は解決されていると見做していいのではないでしょうか。


では何故GUIプログラムとの相性が悪いと思うのかと言うと "即座にタスクを開始/再開する機能" を持っていないからです。
例えば ``asyncio`` においてタスクを立ち上げるには :func:`asyncio.create_task` や :meth:`asyncio.TaskGroup.create_task`
を用いると思うのですがどちらも即座ではありません。
一応私の言う"即座"を明確にしておくと次のテストに通ることを意味します。

.. code-block::

    import asyncio

    flag = False


    async def async_fn():
        global flag; flag = True


    async def main():
        asyncio.create_task(async_fn())
        assert flag


    asyncio.run(main())

このテストは通りません。何故なら :func:`asyncio.create_task` は即座にタスクを立ち上げるわけではなく"いずれ"立ち上がるよう予約するからです。
:meth:`asyncio.TaskGroup.create_task` や :meth:`trio.Nursery.start` や :meth:`trio.Nursery.start_soon` も同様です (最後のは"soon"がついているので当たり前ですが)。

再開する機能に関しても同じで :meth:`asyncio.Event.wait` や :meth:`trio.Event.wait` で停まっているタスクは ``Event.set()``
が呼ばれた時に即座に再開するわけではなく"いずれ"再開するよう予約されます。
すなわち以下のテストは通りません。

.. code-block::

    import asyncio

    flag = False


    async def async_fn(e):
        e.set()
        assert flag


    async def main():
        e = asyncio.Event()
        asyncio.create_task(async_fn(e))
        await e.wait()
        global flag; flag = True


    asyncio.run(main())


即座にタスクを開始/再開できないと何が不都合なのでしょうか？
例としてボタンが押されている間だけその背景色を変える次のような疑似コードを考えます。

.. code-block::

    async def ボタンの背景色の切り替え():
        while True:
            await ボタンが押される
            ボタンの背景色を変える
            await ボタンが離される
            ボタンの背景色を戻す

そしてタスクが ``await ボタンが押される`` の地点で停まっている時にユーザーがボタンを押した状況を考えます。
先程言ったように :mod:`asyncio` や :mod:`trio` は即座にはタスクを再開しないのでまだ背景色は変わりません
(なのでユーザーからするとボタンの反応が悪く感じるかもしれませんがこれから起こる事に比べれば些細な事です)。
ここでタスクが再開する前にユーザーがボタンを離すと何が起こるでしょうか？
その後再開したタスクは ``await ボタンが離される`` の地点で停まることになりますが **ユーザーは既にボタンを離しています** 。
なのでタスクは既に終わってしまった出来事を待つ羽目になり、ユーザーが再度ボタンを押して離すまでは背景色が戻らないままになってしまうのです。

.. note::

    Kivy_ では更に状況が悪くなります。Kivyでは入力イベントは状態の変わるオブジェクトで表されていて、即座にコールバック関数内で処理しないと状態が変わってしまう状況があるからです。
    なのでタスクの再開を待つ余裕はありません。

このように出来事をこぼさずに検知しようとすると即座にタスクを開始/再開できないasyncライブラリ達は苦労します。
具体的には"出来事"を一旦蓄える必要がありそうです。コールバック関数を用いた従来のやり方で"出来事"を記録しておき遅れて開始/再開してきたタスクに伝えるのです(つまりはバッファリング)。
このやり方が速度面で実用的なのか分かりませんがとにかく私にはそれぐらいしか思い浮かびませんでした。
それにたとえそれでうまくいったとしてもユーザーがボタンの反応を悪く感じる問題は残ったままです。

以上が ``asyncgui`` が解決した問題であり ``asyncgui`` の存在理由となります。


asyncguiの特徴
==============

即座にタスクを動かす
------------------------

上で挙げた問題は ``asyncgui`` では起きません。何故なら

* :func:`asyncgui.start` と :meth:`asyncgui.Nursery.start` は即座にタスクを立ち上げ
* :meth:`asyncgui.Event.fire` は即座にタスクを再開するからです。

また他の機能も全て即座にタスクを開始/再開します。
ようするに ``asyncgui`` の全ての機能がそのように動くという事です。

イベントループを持たない
-------------------------

冒頭ではイベントループの同居問題に触れましたが ``asyncgui`` ではそれは起こりません。イベントループを持たないからです。
``asyncgui`` は自身ではそれを持たない代わりに別にあるイベントループ(例えばGUIライブラリが持つ物)に乗っかる形で動作します。
ただしその為には ``asyncgui`` とそのイベントループを取り巻くAPIを繋げる作業が必要となります。
これに関しては :doc:`usage-ja` で解説します。

.. note::

    "別にあるイベントループ"は別のasyncライブラリの物でも構いません。
    つまりは(一部制約はあるものの)二つのasyncライブラリを同一スレッド内で動かすことすら可能です。

グローバルな状態を持たない
---------------------------

元々意図していたわけでは無いのですが ``asyncgui`` はグローバルな状態を全く持たない設計になりました。
全ての状態は

* 自由変数 (関数内で定義された別の関数がある時に内側の関数が外側の関数内のローカル変数に触れているとそれは自由変数であり、状態としての性質を持つようになる)
* コルーチンやジェネレーター内のローカル変数
* インスタンス属性

のどれかで表され

* モジュールレベル変数
* クラス属性

で表すことはありません。

.. note::

    他のasyncライブラリはグローバルな状態を持っています。

    例: `asyncio.tasks._current_tasks`_, `trio._core.GLOBAL_CONTEXT`_

単独ではsleepすらできない
--------------------------

驚くかもしれませんが ``asyncgui`` 単独では入出力はおろか ``await sleep(...)`` すらできません。
その実現にはイベントループが要るからです。
そして上で述べたように ``asyncgui`` はイベントループを持ちません...なのでできないわけです。

ただそれはあくまで単独での話であって上で触れた"作業"を行えば可能です。
むしろ其れがこのライブラリの想定された使い方であり、
``asyncgui`` 自体はPython言語(或いはその処理系)にのみに依存する機能の実装が主で外界(OS)とのやりとりはしません。

.. figure:: ./figure/core-concept-ja.*

.. これは良い所でも悪い所でもあると言えます。
   良い所は ``asyncgui`` 自体は極めて軽量で依存パッケージも少ない事です。
   依存している外部パッケージは ``exceptiongroup`` のみなうえ、Python3.11以上を使っているならそれすら要りません。
   悪い所は各イベントループ毎に"糊"が要ることです。
   :mod:`tkinter` を使いたいなら ``tkinter`` 用の糊を、 :mod:`sched` を使いたいなら ``sched`` 用の糊を


.. 終わりに
   ========

.. というわけで他のasyncライブラリとは大きく異なる事が分かっていただけたと思います。
   どちらが優れている劣っているとかではなくそれぞれ良いところ悪いところがあるわけです。
   ``asyncgui`` の悪い所は言うまでもなくそれ単独では使い物にならず"糊"が要ることです。
   `Kivy用の糊`_ と `tkinter用の糊`_ は既に私が開発しているので必要無いのですがそれ以外に関してはあなたが自分で作らないといけません。
   なので次の章 :doc:`usage-ja` では :mod:`sched` 向けの糊を作りながらその具体的な手順を解説していきます。


.. 上で述べたように ``asyncgui`` 自体はOSとのやりとりが必要な機能を持たないので入出力は"糊"に頼むことになるのですが、
   今の所は"糊"にスレッドの機能を持たせそのスレッド上で同期APIによる入出力を行うのが現実的な選択肢です。
   入出力機能の実装にはかなりの労が必要と思われるからです(まだ試してすらいませんが)。
   なので入出力の量はスレッドを用いても耐えられるだけに抑えて下さい。

.. また ``asyncio`` や ``trio`` はただのasyncライブラリではなくて **async入出力ライブラリ** です。
   その入出力の専門家の真似、 `車輪の再発明`_ をすることに価値はあるんでしょうか？
   私としてはそんな事するくらいなら ``asyncgui`` と専門家を同時に走らせて ``asyncgui`` から専門家の機能を利用するための入口を提供する方が合理的だと思っています。
   (その入口は各専門家毎に必要となるため別のモジュールとしての実装となるでしょう)。
   なので現状は入出力周りの機能を"糊"に与える予定はありません。


.. _Trio: https://trio.readthedocs.io/
.. _guest mode: https://trio.readthedocs.io/en/stable/reference-lowlevel.html#using-guest-mode-to-run-trio-on-top-of-other-event-loops
.. _構造化された並行性: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
.. _Curio: https://curio.readthedocs.io/
.. _PyGame: https://www.pygame.org/
.. _Kivy: https://kivy.org/
.. _BeeWare: https://beeware.org/
.. _PyQt: https://www.riverbankcomputing.com/software/pyqt/
.. _車輪の再発明: https://ja.wikipedia.org/wiki/%E8%BB%8A%E8%BC%AA%E3%81%AE%E5%86%8D%E7%99%BA%E6%98%8E

.. _asyncio.tasks._current_tasks: https://github.com/python/cpython/blob/4890bfe1f906202ef521ffd327cae36e1afa0873/Lib/asyncio/tasks.py#L970-L972
.. _trio._core.GLOBAL_CONTEXT: https://github.com/python-trio/trio/blob/722f1b577d4753de5ea1ca5b5b9f2f1a7c6cb56d/trio/_core/_run.py#L1356
