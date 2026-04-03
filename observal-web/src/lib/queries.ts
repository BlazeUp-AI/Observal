import { gql } from 'urql';

export const TRACES_QUERY = gql`
  query Traces($traceType: String, $mcpId: String, $agentId: String, $limit: Int, $offset: Int) {
    traces(traceType: $traceType, mcpId: $mcpId, agentId: $agentId, limit: $limit, offset: $offset) {
      items {
        traceId
        traceType
        mcpId
        agentId
        name
        startTime
        endTime
        ide
        tags
        metrics {
          totalSpans
          errorCount
          toolCallCount
          totalLatencyMs
        }
      }
      totalCount
      hasMore
    }
  }
`;

export const TRACE_DETAIL_QUERY = gql`
  query TraceDetail($traceId: String!) {
    trace(traceId: $traceId) {
      traceId
      traceType
      mcpId
      agentId
      userId
      name
      startTime
      endTime
      input
      output
      tags
      spans {
        spanId
        type
        name
        method
        startTime
        endTime
        latencyMs
        status
        input
        output
        error
        toolSchemaValid
        toolsAvailable
        tokenCountTotal
      }
      scores {
        scoreId
        name
        source
        value
        comment
      }
    }
  }
`;

export const MCP_METRICS_QUERY = gql`
  query McpMetrics($mcpId: String!, $start: String!, $end: String!) {
    mcpMetrics(mcpId: $mcpId, start: $start, end: $end) {
      toolCallCount
      errorRate
      avgLatencyMs
      p50LatencyMs
      p90LatencyMs
      p99LatencyMs
      timeoutRate
      schemaComplianceRate
    }
  }
`;

export const OVERVIEW_QUERY = gql`
  query Overview($start: String!, $end: String!) {
    overview(start: $start, end: $end) {
      totalTraces
      totalSpans
      toolCallsToday
      errorsToday
    }
    trends(start: $start, end: $end, granularity: "DAY") {
      date
      traces
      spans
      errors
    }
  }
`;

export const SPAN_SUBSCRIPTION = gql`
  subscription SpanCreated($traceId: String!) {
    spanCreated(traceId: $traceId) {
      spanId
      type
      name
      latencyMs
      status
    }
  }
`;
