# Evaluation engine

Observal's evaluation engine scores recorded agent sessions so teams can compare agents, detect regressions, and understand where an agent is weak.

The engine evaluates real traces and spans collected through Observal's telemetry pipeline. It combines managed evaluation templates, LLM-as-judge scoring, deterministic fallback scoring, and scorecards that make agent performance easier to inspect over time.

For deeper details, see:

- [Concepts: Evaluation engine](concepts/evaluation.md)
- [Use case: Evaluate and compare agents](use-cases/evaluate-agents.md)
- [Self-hosting: Evaluation engine](self-hosting/evaluation-engine.md)

## What the eval engine does

The eval engine helps answer questions such as:

- Did the agent complete the user's goal?
- Did it choose the right tools?
- Did tool outputs actually help the task?
- Was the reasoning clear?
- Was the final response useful?
- Was the answer grounded in retrieved or tool-provided context?
- Did the agent retrieve relevant memory or context?
- Did a newer agent version improve or regress?

A typical evaluation flow is:

1. Fetch a trace and its spans.
2. Select the managed templates that apply to each span type.
3. Score each applicable dimension.
4. Store the generated scores.
5. Build scorecards that summarize the run.
6. Compare scorecards across traces, agents, and versions.

The engine is designed around a pluggable backend interface. Today, the primary backend is LLM-as-judge, with a deterministic fallback when no model is configured. The interface is intentionally replaceable so future judge implementations can be added without changing the user workflow.

## Evaluation dimensions

Observal includes managed evaluation templates for common agent-quality dimensions.

| Dimension | Applies to | What it checks |
| --- | --- | --- |
| `tool_selection_accuracy` | `tool_call` spans | Whether the agent selected the right tool for the user's goal. |
| `tool_output_utility` | `tool_call` spans | Whether the tool output advanced the task. |
| `reasoning_clarity` | `reasoning_step` spans | Whether the reasoning step was coherent and logically useful. |
| `response_quality` | `agent_turn` spans | Whether the agent response was useful, complete, and clear. |
| `graph_faithfulness` | `retrieval` spans | Whether GraphRAG output was supported by retrieved context. |
| `recall_accuracy` | `memory_retrieve` spans | Whether retrieved memory was relevant to the current task. |

Some builds also include additional GraphRAG-oriented templates, such as answer relevancy and context precision. These use the same backend and scoring flow as the other managed templates.

Each managed template asks the backend to return JSON containing:

- a numeric score
- a short reason or justification

Scores are written with the trace, span, agent, template, source, value, comment, and timestamp so they can be queried and aggregated later.

## Scorecards

A scorecard is the user-facing result of an evaluation run.

A scorecard can contain:

- overall score
- overall grade
- evaluated agent version
- trace ID
- per-dimension scores
- per-dimension notes
- recommendations
- bottleneck
- raw backend output for debugging

The legacy scorecard path uses a 0-10 score and maps it to a letter grade.

| Score | Grade |
| --- | --- |
| `>= 9` | `A+` |
| `>= 8` | `A` |
| `>= 7` | `B` |
| `>= 6` | `C` |
| `>= 5` | `D` |
| `< 5` | `F` |

The structured scoring path can also expose composite scoring, dimension scores, penalty counts, warnings, and scoring recommendations. This path is preferred when detailed span data is available.

## Running evals from the CLI

Run an evaluation for an agent:

```bash
observal admin eval run <agent-id>
```

Run an evaluation for a specific trace:

```bash
observal admin eval run <agent-id> --trace <trace-id>
```

List scorecards for an agent:

```bash
observal admin eval scorecards <agent-id>
```

Filter scorecards by version:

```bash
observal admin eval scorecards <agent-id> --version <version>
```

Show one scorecard:

```bash
observal admin eval show <scorecard-id>
```

Compare two versions:

```bash
observal admin eval compare <agent-id> --a <version-a> --b <version-b>
```

Show aggregate scoring stats:

```bash
observal admin eval aggregate <agent-id>
```

## API endpoints

The evaluation API is exposed under `/api/v1/eval`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/eval/agents/{agent_id}` | Run an evaluation for an agent. |
| `GET` | `/api/v1/eval/agents/{agent_id}/runs` | List evaluation runs for an agent. |
| `GET` | `/api/v1/eval/agents/{agent_id}/scorecards` | List scorecards for an agent. |
| `GET` | `/api/v1/eval/scorecards/{scorecard_id}` | Fetch one scorecard. |
| `GET` | `/api/v1/eval/agents/{agent_id}/compare` | Compare two agent versions. |
| `POST` | `/api/v1/eval/sessions/{session_id}` | Evaluate or inspect a hook-based session. |
| `POST` | `/api/v1/eval/agents/{agent_id}/session/{session_id}` | Evaluate one agent's contribution inside a session. |
| `GET` | `/api/v1/eval/agents/{agent_id}/aggregate` | Get aggregate scoring stats. |
| `GET` | `/api/v1/eval/scorecards/{scorecard_id}/penalties` | List penalties applied to a scorecard. |
| `GET` | `/api/v1/eval/agents/{agent_id}/sessions` | List telemetry sessions where the agent was used. |

Most evaluation endpoints require admin access.

## Version comparison

Version comparison helps teams decide whether an agent changed for the better.

Use:

```bash
observal admin eval compare <agent-id> --a 1.0.0 --b 1.1.0
```

The comparison endpoint computes average score data for both versions and returns the score delta.

This is useful after changing:

- prompts
- tool descriptions
- MCP configuration
- retrieval strategy
- memory behavior
- model settings
- agent packaging

For reliable comparisons:

- compare versions on similar tasks
- use multiple scorecards per version
- avoid treating a single trace as proof of improvement
- inspect dimension-level changes, not only the final score
- check bottlenecks and recommendations when scores regress

## Configuring the eval backend

The engine supports multiple backend modes.

### AWS Bedrock

```env
EVAL_MODEL_PROVIDER=bedrock
EVAL_MODEL_NAME=us.anthropic.claude-3-5-haiku-20241022-v1:0
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

The Bedrock backend uses the AWS Bedrock Runtime Converse API. The IAM principal must be allowed to invoke the configured model.

### OpenAI-compatible APIs

```env
EVAL_MODEL_PROVIDER=openai
EVAL_MODEL_URL=https://api.openai.com/v1
EVAL_MODEL_API_KEY=...
EVAL_MODEL_NAME=gpt-4o
```

This path also works with Azure OpenAI, Ollama, vLLM, and other servers that implement `/v1/chat/completions`.

For local Ollama:

```env
EVAL_MODEL_PROVIDER=openai
EVAL_MODEL_URL=http://localhost:11434/v1
EVAL_MODEL_API_KEY=
EVAL_MODEL_NAME=llama3
```

### Moonshot / Kimi

```env
EVAL_MODEL_PROVIDER=moonshot
EVAL_MODEL_API_KEY=...
EVAL_MODEL_NAME=kimi-k2.5-preview
```

When `EVAL_MODEL_PROVIDER=moonshot`, the default base URL is `https://api.moonshot.ai/v1`.

### Auto-detection

If `EVAL_MODEL_PROVIDER` is empty, Observal can infer the backend from the configured model name:

- model names containing `anthropic` route to Bedrock
- model names containing `kimi` route to Moonshot
- everything else uses the generic OpenAI-compatible path

### Fallback backend

If no eval model is configured, Observal uses deterministic heuristic scoring.

Fallback mode is useful for smoke tests and local development, but it should not be treated as a replacement for real LLM-based judgment. Configure an eval model before trusting production grades.

## Managed templates

Managed templates are built into the engine rather than authored by users at runtime.

Each template defines:

- an internal template ID
- a display name
- the span type it applies to
- the prompt used by the backend
- the expected JSON output shape

Managed templates keep scoring consistent across agents and versions. They also make scorecards easier to compare because the same dimension names and scoring prompts are reused across runs.

The core managed templates cover:

- tool selection accuracy
- tool output utility
- reasoning clarity
- response quality
- GraphRAG faithfulness
- memory recall accuracy

## Bottleneck detection

Scorecards include a bottleneck field to identify the weakest area of a run.

The bottleneck helps answer "what should we fix first?" instead of only showing a numeric score.

Examples:

| Weak area | Possible interpretation |
| --- | --- |
| Low `tool_selection_accuracy` | Tool descriptions or routing logic may be unclear. |
| Low `tool_output_utility` | Tools may return irrelevant, incomplete, or poorly formatted data. |
| Low `reasoning_clarity` | The prompt or task decomposition may be confusing. |
| Low `response_quality` | The final answer may be incomplete or hard to use. |
| Low `graph_faithfulness` | The agent may be hallucinating or failing to ground claims in retrieved context. |
| Low `recall_accuracy` | Memory retrieval may be returning irrelevant context. |

When structured scoring is available, penalties and watchdog warnings can provide additional evidence for why the bottleneck was selected.

## Extending evaluation dimensions

Custom evaluation dimensions are a future extension point.

Today, dimensions are managed in the evaluation engine. To add a new built-in dimension, a contributor would generally need to:

1. Add a managed template.
2. Choose the span type it applies to.
3. Define the expected JSON output.
4. Add tests for template selection and backend behavior.
5. Update CLI/API documentation if the dimension is user-facing.
6. Add a changelog entry when appropriate.

Future versions may expose user-authored dimensions, but the current managed-template approach keeps scoring consistent and auditable.

## Operational notes

- LLM-as-judge quality depends on the configured judge model.
- The judge model should generally be at least as capable as the agents being evaluated.
- Traces may contain sensitive data; use a local or private model when privacy requires it.
- Evaluation has cost. Run evals selectively or on representative traces.
- A single scorecard is not enough to prove a version is better.
- Version comparisons are most useful when both versions are evaluated on comparable tasks.

## Related docs

- [Concepts: Evaluation engine](concepts/evaluation.md)
- [Use case: Evaluate and compare agents](use-cases/evaluate-agents.md)
- [Self-hosting: Evaluation engine](self-hosting/evaluation-engine.md)
- [CLI reference: admin commands](cli/admin.md)