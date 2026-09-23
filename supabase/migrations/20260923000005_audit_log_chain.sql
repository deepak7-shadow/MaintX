-- ==============================================================================
-- Migration: 20260923000005_audit_log_chain.sql
-- Description: Creates the audit_log_entries table for the tamper-evident
--              Security Event Audit Log with SHA-256 hash chaining.
--
-- Design:
--   - APPEND ONLY: No UPDATE or DELETE policies — only INSERT and SELECT.
--   - Hash chaining: previous_hash + current_hash enforced by application layer.
--   - RLS: All authenticated roles can read; ADMIN, ENGINEER, SUPERVISOR can write.
--   - AUDITOR: Read-only (enforced both at API layer and RLS level).
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. audit_log_entries — Tamper-Evident Hash-Chained Event Log
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_log_entries (
    event_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type        text        NOT NULL,
    user_id           uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    machine_id        uuid        REFERENCES public.machines(id) ON DELETE SET NULL,
    session_id        uuid        REFERENCES public.maintenance_sessions(id) ON DELETE SET NULL,
    event_data        jsonb       NOT NULL DEFAULT '{}'::jsonb,

    -- Hash chaining fields (computed server-side, never supplied by client)
    previous_hash     text        NOT NULL DEFAULT repeat('0', 64),  -- 64 zeros for genesis
    current_hash      text        NOT NULL,

    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Constraints
ALTER TABLE public.audit_log_entries
    ADD CONSTRAINT chk_previous_hash_length CHECK (length(previous_hash) = 64),
    ADD CONSTRAINT chk_current_hash_length  CHECK (length(current_hash) = 64),
    ADD CONSTRAINT chk_event_type_valid CHECK (event_type IN (
        'LOGIN', 'LOGOUT', 'AUTH_FAILURE', 'UNAUTHORIZED_ACCESS',
        'MAINTENANCE_CREATED', 'MAINTENANCE_ASSIGNED', 'MAINTENANCE_APPROVED',
        'MAINTENANCE_STARTED', 'MAINTENANCE_COMPLETED',
        'PLC_BASELINE_SET', 'PLC_INTEGRITY_CHECKED', 'PLC_HASH_MISMATCH', 'PLC_TAMPER_DETECTED',
        'CONFIG_CHANGE_DETECTED', 'CONFIG_CHANGE_AUTHORIZED', 'CONFIG_CHANGE_REJECTED',
        'RISK_ASSESSED', 'CRITICAL_RISK_FLAGGED', 'SAFETY_INTERLOCK_ALERT',
        'DEMO_EVENT', 'DEMO_TAMPER_SIMULATED'
    ));

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
    ON public.audit_log_entries(created_at ASC);

CREATE INDEX IF NOT EXISTS idx_audit_log_event_type
    ON public.audit_log_entries(event_type);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
    ON public.audit_log_entries(user_id)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_machine_id
    ON public.audit_log_entries(machine_id)
    WHERE machine_id IS NOT NULL;

-- Prevent updates and deletes at the database level (APPEND ONLY)
CREATE OR REPLACE FUNCTION public.deny_audit_log_modification()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RAISE EXCEPTION 'audit_log_entries is append-only. UPDATE and DELETE are not permitted.';
END;
$$;

DROP TRIGGER IF EXISTS trg_deny_audit_log_update ON public.audit_log_entries;
CREATE TRIGGER trg_deny_audit_log_update
    BEFORE UPDATE ON public.audit_log_entries
    FOR EACH ROW EXECUTE FUNCTION public.deny_audit_log_modification();

DROP TRIGGER IF EXISTS trg_deny_audit_log_delete ON public.audit_log_entries;
CREATE TRIGGER trg_deny_audit_log_delete
    BEFORE DELETE ON public.audit_log_entries
    FOR EACH ROW EXECUTE FUNCTION public.deny_audit_log_modification();

-- ------------------------------------------------------------------------------
-- 2. Row Level Security
-- ------------------------------------------------------------------------------
ALTER TABLE public.audit_log_entries ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read audit events (transparency)
CREATE POLICY "audit_log_select_all_roles"
    ON public.audit_log_entries
    FOR SELECT
    TO authenticated
    USING (true);

-- Only non-auditor roles can insert (AUDITOR is read-only)
CREATE POLICY "audit_log_insert_non_auditor"
    ON public.audit_log_entries
    FOR INSERT
    TO authenticated
    WITH CHECK (
        public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SUPERVISOR', 'SECURITY_ANALYST')
    );

-- Explicitly deny UPDATE and DELETE via RLS (belt-and-suspenders with triggers)
-- No UPDATE or DELETE policies are defined → implicitly denied for all roles.
