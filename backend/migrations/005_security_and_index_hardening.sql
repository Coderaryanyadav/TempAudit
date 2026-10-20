-- 005_security_and_index_hardening.sql
-- Completes index coverage and ensures rate_limits index is tracked in versioned schema

CREATE INDEX IF NOT EXISTS idx_rate_limits_key_ts ON rate_limits(key, timestamp);
