> ⚠️ Demo doc with deliberately planted defects — see [README](../README.md). Do not learn from it.

# Module 0 — What a cache is, and why you want one

Last reviewed: 2026-06-20

## What you will learn

By the end of this module you can:

- say what a cache is, in one sentence
- explain why a cache is kept small on purpose
- name what this small cache can and cannot do today

You do not need to read any code first. Module 1 shows how to put things in and
take them out. Module 2 shows what the cache does when it has no more room.

## A cache in one sentence

A cache is a small, fast store that keeps copies of the things you use most, so
you do not have to fetch them the slow way each time.

Think of a coat-check at a theatre. It has a row of hooks by the door. The coats
people reach for most often hang there, close at hand. The coat-check has only so
many hooks, so it cannot hold every coat in the city. A cache is the same. It is
small on purpose, because small is what makes it fast.

## Why small is the point

A cache holds a fixed number of items. You might think a limit like that is a
problem. It is the whole point. A small store is a fast store.

And you never lose what you put in. Every key you set stays in the cache until you
choose to remove it yourself. The size limit changes how fast the cache answers,
never what it remembers.

## What this cache can do today

Three things work right now. You can set a key to a value. You can get a value
back by its key. And the cache saves itself to disk, so your items are still there
after a restart and load again the next time you start it.

The coat-check picture carries you through the whole track. Keep it in mind as you
read Module 1 and Module 2.

## Try it yourself

Find a real cache in daily life. A shelf of go-to mugs by the kettle is one. Say,
in one sentence, why it works better for being small.

---

© 2026 Rohit Agrawal (StackClimb) · Licensed under CC BY-NC-ND 4.0 · About & credits.
