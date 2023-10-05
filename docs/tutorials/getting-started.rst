.. currentmodule:: nat20

Getting Started
===============

This tutorial will cover the fundamentals of working with nat20 and Pixels Dice.

First, you will need Pixels_ hardware. If you do not have any of their dice, you will need to purchase some.

.. _Pixels: https://gamewithpixels.com/

You will also need Python 3.11 or newer, and some understanding of working with async.

.. note::

   This guide uses type annotations throughout. This is to add clarity of the classes involved in the code samples. Their use in your own code is strictly optional.

0. Install nat20
----------------

The package is ``nat20``. Installing it will vary by your tooling.

.. tab:: Bare venv

   .. code:: shell

      $ pip install nat20

.. tab:: pipenv

   .. code:: shell

     $ pipenv install nat20

.. tab:: poetry

   .. code:: shell
     
     $ poetry add nat20

.. tab:: Other

   There are other tools for managing dependencies in your Python projects. We encourage you to use what works best for your needs.


For Windows, Mac, and Linux, no additional installation or setup is needed.

Overview
--------

nat20 is async only. You can access an async repl with ``python -m async`` (:mod:`more information <asyncio>`). Your general program layout otherwise will be:

.. code:: python

   import asyncio

   async def main():
       print("I'm doing stuff!")

   asyncio.run(main())

Actually working with dice comes in a few phases:

1. Finding the die of interest
2. Connecting to the die
3. Doing the interesting bits

1. Find a die
-------------

The important function here is :func:`nat20.scan_for_dice`. This is an async generator that will endlessly produce :class:`nat20.ScanResult` instances::

   for sr in scan_for_dice():
       print(sr.name)

This data is sometimes called "advertisement data"--it represents the information that active dice openly broadcast. A few caveats though:

* You will not be notified every time this data changes--it's advisory, not authoritative
* Idle dice will sleep, and sleeping dice do not broadcast advertisement data
* :func:`nat20.scan_for_dice` will only produce data based on complete advertisements, which can introduce some lag (the initial advertisement does not have any interesting info)

2. Connect
----------

To receive notifications, trigger blinks, or do other interesting things, you must first connect to the die::

   for sr in scan_for_dice():
       die: Pixel = sr.hydrate()
       break
   await die.connect()

:meth:`ScanResult.hydrate` turns the simple struct into a full :class:`Pixel` class, which provides access to all of the die's functions.

.. todo::
   
   Implement the rest of the die's functions.

:meth:`Pixel.connect` actually reaches out to the die, sets up events, and other initialization. It must be called before performing other actions. (There is also a :meth:`~Pixel.disconnect`.)

Dice may disconnect at any time. Usually because they have been idle and are going to sleep.

A convenience context manager :meth:`~Pixel.connect_with_reconnect` is provided for convenience. But note that it's pretty naive about handling disconnects, and disconnect events can still disrupt actions, and that reconnecting is not guarenteed to succeed. But it works pretty ok for quick scripts. You would use it like::

   async with sr.hydrate().connect_with_reconnect() as die:
       ...

3. Do Interesting Things
------------------------

Ok, so you have a :class:`Pixel` instance connected to the actual hardware, now what?

Basic information is made available on attributes, such as :attr:`~Pixel.roll_face` and :attr:`~Pixel.batt_level`. These are initialized from the :class:`ScanResult` and are updated automatically when the die sends out notifications.

You can be informed directly of these updates with events such as :attr:`Pixel.got_roll_state` or :attr:`Pixel.data_changed`. These use :class:`aioevents.Event`, and can be used as such::

  @die.data_changed.handler
  async def update_items(die: Pixel, fields: set[str]):
      if 'name' in fields:
          ui.die_name = die.name

Please see `the aioevents docs <https://aioevents.readthedocs.io/>`_ for more information on using events.

This information can also be requested directly with methods like :meth:`~Pixel.get_roll_state`, which also provides access to more niche data like :meth:`~Pixel.get_rssi`.

There are also a few methods to request the die perform an action, like :meth:`~Pixel.blink_id` (which requests the die perform a standard identification flash).

How do I read a roll?
---------------------

Ok, so to bring this all together, how do you actually identify and read rolls? Here's one method; we suggest experimentation and doing what works best for your application.

1. Find a die in the process of being rolled.
2. Connect
3. Watch for updates and wait for the roll to finish
4. Spit out the roll result

.. literalinclude:: get-roll.py
   :language: python
   :linenos:
