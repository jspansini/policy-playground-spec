# Tasks — Policy Playground

## Document Information

- **Feature Name**: Policy Playground
- **Version**: 1.2 (draft, pending human approval)
- **Status**: Tasks phase — awaiting approval before implementation. No code is written until this plan is explicitly approved.
- **Related documents**:
  - Requirements: `.kiro/specs/policy-playground/requirements.md` (1.2; 1.0 approved, R1–R16 + NFRs + Decision Log)
  - Design: `.kiro/specs/policy-playground/design.md` (1.2; 1.0 approved)

## Implementation Overview

This plan turns the approved design into incremental, test-driven coding tasks. It builds the MVP core on the **synthetic fixture** (`fixtures/policy-playground-demo-policy.json`) with the **`SimulatedRunner`** (results always labeled `SIMULADO`), exactly as the design scopes it. Tasks are ordered so each step builds on validated earlier work: data contract → policy model/validation → evaluator → scenarios/discovery → simulated execution → comparison → investigation record/audit → AI investigation (including deterministic generators) → UI → governance/FinOps/metrics → end-to-end → AWS deployment.

Tasks that depend on real credit-policy platform access or on an open question are marked **[CONDITIONAL]** with the gating OQ/risk; they are not started unless that gate is resolved, matching the design's ◑ coverage rows (§14.1).

### Development Approach

- **Testing strategy**: test-driven per task — unit tests alongside each module; the design's §14 assertions are the acceptance checks.
- **Integration strategy**: single modular-monolith app (design D-1); modules integrated behind the interfaces named in §4/§6/§9.
- **Determinism invariant**: AI code paths never produce or raise an impact number; `evidenceLevel` is derived only from a deterministic `ExecutionResult` (design §6.2, §9.3).
- **No implementation details beyond design**: tasks do not pick application frameworks (still deferred, design §3). AWS services are the ones fixed in design §16 and are used only in Phase 9; Phases 1–8 run locally with no cloud dependency, so the core can be tested before deployment.

---

## Implementation Plan

### Phase 1: Project foundation and policy data contract

- [ ] 1. Set up the single-application skeleton and shared types
  - Create the modular-monolith structure with the six internal boundaries as modules (interface, orchestration, policy-representation, execution, ai-investigation, governance) per design §4
  - Add build/lint/test tooling and a test runner; no business logic yet
  - Define shared type stubs for `PolicyModel`, `Rule`, `Variable`, `Parameter`, `Dag`, `Motivo`, `Scenario`, `ExecutionResult`, `ValidationOutcome`, `Finding`, `InvestigationRecord` from the design §6.2 class model (interfaces only)
  - Verifiable completion (evidence, not just files): the build and lint commands run clean, the test runner executes, and a smoke test imports every module boundary and the shared types and asserts they resolve (guards against broken wiring/circular imports) — this is the only task whose "test" is a build/smoke check rather than behavior
  - _Requirements: R16, R1 (foundation); design §3, §4, §6.2_

- [ ] 2. Implement the Policy Spec data model and loader
  - Parse the nine Policy Spec sections (`policy`, `stages`, `rules`, `variables`, `parameters`, `dag`, `motivos`, `validation_map`, `output_vars`) into the in-memory `PolicyModel` (design §6.1/§6.2), and load the complementary `fixtures/policy-playground-demo-extensions.json` (design §6.1.1) without ever writing to the Policy Spec
  - Derive `consumed_by` by inverting rule `inputs`/`outputs`
  - Deduplicate parameters by the design key `(name, scope)` with **explicit, deterministic** behavior: a predefined parameter (declared in `parameters`) always wins over an auto-extracted one with the same key; two **predefined** parameters sharing the same key are a conflict, not a silent merge; every merge/conflict is recorded in the `ValidationReport` with both source definitions and the resolution
  - Load the synthetic fixture as the reference policy
  - **Fixture note / open gap (OQ-17 — provisional MVP behavior only, do not resolve by assumption):** in the current fixture, `parameters` entries (P001, P002) have **no `scope` field** — `scope` appears only on `rules` and `motivos`. So the `(name, scope)` key the Design specifies is not directly computable from the parameter object alone, and Design §6.2 does not define how a parameter's `scope` is obtained. Implement the dedup behind a single documented key function `paramKey(param)` and apply this **provisional strategy, valid only for the MVP on the synthetic fixture**:
    - while the fixture provides no `scope`, use `name` as the dedup key (this is a fixture-scoped fallback, not the design's `(name, scope)` rule);
    - collisions between two **predefined** definitions on that key are detected and handled with the **blocking** behavior already defined above (reported as a conflict, never silently merged);
    - predefined-vs-auto-extracted collisions keep the predefined definition as a recorded merge;
    - every merge and every conflict stays **traceable** in the `ValidationReport`, naming both source definitions and the resolution.
    This provisional strategy **must not be presented or reused as the definitive rule for the real Policy Spec schema**, and no scope-derivation rule is to be invented. See the OQ-17 note at the end of this document.
  - Unit tests (against the real fixture): fixture loads; `consumed_by` for `renda_mensal` resolves to a set **derived from the fixture** (inverting `inputs`), expected {R005, R007} and asserted to match the loaded model, not hardcoded independently; a predefined-vs-auto-extracted collision keeps the predefined definition and records the merge; a predefined-vs-predefined `name` collision is reported as a conflict (blocking) rather than merged; the recorded merge/conflict entry names both sources
  - _Requirements: R16.1, R16.3, R1.1; design §6.1, §6.2; open: OQ-17 (parameter `scope` source for the dedup key)_

- [ ] 3. Implement Policy Spec validation (block-on-invalid)
- [ ] 3.1 Implement structural + referential + DAG validation
  - Produce a structured `ValidationReport`: schema/shape, referential integrity (`depends_on`, `parameters`, `produced_by`, `motivo.rule_id`, `used_by`), DAG integrity (cycles, orphans, `execution_order` vs `depends_on` mismatch), unknown `logic.type` as a hard error
  - Block exploration/investigation when any blocking check fails; emit a specific, comprehensible message naming the section/field/rule/edge
  - Unit tests: valid fixture passes; mutated fixtures (missing field, dangling `depends_on`, injected cycle, unknown `logic.type`, and a predefined-vs-predefined duplicate-parameter collision per task 2) each fail with the right message and do not proceed
  - A stage with no entry in the extensions `stage_area`, or with a value outside {Extraction, ETL, Hard filters, Final base}, produces a **non-blocking warning** in the `ValidationReport` (design §6.1)
  - Checks 6–8 of design §7.1: extensions bound to the loaded Policy Spec (`policy_id`, `source_commit`, known stage and parameter ids); baseline parameter values inside `parameter_domains`; referenced dataset file exists, `contains_pii: false`, `record_count` matches (blocks execution only)
  - Unit tests: an extensions file pointing to another `source_commit` is rejected while the Policy Spec still loads; a P001 domain that excludes 2500 is reported; removing the dataset file blocks execution only; the Policy Spec file is unchanged after the run
  - _Requirements: R16.2, R1.3, R1.2; design §6.1, §7.1, §13_

### Phase 2: Deterministic rule evaluation and dependency discovery

- [ ] 4. Implement the closed, typed rule evaluator
- [ ] 4.1 Implement `json_extract` and `matrix_lookup`
  - `json_extract`: read `path` from a synthetic payload, apply `cast` (R001–R003)
  - `matrix_lookup`: resolve `row_key`/`col_key`, index `matrix` (R008)
  - Unit tests over known synthetic inputs produce deterministic outputs
  - _Requirements: R5.1; design §7.2, D-6_
- [ ] 4.2 Implement `case_when` over a fixed, validated grammar
  - Parse the condition into the small AST `{var|param|literal} {comparator} {var|param|literal}` joined by `AND`/`OR`, comparators `=,>=,<=,>,<`; first true branch wins else `else`
  - Reject anything outside the grammar as a validation error (never best-effort); never execute arbitrary/model-generated expressions
  - Surface R007's inline literal thresholds as read-only derived thresholds (only `parameters` P001/P002 are editable per R2/OQ-5)
  - Unit tests: R005 (`renda_mensal >= renda_minima`) and R009 branches evaluate deterministically; out-of-grammar expression is rejected
  - _Requirements: R5.1, R5.10, R2 (OQ-5 scope); design §7.2, D-6_

- [ ] 5. Implement baseline isolation and scenario overlay
  - Treat the loaded `PolicyModel` as the immutable baseline; represent a `Scenario` as `baseline + ParamOverride[]` applied at eval time (e.g. `{P001: 3000}`)
  - Unit test: after a scenario run the baseline object is byte-identical (no mutation)
  - _Requirements: R4.4, R5.9; design §8.1, D-5_

- [ ] 6. Implement reverse dependency discovery over the DAG
  - From a changed parameter: seed via `used_by`, forward closure via `outputs → consumed_by`, required-upstream via `depends_on` closure; order the execution set by `dag.execution_order` (design §8.2 — do not extend the algorithm beyond this)
  - Implement objective-first discovery as `PolicyModel.requiredForOutput(outputVar)` (closure from the producing rule)
  - Distinguish, per design §8.2, the **changed path recomputed for the scenario** (seed + forward closure + its required upstream) from **baseline-reused inputs** (other inputs a downstream rule needs, whose parameters did not change) — the test expectations below rely on this distinction
  - **Derive the expected set from the real fixture, do not presume it.** The test MUST compute the expected set from the loaded `PolicyModel` (traversing `used_by`/`depends_on`/`inputs`/`outputs`/`consumed_by`) and compare the algorithm's output to that derived set. If the loaded graph does not yield the documented example, the test MUST fail and surface the inconsistency — never edit the expected value or the fixture to force a pass.
  - Unit tests (all against the real fixture):
    - **Changed-path set for P001:** expected, derived from the fixture, is {R001, R005, R009} — R005 is the seed (`used_by`), R001 its required upstream (`depends_on`), R009 the forward closure via `status_renda ∈ R009.inputs`. Assert the algorithm reproduces exactly the fixture-derived set.
    - **Indirect dependency:** R009 is reached only transitively from P001 (P001→R005→`status_renda`→R009), proving indirect-closure handling, not just direct `used_by`.
    - **Affected vs. not-affected:** R002/R003/R004/R006/R007/R008 are not in the changed-path set for P001; where `resultado` is the comparison target, R009's other inputs (`status_idade`, `status_comprometimento`, `limite_sugerido`) are supplied from the baseline, not recomputed — assert both the "not recomputed" and the "available from baseline" conditions.
    - **Execution order:** the returned order is consistent with `depends_on` and `dag.execution_order` (R001 before R005 before R009); assert a topological check, not a fixed list only.
    - **Objective-first:** `requiredForOutput('resultado')` returns the fixture-derived closure of R009 (R009 + its transitive `depends_on`).
    - **No executable path / insufficient data:** an objective that maps to no producing rule, or whose closure needs an input with no producer and no payload path, yields an explicit "no executable path / insufficient data" outcome (consumed later by task 7's `cannot_calculate` and §13), not a partial silent result.
    - **Cycles / invalid references:** assert these are rejected earlier by validation (task 3.1) and that discovery is only ever run on a validated model — discovery does not re-handle them.
  - _Requirements: R5.3, R5.4; design §8.2, §6.2, §7.1_

### Phase 3: Deterministic execution and comparison (SIMULADO)

- [ ] 7. Implement the `ImpactStudyRunner` interface and `SimulatedRunner`
  - Define `ImpactStudyRunner.runScenario(policyVersion, scenario, affectedSubDag) -> ExecutionResult`
  - `SimulatedRunner`: execute the evaluator over the affected sub-DAG against the synthetic dataset referenced in the extensions `datasets` (`fixtures/policy-playground-demo-dataset.json`, 12 records); always set `mode=SIMULADO`, `status=ok`; record its `dataset_version`; perform no real-history comparison
  - **Scope statement (make explicit in code docs and output):** a `SimulatedRunner` run demonstrates the **deterministic behavior of the rules over synthetic payloads**; it does **not** prove real impact against historical `Motivo de Decisão` data. Preserve the design distinction between execution, validation, and evidence level (§9.3): a run that completed is not, by itself, validated.
  - Record `ExecutionResult` with `executionId`, `attempt`, `source=deterministic`, `createdAt`; derive `evidenceLevel` via the canonical map (`SIMULADO & ok → simulated`), never set directly; no AI path may write or raise a result
  - Verifiable acceptance criteria (unit tests, against the real fixture):
    - every `SimulatedRunner` result has `mode=SIMULADO` and derived `evidenceLevel=simulated` — never `study_validated`; a test asserts there is no code path by which a simulated run reaches `study_validated`
    - the result object marks itself simulated such that any consumer (comparison task 8, UI task 16) can only render it as SIMULADO — assert the simulated flag is present and non-strippable in the result contract
    - when no baseline/history is available, the runner/comparison returns an explicit "cannot compare / not available" state and **never** fabricates a baseline or a comparison (ties to task 8)
    - an evaluator failure yields `status=cannot_calculate` with no substituted/estimated value and `evidenceLevel=none`
    - a "no executable path / insufficient data" discovery outcome (task 6) maps to `status=cannot_calculate`, not to a partial number
  - _Requirements: R5.1, R5.5, R5.7, R5.8, R5.10; design §9.1, §9.3, §6.2_

- [ ] 7.1 Thin vertical slice — load → override → discover → simulate → baseline intact (early integration checkpoint)
  - Integrate the already-built pieces (tasks 2, 3.1, 4, 5, 6, 7) into one minimal headless flow, with **no UI, no AI, no governance** yet, to catch module-interface mismatches early rather than only at task 20
  - Flow: (1) load + validate the fixture; (2) apply a scenario override (`P001 = 3000`); (3) discover and execute only the required rule subset; (4) obtain an explicitly simulated result; (5) assert the baseline model is unchanged
  - Integration test asserts the vertical: validation passed; the executed subset equals the fixture-derived changed-path set from task 6; the result is `mode=SIMULADO`/`evidenceLevel=simulated`; the baseline is byte-identical after the run
  - This is an incremental checkpoint only; it does **not** replace task 20's full end-to-end validation (which adds AI, UI, decision, audit, governance)
  - _Requirements: R5.1, R5.3, R5.4, R5.9, R16.2 (integrated subset); design §5, §8.1, §8.2, §9.1_

- [ ] 7.2 Implement the asynchronous, idempotent execution contract
  - `POST /executions` computes the idempotency key `sha256(policyVersion, sorted(overrides), datasetVersion, runnerVersion)` (design §9.4); a key with a successful result returns it without running compute; otherwise a job is created in `pending`
  - Job states `pending → running → done`; `GET /executions/{id}` returns `jobState` and, when done, the `ExecutionResult`; configurable timeout ends the job as `cannot_calculate`
  - Record `policyVersion` (Policy Spec `source_commit` + object version), `datasetVersion` and `runnerVersion` on every `ExecutionResult`
  - Unit tests: the same request twice returns the same `executionId` and runs the runner once; different overrides produce different keys; a timeout yields `cannot_calculate` with no number; re-running a recorded key against the recorded versions yields identical `outputs`, and a forced mismatch raises an integrity error
  - _Requirements: R5.7, R14.6, NFR FinOps 3, NFR Reliability 3, NFR Performance 1; design §9.4, D-12_

- [ ] 8. Implement baseline-vs-scenario comparison capability
  - Reusable comparison over `output_vars` (`resultado`, `limite_sugerido`) plus affected `motivos`, run for baseline and scenario; carry the current execution's `evidenceLevel` badge
  - If baseline results are unavailable, return a "comparison cannot be shown" state (no fabricated comparison)
  - Unit tests: comparison surfaces both runs with related rules/data context; missing-baseline path returns the explicit state
  - _Requirements: R6.1, R6.2, R6.3, R6.4; design §9.1, §11_

### Phase 4: Investigation record, findings lifecycle, and audit

- [ ] 9. Implement the append-only InvestigationRecord and finding lifecycle
- [ ] 9.1 Implement the record and execution history (append-only)
  - Append-only `InvestigationRecord` linking hypothesis → params → policy version → scenario(s) → execution(s) → finding(s) → human decision(s); executions referenced by `executionIds[]` + `currentExecutionId`, never overwritten on re-run
  - Unit tests: a re-run appends a new `ExecutionResult` (incremented `attempt`), prior results remain, `currentExecutionId` points to newest; records are only appended, never rewritten
  - _Requirements: R14.1, R14.2, R14.3; design §6.2, §10.1, §12_
- [ ] 9.2 Implement the `Finding` state machine and evidence derivation
  - Transitions per design §10.1: `suggested → {under_investigation | rejected}`, `under_investigation → {executed | rejected}`, `executed → {accepted | rejected | re-run}`, `accepted → under_investigation` (re-run); evidence derived only from executions
  - `investigationState` and `evidenceLevel` move independently (accept/reject never changes evidence)
  - Unit tests: rejection before any execution is allowed and leaves `evidenceLevel=none`; accepting changes state but not evidence
  - _Requirements: R7.2, R7.4, R8.4, R9.2, R10.1, R10.4; design §10.1, §11_

- [ ] 9.3 Persist the record and write the audit lake
  - Implement the `InvestigationRecord` repository behind one interface with two adapters: in-memory (local tests) and DynamoDB (design D-11)
  - Emit every event (hypothesis, confirmation, execution, finding, assessment, decision) to an audit writer that puts one JSON object per `eventId` in the S3 audit bucket; retries reuse the same key; failures are retried and alarmed
  - Unit/integration tests: a session reloaded from the store reproduces the same chain; each event produces exactly one audit object even when the writer is retried; the application role cannot update or delete audit objects
  - _Requirements: R14.1, R14.4, R14.5; design §12, D-11_

### Phase 5: AI-assisted investigation (advisory, bounded)

- [ ] 10. Implement hypothesis structuring from intent
  - Produce a structured hypothesis naming the policy elements involved and the change under test; request clarification when intent is ambiguous/incomplete; present for human confirmation before building a scenario; treat the hypothesis as a proposal only
  - Build the model prompt from Policy Spec + scenario structure with PII minimized (no raw credit data)
  - Unit tests: structured hypothesis names elements + change; ambiguous intent triggers a clarification path; no hypothesis is treated as evidence
  - _Requirements: R3.1, R3.3, R3.4, R3.5; design §5, §10, §12_

- [ ] 11. Implement human confirmation of AI-proposed modifications
  - Present any AI-proposed modification for explicit confirmation before it enters a scenario; apply the specialist's edited version when edited; never apply without confirmation; confine every modification to an experimental scenario
  - Unit tests: unconfirmed modification is not applied; edited version overrides the AI proposal; no path applies a modification to production
  - _Requirements: R4.1, R4.2, R4.3, R4.4; design §5, §11_

- [ ] 12. Implement bounded scenario/finding suggestions
  - Return at most N ranked suggestions per request (configurable session cap, small default); each born `source=ai_suggestion`, `evidenceLevel=none`; no unbounded stream; no autonomous red-team loop
  - A finding reaches `evidenceLevel=simulated` only after a deterministic run; "cannot answer" keeps `evidenceLevel=none` and states the limitation
  - Unit tests: suggestion set is capped; no `ai_suggestion` carries a numeric impact or evidence above `none` without an `ExecutionResult`
  - _Requirements: R7.1, R7.3, R8.1, R8.2, R8.3; design §10, §9.3_

- [ ] 12.1 Implement deterministic candidate generators G1 and G2
  - G1 (shared-input neighbours): rules outside the changed path (task 6) whose `inputs` share a non-parameter variable with it, with their forward closure attached
  - G2 (branch reachability): for analyzable `case_when` conditions over one numeric variable, compute per-branch intervals with first-match semantics, intersect with the target-outcome constraint, and report branches newly unreachable / newly reachable vs. the baseline, propagated to `matrix_lookup` rows
  - Generator output is a `Finding` with `source=deterministic_analysis`, `evidenceLevel=none`, `generator`, and `structuralBasis`; it never calls the model and never carries an impact number
  - Unit tests (against the real fixture; derive expectations from the loaded model, do not hardcode them independently):
    - P001 = 3000: G1 returns R007 with R008 attached
    - P001 = 3000: G2 reports R007 `BASICA` newly unreachable under approval (R009), with R008 row `BASICA` attached
    - P001 = 2500 (no change): G2 reports nothing new
    - an out-of-grammar condition is reported as "não analisável", not guessed
  - _Requirements: R8.1, R8.5, R5.10; design §10.3, D-10_

- [ ] 12.2 Implement feedback-aware ranking
  - Score = `w_struct · [deterministic_analysis] + w_fb · (relevant + 1) / (assessed + 2)` per (policy, kind), weights in configuration; apply the cap *N* (task 12) after ranking, over deterministic and model suggestions together
  - Unit tests: with no assessments the feedback term is 0.5 for every kind; recorded assessments change the order as expected; the cap is applied after ranking
  - _Requirements: R8.2, R8.4, R8.6; design §10.2, §10.3_

- [ ] 13. Implement finding → investigable scenario
  - Turn a relevant finding into a scenario that goes through the same confirmation + execution + evidence path; default to explicit specialist action to launch execution (OQ-8 default)
  - Unit tests: a finding-derived scenario routes through confirmation/execution/evidence like any other; no auto-advance to a committed change
  - _Requirements: R9.1, R9.2, R9.3; design §10, §11_

### Phase 6: Interface

- [ ] 14. Implement policy exploration and DAG visualization
  - Render rules, variables, parameters, dependencies, and `motivos` from the loaded Policy Spec; indicate each element's policy area (Extraction/ETL/Hard filters/Final base) via `rule.stage_id → stage_area` (extensions file), showing "área da política não informada" when absent; make each element's origin traceable; show the explicit "cannot be explored" state on invalid/unavailable policy
  - Component tests for rendering and the error/empty states
  - _Requirements: R1.1, R1.2, R1.3, R1.4; design §4, §7.1_

- [ ] 15. Implement the hybrid what-if editor and investigation entry points
  - Visual parameter editing for supported `parameters` (P001/P002) with preview and baseline/scenario diff, using `parameter_domains` from the extensions file (`min`, `max`, `step`) for the form control and rejecting values outside it with the accepted range; natural-language hypothesis entry; both as one unified experience; two entry points (visual exploration / business question) without forcing a choice up front
  - Component tests: editing P001 produces a scenario overlay and a diff without mutating baseline; both entry points reach a structured hypothesis
  - _Requirements: R2.1, R2.2, R2.3, R2.4, R2.5; design §4, §5, §8.1_

- [ ] 16. Implement results, evidence badges, and human decision UI
  - Present comparison and findings with explicit evidence-level badges: `none` ("Hipótese sem comprovação"), `simulated` ("Resultado SIMULADO — não é impacto real", persistent badge on every number), `study_validated` label reserved for real validated runs; badge derived from current execution `status`+`mode`
  - Accept/reject findings and select a scenario as promising (enables the deterministic tail only on explicit selection); accepting is never read as production approval
  - Record the hypothesis decision as `HumanDecision` with outcome Accept / Reject / Defer and a mandatory rationale; a later decision creates a new record with `supersedes`, never an edit
  - Component tests: a simulated number never renders without the SIMULADO badge; accept/reject updates state but not evidence; selection gates the tail; a decision without rationale is refused; a second decision leaves the first unchanged and visible; `defer` does not enable the tail
  - _Requirements: R7.4, R10.1–R10.6; design §6.2, §11, §9.3_

### Phase 7: Governance, privacy, and FinOps

- [ ] 17. Implement the authorization boundary and model-privacy minimization
  - Route all credit-data and policy/dataset access through an injected authorization boundary with a **simplified demo role set** (design §12, D-8)
  - **Scope statement (make explicit):** this is the MVP's simplified, injected access control for the demo — it is **not** a real integration with corporate identity/authorization. Reuse of real governance/identity is a separate, gated concern (R15 scope note, OQ-11) and is **not** implemented here. Do not claim full enterprise governance.
  - Keep the authorization boundary as a single injectable seam so the real mechanism can replace it later without touching callers
  - Verifiable acceptance criteria (unit tests):
    - an unauthorized request for a policy or dataset is refused and **no protected data is exposed** in the response or in any error payload
    - access to a policy and to a dataset each pass through the defined authorization boundary (assert the boundary is invoked on every such path; no bypass path exists)
    - the AI prompt builder includes **no raw `Motivo de Decisão` rows** and no unnecessary personal data — assert prompts are built only from Policy Spec/scenario structure + synthetic payloads
    - an authorization failure is surfaced **as an authorization failure**, never as "no data"/empty-result, and is not worked around by any alternative flow (assert the failure type is distinct from the empty/unavailable states of tasks 7/8/18)
  - _Requirements: R15.1, R15.2, R15.3; design §12, D-8; real identity is OQ-11 (not in MVP)_

- [ ] 18. Implement FinOps session cap and reliability states
  - Enforce the per-session caps (default 10 findings shown; bounded model calls) with remaining findings available on request, and surface a per-hypothesis cost indicator; implement the reliability states (external capability unavailable → state the limitation, never fabricate)
  - Model-outage mode: exploration, visual editing, execution and decisions remain available; the interface states that natural-language input and AI suggestions are unavailable
  - Idempotency keys on every state-changing endpoint (hypotheses, executions, decisions)
  - Unit tests: caps are enforced and configurable; unavailable-dependency path communicates the limitation and fabricates nothing; with the model adapter failing, the non-AI flow completes; a retried request with the same idempotency key creates no duplicate
  - _Requirements: NFR FinOps 1–2, NFR Reliability 1–3, R5.7; design §12, §13_

- [ ] 19. Implement progress feedback and domain-context staleness signaling
  - Keep the specialist informed of progress while an execution runs; where a domain-context artifact is used, signal potential staleness and never silently present it as current
  - Component/unit tests: progress state shown during a run; stale/unknown context raises a visible uncertainty indicator
  - _Requirements: NFR performance (progress), R13.1, R13.2, R13.3; design §12, §13, §15_

- [ ] 19.1 Instrument product metrics
  - Record `hypothesis.submittedAt` and the first `ExecutionResult.createdAt` per hypothesis in the `InvestigationRecord`; expose the in-app hypothesis-to-evidence time and the per-session relevant-finding share through a metrics port (local implementation in Phases 1–8, CloudWatch in task 23)
  - Record model token usage per hypothesis from the model adapter (feeds the FinOps indicator of task 18)
  - Unit tests: a hypothesis reaching a deterministic result records both timestamps; one ending in `cannot_calculate` records no evidence timestamp; the relevant share counts only assessed findings
  - _Requirements: Primary-objective NFR 2–3, NFR FinOps; design §12_

### Phase 8: End-to-end validation (MVP core)

- [ ] 20. Wire and validate the full worked-example flow (R005/P001, SIMULADO)
  - Integrate modules end to end for "renda mínima 2500 → 3000": structure hypothesis → confirm → scenario overlay → reverse discovery (R001→R005→R009) → SimulatedRunner → baseline/scenario comparison → bounded suggestions (G1/G2 + model, ranked) → finding "R007 BASICA inalcançável para aprovados" → finding → scenario → SimulatedRunner over `renda_mensal ∈ [2500, 3000)` → accept/reject → recorded investigation with metrics
  - End-to-end tests assert the design invariants: deterministic-only impact, SIMULADO labeling everywhere, state/evidence separation, append-only history, no production effect; and that the G2 finding appears in the bounded set for this scenario
  - _Requirements: R1–R10, R14, R16, Primary-objective NFR 2–3 (integrated); design §5, §10.3, §14_

### Phase 9: AWS deployment (design §16)

Runs after the MVP core passes task 20. It changes where modules run, not what they do.

- [ ] 21. Provision the AWS stack with AWS CDK
  - One stack per environment: S3 + CloudFront + WAF for the SPA; API Gateway HTTP API with Cognito JWT authorizer, VPC Link and internal ALB; ECS cluster with one Fargate service (≥ 2 tasks across 2 AZs, auto scaling on CPU and request count) and a runner task definition from the same image; DynamoDB tables (on-demand); versioned S3 bucket for the Policy Spec; S3 audit bucket with no update/delete for the application role (Object Lock as an option); Athena workgroup over the audit bucket; S3 bucket for demo artifacts; KMS keys; Secrets Manager; cost-allocation tags; AWS Budgets alarm
  - Cognito user pool with groups Policy Specialist, Risk Approver, Data Analyst and Viewer, and a SAML identity provider slot for Azure AD (connected when corporate approval exists; demo users otherwise)
  - Verifiable completion: `cdk synth` succeeds; after deploy, loading the fixture from S3 through the API returns the same `ValidationReport` as the local run; stopping one API task does not interrupt an open session
  - _Requirements: R14.4–14.5, R15.3–15.6, R16.1, NFR Scalability 1–3, NFR FinOps; design §16, D-8, D-9, D-11_

- [ ] 22. Connect the model adapter to Amazon Bedrock with Guardrails
  - Implement the model adapter over the Bedrock Converse API; attach a Bedrock guardrail with sensitive-information filters on input and output; read token usage from each response for task 19.1
  - Tests: the adapter is the only code path that calls the model; prompts still contain no raw `Motivo de Decisão` rows (task 17 assertions run against the deployed adapter); a guardrail intervention is surfaced as such, never as an empty suggestion set
  - _Requirements: R15.2, R3, R8, NFR FinOps; design §12, §16_

- [ ] 23. Wire observability and product metrics to CloudWatch
  - Structured logs, X-Ray tracing on the API and ECS tasks, and the metrics port of task 19.1 emitting custom CloudWatch metrics (hypothesis-to-evidence time, relevant-finding share, tokens per hypothesis)
  - Verifiable completion: running the task 20 flow against the deployed stack produces one trace per request and data points for each metric
  - _Requirements: Primary-objective NFR 2–3, NFR performance, NFR FinOps; design §12, §16_

- [ ] 24. Validate scalability and resilience on the deployed stack
  - Load test with 50 concurrent simulated sessions running the task 20 flow; record P95 of hypothesis structuring and API error rate
  - Start a long runner job and confirm API latency for other sessions stays within the baseline
  - Stop one API task during a session and confirm the session continues on the other task
  - Verifiable completion: P95 structuring ≤ 30 s, zero errors attributable to the Playground, results recorded in the repository
  - _Requirements: NFR Performance 2, NFR Scalability 1–3, NFR Reliability 2; design §14, §16.1_

---

## Conditional tasks (gated by an open question / credit-policy platform access — not started until resolved)

These correspond to the ◑ rows in design §14.1. They are explicitly out of the MVP-core start set and must not be begun until the gate is resolved by a human decision.

- [ ] C1. **[CONDITIONAL — OQ-4]** Implement `RealStudyRunner` (real deterministic execution)
  - Behind the same `ImpactStudyRunner` interface; drive real studies, compare the final base against `Motivo de Decisão` using `validation_map`/`output_vars`; implement the §9.3 validation step producing `status ∈ {validated, executed_unvalidated, validation_failed}` and `ValidationOutcome`
  - Run each real study as an on-demand ECS task (RunTask) under the job contract of task 7.2, against anonymized/synthetic data only
  - Validation thresholds/method are themselves gated by **OQ-6**; do not invent tolerances
  - _Requirements: R5.5, R5.6; design §9.1, §9.3 — gated by OQ-4, OQ-6_

- [ ] C2. **[CONDITIONAL — OQ-9 / risk R-6]** Implement code + tests generation (credit-policy platform conventions)
  - **Gate:** not started until a human resolves OQ-9 and confirms the actual credit-policy platform repository, skills, and conventions are reachable. Do **not** presume Kiro has that access; do **not** stand up a fictional integration or claim it works.
  - Only for a human-selected, human-reviewed scenario; when the real credit-policy platform access is confirmed, generate functional policy code and tests consistent with the real credit-policy platform repo structure and reuse credit-policy platform skills where applicable
  - **Fallback (always available, no credit-policy platform access needed):** produce a clearly-labeled demonstration artifact (diff + tests) that is explicitly **not** submitted anywhere — never presented as validated against real credit-policy platform
  - Whether a real PR is required for the hackathon is a human decision (not decided here)
  - _Requirements: R11.1, R11.2, R11.3, R11.4; design §9.2 — gated by OQ-9/R-6_

- [ ] C3. **[CONDITIONAL — OQ-9 / risk R-6]** Implement pull-request creation (review-only)
  - **Gate:** not started until a human resolves OQ-9 and the repository access + PR mechanics are confirmed available. Do **not** presume repo access; do **not** simulate a PR as if real.
  - When confirmed: open a PR against the appropriate credit-policy platform repository as a **review request only** (never merge/deploy); report failure explicitly; keep the PR traceable to scenario/evidence/selection
  - **Fallback:** present the PR intent + the traceable package (scenario → evidence → selection → diff) **without opening a real PR**, clearly labeled as not submitted
  - The real-PR requirement is a human call tied to OQ-9 and access availability; this plan does not decide it for the user
  - _Requirements: R12.1, R12.2, R12.3, R12.4; design §9.2 — gated by OQ-9/R-6_

- [ ] C4. **[CONDITIONAL — governance request]** Enforce storage-level immutability on the audit lake
  - Persistence and the append-only audit lake moved to the MVP core in 1.2 (task 9.3); what remains conditional is write-once enforcement with S3 Object Lock and a retention policy, enabled only if governance requires it
  - _Requirements: R14.5 (strength); design §12_

- [ ] C5. **[CONDITIONAL — OQ-2 / OQ-15]** Adapt the loader/validator to the real Policy Spec schema
  - Reconcile the fixture-based contract with the real upstream Policy Spec schema and freshness source once confirmed
  - _Requirements: R1, R13, R16; design §6, §15 — gated by OQ-2/OQ-15_

---

## Requirements coverage check (every requirement maps to a task)

| Requirement | Task(s) |
|-------------|---------|
| R1 Policy exploration | 2, 3, 3.1 (policy-area warning), 14 |
| R2 Two entry points / hybrid | 15 |
| R3 Hypothesis structuring | 10 |
| R4 Human confirmation | 5, 11 |
| R5 Deterministic impact (SIMULADO core) | 4, 5, 6, 7, 7.1 (+ C1 for real) |
| R6 Baseline vs scenario | 8 |
| R7 Evidence / proven-unproven | 9.2, 12, 16 |
| R8 AI discovery (bounded) | 12, 12.1, 12.2 |
| R9 Finding → scenario | 13 |
| R10 Human decision | 9.2, 16 |
| R11 Code+tests | C2 |
| R12 Pull request | C3 |
| R13 Domain-context freshness | 19 (+ C5) |
| R14 Traceability/audit | 7.2, 9.1, 9.3 (+ C4 for storage-level immutability) |
| R15 Governed data / privacy | 17, 21, 22 |
| R16 Consume+validate Policy Spec | 2, 3 (+ C5 real schema) |
| NFR lead-time | 19.1, 20, 23 (in-app proxy); end-to-end measurement OQ-13 |
| NFR usability (no code) | 10, 15 |
| NFR performance (progress, 30 s P95) | 7.2, 19, 24 |
| NFR scalability | 21, 24 |
| NFR FinOps | 7.2, 12, 18, 19.1, 21, 23 |
| NFR reliability/integrity | 7, 7.2, 18, 24 |

Every R1–R16 and NFR maps to at least one task. Tasks C1–C5 are conditional and carry their gating OQ/risk; nothing architecturally foreseen but un-gated is presented as MVP-core work.

---

## Open item surfaced during this Tasks revision (needs human decision — not resolved by assumption)

- **OQ-17 — parameter dedup key.** Design §6.2 and task 2 dedup parameters by `(name, scope)`, but the fixture's `parameters` carry no `scope` field (scope exists only on `rules`/`motivos`), so the source of a parameter's `scope` for the dedup key is undefined. Task 2 therefore applies a **provisional, fixture-scoped** behavior (key by `name` while `scope` is absent; predefined-vs-predefined collisions are blocking; all merges/conflicts stay traceable). Resolution rules:
  - the **definitive** dedup key depends on confirmation of the **real Policy Spec contract** or an explicit, evidence-based human decision — it is **not** to be resolved by assumption;
  - the fixture's missing `scope` **must not be "fixed" silently**, and the fixture's absence of `scope` **must not be used to infer** how the real system behaves (the provisional `name`-only key is a demo fallback, not a model of production);
  - the provisional strategy is explicitly **not** the definitive rule for the real schema;
  - adapting to the real schema remains gated by the already-registered questions, **especially OQ-2 (real Policy Spec owner/availability/freshness) and OQ-15 (minimal real structure/validation)**, and is carried out under conditional task **C5**.
  This is a documentation/decision gap, **not a blocker** for starting the MVP-core tasks on the synthetic fixture, because the provisional behavior is explicitly delimited above.

## Approval Gate

This is the Tasks phase deliverable. Per the Kiro Specs workflow, implementation does not begin until this plan is explicitly approved. On approval, tasks are executed in order; conditional tasks (C1–C5) stay blocked until their gating open question is resolved by a human decision.

## Revision History

| Version | Change | Reason |
|---------|--------|--------|
| 0.1 | Initial tasks drafted from Design 1.0. | — |
| 1.1 | Tasks 12.1 (generators G1/G2) and 12.2 (feedback-aware ranking). | Requirements 1.1 R8.5–8.6; design §10.3. |
| 1.1 | Task 19.1 (product metrics and token usage). | Requirements 1.1 Primary-objective NFR 2–3; design §12. |
| 1.1 | Phase 9, tasks 21–23 (CDK stack, Bedrock + Guardrails, CloudWatch). | Design 1.1 §16. |
| 1.1 | Task 3.1 `area` warning; task 14 area rendering; task 20 extended with the G2 finding; C4 names the DynamoDB store. | Design 1.1 §6.1, §10.3, §16. |
| 1.2 | Task 7.2 (asynchronous, idempotent, reproducible execution) and 9.3 (DynamoDB persistence + S3 audit lake) added to the core. | Requirements 1.2 R14.4–14.6, NFR FinOps 3, Reliability 3; design D-11, D-12. |
| 1.2 | Task 16 records Accept / Reject / Defer decisions, immutable and superseded; task 18 adds model-outage mode and idempotency keys. | Requirements 1.2 R10.5–10.6, NFR Reliability 2–3. |
| 1.2 | Task 21 provisions ECS Fargate, API Gateway + VPC Link + ALB, DynamoDB, audit bucket, Athena and Cognito groups with an Azure AD slot; task 24 validates scale and resilience. | Design 1.2 §16, D-9; team decisions D-Q5, D-Q7, D-Q8, D-Q9. |
| 1.2 | C4 narrowed to storage-level immutability (Object Lock); persistence is now core. | OQ-16 and OQ-10 resolved. |
| 1.2 | Tasks 2, 3.1, 7, 14 and 15 read Playground metadata from the complementary extensions file and the synthetic dataset; the Policy Spec fixture is never modified. | R16.3; design §6.1.1. |
