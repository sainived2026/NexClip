# Prompt Anti-Patterns — Detection & Correction Catalog

A comprehensive catalog of common prompt anti-patterns that reduce output quality. Detect these during Stage 5 of the Enhancement Pipeline and apply the specified correction.

---

## Critical Anti-Patterns (Always Fix)

### 1. The XY Problem
**Signal:** User asks about their attempted solution, not the actual problem.
**Example:** "How do I parse the JWT token header in Python?" (when the real problem is "users are getting 401 errors")
**Correction:** Surface the real problem. Ask: "What's the outcome you're trying to achieve?" Then solve at the root.

### 2. Premature Solution Lock-In
**Signal:** "Use Redis for caching" before evaluating whether caching is the right approach, or whether Redis is the right cache.
**Correction:** Reframe as goal ("reduce API response time from 3s to <500ms"), then evaluate solution options including the user's suggestion.

### 3. Scope Explosion
**Signal:** "And while you're at it...", "Oh also...", "One more thing...", "And make sure to also..."
**Correction:** Decompose into numbered, prioritized sub-tasks. Complete each before starting the next. Flag scope additions for separate handling.

### 4. Assumed Context
**Signal:** "Fix the error in the handler" — which handler? What error? Which file?
**Correction:** Resolve all ambiguous references using project structure, recent changes, and active file context. If still ambiguous, ask ONE targeted question.

### 5. Vague Quality Targets
**Signal:** "Make it professional", "Make it look modern", "Clean up the code"
**Correction:** Translate to measurable criteria.
- "Professional" → Consistent typography, proper spacing, aligned to design system
- "Modern" → Current framework patterns, latest CSS features, responsive layout
- "Clean" → Reduced cyclomatic complexity, extracted functions, named constants, documentation

---

## Structural Anti-Patterns (Fix When Detected)

### 6. Missing Negation
**Signal:** Only says what TO do, never what NOT to do.
**Example:** "Add user authentication" (but doesn't mention: don't break existing public endpoints, don't store passwords in plaintext)
**Correction:** Add explicit constraints and boundaries. Include "Do NOT" section for critical safety rails.

### 7. Kitchen Sink
**Signal:** A single prompt covering 5+ unrelated concerns. "Set up the database, design the API, create the frontend, write tests, and deploy to production."
**Correction:** Decompose into sequential phases with dependencies. Identify which tasks can run in parallel.

### 8. Cargo Cult
**Signal:** "Do it like Netflix / Google / Airbnb"
**Correction:** Extract the actual principles being referenced (horizontal scaling, micro-frontends, design system consistency) and apply based on project context and scale.

### 9. Perfectionism Trap
**Signal:** "Make it production-ready" on a prototype, or excessive requirements on a first iteration.
**Correction:** Calibrate quality level to context. MVP vs production vs enterprise. Define "good enough for now" and "future improvements" explicitly.

### 10. Moving Target
**Signal:** Requirements change mid-implementation. "Actually, instead of X, do Y" or "Wait, also add Z."
**Correction:** Checkpoint current progress, confirm new direction, re-enhance from the new baseline. Don't attempt to merge conflicting requirements.

---

## Cognitive Anti-Patterns (Awareness Level)

### 11. Anchoring Bias
**Signal:** First mentioned approach becomes the default even when better options exist.
**Correction:** Force consideration of at least 2 alternatives before proceeding with any approach.

### 12. Recency Bias
**Signal:** Using the most recently discussed technology/pattern even when it's not the best fit.
**Correction:** Evaluate against project context and requirements, not conversation recency.

### 13. Confirmation Bias
**Signal:** Only looking for evidence that supports the current approach, ignoring contrary signals.
**Correction:** Explicitly list arguments AGAINST the chosen approach before proceeding.

### 14. Sunk Cost Fallacy
**Signal:** Continuing with a failing approach because effort was already invested.
**Correction:** Evaluate current state objectively. If the approach is failing, switching costs less than persisting.

### 15. Bikeshedding
**Signal:** Spending disproportionate time on trivial decisions (variable names, color shades) while ignoring critical architecture.
**Correction:** Timebox trivial decisions (30 seconds), invest time in high-impact decisions.

---

## Detection Heuristics Summary

Use these quick signals during intake to flag likely anti-patterns:

| Signal | Likely Anti-Pattern(s) |
|--------|----------------------|
| Prompt mentions a specific tool/library as the solution | #2 Premature Solution |
| "How do I do X with Y?" | #1 XY Problem |
| Prompt has 3+ "and also" / "while you're at it" | #3 Scope Explosion |
| Pronouns without antecedents ("fix it", "update that") | #4 Assumed Context |
| Subjective quality adjectives only | #5 Vague Quality |
| Only positive requirements, no constraints | #6 Missing Negation |
| 5+ distinct concerns in one message | #7 Kitchen Sink |
| References to how big companies do it | #8 Cargo Cult |
| "Production-ready" on day 1 | #9 Perfectionism |
| "Actually..." or "Wait, instead..." | #10 Moving Target |

---

## Correction Priority

When multiple anti-patterns are detected, fix in this order:
1. **#1 XY Problem** — Wrong problem invalidates everything
2. **#4 Assumed Context** — Can't enhance what you can't locate
3. **#3 Scope Explosion** — Must bound scope before enhancing
4. **#5 Vague Quality** — Measurable criteria enable everything else
5. **All others** — Fix in detection order
