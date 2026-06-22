# Module 3 — How the request pipeline fits together

Last reviewed: 2026-06-15

## What you will learn

By the end of this module you can:

- name the five steps a request goes through, in order
- say what each step is for, in one short sentence
- spot which step a fault belongs to when something breaks

You do not need to read any code first. We build the picture one step at a time.

## The five steps, in plain words

A request comes in at one end and a result goes out at the other. In between, it
passes through five steps. Each step does one job and hands the work to the next.

1. **Take it in.** The first step reads the request and checks it is well formed.
   Think of a front desk that takes your form and makes sure no box is blank.
2. **Pull out the facts.** The next step picks out the parts the system needs.
   It is like a clerk who highlights the lines that matter and ignores the rest.
3. **Draft the answer.** Now the system writes a first draft of the result.
4. **Run the checks.** The draft is tested against a set of rules before anyone
   sees it. A draft that fails a rule is sent back, not shipped.
5. **Store the result.** The last step saves the result so it can be read later.

Each arrow between steps is a hand-off. If you can name the five steps, you can
follow a request from one end to the other and back.

## Why the order matters

The order is not a free choice. You cannot check a draft before you have written
one, and you cannot write a draft before you know the facts. Each step needs the
one before it to have finished. That is why a fault early on shows up as a strange
result much later: the bad input was carried along the whole way.

## Find the step that broke

When a result looks wrong, you do not need to read the whole system. You walk the
five steps in order and ask a plain question at each one:

- Did the request come in clean? If not, the fault is in step one.
- Were the right facts pulled out? If not, the fault is in step two.
- Was the draft sound? If not, the fault is in step three.
- Did the checks run and pass? If a bad draft slipped through, look at step four.
- Was the result stored and read back the same? If not, the fault is in step five.

The first question that gets a "no" points at the step to fix. This saves you from
guessing, and it works the same way every time.

## A note on what is real today

The first four steps run today. The store step has a known limit: results older
than a year are not yet read back in full. A fuller history view is planned
[designed, not yet built], so do not rely on old results in this module's exercises.

## Try it yourself

Pick any result you have seen and walk the five steps out loud. Say what each step
did with it. If you get stuck, that stuck point is the step to study next.

---

© 2026 Rohit Agrawal (StackClimb) · Licensed under CC BY-NC-ND 4.0 · About & credits.
