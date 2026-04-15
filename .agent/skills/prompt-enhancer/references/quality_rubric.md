# Quality Rubric — Prompt Enhancement Scoring

Scoring system to validate that an enhanced prompt meets enterprise-grade standards before execution.

---

## Dimensions & Weights

| # | Dimension | Weight | Description |
|---|-----------|--------|-------------|
| 1 | **Completeness** | 25% | All necessary context, constraints, and requirements are present |
| 2 | **Specificity** | 25% | Uses precise verbs, file paths, function names, and measurable criteria |
| 3 | **Actionability** | 20% | Can be executed step-by-step without further clarification |
| 4 | **Context-Awareness** | 15% | Aligned with project conventions, stack, and existing patterns |
| 5 | **Risk-Awareness** | 15% | Failure modes, edge cases, and rollback plans identified |

---

## Scoring Guide

### 1. Completeness (25%)

| Score | Criteria |
|-------|----------|
| **1** | Missing 3+ of the 6W dimensions (Who, What, Why, Where, When, How) |
| **2** | Missing 2 of the 6W dimensions |
| **3** | All 6W dimensions addressed, but some are superficial |
| **4** | All 6W dimensions well-addressed, success criteria defined |
| **5** | Comprehensive: 6W + edge cases + constraints + success criteria + rollback |

### 2. Specificity (25%)

| Score | Criteria |
|-------|----------|
| **1** | Vague verbs ("fix", "improve"), no file paths, no measurable outcomes |
| **2** | Some specific verbs, but locations and outcomes still vague |
| **3** | Specific verbs and file paths, but outcomes are qualitative not quantitative |
| **4** | Precise verbs, exact file paths/function names, measurable success criteria |
| **5** | All of 4, plus line-level specificity, version constraints, and benchmark targets |

### 3. Actionability (20%)

| Score | Criteria |
|-------|----------|
| **1** | "Make it better" — no actionable steps |
| **2** | General direction but requires significant interpretation |
| **3** | Clear steps, but execution order or dependencies unclear |
| **4** | Step-by-step executable with clear ordering and dependencies |
| **5** | Step-by-step with verification at each stage, decision points flagged, alternative paths defined |

### 4. Context-Awareness (15%)

| Score | Criteria |
|-------|----------|
| **1** | No project context — could apply to any codebase |
| **2** | Mentions stack/framework but ignores project conventions |
| **3** | References project files/patterns, but may miss conventions |
| **4** | Fully aligned with project patterns, conventions, and tech decisions |
| **5** | Aligned + leverages existing utilities, follows contribution guidelines, maintains consistency |

### 5. Risk-Awareness (15%)

| Score | Criteria |
|-------|----------|
| **1** | No failure modes considered |
| **2** | Acknowledges "something could go wrong" without specifics |
| **3** | 1-2 specific failure modes with mitigations |
| **4** | Comprehensive failure modes, edge cases, and rollback strategy |
| **5** | All of 4, plus blast radius analysis, monitoring strategy, and graceful degradation |

---

## Thresholds

| Weighted Score | Rating | Action |
|---------------|--------|--------|
| **4.5 – 5.0** | ★★★★★ Exceptional | Proceed immediately |
| **3.5 – 4.4** | ★★★★ Strong | Proceed — note any assumptions |
| **2.5 – 3.4** | ★★★ Adequate | Proceed with caution — monitor for gaps |
| **1.5 – 2.4** | ★★ Weak | Re-enhance before proceeding |
| **1.0 – 1.4** | ★ Critical | Ask clarifying question before any action |

---

## Quick Self-Assessment

For rapid scoring during normal operation, use this compressed checklist:

```
COMPLETENESS:  Do I know WHO/WHAT/WHY/WHERE/WHEN/HOW?     [Y/N]
SPECIFICITY:   Am I using exact file paths and precise verbs? [Y/N]
ACTIONABILITY: Can I execute this step-by-step right now?     [Y/N]
CONTEXT:       Does this match how this project works?        [Y/N]
RISK:          Have I considered what could go wrong?          [Y/N]

≥4 YES → Proceed
 3 YES → Proceed with noted gaps
≤2 YES → Re-enhance or ask
```
