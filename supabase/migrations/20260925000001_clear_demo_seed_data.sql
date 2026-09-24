-- ==============================================================================
-- Migration: 20260925000001_clear_demo_seed_data.sql
-- Description: Removes all demo/random seed data inserted by earlier migrations
--              and seed scripts. Leaves the schema (tables, functions, RLS)
--              completely intact. Run this before loading real simulation data.
-- ==============================================================================

-- ── 1. Configuration changes & risk history ───────────────────────────────────
DELETE FROM public.configuration_changes WHERE TRUE;

-- ── 2. Maintenance sessions / requests ───────────────────────────────────────
DELETE FROM public.maintenance_sessions WHERE TRUE;
DELETE FROM public.maintenance_requests WHERE TRUE;

-- ── 3. Security / audit events ────────────────────────────────────────────────
DELETE FROM public.security_events WHERE TRUE;

-- ── 4. PLC baselines & logic versions ────────────────────────────────────────
DELETE FROM public.plc_logic_baselines WHERE TRUE;
DELETE FROM public.plc_logic_versions  WHERE TRUE;

-- ── 5. PLC scan results ───────────────────────────────────────────────────────
DELETE FROM public.plc_scan_results WHERE TRUE;

-- ── 6. Historical baseline statistics ────────────────────────────────────────
DELETE FROM public.historical_changes WHERE TRUE;

-- ── 7. Machines (removes all demo machines — re-seed with real assets) ────────
DELETE FROM public.machines WHERE TRUE;

-- ── 8. Notifications ─────────────────────────────────────────────────────────
DELETE FROM public.notifications WHERE TRUE;

-- ── Done ─────────────────────────────────────────────────────────────────────
-- All demo/random data has been removed.
-- Schema, RLS policies, and user profiles are untouched.
-- Load your simulation data now.
