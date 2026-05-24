<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Concepts

Understand the mental models that power Observal.

This section goes beyond setup and commands to explain the architectural ideas behind the platform — how telemetry flows through the system, how evaluations are computed, and why Observal is designed the way it is.

If you're looking to contribute, extend integrations, or deeply understand the platform internals, start here.

| Page                  | What it covers                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------ |
| **Data model**        | How traces, spans, sessions, scores, and evaluations are structured and connected                      |
| **Evaluation engine** | The scoring pipeline, BenchJack hardening, sanitization layers, canary checks, and watchdog safeguards |
| **Shim vs proxy**     | How transparent interception works, when each strategy is used, and the tradeoffs between them         |

## Recommended Reading Path

New to Observal?

Start with **Getting Started → Core Concepts** for the fast 10-minute overview.

Then return to this section for the deeper architectural dive into how the platform operates internally.

## Why These Concepts Matter

Observal is not just an observability dashboard.

It is a full telemetry and evaluation layer for AI coding agents — designed to make agent behavior measurable, inspectable, reproducible, and improvable across different IDEs, models, and execution environments.

Understanding these concepts will help you:

* Debug agent behavior faster
* Build better integrations
* Contribute to the platform confidently
* Interpret traces and evaluations correctly
* Extend Observal’s telemetry pipeline safely
