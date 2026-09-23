-- ==============================================================================
-- Migration: 20260923000003_stage4_demo_seed.sql
-- Description: Seed demo maintenance request MNT-2026-1842 and application
--              data. Demo auth users (TECH-042, SUP-001) are created via
--              the backend seed_users.py script using the Admin API, which
--              also triggers the handle_new_user() trigger to create profiles.
--              This migration only seeds data that does NOT depend on FK to
--              auth.users — and conditionally seeds profiles if they exist.
-- ==============================================================================

-- ----------------------------------------------------------------------------
-- 1. Ensure CNC-01 exists
-- ----------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.machines WHERE machine_code = 'CNC-01') THEN
    RAISE EXCEPTION 'CNC-01 not found — run migration 20260923000001 first.';
  END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Seed demo maintenance request MNT-2026-1842
--    Only inserts if both engineer and supervisor profiles already exist
--    (created by seed_users.py / Supabase Admin API signup).
-- ----------------------------------------------------------------------------
DO $$
DECLARE
  v_machine_id uuid;
  v_engineer_id uuid;
  v_supervisor_id uuid;
BEGIN
  SELECT id INTO v_machine_id FROM public.machines WHERE machine_code = 'CNC-01';
  SELECT id INTO v_engineer_id FROM public.profiles WHERE engineer_code = 'TECH-042' LIMIT 1;
  SELECT id INTO v_supervisor_id FROM public.profiles WHERE engineer_code = 'SUP-001' LIMIT 1;

  IF v_engineer_id IS NOT NULL AND v_supervisor_id IS NOT NULL THEN
    INSERT INTO public.maintenance_requests (
      request_number,
      machine_id,
      engineer_id,
      supervisor_id,
      reason,
      maintenance_type,
      expected_changes,
      priority,
      approval_status,
      status,
      scheduled_start,
      scheduled_end
    )
    VALUES (
      'MNT-2026-1842',
      v_machine_id,
      v_engineer_id,
      v_supervisor_id,
      'Production configuration update: motor speed upgrade from 3000 RPM to 3200 RPM, and PLC logic upgrade from v17 to v18 for improved cycle time and energy efficiency.',
      'FIRMWARE_UPDATE',
      '[
        {"parameter": "motor_speed_rpm", "from_value": 3000, "to_value": 3200, "reason": "Production throughput optimisation."},
        {"parameter": "plc_version", "from_value": "v17", "to_value": "v18", "reason": "PLC v18 includes improved interlocks and cycle optimisation."}
      ]'::jsonb,
      'HIGH',
      'PENDING',
      'SUBMITTED',
      now(),
      now() + interval '4 hours'
    )
    ON CONFLICT (request_number) DO NOTHING;

    RAISE NOTICE 'MNT-2026-1842 seeded for CNC-01 with engineer % and supervisor %', v_engineer_id, v_supervisor_id;
  ELSE
    RAISE NOTICE 'Demo users not yet present — MNT-2026-1842 skipped. Run seed_users.py then re-apply.';
  END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Seed historical baseline data for risk scoring
-- ----------------------------------------------------------------------------
INSERT INTO public.historical_changes (
  machine_code, parameter_name, category, typical_magnitude, change_frequency_per_month, historical_risk_mean
)
VALUES
  ('CNC-01', 'motor_speed_rpm', 'PARAMETERS', 200, 2.0, 22.0),
  ('CNC-01', 'plc_version',     'FIRMWARE',   1,   0.5, 55.0)
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Seed genesis security audit event (static hash — no pgcrypto needed)
-- ----------------------------------------------------------------------------
INSERT INTO public.security_events (
  event_type,
  machine_id,
  payload,
  severity,
  previous_hash,
  current_hash
)
SELECT
  'MACHINE_REGISTERED',
  m.id,
  jsonb_build_object(
    'machine_code', 'CNC-01',
    'description', 'Stage 4 demo seed — CNC-01 registered in audit chain',
    'plc_version', 'v17',
    'firmware', '4.2.1'
  ),
  'INFO',
  '0000000000000000000000000000000000000000000000000000000000000000',
  'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'
FROM public.machines m
WHERE m.machine_code = 'CNC-01'
  AND NOT EXISTS (
    SELECT 1 FROM public.security_events
    WHERE event_type = 'MACHINE_REGISTERED'
      AND machine_id = m.id
  );
