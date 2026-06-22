# Deploy notes (FIXTURE — contains a deliberate fake secret)

Last reviewed: 2026-06-10

This is a deliberately broken test fixture. The token below is a **synthetic,
non-working** AWS-style access key id, included only so the secret scan can prove
it catches a real-shaped credential on a page. It is not a real key.

```
AWS_ACCESS_KEY_ID=AKIA3MZ7QWERTYUIOPAS
```

A published page must never carry a credential of this shape. The verifier should
FAIL on this line and tell the author to redact it before publishing.

© 2026 Rohit Agrawal (StackClimb) · Internal — not for distribution.
