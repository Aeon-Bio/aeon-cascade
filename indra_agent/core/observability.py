"""Observability layer for INDRA agent.

Provides:
- Structured logging
- Distributed tracing
- Metrics collection
- Performance monitoring

This addresses ARCHITECTURE_FIX_PLAN.md Issue #9 (Zero Observability).
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """System-wide metrics collector.

    Tracks:
    - INDRA API calls and cache hits
    - Bedrock API calls and throttles
    - Average latencies
    - Error rates
    """

    # INDRA metrics
    indra_calls: int = 0
    indra_cache_hits: int = 0
    indra_errors: int = 0
    indra_timeouts: int = 0
    indra_total_latency_ms: float = 0.0

    # Bedrock metrics
    bedrock_calls: int = 0
    bedrock_cache_hits: int = 0
    bedrock_throttles: int = 0
    bedrock_errors: int = 0
    bedrock_total_latency_ms: float = 0.0

    # Graph construction metrics
    graphs_built: int = 0
    avg_nodes_per_graph: float = 0.0
    avg_edges_per_graph: float = 0.0

    # Overall metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_request_latency_ms: float = 0.0

    def __post_init__(self):
        """Initialize derived metrics."""
        self.start_time = time.time()

    @property
    def indra_cache_hit_rate(self) -> float:
        """Calculate INDRA cache hit rate."""
        total = self.indra_calls + self.indra_cache_hits
        return self.indra_cache_hits / total if total > 0 else 0.0

    @property
    def bedrock_cache_hit_rate(self) -> float:
        """Calculate Bedrock cache hit rate."""
        total = self.bedrock_calls + self.bedrock_cache_hits
        return self.bedrock_cache_hits / total if total > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Calculate overall error rate."""
        total = self.successful_requests + self.failed_requests
        return self.failed_requests / total if total > 0 else 0.0

    @property
    def avg_indra_latency_ms(self) -> float:
        """Calculate average INDRA API latency."""
        return self.indra_total_latency_ms / self.indra_calls if self.indra_calls > 0 else 0.0

    @property
    def avg_bedrock_latency_ms(self) -> float:
        """Calculate average Bedrock API latency."""
        return self.bedrock_total_latency_ms / self.bedrock_calls if self.bedrock_calls > 0 else 0.0

    @property
    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds."""
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        return {
            "indra": {
                "calls": self.indra_calls,
                "cache_hits": self.indra_cache_hits,
                "cache_hit_rate": f"{self.indra_cache_hit_rate:.2%}",
                "errors": self.indra_errors,
                "timeouts": self.indra_timeouts,
                "avg_latency_ms": f"{self.avg_indra_latency_ms:.1f}",
            },
            "bedrock": {
                "calls": self.bedrock_calls,
                "cache_hits": self.bedrock_cache_hits,
                "cache_hit_rate": f"{self.bedrock_cache_hit_rate:.2%}",
                "throttles": self.bedrock_throttles,
                "errors": self.bedrock_errors,
                "avg_latency_ms": f"{self.avg_bedrock_latency_ms:.1f}",
            },
            "graphs": {
                "built": self.graphs_built,
                "avg_nodes": f"{self.avg_nodes_per_graph:.1f}",
                "avg_edges": f"{self.avg_edges_per_graph:.1f}",
            },
            "overall": {
                "total_requests": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "error_rate": f"{self.error_rate:.2%}",
                "avg_latency_ms": f"{self.avg_request_latency_ms:.1f}",
                "uptime_seconds": f"{self.uptime_seconds:.0f}",
            },
        }

    def log_summary(self):
        """Log metrics summary."""
        logger.info("=== System Metrics Summary ===")
        logger.info(f"INDRA: {self.indra_calls} calls, {self.indra_cache_hit_rate:.1%} cache hit rate, "
                    f"{self.avg_indra_latency_ms:.0f}ms avg latency")
        logger.info(f"Bedrock: {self.bedrock_calls} calls, {self.bedrock_throttles} throttles, "
                    f"{self.avg_bedrock_latency_ms:.0f}ms avg latency")
        logger.info(f"Overall: {self.total_requests} requests, {self.error_rate:.1%} error rate, "
                    f"{self.avg_request_latency_ms:.0f}ms avg latency")


# Global metrics instance
_metrics = Metrics()


def get_metrics() -> Metrics:
    """Get global metrics instance."""
    return _metrics


@dataclass
class TraceSpan:
    """Distributed tracing span.

    Simplified tracing without OpenTelemetry dependency for MVP.
    Can be replaced with OpenTelemetry in production.
    """

    operation_name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "in_progress"  # "in_progress" | "success" | "error"
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Calculate span duration in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000

    def set_attribute(self, key: str, value: Any):
        """Set span attribute."""
        self.attributes[key] = value

    def set_status(self, status: str, error: Optional[str] = None):
        """Set span status."""
        self.status = status
        self.error = error
        if self.end_time is None:
            self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Export span as dictionary."""
        return {
            "operation": self.operation_name,
            "duration_ms": f"{self.duration_ms:.1f}",
            "status": self.status,
            "attributes": self.attributes,
            "error": self.error,
        }


class ObservabilityLayer:
    """Central observability layer.

    Usage:
        obs = ObservabilityLayer()

        # Trace an operation
        with obs.trace_operation("indra_query", source="PM2.5", target="CRP"):
            result = await indra_api.get_paths(source, target)

        # Record metrics
        obs.record_indra_call(latency_ms=123, cache_hit=False)
        obs.record_bedrock_call(latency_ms=456, throttled=False)

        # Get metrics
        metrics = obs.get_metrics()
        logger.info(metrics.to_dict())
    """

    def __init__(self):
        """Initialize observability layer."""
        self.metrics = _metrics
        self.logger = logger

    @contextmanager
    def trace_operation(self, operation_name: str, **attributes):
        """Trace an operation with timing and error handling.

        Args:
            operation_name: Name of the operation (e.g., "indra_query")
            **attributes: Additional attributes to log (e.g., source="PM2.5")

        Yields:
            TraceSpan: Span object for adding attributes during execution

        Example:
            with obs.trace_operation("indra_query", source="PM2.5", target="CRP") as span:
                result = await indra_api.get_paths("PM2.5", "CRP")
                span.set_attribute("paths_found", len(result))
        """
        span = TraceSpan(operation_name=operation_name, attributes=attributes)

        self.logger.info(
            f"→ {operation_name} started",
            extra={"attributes": attributes}
        )

        try:
            yield span
            span.set_status("success")

            self.logger.info(
                f"✓ {operation_name} completed in {span.duration_ms:.0f}ms",
                extra=span.to_dict()
            )

        except Exception as e:
            span.set_status("error", str(e))

            self.logger.error(
                f"✗ {operation_name} failed after {span.duration_ms:.0f}ms: {e}",
                extra=span.to_dict(),
                exc_info=True
            )

            # Update metrics
            if "indra" in operation_name.lower():
                self.metrics.indra_errors += 1
            elif "bedrock" in operation_name.lower():
                self.metrics.bedrock_errors += 1

            raise

    def record_indra_call(self, latency_ms: float, cache_hit: bool = False,
                          timeout: bool = False, error: bool = False):
        """Record INDRA API call metrics.

        Args:
            latency_ms: Call latency in milliseconds
            cache_hit: Whether result came from cache
            timeout: Whether call timed out
            error: Whether call resulted in error
        """
        if cache_hit:
            self.metrics.indra_cache_hits += 1
        else:
            self.metrics.indra_calls += 1
            self.metrics.indra_total_latency_ms += latency_ms

        if timeout:
            self.metrics.indra_timeouts += 1

        if error:
            self.metrics.indra_errors += 1

        # Log warning if latency is high
        if latency_ms > 5000:  # > 5 seconds
            self.logger.warning(
                f"Slow INDRA call: {latency_ms:.0f}ms "
                f"(cache_hit={cache_hit}, timeout={timeout})"
            )

    def record_bedrock_call(self, latency_ms: float, cache_hit: bool = False,
                            throttled: bool = False, error: bool = False):
        """Record Bedrock API call metrics.

        Args:
            latency_ms: Call latency in milliseconds
            cache_hit: Whether result came from cache
            throttled: Whether call was throttled
            error: Whether call resulted in error
        """
        if cache_hit:
            self.metrics.bedrock_cache_hits += 1
        else:
            self.metrics.bedrock_calls += 1
            self.metrics.bedrock_total_latency_ms += latency_ms

        if throttled:
            self.metrics.bedrock_throttles += 1
            self.logger.warning(
                f"Bedrock throttle detected (call #{self.metrics.bedrock_throttles})"
            )

        if error:
            self.metrics.bedrock_errors += 1

        # Log warning if latency is high
        if latency_ms > 3000:  # > 3 seconds
            self.logger.warning(
                f"Slow Bedrock call: {latency_ms:.0f}ms "
                f"(cache_hit={cache_hit}, throttled={throttled})"
            )

    def record_graph_built(self, node_count: int, edge_count: int):
        """Record graph construction metrics.

        Args:
            node_count: Number of nodes in graph
            edge_count: Number of edges in graph
        """
        self.metrics.graphs_built += 1

        # Update running averages
        n = self.metrics.graphs_built
        self.metrics.avg_nodes_per_graph = (
            (self.metrics.avg_nodes_per_graph * (n - 1) + node_count) / n
        )
        self.metrics.avg_edges_per_graph = (
            (self.metrics.avg_edges_per_graph * (n - 1) + edge_count) / n
        )

    def record_request(self, latency_ms: float, success: bool):
        """Record overall request metrics.

        Args:
            latency_ms: Total request latency in milliseconds
            success: Whether request succeeded
        """
        self.metrics.total_requests += 1

        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1

        # Update running average latency
        n = self.metrics.total_requests
        self.metrics.avg_request_latency_ms = (
            (self.metrics.avg_request_latency_ms * (n - 1) + latency_ms) / n
        )

        # Alert if error rate exceeds threshold
        if self.metrics.error_rate > 0.05:  # > 5%
            self.logger.error(
                f"High error rate: {self.metrics.error_rate:.1%} "
                f"({self.metrics.failed_requests}/{self.metrics.total_requests} requests failed)"
            )

    def get_metrics(self) -> Metrics:
        """Get current metrics snapshot."""
        return self.metrics

    def log_metrics(self):
        """Log current metrics summary."""
        self.metrics.log_summary()


# Global observability instance
_observability = ObservabilityLayer()


def get_observability() -> ObservabilityLayer:
    """Get global observability instance.

    Example:
        obs = get_observability()
        with obs.trace_operation("my_operation"):
            # ... do work ...
    """
    return _observability
