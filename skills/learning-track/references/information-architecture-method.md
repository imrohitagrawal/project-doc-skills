# Information architecture — deriving the module map from any project

The goal is a module map that fits *this* project, not a generic template. Use this method to
produce one, then bring it to the owner before writing all the modules.

## Instructional-design constraints (why the structure looks the way it does)

- **One objective per module.** A module teaches one idea. If it needs two, it is two modules.
- **Split at ~20 minutes.** Working memory holds only a handful of items; once a module passes
  roughly twenty minutes of core reading, split it.
- **Meaningful chunks, grouped into parts.** Group modules into a small number of *parts* so readers
  can navigate and self-select depth.
- **Orientation first.** The first module assumes nothing and explains how to read the rest.
- **A glossary runs across everything.** Define terms on first use *and* collect them in one place.
- **A worked example threads through.** One example, deepening as the reader advances.
- **Practice at the end.** A ladder of small projects readers can build themselves.

## Steps

1. **Inventory the project's concepts.** From the repository, ADRs, contracts, and stack, list every
   concept a reader must understand: the problem domain, the lifecycle stages the project touches,
   the architecture and patterns, each significant technology, and (if the project uses AI) the AI
   techniques (prompting, retrieval, tools, agents, evaluation, safety, observability).
2. **Cluster into parts.** Group related concepts. A common, reusable shape:
   - *Orientation* — how to read; who it is for.
   - *The problem and foundations* — the problem in plain words; what software is and how it is built;
     the field basics the project relies on.
   - *How this project is built* — its architecture, how the work was cut into small steps, and how it
     is designed to keep running.
   - *The deep dive* — the techniques that make this project distinctive, taught properly.
   - *Trust, quality, operations* — how the system is tested, proven, monitored, and improved.
   - *Building it yourself, and practice* — how to build responsibly, plus the project ladder.
   Adapt the parts to the project; a data pipeline, a game, and a QA platform will differ.
3. **Turn clusters into modules.** One objective each; split anything over ~20 minutes. Number them
   within parts (M0, M1, M2 …).
4. **Map the worked example across modules.** Decide which slice of the example each module uses, and
   where it runs end to end (usually in the "how it is built" and "trust/quality" parts).
5. **Plan the practice ladder.** If there are several audiences, write one ladder per audience, all
   converging at the top on building a small piece of *this* project. See the blueprint below.
6. **Mark depth and visuals.** For each module, note whether it needs an under-the-hood layer, a
   diagram, or a GIF (a GIF only when motion adds meaning to a *differentiating* idea — see
   `house-style.md` Section 7).

## Per-module blueprint (fill before writing)

For each module record: the single objective; the plain-words story; the under-the-hood points; the
"why" behind each choice it covers; the slice of the worked example; the failure modes to teach; the
diagram(s); the new glossary terms; and 2–3 self-check questions.

## A reusable starting shape (adapt, do not copy blindly)

PART A — Orientation: M0 read this first.
PART B — The problem and foundations: the problem; what software is and the lifecycle; system design
and patterns; the technologies and why; (if AI) the AI foundations.
PART C — How this project is built: the architecture; from zero to phases; designed to run and last.
PART D — The deep dive: the distinctive techniques, one per module, taught with failure modes.
PART E — Trust, quality, operations: testing; proving and securing; feedback loops; monitoring.
PART F — Building it yourself: building responsibly; the practice ladder.
CROSS-CUTTING — glossary; the worked end-to-end example.

## If the project uses AI, the deep dive expands (a transferable shape)

For an AI project, "PART D — the deep dive" is rarely one module — it is the heart of the track, and
the most reusable part of it, because the techniques are the same across AI projects even though the
stack differs. Keep the *concepts* generic so they transfer; keep the project's own ties (its vector
store, its model-routing order, its tool connector) clearly labelled and swappable. A proven module
breakdown to adapt:

- **Talking to models** — prompting and *context engineering* (system instructions, knowledge,
  memory, tools, state), and the build decision: prompt → retrieval → fine-tune → distil
  (fine-tuning changes behaviour, retrieval supplies knowledge; combine for production). The
  prompting toolbox: few-shot, chain-of-thought, schema-constrained output, self-consistency.
- **Giving models knowledge — retrieval (RAG) internals** — embeddings (bi-encoder vs cross-encoder,
  cosine); the chunking menu (fixed, recursive default, semantic, document-aware, hierarchical,
  contextual retrieval) with illustrative sizes clearly labelled "proposed, not locked"; retrieval
  (dense vs sparse/BM25 vs hybrid with reciprocal-rank fusion; re-ranking; metadata filtering; query
  transformation; the lost-in-the-middle effect). The honest lesson: data quality often matters more
  than chunk size, and small focused documents may need no chunking.
- **Giving models hands — tools, function calling, and a tool standard (MCP).** Schema-validated
  tool calls; a standard catalogue (server) exposing tools, resources, and prompts.
- **Giving models autonomy — agents.** The pattern taxonomy (ReAct, Reflection, Planning, Tool Use,
  Multi-Agent, Evaluator-Optimizer, Human-in-the-Loop); control flow (when an agent fires, when it
  stops); agentic retrieval (re-retrieve, self-grade, rewrite). The reality check: most production AI
  failures are architectural, not model quality — start simple, add a pattern only when a failure
  mode demands it.
- **Keeping models safe and affordable** — guardrails (input, retrieval, output rails; the retrieval
  rail guards against instructions hidden in ingested text; the honest caveat that guardrails alone
  are not enough — defence in depth); model routing (cheaper model where it suffices); cost and
  latency discipline (token cost, caching repeated context, right-sizing).

And on the trust side ("PART E"), the AI-specific testing modules:

- **Testing a system whose answers vary** — the oracle problem and non-determinism; evals as the new
  unit tests (golden sets, offline-in-CI plus online-on-traffic); grounding and anti-hallucination
  (faithfulness vs answer-relevancy vs context-recall, and the trap that high faithfulness is not
  correctness); metamorphic and property testing (assert relations under input transformations when
  there is no fixed expected output); the model-as-judge caution (calibrate the judge against a
  human-labelled set).
- **Proving the system is trustworthy and secure** — testing the generated artifacts (mutation
  testing: inject a bug, confirm a test catches it); adversarial and security testing (instructions
  hidden in ingested text are a real threat; defence in depth plus regular red-teaming); the
  *confidence stack* — no single technique suffices, so layer them.
- **Feedback loops** — production signal becomes the ground truth for the next iteration; drift
  detection with alerts and rollback.
- **Monitoring and observability** — the three pillars plus OpenTelemetry; why AI observability
  differs (you need the exact input, parameters, and temperature to reproduce a non-deterministic
  issue; cost tracks tokens; prompts may hold personal data, so store content in span *events*, not
  indexed attributes).

Carry the depth bar from the skill's Step 5 (the retrieval reference set, and the honest-builder
thread) through every module in these two parts.

## If the project was built with AI, Part F opens with "building responsibly" (a transferable shape)

For any project built with the help of an AI coding agent, the first module of Part F is a method
lesson the reader will carry into their own work — and it transfers across projects, because the
discipline is the same whatever the stack. Frame it as guidance for the *reader*, never as a claim
about the author's skill or motives. The reusable breakdown:

- **The trap to name first.** Trading structure for speed — letting an agent generate code by feel
  without design, review, or tests — accumulates compounding debt. AI amplifies both strengths and
  weaknesses; the hard part of software was never the typing. Give a concrete failure: a feature that
  "worked" in a demo but had no tests, no error handling, and a security hole no one read.
- **The evidence, cited and caveated.** Independent measurements have found that a large share of
  AI-generated code ships a common security weakness, and that bigger models have not reliably closed
  the gap. Cite a current, credible measurement precisely (author/title/year + a stable link) and
  **label it as a field finding that can move** — do not fabricate or freeze a specific percentage as
  a constant. State the direction with confidence and any exact figure with care (house style
  Section 4).
- **The operating model that works.** Treat the AI as a *fast junior developer that needs
  supervision*: useful and quick, but not trusted unreviewed. The human stays the architect and the
  final gate; budget time each iteration to pay down the debt the speed creates. Tie this to the
  project's own gates — the reviews, the tests, the human approval step — as the concrete instance of
  the rule.
- **What the reader needs first** — in order: the lifecycle, then AI literacy, then judgement. The
  tools are downstream of those three; a reader who has them can use any agent well, and a reader who
  lacks them is amplified in the wrong direction.
- **The one neutral line, if the project must state it.** If the project was built with AI assistance
  and a *public* page has to say so, use exactly one neutral factual line and no career, hiring, or
  motivation framing (house style Section 8; the profile's AI-assistance note). Internal docs may
  describe the workflow and the tools in full.

Keep all of this project-agnostic; the lesson is the transferable part, and the project's own review
gates are simply the worked example of it. The practice ladder (below) is where the reader then turns
the lesson into doing.

## The practice ladder (a blueprint, adapt to the project)

The practice part is not an afterthought — it is where the reader turns understanding into doing.
Shape it as a *ladder*: small first rungs, each adding one capability, climbing to a capstone that
**reproduces a small slice of this project**.

- **One ladder per audience.** If the track serves several audiences (for example: students;
  professionals from another field; software professionals new to AI), write a ladder for each, in
  that audience's language, all converging at the top on building a piece of the project.
- **Each rung names the one concept it exercises**, and builds on the rung below.
- **The shape of a climb** (illustrative — adapt the rungs to the project's domain): a first tiny
  program → a small useful tool → an app that calls an external service → the project's first
  distinctive technique in isolation → that technique with a quality check around it → a capstone
  that wires several together into a miniature of the real system, with the project's own kind of
  proof (its traceability, its scorecard, its feedback loop).
- **Keep it buildable.** Every rung should be something the reader can finish; point to a public
  sandbox or sample data where a real service is needed.
