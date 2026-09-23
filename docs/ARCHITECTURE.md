# MaintX — PLC Logic Integrity & Maintenance Accountability Platform

## System Architecture & Security Specification

### 1. Core Workflow
```
PLAN → BASELINE → WATCH → COMPARE → CHECK AUTHORIZATION → CALCULATE RISK → EXPLAIN → VERIFY → LOG
```

### 2. Core Security Principles
- **Untrusted Frontend**: Never trust `user_id`, `role`, authorization flags, risk scores, hashes, or approval status supplied by client-side code.
- **Tamper-Evident Design**: The platform uses cryptographic hash chaining (SHA-256) to ensure all maintenance actions and audit logs are verifiable and tamper-evident (never claiming absolute "tamper-proof").
- **Authoritative Database & Backend**: Supabase PostgreSQL with Row Level Security (RLS) and FastAPI backend authorization.
- **PLC Logic Canonicalization**: PLC structured JSON representations are strictly normalized before computing SHA-256 hashes to guarantee deterministic integrity verification across formatting variations.
- **Deterministic Risk Engine**: Authoritative rule-based scoring (0–100) clamped to LOW, MEDIUM, HIGH, and CRITICAL levels.
- **AI/ML as Assistant Only**: Isolation Forest anomaly scoring provides advisory flags; it never overrides deterministic safety rules.

### 3. Roles and Responsibilities (RBAC)
- **ADMIN**: System administration, machine registry, configuration policies.
- **MAINTENANCE_ENGINEER**: Execution of assigned maintenance jobs, parameter changes.
- **SUPERVISOR**: Maintenance approval, high-risk change authorization, sign-off.
- **SECURITY_ANALYST**: Security incident review, audit log integrity validation, anomaly investigation.
- **AUDITOR**: Read-only compliance review, tamper verification, report inspection.

### 4. Database Schema Structure
The persistent database comprises 18 relational tables managed under Supabase PostgreSQL:
1. `profiles`
2. `machines`
3. `machine_states`
4. `maintenance_requests`
5. `maintenance_sessions`
6. `machine_baselines`
7. `plc_logic_baselines`
8. `plc_logic_versions`
9. `plc_logic_diffs`
10. `configuration_changes`
11. `risk_assessments`
12. `approvals`
13. `security_events`
14. `verification_results`
15. `maintenance_reports`
16. `historical_changes`
17. `change_policies`
18. `notifications`
19. `process_impact_assessments`

