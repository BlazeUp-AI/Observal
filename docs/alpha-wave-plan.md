# Alpha Wave — Dashboard Rewrite Plan

## Context Summary

We're rewriting the Observal web UI from bare-bones HTML to a Langfuse-quality dashboard.

### Current state
- Vite + React + urql + Tailwind v4 (just added)
- Dark theme with CSS variables
- Basic components: Card, StatCard, Badge, DataTable, Tabs, EmptyState, PageHeader, Spinner
- Collapsible sidebar with 8 nav items
- Pages: Overview (stat cards + area chart), Traces (table), Trace Detail (span table), MCP Metrics (stat cards + bar chart), MCP List, Agent List, Reviews, Settings, Login
- All pages are functional but visually basic — no filters, no trace tree, no sessions, no proper charts

### What Langfuse has that we need
- Proper sidebar with grouped sections (Observability, Evaluation, etc.)
- Dashboard home with multiple chart cards (traces over time, top traces bar list, latency charts, model usage, cost, user activity, scores)
- Traces table with: sortable columns, date range picker, filters sidebar, column visibility, input/output preview, token/cost badges, click-to-detail
- Trace detail with: hierarchical tree view (indented spans with connector lines), timeline/gantt view, span content (input/output, tokens, cost, scores), back navigation
- Sessions page: session list with trace count, duration, cost, tokens — click to conversation timeline
- Scores page
- Users page
- Proper status badges with animated dots
- Recharts with proper theming (gradients, grid, tooltips)

### What we adapt for Observal (not in Langfuse)
- MCP Servers page (registry browser)
- Agents page (agent registry)
- Reviews page (admin workflow)
- MCP Metrics page (per-MCP analytics)
- Evaluations page (LLM-as-judge scorecards)

## Tech Stack (matching Langfuse)
- Tailwind CSS v4 (already installed)
- Recharts (already installed)
- lucide-react (already installed)
- clsx + tailwind-merge (already installed)
- class-variance-authority (already installed)
- @tanstack/react-virtual (need to install — for virtualized trace trees)

## File Structure

```
src/
├── index.css                    # Tailwind theme (dark + light)
├── main.tsx                     # Entry
├── App.tsx                      # Router + providers
├── lib/
│   ├── utils.ts                 # cn()
│   ├── urql.ts                  # GraphQL client
│   ├── queries.ts               # GraphQL queries
│   └── api.ts                   # REST API helper
├── components/
│   ├── ui/                      # Base component library
│   │   ├── badge.tsx
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── data-table.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── separator.tsx
│   │   ├── spinner.tsx
│   │   ├── stat-card.tsx
│   │   ├── status-badge.tsx
│   │   ├── tabs.tsx
│   │   └── empty-state.tsx
│   ├── layout/
│   │   ├── AppLayout.tsx        # Sidebar + content wrapper
│   │   ├── PageHeader.tsx       # Page title + breadcrumb + actions
│   │   └── Sidebar.tsx          # Navigation with groups
│   ├── charts/
│   │   ├── AreaTimeSeriesChart.tsx
│   │   ├── BarChart.tsx
│   │   ├── HorizontalBarList.tsx
│   │   └── ChartCard.tsx        # DashboardCard wrapper for charts
│   └── traces/
│       ├── TraceTree.tsx         # Hierarchical span tree
│       ├── TraceTreeNode.tsx     # Single tree node with connectors
│       ├── SpanContent.tsx       # Span detail (name, tokens, cost, status)
│       └── TraceTimeline.tsx     # Gantt-style timeline
├── pages/
│   ├── Dashboard.tsx            # Home with chart grid
│   ├── Traces.tsx               # Trace list with filters
│   ├── TraceDetail.tsx          # Tree + timeline + detail panel
│   ├── Sessions.tsx             # Session list
│   ├── SessionDetail.tsx        # Conversation timeline
│   ├── McpServers.tsx           # MCP registry
│   ├── McpDetail.tsx            # MCP metrics + traces
│   ├── Agents.tsx               # Agent registry
│   ├── AgentDetail.tsx          # Agent metrics + evals
│   ├── Reviews.tsx              # Admin review queue
│   ├── Scores.tsx               # Score analytics
│   ├── Evaluations.tsx          # Eval scorecards
│   ├── Users.tsx                # User analytics
│   ├── Settings.tsx             # Enterprise settings
│   └── Login.tsx                # Auth
```

## Implementation Order

### Batch 1: Foundation (parallel subagents)
1. Theme + base UI components (badge, button, card, input, select, separator, status-badge, tabs)
2. Layout (sidebar with grouped nav, page header with breadcrumbs)
3. Chart components (area time series, bar chart, horizontal bar list, chart card wrapper)
4. REST API helper + auth context

### Batch 2: Core Pages (parallel subagents)
1. Dashboard home (stat cards + chart grid: traces over time, top tools, latency, errors)
2. Traces page (filterable table with date range, column visibility, token/cost badges)
3. Trace detail (tree view with connector lines, span content, timeline)
4. Sessions page + session detail

### Batch 3: Registry Pages (parallel subagents)
1. MCP Servers + MCP Detail (registry + metrics)
2. Agents + Agent Detail (registry + evals)
3. Reviews (admin queue with approve/reject)
4. Scores + Users + Evaluations + Settings

### Batch 4: Polish
1. Animations, transitions, loading states
2. Responsive design
3. Keyboard shortcuts
4. Final integration testing
