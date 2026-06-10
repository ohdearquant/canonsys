"""Infrastructure phrase constants.

Threshold values and defaults for infrastructure operations.
"""

__all__ = [
    "DEFAULT_COOLDOWN_HOURS",
    "DEFAULT_LOOKBACK_HOURS",
    "DEFAULT_MAX_SAFE_DEPTH",
    "DEFAULT_SLA_HOURS",
    "DEFAULT_THRESHOLD_PCT",
    "THRESHOLD_HIGH",
    "THRESHOLD_LOW",
    "THRESHOLD_MEDIUM",
]

# DR test cooldown defaults
DEFAULT_COOLDOWN_HOURS = 168  # 1 week
DEFAULT_SLA_HOURS = 4  # 4 hours = ~99.5% availability over 30 days

# Row count thresholds for exfiltration risk
THRESHOLD_LOW = 1000
THRESHOLD_MEDIUM = 10000
THRESHOLD_HIGH = 100000

# Subdomain depth threshold
DEFAULT_MAX_SAFE_DEPTH = 4

# Utilization volatility defaults
DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_THRESHOLD_PCT = 50
