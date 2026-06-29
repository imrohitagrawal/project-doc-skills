> ⚠️ Demo doc with deliberately planted defects — see [README](../README.md). Do not learn from it.

# Glossary

Last reviewed: 2026-06-20

Plain definitions for every term this track uses. If a word is not clear in a
module, look for it here first.

- **Cache.** A small, fast store that keeps copies of the things you use most, so
  you do not have to fetch them the slow way each time.
- **Key.** The short label you store a value under, and later use to get it back.
- **Value.** The thing you keep in the cache. The key points to it.
- **Capacity.** The largest number of items the cache will hold at once.
- **Least recently used (LRU).** The item that has gone the longest without being
  touched. "Touched" means read or written. This is the item the cache removes
  first when it needs room.
- **Most recently used.** The item you touched last. It is the safest from removal.
- **Miss.** When you ask for a key the cache does not hold.
- **Hit.** When you ask for a key the cache does hold, and get its value back.
- **Touch.** To get or set an item. Touching an item makes it the most recently
  used.

---

© 2026 Rohit Agrawal (StackClimb) · Licensed under CC BY-NC-ND 4.0 · About & credits.
