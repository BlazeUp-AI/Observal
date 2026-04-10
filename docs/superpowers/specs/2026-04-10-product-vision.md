# Observal: Agent Registry with Observability

**Date:** 2026-04-10  
**Epic:** [#77 - Pivot to Agent-Centric Registry](https://github.com/BlazeUp-AI/Observal/issues/77)

## What is Observal?

**Observal is a self-hosted agent registry for AI-assisted coding.** Organizations use it to discover, compose, deploy, and monitor AI agents across their engineering teams.

Think of it like **Docker Hub for AI agents**: developers submit components (MCPs, skills, hooks, prompts, sandboxes) but users only pull complete agents. The registry provides version control, dependency management, and runtime observability for every agent deployed.

## The Car Factory Analogy

```
Components In (Parts)          Agents Out (Complete Cars)
─────────────────────         ──────────────────────────
→ MCPs                         
→ Skills                        → Code Review Agent
→ Hooks                         → Test Generation Agent
→ Prompts                       → Debugging Agent
→ Sandboxes                     → Documentation Agent
```

**Users submit parts, but only get out complete cars.** You don't install individual MCPs or skills—you pull an agent that bundles everything together, tested and ready to run.

## Core Value Proposition

### For Engineering Teams
"Deploy production-ready AI agents with full visibility into what they're doing and whether they're helping."

### For Platform Teams  
"Run your own agent registry with private components, org-level access control, and telemetry export to your existing observability stack."

### For Agent Builders
"Compose agents from a component marketplace, version them in Git, and see real usage metrics from deployments."

## Product Pillars

### 1. Agent Registry (Primary)

**The main product:** A self-hosted marketplace where organizations discover, compose, and distribute AI agents.

**Core Features:**
- **Public + Private Components**: Browse public MCPs/skills, add private org-internal components
- **Git-Based Versioning**: All components sourced from Git (GitHub/GitLab/Bitbucket), version pinned via commits/tags
- **Agent Composition**: Visual builder (Web UI) + CLI to assemble agents from components
- **One-Command Deploy**: `observal pull code-reviewer --ide cursor` installs agent with all dependencies
- **Leaderboards & Discovery**: Most downloaded agents, trending components, user ratings
- **FastMCP Enforcement**: All MCPs validated to use FastMCP for standardization

**Why Agent-First?**
- Clear mental model: users understand "install an agent" better than "install 5 MCPs + 3 skills"
- Reduces decision fatigue: curated bundles vs. infinite component combinations
- Network effects: popular agents drive component discovery, not vice versa
- Natural monetization: enterprise agents, private registries, agent marketplace

### 2. Observability & Telemetry (Secondary)

**The differentiator:** Unlike other agent platforms, Observal tells you whether your agents are actually helping.

**Core Features:**
- **Transparent Telemetry**: Shims/proxies capture every tool call, skill activation, hook execution without modifying behavior
- **Trace Visualization**: See the full tree of MCP calls, skill invocations, and LLM interactions for each session
- **Real-Time Streaming**: WebSocket-based trace viewer updates live as agents work
- **Component Metrics**: Which MCPs are slowest? Which skills cause errors? Which hooks block legitimate actions?
- **Download Analytics**: How many users installed this agent? Which components are most reused?

**Why Observability Matters:**
- Teams can't improve what they can't measure
- Identifies which tools speed up development vs. waste time
- Detects patterns (e.g., "filesystem-mcp times out on large repos")
- Justifies investment in AI tooling to leadership

### 3. Metrics & Dashboards (Secondary)

**The integration layer:** Observal doesn't replace your existing observability tools—it feeds them.

**Core Features:**
- **Prometheus Exporter**: `/metrics` endpoint for Grafana dashboards
- **Loki Exporter**: Stream agent logs to Grafana Loki
- **Datadog Exporter**: Send traces to Datadog APM via OpenTelemetry
- **OpenTelemetry Support**: Works with any OTEL-compatible backend (Jaeger, Tempo, Honeycomb)
- **Pre-Built Dashboards**: Grafana JSON templates for agent performance, MCP latency, skill activation rates

**Why Export, Not Replace:**
- Organizations already have observability stacks (Grafana, Datadog, etc.)
- Observal specializes in agent-specific metrics, existing tools handle infrastructure
- Lower barrier to adoption: "add to your stack" vs. "replace your stack"

### 4. Evals (Future)

**The quality gate:** Automated evaluation of agent performance using LLM-as-judge and structural checks.

**Planned Features:**
- **Session Scoring**: After each agent session, score across dimensions (tool selection, prompt quality, code correctness)
- **Scorecards**: Compare agent versions on real developer workflows
- **RAGAS for RAG**: Evaluate GraphRAG retrieval spans (faithfulness, relevancy, precision, recall)
- **A/B Testing**: Deploy two agent versions, route traffic, compare scores
- **Regression Detection**: Alert when new agent version performs worse than previous

**Why Evals Later:**
- Registry must work well first (no point evaluating agents you can't deploy)
- Requires corpus of real telemetry data to be meaningful
- LLM-as-judge quality improving rapidly (wait for better models)

**Current Status:** Basic eval engine exists but not production-ready. Phase 4 work.

## User Personas

### 1. Platform Engineer (Primary)
**Goal:** Set up internal agent registry for 100+ person eng team  
**Needs:**
- Private component hosting (can't use public MCPs due to security policy)
- Org-level access control (only eng team sees internal tools)
- Integration with existing Datadog/Grafana stack
- Self-hosted (no SaaS, data stays internal)

**Journey:**
```
1. Deploy Observal via Docker Compose
2. Configure internal GitLab as component source
3. Import org's private MCPs/skills
4. Create "approved-stack" agent with blessed components
5. Developers pull agents via CLI
6. Platform team monitors usage in Grafana
```

### 2. Agent Builder (Secondary)
**Goal:** Create and share reusable agents  
**Needs:**
- Discover existing components (browse MCP library)
- Compose agent with Web UI (no YAML editing)
- Test agent in sandbox before publishing
- See download metrics (validate market demand)

**Journey:**
```
1. Browse component library ("what MCPs exist?")
2. Add filesystem-mcp + database-mcp + tdd-skill to new agent
3. Test in sandbox (observal agent test)
4. Publish to registry (observal agent publish)
5. Share with team ("observal pull my-agent")
6. Monitor: "50 installs, 4.5 stars, avg 20 tool calls/session"
```

### 3. Developer (End User)
**Goal:** Install agent and start coding  
**Needs:**
- One command to install (`observal pull <agent>`)
- Works with existing IDE (Claude Code, Cursor, Kiro, VS Code)
- Zero configuration (agent handles MCP setup, shims, etc.)
- Visibility into what agent is doing (trace viewer)

**Journey:**
```
1. Browse agent registry ("what agents exist?")
2. Find "code-reviewer" agent (4.8 stars, 1k downloads)
3. Run: observal pull code-reviewer --ide cursor
4. Agent auto-installs with all dependencies
5. Open Cursor, agent is available
6. Review session traces in Observal dashboard
```

## Competitive Landscape

| Product | Category | Positioning | Key Difference |
|---------|----------|-------------|----------------|
| **Anthropic MCP** | Protocol | Open protocol for tool integration | We're a registry/marketplace for MCP servers |
| **Hugging Face** | Model Hub | Discover and deploy AI models | We focus on agents (composed tools), not models |
| **Docker Hub** | Container Registry | Discover and deploy containers | Similar model applied to AI agents |
| **Cursor/Claude Code** | AI IDE | Code editor with AI features | We provide agents that plug into these IDEs |
| **Langfuse** | LLM Observability | Trace LLM calls | We trace the full agent stack (tools, skills, hooks) |
| **Weights & Biases** | ML Ops | Experiment tracking for ML | We focus on agent development, not model training |

**Unique Position:** We're the only agent registry with built-in observability and telemetry export.

## Success Metrics

### Phase 1 (MVP Registry) - Months 1-3
- [ ] 10 organizations self-host Observal
- [ ] 100+ agents in public registry
- [ ] 500+ components (MCPs, skills, hooks, prompts, sandboxes)
- [ ] 1,000 agent installs via `observal pull`

### Phase 2 (Observability) - Months 4-6  
- [ ] 50 orgs exporting to Grafana/Datadog
- [ ] 10,000 agent sessions traced
- [ ] 50% of installs using telemetry features
- [ ] 5 case studies of teams improving workflows based on metrics

### Phase 3 (Growth) - Months 7-12
- [ ] 200 organizations (50 paid enterprise)
- [ ] 1,000+ agents, 5,000+ components
- [ ] 100,000 agent installs
- [ ] Component marketplace with paid listings

### Phase 4 (Evals) - Year 2
- [ ] Eval engine running on 80% of traces
- [ ] A/B testing framework used by 20+ orgs
- [ ] Automated regression detection
- [ ] Agent quality scoring standard adopted industry-wide

## Go-To-Market Strategy

### 1. Open Source Community (Phase 1)
- Launch on GitHub with Apache 2.0 license
- Submit to Hacker News, Reddit (r/LocalLLaMA, r/MachineLearning)
- Write blog posts: "We built Docker Hub for AI agents"
- Create video demos: "0 to deployed agent in 5 minutes"
- Seed public registry with 20 high-quality agents

### 2. Self-Hosted Enterprise (Phase 2)
- Target: 100-1000 person eng teams with security requirements
- Sales motion: Inbound (download, trial, convert to paid support)
- Pricing: Free (self-hosted) + Paid (enterprise features)
- Enterprise features: SSO, audit logs, priority support, SLAs

### 3. Agent Marketplace (Phase 3)
- Enable paid agent listings (builders set price)
- Observal takes 20% commission
- Verified badges for high-quality agents
- Enterprise procurement (bulk licenses, site-wide deployments)

## Technical Architecture (High-Level)

```
┌─────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                 │
│  - Agent registry browser                           │
│  - Component library                                │
│  - Agent builder (visual composer)                  │
│  - Trace viewer (live streaming)                    │
│  - Metrics dashboards                               │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Backend API (Python FastAPI)                       │
│  - Registry CRUD (agents, components)               │
│  - Git mirroring service                            │
│  - Admin review workflow                            │
│  - Telemetry ingestion                              │
│  - GraphQL API (traces, spans, metrics)             │
└─────────────────────────────────────────────────────┘
         │                             │
         ▼                             ▼
┌──────────────────┐        ┌──────────────────────┐
│  PostgreSQL      │        │  ClickHouse          │
│  - Agents        │        │  - Traces            │
│  - Components    │        │  - Spans             │
│  - Users/Orgs    │        │  - Scores            │
│  - Downloads     │        │  - Metrics           │
└──────────────────┘        └──────────────────────┘
         │                             │
         ▼                             ▼
┌─────────────────────────────────────────────────────┐
│  Exporters                                          │
│  - Prometheus /metrics                              │
│  - Loki (log streaming)                             │
│  - Datadog (StatsD/OTEL)                            │
│  - OpenTelemetry (generic)                          │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  User's Observability Stack                         │
│  - Grafana dashboards                               │
│  - Datadog APM                                      │
│  - Custom dashboards                                │
└─────────────────────────────────────────────────────┘
```

## Roadmap

### Q2 2026: Core Registry
- [x] #78 - Redesign data model for agent-centric architecture
- [ ] #79 - Implement Git mirroring service for components
- [ ] #80 - Build agent composition and resolver
- [ ] #81 - Implement `observal pull` command
- [ ] #82 - Add agent CLI commands (init, add, build, publish)
- [ ] #91 - Remove GraphRAG registry type
- [ ] #92 - Enforce FastMCP for all MCPs
- [ ] #93 - Implement download tracking with bot prevention

### Q3 2026: Web UI
- [ ] #83 - Build component browser (read-only)
- [ ] #84 - Build agent builder UI
- [ ] #85 - Build public agent registry frontend

### Q4 2026: Telemetry Exporters
- [ ] #86 - Implement Prometheus/Grafana exporter
- [ ] #87 - Implement Loki log exporter
- [ ] #88 - Implement Datadog/OpenTelemetry exporter

### Q1 2027: Private Registry
- [ ] #89 - Add org-level auth and private components
- [ ] #90 - Support internal Git providers (GitLab/Bitbucket self-hosted)

### Q2 2027: Evals (Phase 4)
- [ ] Eval engine improvements
- [ ] A/B testing framework
- [ ] Automated regression detection
- [ ] Agent quality scoring

## Design Principles

### 1. Registry First, Observability Second
The registry must work perfectly even if you never look at a single trace. Observability is a value-add, not a prerequisite.

### 2. Self-Hosted by Default
Organizations own their data. SaaS is optional, self-hosted is tier-1 supported.

### 3. Git is the Source of Truth
Components live in Git repos. Observal mirrors and caches them, but Git is authoritative. No vendor lock-in.

### 4. IDE Agnostic
Support Claude Code, Cursor, Kiro, VS Code, Windsurf, Gemini CLI, Codex CLI. Don't favor any IDE.

### 5. Export, Don't Replace
Integrate with existing observability stacks (Grafana, Datadog). Don't force teams to abandon their tools.

### 6. Zero Configuration Pull
`observal pull <agent>` should work with zero config files edited. The agent manifest contains everything needed.

### 7. FastMCP Standard
Enforce FastMCP for all MCPs. Standardization enables automatic validation, tool introspection, and better DX.

### 8. Component Marketplace
Components should be discoverable, rateable, and eventually monetizable. Build for a thriving ecosystem.

## Open Questions

1. **Monetization:** Free forever? Paid enterprise features? Transaction fees on marketplace?
2. **SaaS Option:** Do we offer cloud-hosted Observal, or only self-hosted?
3. **Agent Certification:** Should we have "verified" badges for high-quality agents?
4. **Component Namespacing:** How do we prevent name collisions (e.g., two "filesystem-mcp"s)?
5. **Eval Standards:** Can we create industry-standard eval benchmarks for agent quality?

## Conclusion

**Observal is Docker Hub for AI agents.** It solves the agent distribution and observability problem that every engineering team faces when adopting AI-assisted coding.

By positioning as a registry first, we have a clear value prop ("install production-ready agents") with observability as a powerful differentiator ("see what's working and what's not").

The self-hosted model targets our best customers (security-conscious orgs with 100+ engineers) while the component marketplace creates long-term network effects.

Success means becoming the standard way teams discover, deploy, and monitor AI agents—just like Docker Hub became the standard for containers.
