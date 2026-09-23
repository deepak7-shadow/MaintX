-- ==============================================================================
-- MaintX — PLC Logic Integrity & Maintenance Accountability Platform
-- Migration: 20260923000001_maintx_core_schema.sql
-- Description: Core schema, 19 tables, indexes, constraints, RLS, & seed data
-- Target Engine: PostgreSQL 17 (Supabase)
-- ==============================================================================

-- Enable required cryptographic extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- 1. PROFILES (Authoritative User Entity & Roles)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email text NOT NULL,
    full_name text,
    role text NOT NULL DEFAULT 'MAINTENANCE_ENGINEER' CHECK (role IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SUPERVISOR', 'SECURITY_ANALYST', 'AUDITOR')),
    engineer_code text UNIQUE,
    department text DEFAULT 'Operations',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- HELPER: Authoritative Role Resolver
-- Resolves user's role directly from database, never trusting client JWT claims
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_auth_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT role FROM public.profiles WHERE id = auth.uid() LIMIT 1;
$$;

-- Trigger to prevent non-admins from escalating roles
CREATE OR REPLACE FUNCTION public.prevent_role_escalation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.role <> OLD.role AND (auth.uid() IS NULL OR public.get_auth_role() <> 'ADMIN') THEN
    RAISE EXCEPTION 'Only administrators can modify user roles';
  END IF;
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_role_escalation ON public.profiles;
CREATE TRIGGER trg_prevent_role_escalation
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.prevent_role_escalation();

-- Trigger to automatically create a profile when a new user signs up in Supabase Auth
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, role, department)
  VALUES (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    CASE 
      WHEN new.raw_user_meta_data->>'role' IN ('MAINTENANCE_ENGINEER', 'SUPERVISOR', 'SECURITY_ANALYST', 'AUDITOR') 
      THEN new.raw_user_meta_data->>'role'
      ELSE 'MAINTENANCE_ENGINEER'
    END,
    coalesce(new.raw_user_meta_data->>'department', 'Operations')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ------------------------------------------------------------------------------
-- 2. MACHINES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.machines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_code text UNIQUE NOT NULL,
    name text NOT NULL,
    machine_type text NOT NULL,
    criticality text NOT NULL CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    location text NOT NULL,
    status text NOT NULL DEFAULT 'IDLE' CHECK (status IN ('IDLE', 'OPERATIONAL', 'MAINTENANCE_MODE', 'LOCKOUT_TAGOUT', 'COMPROMISED', 'DECOMMISSIONED')),
    plc_version text NOT NULL DEFAULT 'v17',
    plc_integrity_status text NOT NULL DEFAULT 'VERIFIED' CHECK (plc_integrity_status IN ('VERIFIED', 'REVIEW_REQUIRED', 'FAILED', 'COMPROMISED')),
    firmware text NOT NULL DEFAULT '4.2.1',
    ip_address inet NOT NULL,
    subnet text NOT NULL DEFAULT '255.255.255.0',
    gateway inet NOT NULL,
    firewall_configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    safety_configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 3. MACHINE_STATES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.machine_states (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    motor_speed_rpm numeric,
    temperature_celsius numeric,
    pressure_bar numeric,
    operating_mode text NOT NULL DEFAULT 'AUTO',
    ip_address inet,
    plc_version text,
    plc_hash text,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_state jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid REFERENCES public.profiles(id)
);

-- ------------------------------------------------------------------------------
-- 4. MAINTENANCE_REQUESTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.maintenance_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_number text UNIQUE NOT NULL,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    engineer_id uuid NOT NULL REFERENCES public.profiles(id),
    supervisor_id uuid REFERENCES public.profiles(id),
    reason text NOT NULL,
    maintenance_type text NOT NULL CHECK (maintenance_type IN ('SCHEDULED_MAINTENANCE', 'EMERGENCY_REPAIR', 'FIRMWARE_UPDATE', 'LOGIC_OPTIMIZATION', 'SECURITY_PATCH')),
    expected_changes jsonb NOT NULL DEFAULT '[]'::jsonb,
    priority text NOT NULL DEFAULT 'MEDIUM' CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    approval_status text NOT NULL DEFAULT 'PENDING' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'IN_PROGRESS', 'VERIFYING', 'COMPLETED', 'REJECTED', 'CLOSED')),
    scheduled_start timestamptz NOT NULL DEFAULT now(),
    scheduled_end timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 5. MAINTENANCE_SESSIONS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.maintenance_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES public.maintenance_requests(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    engineer_id uuid NOT NULL REFERENCES public.profiles(id),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    session_status text NOT NULL DEFAULT 'ACTIVE' CHECK (session_status IN ('ACTIVE', 'COMPLETED', 'ABORTED', 'LOCKED')),
    baseline_captured boolean NOT NULL DEFAULT false,
    verification_status text NOT NULL DEFAULT 'PENDING' CHECK (verification_status IN ('PENDING', 'VERIFIED', 'REVIEW_REQUIRED', 'FAILED')),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 6. MACHINE_BASELINES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.machine_baselines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    captured_at timestamptz NOT NULL DEFAULT now(),
    parameters jsonb NOT NULL,
    network_configuration jsonb NOT NULL,
    firmware text NOT NULL,
    firewall_configuration jsonb NOT NULL,
    safety_configuration jsonb NOT NULL,
    baseline_hash text NOT NULL,
    captured_by uuid NOT NULL REFERENCES public.profiles(id)
);

-- ------------------------------------------------------------------------------
-- 7. PLC_LOGIC_BASELINES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.plc_logic_baselines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    session_id uuid REFERENCES public.maintenance_sessions(id) ON DELETE SET NULL,
    plc_version text NOT NULL,
    raw_logic jsonb NOT NULL,
    canonical_logic jsonb NOT NULL,
    sha256_hash text NOT NULL,
    fingerprint text NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    captured_by uuid NOT NULL REFERENCES public.profiles(id),
    is_trusted_baseline boolean NOT NULL DEFAULT true
);

-- ------------------------------------------------------------------------------
-- 8. PLC_LOGIC_VERSIONS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.plc_logic_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    session_id uuid REFERENCES public.maintenance_sessions(id) ON DELETE SET NULL,
    version text NOT NULL,
    canonical_logic jsonb NOT NULL,
    sha256_hash text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    recorded_by uuid REFERENCES public.profiles(id),
    status text NOT NULL DEFAULT 'RECORDED' CHECK (status IN ('RECORDED', 'APPROVED', 'REJECTED', 'ROLLED_BACK'))
);

-- ------------------------------------------------------------------------------
-- 9. PLC_LOGIC_DIFFS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.plc_logic_diffs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    baseline_id uuid REFERENCES public.plc_logic_baselines(id),
    compared_version text NOT NULL,
    baseline_hash text NOT NULL,
    current_hash text NOT NULL,
    is_hash_identical boolean NOT NULL,
    added_networks jsonb NOT NULL DEFAULT '[]'::jsonb,
    removed_networks jsonb NOT NULL DEFAULT '[]'::jsonb,
    modified_networks jsonb NOT NULL DEFAULT '[]'::jsonb,
    changed_timers jsonb NOT NULL DEFAULT '[]'::jsonb,
    changed_setpoints jsonb NOT NULL DEFAULT '[]'::jsonb,
    changed_interlocks jsonb NOT NULL DEFAULT '[]'::jsonb,
    safety_related_changes boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 10. CONFIGURATION_CHANGES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.configuration_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES public.profiles(id),
    user_role text NOT NULL,
    category text NOT NULL CHECK (category IN ('PARAMETERS', 'PLC_LOGIC', 'NETWORK', 'FIREWALL', 'FIRMWARE', 'SAFETY_CONFIG')),
    parameter_name text NOT NULL,
    old_value jsonb,
    new_value jsonb,
    reason text NOT NULL,
    is_expected boolean NOT NULL,
    is_authorized boolean NOT NULL,
    risk_score integer NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_level text NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    ai_anomaly_score integer CHECK (ai_anomaly_score >= 0 AND ai_anomaly_score <= 100),
    requires_supervisor_approval boolean NOT NULL DEFAULT false,
    approval_status text NOT NULL DEFAULT 'PENDING' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED', 'AUTO_AUTHORIZED')),
    timestamp timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 11. RISK_ASSESSMENTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.risk_assessments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id uuid REFERENCES public.configuration_changes(id) ON DELETE CASCADE,
    session_id uuid REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    calculated_score integer NOT NULL CHECK (calculated_score >= 0 AND calculated_score <= 100),
    risk_level text NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    scoring_breakdown jsonb NOT NULL,
    ai_anomaly_score integer CHECK (ai_anomaly_score >= 0 AND ai_anomaly_score <= 100),
    ai_explanation text,
    engine_version text NOT NULL DEFAULT '1.0.0-deterministic',
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 12. APPROVALS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid REFERENCES public.maintenance_requests(id) ON DELETE CASCADE,
    change_id uuid REFERENCES public.configuration_changes(id) ON DELETE CASCADE,
    approver_id uuid NOT NULL REFERENCES public.profiles(id),
    approver_role text NOT NULL CHECK (approver_role IN ('ADMIN', 'SUPERVISOR')),
    decision text NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
    comments text,
    decided_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 13. SECURITY_EVENTS (Tamper-Evident SHA-256 Hash Chain)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.security_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_number bigserial UNIQUE,
    event_type text NOT NULL CHECK (event_type IN (
        'LOGIN', 'LOGOUT', 'MAINTENANCE_REQUEST_CREATED', 'MAINTENANCE_APPROVED',
        'MAINTENANCE_STARTED', 'BASELINE_CAPTURED', 'PLC_BASELINE_CAPTURED',
        'CONFIGURATION_CHANGED', 'PLC_LOGIC_CHANGED', 'PLC_LOGIC_DIFF_GENERATED',
        'RISK_ASSESSED', 'SUPERVISOR_APPROVED', 'SUPERVISOR_REJECTED',
        'VERIFICATION_STARTED', 'VERIFICATION_COMPLETED', 'MAINTENANCE_CLOSED',
        'LOG_INTEGRITY_CHECKED', 'UNAUTHORIZED_CHANGE_DETECTED', 'SAFETY_INTERLOCK_VIOLATION',
        'MACHINE_REGISTERED', 'POLICY_UPDATED', 'TAMPER_DETECTED', 'SECURITY_ALERT'
    )),
    machine_id uuid REFERENCES public.machines(id) ON DELETE SET NULL,
    session_id uuid REFERENCES public.maintenance_sessions(id) ON DELETE SET NULL,
    actor_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    actor_role text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    severity text NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    previous_hash text NOT NULL,
    current_hash text NOT NULL,
    is_tampered_demo boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 14. VERIFICATION_RESULTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.verification_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE RESTRICT,
    verified_by uuid NOT NULL REFERENCES public.profiles(id),
    final_status text NOT NULL CHECK (final_status IN ('VERIFIED', 'REVIEW_REQUIRED', 'FAILED')),
    plc_integrity_passed boolean NOT NULL,
    all_changes_authorized boolean NOT NULL,
    unresolved_critical_changes integer NOT NULL DEFAULT 0,
    expected_changes_count integer NOT NULL DEFAULT 0,
    unexpected_changes_count integer NOT NULL DEFAULT 0,
    unauthorized_changes_count integer NOT NULL DEFAULT 0,
    verification_report jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 15. MAINTENANCE_REPORTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.maintenance_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    report_number text UNIQUE NOT NULL,
    generated_by uuid NOT NULL REFERENCES public.profiles(id),
    summary text NOT NULL,
    details jsonb NOT NULL,
    risk_summary jsonb NOT NULL,
    plc_diff_summary jsonb NOT NULL,
    log_integrity_status text NOT NULL DEFAULT 'VERIFIED',
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 16. HISTORICAL_CHANGES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.historical_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_code text NOT NULL,
    parameter_name text NOT NULL,
    category text NOT NULL,
    typical_magnitude numeric,
    change_frequency_per_month numeric,
    historical_risk_mean numeric,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 17. CHANGE_POLICIES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.change_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category text NOT NULL,
    parameter_pattern text NOT NULL,
    requires_supervisor boolean NOT NULL DEFAULT true,
    auto_block_if_unauthorized boolean NOT NULL DEFAULT true,
    base_risk_points integer NOT NULL DEFAULT 25,
    description text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_category_parameter UNIQUE (category, parameter_pattern)
);

-- ------------------------------------------------------------------------------
-- 18. NOTIFICATIONS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title text NOT NULL,
    message text NOT NULL,
    severity text NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL', 'SUCCESS', 'ERROR')),
    category text NOT NULL,
    reference_id uuid,
    is_read boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 19. PROCESS_IMPACT_ASSESSMENTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.process_impact_assessments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid REFERENCES public.maintenance_sessions(id) ON DELETE CASCADE,
    machine_id uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
    parameter_changed text NOT NULL,
    old_value numeric,
    new_value numeric,
    predicted_temperature_celsius numeric,
    temperature_limit numeric,
    predicted_pressure_bar numeric,
    pressure_limit numeric,
    is_temperature_violated boolean NOT NULL,
    is_pressure_violated boolean NOT NULL,
    warning_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ==============================================================================
-- INDEXES FOR PERFORMANCE & AUDIT QUERIES
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_machines_code ON public.machines(machine_code);
CREATE INDEX IF NOT EXISTS idx_machines_status ON public.machines(status);
CREATE INDEX IF NOT EXISTS idx_machine_states_machine ON public.machine_states(machine_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_requests_machine ON public.maintenance_requests(machine_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_requests_status ON public.maintenance_requests(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_sessions_request ON public.maintenance_sessions(request_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_sessions_machine ON public.maintenance_sessions(machine_id);
CREATE INDEX IF NOT EXISTS idx_plc_baselines_machine ON public.plc_logic_baselines(machine_id);
CREATE INDEX IF NOT EXISTS idx_plc_baselines_hash ON public.plc_logic_baselines(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_plc_diffs_session ON public.plc_logic_diffs(session_id);
CREATE INDEX IF NOT EXISTS idx_config_changes_session ON public.configuration_changes(session_id);
CREATE INDEX IF NOT EXISTS idx_config_changes_machine ON public.configuration_changes(machine_id);
CREATE INDEX IF NOT EXISTS idx_config_changes_risk ON public.configuration_changes(risk_level);
CREATE INDEX IF NOT EXISTS idx_security_events_chain ON public.security_events(event_number ASC);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON public.security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON public.notifications(recipient_id, is_read);
CREATE INDEX IF NOT EXISTS idx_historical_changes_machine ON public.historical_changes(machine_code, parameter_name);
CREATE INDEX IF NOT EXISTS idx_process_impact_machine ON public.process_impact_assessments(machine_id);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.machines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.machine_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenance_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenance_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.machine_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plc_logic_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plc_logic_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plc_logic_diffs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.configuration_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verification_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenance_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historical_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.change_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.process_impact_assessments ENABLE ROW LEVEL SECURITY;

-- 1. PROFILES RLS
CREATE POLICY "Users can view their own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id OR public.get_auth_role() IN ('ADMIN', 'SUPERVISOR', 'SECURITY_ANALYST', 'AUDITOR'));

CREATE POLICY "Users can update their own profile details"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can insert their own profile"
    ON public.profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Admins can manage all profiles"
    ON public.profiles FOR ALL
    USING (public.get_auth_role() = 'ADMIN');

-- 2. MACHINES RLS
CREATE POLICY "Authenticated users can view machines"
    ON public.machines FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Admins and Supervisors can modify machines"
    ON public.machines FOR ALL
    USING (public.get_auth_role() IN ('ADMIN', 'SUPERVISOR'));

-- 3. MACHINE_STATES RLS
CREATE POLICY "Authenticated users can view machine states"
    ON public.machine_states FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Engineers and Admins can insert machine states"
    ON public.machine_states FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SUPERVISOR'));

-- 4. MAINTENANCE_REQUESTS RLS
CREATE POLICY "Authenticated users can view maintenance requests"
    ON public.maintenance_requests FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Engineers and Admins can create maintenance requests"
    ON public.maintenance_requests FOR INSERT
    WITH CHECK (auth.uid() = engineer_id OR public.get_auth_role() IN ('ADMIN', 'SUPERVISOR'));

CREATE POLICY "Supervisors and Admins can approve maintenance requests"
    ON public.maintenance_requests FOR UPDATE
    USING (public.get_auth_role() IN ('ADMIN', 'SUPERVISOR') OR (auth.uid() = engineer_id AND status = 'DRAFT'));

-- 5. MAINTENANCE_SESSIONS RLS
CREATE POLICY "Authenticated users can view maintenance sessions"
    ON public.maintenance_sessions FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Engineers can manage their assigned sessions"
    ON public.maintenance_sessions FOR ALL
    USING (auth.uid() = engineer_id OR public.get_auth_role() IN ('ADMIN', 'SUPERVISOR'));

-- 6. BASELINES & PLC RLS
CREATE POLICY "Authenticated users can view baselines and PLC data"
    ON public.machine_baselines FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated users can view plc baselines"
    ON public.plc_logic_baselines FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated users can view plc versions"
    ON public.plc_logic_versions FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated users can view plc diffs"
    ON public.plc_logic_diffs FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Engineers and Admins can insert baselines"
    ON public.machine_baselines FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER'));
CREATE POLICY "Engineers and Admins can insert plc baselines"
    ON public.plc_logic_baselines FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER'));
CREATE POLICY "Engineers and Admins can insert plc versions"
    ON public.plc_logic_versions FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER'));
CREATE POLICY "Engineers and Admins can insert plc diffs"
    ON public.plc_logic_diffs FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SECURITY_ANALYST'));

-- 7. CONFIGURATION_CHANGES RLS
CREATE POLICY "Authenticated users can view configuration changes"
    ON public.configuration_changes FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Engineers can submit configuration changes"
    ON public.configuration_changes FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER'));

CREATE POLICY "Supervisors can update approval status on changes"
    ON public.configuration_changes FOR UPDATE
    USING (public.get_auth_role() IN ('ADMIN', 'SUPERVISOR'));

-- 8. RISK_ASSESSMENTS & APPROVALS RLS
CREATE POLICY "Authenticated users can view risk assessments"
    ON public.risk_assessments FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "System and analysts can insert risk assessments"
    ON public.risk_assessments FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'SECURITY_ANALYST', 'SUPERVISOR', 'MAINTENANCE_ENGINEER'));

CREATE POLICY "Authenticated users can view approvals"
    ON public.approvals FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Supervisors and Admins can create approvals"
    ON public.approvals FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'SUPERVISOR'));

-- 9. SECURITY_EVENTS (Tamper-Evident Hash Chain: Append-Only Immutability)
CREATE POLICY "All authenticated users can view audit security events"
    ON public.security_events FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "System services can append audit logs"
    ON public.security_events FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

-- 10. VERIFICATION_RESULTS & REPORTS RLS
CREATE POLICY "Authenticated users can view verification results"
    ON public.verification_results FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Supervisors and Admins can insert verification results"
    ON public.verification_results FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'SUPERVISOR'));

CREATE POLICY "Authenticated users can view reports"
    ON public.maintenance_reports FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authorized roles can create reports"
    ON public.maintenance_reports FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'SUPERVISOR', 'AUDITOR', 'SECURITY_ANALYST'));

-- 11. HISTORICAL CHANGES RLS
CREATE POLICY "Authenticated users can view historical changes"
    ON public.historical_changes FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Engineers and Admins can insert historical changes"
    ON public.historical_changes FOR INSERT
    WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SECURITY_ANALYST'));

-- 12. POLICIES & NOTIFICATIONS RLS
CREATE POLICY "Authenticated users can read change policies"
    ON public.change_policies FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Admins can manage change policies"
    ON public.change_policies FOR ALL USING (public.get_auth_role() = 'ADMIN');

CREATE POLICY "Users can view their notifications"
    ON public.notifications FOR SELECT USING (auth.uid() = recipient_id OR public.get_auth_role() = 'ADMIN');
CREATE POLICY "Users can update their notifications read status"
    ON public.notifications FOR UPDATE USING (auth.uid() = recipient_id);
CREATE POLICY "Authenticated users can create notifications"
    ON public.notifications FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can view impact assessments"
    ON public.process_impact_assessments FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Engineers and Admins can insert impact assessments"
    ON public.process_impact_assessments FOR INSERT WITH CHECK (public.get_auth_role() IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SUPERVISOR'));

-- ==============================================================================
-- INITIAL SEED DATA
-- ==============================================================================

-- 1. Initial Change Policies
INSERT INTO public.change_policies (category, parameter_pattern, requires_supervisor, auto_block_if_unauthorized, base_risk_points, description)
VALUES 
    ('SAFETY_CONFIG', '*', true, true, 40, 'Safety circuit or interlock modifications require mandatory supervisor sign-off.'),
    ('FIREWALL', '*', true, true, 30, 'Industrial firewall policy changes require supervisor sign-off.'),
    ('FIRMWARE', '*', true, true, 30, 'Firmware flash or version updates require supervisor approval.'),
    ('PLC_LOGIC', 'interlocks.*', true, true, 40, 'PLC interlock logic adjustments are critical risk.'),
    ('PLC_LOGIC', 'timers.*', false, false, 15, 'PLC timer adjustments above expected baseline threshold.'),
    ('NETWORK', 'ip_address', true, true, 25, 'IP address and subnet changes carry network risk.'),
    ('PARAMETERS', 'motor_speed_rpm', false, false, 10, 'Motor operational speed setpoint adjustments.')
ON CONFLICT (category, parameter_pattern) DO NOTHING;

-- 2. Initial Industrial Assets (Machines)
INSERT INTO public.machines (
    machine_code,
    name,
    machine_type,
    criticality,
    location,
    status,
    plc_version,
    plc_integrity_status,
    firmware,
    ip_address,
    subnet,
    gateway,
    firewall_configuration,
    safety_configuration,
    parameters
) VALUES 
(
    'CNC-01',
    'Precision 5-Axis Milling Machine',
    'CNC_MILLING',
    'CRITICAL',
    'Sector 4 - Advanced Machining Cell',
    'OPERATIONAL',
    'v17',
    'VERIFIED',
    '4.2.1',
    '192.168.10.20',
    '255.255.255.0',
    '192.168.10.1',
    '{"allowed_inbound_ports": [502, 44818, 102], "mac_filtering": true, "inspection_mode": "STRICT"}'::jsonb,
    '{"estop_circuit": "DUAL_CHANNEL_CAT4", "light_curtain_active": true, "interlock_n7_engaged": true}'::jsonb,
    '{"motor_speed_rpm": 3000, "temperature_limit_celsius": 80, "pressure_limit_bar": 5.0, "operating_mode": "AUTO"}'::jsonb
),
(
    'ROBOT-02',
    '6-Axis Articulated Welding Robot',
    'ROBOTIC_ARM',
    'HIGH',
    'Sector 2 - Automotive Chassis Line',
    'OPERATIONAL',
    'v16',
    'VERIFIED',
    '3.9.0',
    '192.168.10.35',
    '255.255.255.0',
    '192.168.10.1',
    '{"allowed_inbound_ports": [502, 44818], "mac_filtering": true, "inspection_mode": "STRICT"}'::jsonb,
    '{"estop_circuit": "DUAL_CHANNEL_CAT4", "safety_gate_switch": true, "speed_monitoring": "SLS_ACTIVE"}'::jsonb,
    '{"weld_current_amps": 220, "gas_flow_lpm": 15, "operating_mode": "AUTO"}'::jsonb
)
ON CONFLICT (machine_code) DO NOTHING;

-- 3. Genesis Hash Chain Audit Entry
INSERT INTO public.security_events (
    event_type,
    payload,
    severity,
    previous_hash,
    current_hash,
    created_at
) VALUES (
    'LOGIN',
    '{"description": "Genesis block for MaintX tamper-evident audit ledger", "system": "MaintX Core", "integrity": "TAMPER-EVIDENT"}'::jsonb,
    'INFO',
    '0000000000000000000000000000000000000000000000000000000000000000',
    'GENESIS_e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    now()
) ON CONFLICT DO NOTHING;

-- 4. Initial Historical Baseline Data for Anomaly Scoring
INSERT INTO public.historical_changes (machine_code, parameter_name, category, typical_magnitude, change_frequency_per_month, historical_risk_mean)
VALUES 
    ('CNC-01', 'motor_speed_rpm', 'PARAMETERS', 100, 4.2, 15.5),
    ('CNC-01', 'temperature_limit_celsius', 'PARAMETERS', 5, 0.8, 22.0),
    ('CNC-01', 'timers.T1_debounce', 'PLC_LOGIC', 25, 2.0, 18.0),
    ('ROBOT-02', 'weld_current_amps', 'PARAMETERS', 15, 5.5, 28.0),
    ('ROBOT-02', 'interlocks.safety_zone', 'SAFETY_CONFIG', 1, 0.2, 85.0);
