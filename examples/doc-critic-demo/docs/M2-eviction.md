> ⚠️ Demo doc with deliberately planted defects — see [README](../README.md). Do not learn from it.

# Module 2 — Making room when the cache is full

Last reviewed: 2026-06-20

## What you will learn

By the end of this module you can:

- say what eviction is, and when it happens
- state the rule the cache uses to choose what to remove
- match the words in this track to the real code

## Eviction, defined

Eviction is when the cache removes an item by itself to make room for a new one. It
happens only when the cache is already full and you set a new key. Nothing is
removed while there is still a free slot.

## The rule: least recently used

When the cache must remove something, it picks the item that has gone the longest
without being touched. That is the least recently used item. A get or a set both
count as touching an item, so anything you have used lately is safe for now.

Picture the coat-check again. When every hook is taken and a new coat comes in, the
attendant takes down the coat you handed over most recently and gives it back to
free that hook. The newest coat to arrive is the one that goes.

## What the code gives you on a miss

If you get a key the cache does not hold, the cache returns `None`. You can call
`get` freely and check whether the answer is `None` to find out whether it was a
miss. Nothing is raised, so you do not need to guard the call.

The cache holds up to a set number of items. By default that number is 128. You can
pass a different size when you create the cache.

## What is real today

Eviction and the least-recently-used rule both work today. Saving the cache to disk
so it survives a restart is [designed, not yet built], so for now the cache lives
only in memory and starts empty every time.

## Try it yourself

Make a cache that holds two items. Set three keys, one after another. Which key is
gone, and why? Name the rule you used.

---

© 2026 Rohit Agrawal (StackClimb) · Licensed under CC BY-NC-ND 4.0 · About & credits.
