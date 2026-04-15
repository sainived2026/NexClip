# Enhancement Matrices — Category-Specific Strategies

Deep-dive enhancement rules for each prompt category. The main SKILL.md classifies the prompt then routes here for type-specific enrichment.

---

## Code Generation

### Mandatory Enrichments
- **Architecture**: Where does this code live? What imports it? What does it export?
- **Pattern Adherence**: Does this codebase prefer OOP or functional? REST or GraphQL? What naming conventions?
- **Error Handling**: Define error states, fallback behavior, user-facing error messages
- **Input Validation**: Define valid inputs, boundary conditions, type guards
- **Testing**: Unit tests for logic, integration tests for flows, edge case coverage
- **Documentation**: JSDoc/docstrings for public APIs, inline comments only for "why"

### Enhancement Checklist
```
□ File path determined
□ Related files identified (imports, exports, tests)
□ Error handling strategy defined (try/catch, Result type, etc.)
□ Input validation specified
□ Output format defined
□ Edge cases listed (null, empty, overflow, concurrent)
□ Test strategy stated (unit, integration, e2e)
□ Performance constraints noted (if applicable)
```

---

## Debugging

### Mandatory Enrichments
- **Reproduction**: Exact steps, environment, input data that triggers the bug
- **Isolation**: Binary search — which component/layer fails? Frontend, backend, database, network?
- **Root Cause vs Symptom**: "Login fails" is a symptom, "JWT verification uses expired secret key" is a root cause
- **Verification**: How to confirm the fix actually works and doesn't introduce regressions
- **Blast Radius**: What else could be affected by this bug or its fix?

### Enhancement Checklist
```
□ Error message captured verbatim
□ Stack trace or logs identified
□ Reproduction steps documented (or requested)
□ Affected component(s) isolated
□ "Since when?" timeline established (recent change?)
□ Root cause hypothesis formed
□ Fix approach defined
□ Regression test planned
```

---

## Refactoring

### Mandatory Enrichments
- **Motivation**: Why refactor? Tech debt metric? Performance? Readability? Extensibility?
- **Scope Boundary**: ONLY touch files within scope. No "while we're at it" additions
- **Backward Compatibility**: Existing API consumers, interface contracts, test expectations
- **Incremental Strategy**: Can this be done in stages? Feature-flagged?
- **Metrics**: How to measure improvement (cyclomatic complexity, LOC, bundle size, test coverage)

### Enhancement Checklist
```
□ Refactoring motivation explicit
□ Files in scope listed
□ Files explicitly out of scope listed
□ Breaking changes identified (or confirmed none)
□ Test coverage before refactor measured
□ Incremental migration path defined (if large)
□ Success metric defined
```

---

## Design / UI

### Mandatory Enrichments
- **Platform & Viewport**: Desktop-first? Mobile-first? Responsive breakpoints?
- **Design System**: Existing tokens? Colors, fonts, spacing, component library?
- **Accessibility**: WCAG level, screen reader, keyboard navigation, color contrast
- **Interactivity**: Hover states, transitions, animations, loading states, empty states
- **Content**: Real content vs placeholder? Text length constraints?

### Enhancement Checklist
```
□ Platform/viewport specified
□ Design system/tokens referenced
□ Color palette defined or referenced
□ Typography system defined or referenced
□ Component hierarchy structured
□ Interaction states listed (hover, active, focus, disabled, loading, empty, error)
□ Responsive behavior defined
□ Accessibility requirements stated
```

---

## Research / Investigation

### Mandatory Enrichments
- **Scope & Depth**: Broad survey or deep dive? How many options to compare?
- **Sources**: Codebase-only? Docs? Web search? Specific URLs?
- **Deliverable Format**: Summary, comparison table, recommendation, implementation plan?
- **Decision Criteria**: What factors matter? Speed? Cost? Simplicity? Ecosystem?

### Enhancement Checklist
```
□ Research question precisely defined
□ Scope bounded (time, depth, breadth)
□ Source priority set (codebase first, then docs, then web)
□ Deliverable format specified
□ Decision criteria listed and weighted
□ Known constraints or preferences stated
```

---

## Planning / Architecture

### Mandatory Enrichments
- **Goals**: Business goals, technical goals, timeline
- **Constraints**: Budget, team size, existing tech stack, compliance requirements
- **Risks**: Technical risks, dependency risks, timeline risks
- **Phases**: Break into incremental deliverable phases
- **Decision Points**: Where does the user need to make a choice?

### Enhancement Checklist
```
□ Goals (business + technical) explicit
□ Non-negotiable constraints listed
□ Flexible constraints (nice-to-haves) listed
□ Risk register with mitigations
□ Phase breakdown with deliverables
□ Success criteria per phase
□ Decision points flagged
```

---

## Configuration / Setup

### Mandatory Enrichments
- **Environment**: Development, staging, production? Local, Docker, cloud?
- **Dependencies**: Exact versions, peer dependencies, conflict resolution
- **Validation**: How to verify the configuration works?
- **Security**: No secrets in code, `.env` usage, `.gitignore` coverage
- **Documentation**: Document all non-obvious configuration choices

### Enhancement Checklist
```
□ Target environment specified
□ Required dependencies listed with versions
□ Environment variables documented
□ Configuration validation method defined
□ Security review: no hardcoded secrets
□ Rollback plan if configuration breaks things
```

---

## Testing

### Mandatory Enrichments
- **Test Scope**: Unit, integration, E2E? Which layers?
- **Test Cases**: Happy path, error cases, edge cases, boundary values
- **Mocking Strategy**: What to mock, what to run against real services
- **CI/CD Integration**: Where do these tests run? What gates do they enforce?
- **Coverage Targets**: Line coverage, branch coverage, mutation testing

### Enhancement Checklist
```
□ Test scope defined (unit/integration/e2e)
□ Happy path cases listed
□ Error/failure cases listed
□ Edge cases listed (null, empty, boundary, concurrent)
□ Mock/stub strategy defined
□ Test data strategy defined (fixtures, factories, seeds)
□ Coverage target stated
□ CI/CD pipeline integration specified
```

---

## Security

### Mandatory Enrichments
- **Threat Model**: What are the assets? Who are the adversaries?
- **Attack Surface**: Input validation, authentication, authorization boundaries
- **Mitigation**: Specific controls for each identified threat
- **Audit Trail**: Logging, monitoring, alerting for security events
- **Compliance**: Relevant standards (OWASP, SOC2, GDPR, etc.)

### Enhancement Checklist
```
□ Assets identified (data, services, secrets)
□ Threat actors identified (external, internal, automated)
□ Attack vectors mapped (OWASP Top 10 alignment)
□ Mitigation controls specified per threat
□ Input validation on all user-controlled data
□ Auth/authz boundaries defined
□ Secrets management strategy defined
□ Audit logging plan
□ Compliance requirements listed
```

---

## Performance Optimization

### Mandatory Enrichments
- **Metrics**: What are we measuring? Latency, throughput, memory, bundle size?
- **Baseline**: Current performance numbers
- **Profiling**: Where is the bottleneck? CPU, I/O, network, memory?
- **Tradeoffs**: What can we sacrifice for performance? Readability? Features? Accuracy?
- **Verification**: Load testing, benchmarking, before/after comparison

### Enhancement Checklist
```
□ Performance metric(s) identified
□ Baseline measurement captured (or requested)
□ Bottleneck hypothesis formed
□ Profiling strategy defined
□ Target performance numbers set
□ Tradeoffs acknowledged
□ Verification method defined (benchmark, load test)
□ Regression monitoring plan
```
