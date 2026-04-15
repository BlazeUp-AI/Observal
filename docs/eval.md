# Evaluation Subsystem

Observal's agent evaluation pipeline. Scores agent traces across multiple dimensions using a combination of structural analysis, LLM-as-judge scoring, and adversarial robustness checks. Hardened against BenchJack-style benchmark gaming attacks.

Built by Swathi.

## Architecture

The pipeline processes a recorded agent trace through several scorers in sequence, then aggregates the results into a scorecard with a composite grade (A through F).

```
Trace
  -> TraceSanitizer         (strip injection attempts)
  -> CanaryDetector         (detect parroted canary tokens)
  -> StructuralScorer       (rule-based: tool efficiency, failures, duplicates)
  -> SLMScorer              (LLM judge: goal completion, factual grounding, thought process)
  -> AdversarialScorer      (detect benchmark gaming, evaluator probing)
  -> EvalWatchdog           (meta-check: did scoring actually score anything?)
  -> ScoreAggregator        (weighted combination, penalties, grade)
  -> Scorecard
```

## Scoring Dimensions

| Dimension | Scorer | Method |
|-----------|--------|--------|
| Task completion | SLMScorer | LLM judge evaluates whether the agent achieved its goal |
| Tool usage efficiency | StructuralScorer | Rule-based: duplicate calls, unused results, excessive retries |
| Factual grounding | SLMScorer | LLM judge checks claims against tool output |
| Thought process | SLMScorer | LLM judge evaluates reasoning chain quality |
| Adversarial robustness | AdversarialScorer | Structural: injection detection, evaluator path probing |

Each dimension produces a score from 0 to 10. The `ScoreAggregator` combines them using configurable weights, applies penalties, and maps the result to a letter grade.

## BenchJack Hardening

The pipeline is designed to resist agents that try to game their evaluations. Mitigations are organized by BenchJack pattern number:

| Pattern | Attack | Mitigation |
|---------|--------|-----------|
| 1 | Score inflation via dummy outputs | EvalWatchdog detects dimensions that return perfect scores without checking anything |
| 2 | Skipped dimensions defaulting to 100 | EvalWatchdog flags missing dimensions |
| 4 | Prompt injection in agent output | TraceSanitizer strips injection attempts before they reach the LLM judge |
| 5 | Fragile string matching | MatchingEngine uses normalized comparison with fuzzy matching |
| 6 | Scoring code that does not actually score | `test_eval_completeness.py` meta-tests validate the scoring engine itself |
| Self-test | All of the above | `test_adversarial_self.py` runs BenchJack attacks against Observal's own pipeline |

## File Map

### Backend Services (`observal-server/services/eval/`)

| File | Purpose |
|------|---------|
| `eval_service.py` | Top-level orchestrator. Wires together all scorers and runs the full pipeline. |
| `eval_engine.py` | LLM backend abstraction (`LLMJudgeBackend`, `FallbackBackend`). Calls the eval model. |
| `eval_watchdog.py` | Meta-checker that detects scoring anomalies (perfect scores, missing dimensions). |
| `sanitizer.py` | `TraceSanitizer` that strips prompt injection attempts from trace data before scoring. |
| `adversarial_scorer.py` | Structural scorer for adversarial robustness. Detects evaluator path probing and gaming attempts. |
| `canary.py` | `CanaryDetector` injects canary tokens and checks if agents parrot them back. |
| `score_aggregator.py` | Weighted dimension aggregation, penalty application, grade mapping (A through F). |
| `slm_scorer.py` | LLM-as-judge scoring for goal completion, factual grounding, and thought process. |
| `structural_scorer.py` | Rule-based scoring for tool efficiency, failures, and duplicates. Includes `MatchingEngine`. |
| `ragas_eval.py` | RAGAS metrics (faithfulness, answer relevancy, context precision, context recall) for GraphRAG spans. |

### Models and Schemas

| File | Purpose |
|------|---------|
| `models/eval.py` | `EvalRun`, `Scorecard`, `ScorecardDimension` ORM models |
| `models/scoring.py` | `ScoringDimension`, dimension weights, penalty definitions |
| `models/sanitization.py` | `SanitizationReport` model |
| `schemas/eval.py` | Pydantic request/response schemas for the eval API |
| `schemas/judge_output.py` | Structured output schemas for SLM judge responses |

### API

| File | Purpose |
|------|---------|
| `api/routes/eval.py` | REST endpoints: trigger evals, fetch scorecards, run agent-scoped evaluations |

### Frontend Components (`web/src/components/dashboard/`)

| File | Purpose |
|------|---------|
| `agent-aggregate-chart.tsx` | Score trend line/area chart |
| `dimension-radar.tsx` | Polar chart for dimension scores |
| `penalty-accordion.tsx` | Expandable penalty details |

### Tests (`tests/eval/`)

| File | What it tests |
|------|--------------|
| `test_eval_phase8.py` | Eval engine: templates, backends, trace scoring |
| `test_eval_completeness.py` | Meta-tests: validates the scoring engine actually evaluates (BenchJack Pattern 6) |
| `test_phase8a_sanitizer.py` | TraceSanitizer and SLM prompt hardening |
| `test_phase8b_matching.py` | MatchingEngine and NumericComparator |
| `test_phase8d_adversarial.py` | AdversarialScorer dimensions and penalties |
| `test_phase8e_canary.py` | CanaryDetector inject/detect/report cycle |
| `test_phase8g_pipeline.py` | Full pipeline integration: all scorers wired together |
| `test_score_aggregator.py` | Weighted aggregation and grade mapping |
| `test_slm_scorer.py` | SLM scoring with mocked backends |
| `test_structural_scorer.py` | Tool efficiency, failures, deduplication |
| `test_adversarial_self.py` | BenchJack self-attacks against Observal's own scoring |
| `test_ragas_eval.py` | RAGAS metric computation |

## Running Eval Tests

```bash
cd observal-server
uv run pytest ../tests/eval/ -q        # all eval tests (270 tests)
uv run pytest ../tests/eval/ -v -k canary  # just canary tests
```
