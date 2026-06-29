> ⚠️ Demo doc with deliberately planted defects — see [README](../README.md). Do not learn from it.

# Module 1 — Putting things in and taking them out

Last reviewed: 2026-06-20

## What you will learn

By the end of this module you can:

- set a key to a value, and get the value back
- say what the cache does each time you touch an item
- explain, in plain words, what a miss is

You met the coat-check picture in Module 0. We use it again here.

## Set: hang a coat on a hook

To put something in, you set a key to a value. The key is a short label. The value
is the thing you want to keep. In the coat-check, the key is your ticket number and
the value is your coat.

If you set a key that is already there, the cache keeps the new value and marks
that item as the most recently used, because you just touched it.

## Get: ask for it back by its key

To read something, you get it by its key. If the key is there, you get its value,
and the cache marks that item as the most recently used too.

Touching an item matters for more than the read. Each time you get or set a key,
the cache remembers it as recent. That running order is what the cache uses to
decide which item it will evict first once it runs out of room. So a get is never
just a read. It also changes what stays and what goes.

## What a miss is

A miss is when you ask for a key the cache does not hold. Module 2 shows the exact
result the code gives you on a miss, and how to handle it in your own code.

## Try it yourself

On paper, set three tickets to three coats. Then get the second ticket. Which item
is now the most recently used? Write your answer down. Module 2 builds on it.

---

© 2026 Rohit Agrawal (StackClimb) · Licensed under CC BY-NC-ND 4.0 · About & credits.
