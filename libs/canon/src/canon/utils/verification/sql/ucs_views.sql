-- UCS-v1 SQL Views for OPA Integration
-- Author: Jason La Barbera
-- Captured: 2026-01-13
--
-- These views feed data.ceps and data.signing_keys to OPA.
-- Do NOT have OPA query Postgres directly in the hot path.

-- -----------------------------------------------------------------------------
-- View: Certificate ↔ CEP integrity checks (hash + type + lifecycle)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_certificate_cep_integrity AS
SELECT
  p.certificate_id,
  p.cep_id,
  p.cep_type AS referenced_type,
  e.cep_type AS actual_type,
  (p.cep_type = e.cep_type) AS type_matches,

  p.cep_hash AS referenced_hash,
  e.final_hash AS actual_hash,
  (p.cep_hash = e.final_hash) AS hash_matches,

  e.status AS cep_status,
  e.valid_until_utc,
  (now() <= e.valid_until_utc) AS not_expired,

  -- a single boolean gate you can consume directly
  (
    (p.cep_hash = e.final_hash)
    AND (p.cep_type = e.cep_type)
    AND (e.status = 'ACTIVE')
    AND (now() <= e.valid_until_utc)
  ) AS cep_pointer_valid
FROM ucs_evidence_pointer p
JOIN cep e ON e.cep_id = p.cep_id;


-- -----------------------------------------------------------------------------
-- View: Signing time must be valid relative to key validity + revocation
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_certificate_signing_time_valid AS
SELECT
  c.certificate_id,
  c.signing_key_id,
  c.signed_at_utc,

  k.valid_from_utc,
  k.valid_to_utc,
  k.revoked_at_utc,
  k.status AS key_status,

  CASE
    WHEN c.signed_at_utc < k.valid_from_utc THEN false
    WHEN k.valid_to_utc IS NOT NULL AND c.signed_at_utc > k.valid_to_utc THEN false
    WHEN k.revoked_at_utc IS NOT NULL AND c.signed_at_utc >= k.revoked_at_utc THEN false
    WHEN k.status = 'REVOKED' THEN false
    ELSE true
  END AS signing_time_valid
FROM ucs_certificate c
JOIN signing_keys k ON k.key_id = c.signing_key_id;


-- -----------------------------------------------------------------------------
-- View: Workflow evidence requirements
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_workflow_requires_evidence AS
SELECT
  c.certificate_id,
  c.workflow_type,
  CASE
    WHEN c.workflow_type IN ('TERMINATION_DECISION', 'INVESTIGATION_CLOSE', 'PIP_FAIL') THEN true
    WHEN c.workflow_type IN ('EXEC_OVERRIDE') THEN false
    ELSE true
  END AS requires_evidence
FROM ucs_certificate c;


-- -----------------------------------------------------------------------------
-- View: Certificate dependency health summary (any invalid CEP pointer blocks)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_certificate_dependency_health AS
SELECT
  c.certificate_id,
  c.workflow_type,
  count(p.cep_id) AS cep_count,
  bool_and(i.cep_pointer_valid) AS all_ceps_valid,
  bool_or(NOT i.cep_pointer_valid) AS any_cep_invalid
FROM ucs_certificate c
LEFT JOIN ucs_evidence_pointer p ON p.certificate_id = c.certificate_id
LEFT JOIN v_certificate_cep_integrity i ON i.certificate_id = c.certificate_id AND i.cep_id = p.cep_id
GROUP BY c.certificate_id, c.workflow_type;


-- -----------------------------------------------------------------------------
-- Query: Build data.ceps for OPA (run periodically or on-demand)
-- -----------------------------------------------------------------------------
-- SELECT
--   cep_id,
--   cep_type,
--   final_hash,
--   status,
--   to_char(valid_until_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS valid_until_utc
-- FROM cep;
--
-- Transform into JSON:
-- "ceps": {
--   "<cep_id>": {
--     "type": "<cep_type>",
--     "final_hash": "<final_hash>",
--     "status": "<status>",
--     "valid_until_utc": "<valid_until_utc>"
--   }
-- }


-- -----------------------------------------------------------------------------
-- Query: Build data.signing_keys for OPA
-- -----------------------------------------------------------------------------
-- SELECT
--   key_id,
--   to_char(valid_from_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS valid_from_utc,
--   CASE WHEN valid_to_utc IS NULL THEN NULL
--        ELSE to_char(valid_to_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') END AS valid_to_utc,
--   CASE WHEN revoked_at_utc IS NULL THEN NULL
--        ELSE to_char(revoked_at_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') END AS revoked_at_utc
-- FROM signing_keys;
--
-- Transform into JSON:
-- "signing_keys": {
--   "<key_id>": { "valid_from_utc": "...", "valid_to_utc": null, "revoked_at_utc": null }
-- }


-- -----------------------------------------------------------------------------
-- Note: data.roles is static config (checked into repo)
-- -----------------------------------------------------------------------------
-- {
--   "roles": {
--     "TERMINATION_DECISION": ["HRBP_DIRECTOR", "ER_LEAD", "LEGAL_COUNSEL"],
--     "EXEC_OVERRIDE": ["CHRO", "GC", "CEO"]
--   }
-- }
