from prometheus_client import Counter, Histogram

EVENTS_INGESTED = Counter(
    "event_engine_events_ingested_total",
    "Accepted event envelopes",
    ["outcome"],
)
DELIVERY_ATTEMPTS = Counter(
    "event_engine_delivery_attempts_total",
    "Delivery adapter attempts",
    ["adapter", "outcome"],
)
DELIVERY_DURATION = Histogram(
    "event_engine_delivery_duration_seconds",
    "Delivery adapter latency",
    ["adapter"],
)
DELIVERIES_RECOVERED = Counter(
    "event_engine_deliveries_recovered_total",
    "Expired delivery leases recovered",
)
