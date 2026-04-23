# Observal Architecture

## High-Level Architecture Diagram

```mermaid
flowchart LR
IDE[IDE / CLI] --> Shim
Shim --> API[Observal Server API]
API --> PG[(PostgreSQL)]
Shim --> CH[(ClickHouse)]
API --> Web[Web UI]
Worker --> API
Worker --> CH[(ClickHouse)]