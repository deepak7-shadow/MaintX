-- ==============================================================================
-- Migration: 20260923000004_plc_simulator_tables.sql
-- Description: Tables for the software PLC simulator.
--              REWRITTEN to be fully idempotent using ALTER TABLE IF NOT EXISTS
--              patterns to handle partial prior execution.
-- ==============================================================================

-- ----------------------------------------------------------------------------
-- 1. plc_logic_versions — drop and recreate cleanly (idempotent)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS public.plc_logic_versions CASCADE;

CREATE TABLE public.plc_logic_versions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  machine_id      uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
  version_tag     text NOT NULL,
  description     text DEFAULT '',
  program_json    jsonb NOT NULL,
  canonical_json  text NOT NULL DEFAULT '{}',
  sha256_hash     char(64) NOT NULL,
  network_count   integer NOT NULL DEFAULT 0,
  is_baseline     boolean NOT NULL DEFAULT false,
  is_active       boolean NOT NULL DEFAULT true,
  created_by      uuid NOT NULL REFERENCES public.profiles(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_plc_versions_machine        ON public.plc_logic_versions(machine_id);
CREATE INDEX idx_plc_versions_hash           ON public.plc_logic_versions(sha256_hash);
CREATE INDEX idx_plc_versions_machine_active ON public.plc_logic_versions(machine_id, is_active);

-- ----------------------------------------------------------------------------
-- 2. plc_logic_baselines — drop and recreate cleanly
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS public.plc_logic_baselines CASCADE;

CREATE TABLE public.plc_logic_baselines (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  machine_id      uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
  version_id      uuid NOT NULL REFERENCES public.plc_logic_versions(id),
  version_tag     text NOT NULL,
  sha256_hash     char(64) NOT NULL,
  network_count   integer NOT NULL DEFAULT 0,
  is_active       boolean NOT NULL DEFAULT true,
  established_by  uuid NOT NULL REFERENCES public.profiles(id),
  established_at  timestamptz NOT NULL DEFAULT now(),
  notes           text
);

CREATE INDEX idx_plc_baselines_machine ON public.plc_logic_baselines(machine_id);
CREATE UNIQUE INDEX idx_plc_baselines_active_unique
  ON public.plc_logic_baselines(machine_id)
  WHERE is_active = true;

-- ----------------------------------------------------------------------------
-- 3. plc_logic_diffs — drop and recreate cleanly
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS public.plc_logic_diffs CASCADE;

CREATE TABLE public.plc_logic_diffs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  machine_id          uuid NOT NULL REFERENCES public.machines(id) ON DELETE CASCADE,
  baseline_version    text NOT NULL,
  current_version     text NOT NULL,
  baseline_hash       char(64) NOT NULL,
  current_hash        char(64) NOT NULL,
  hash_match          boolean NOT NULL,
  integrity_status    text NOT NULL,
  integrity_message   text NOT NULL,
  network_diffs       jsonb NOT NULL DEFAULT '[]',
  added_networks      text[] NOT NULL DEFAULT '{}',
  removed_networks    text[] NOT NULL DEFAULT '{}',
  modified_networks   text[] NOT NULL DEFAULT '{}',
  safety_violations   text[] NOT NULL DEFAULT '{}',
  total_changes       integer NOT NULL DEFAULT 0,
  checked_by          uuid REFERENCES public.profiles(id),
  analysed_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_plc_diffs_machine ON public.plc_logic_diffs(machine_id, analysed_at DESC);

-- ----------------------------------------------------------------------------
-- 4. Enable RLS
-- ----------------------------------------------------------------------------
ALTER TABLE public.plc_logic_versions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plc_logic_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plc_logic_diffs     ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 5. RLS Policies — plc_logic_versions
-- ----------------------------------------------------------------------------
CREATE POLICY "plc_versions_read"
  ON public.plc_logic_versions FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "plc_versions_insert"
  ON public.plc_logic_versions FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('MAINTENANCE_ENGINEER', 'SUPERVISOR', 'ADMIN')
    )
  );

CREATE POLICY "plc_versions_update_admin"
  ON public.plc_logic_versions FOR UPDATE
  USING (
    EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'ADMIN')
  );

-- ----------------------------------------------------------------------------
-- 6. RLS Policies — plc_logic_baselines
-- ----------------------------------------------------------------------------
CREATE POLICY "plc_baselines_read"
  ON public.plc_logic_baselines FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "plc_baselines_insert"
  ON public.plc_logic_baselines FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('SUPERVISOR', 'ADMIN')
    )
  );

CREATE POLICY "plc_baselines_update"
  ON public.plc_logic_baselines FOR UPDATE
  USING (
    EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN'))
  );

-- ----------------------------------------------------------------------------
-- 7. RLS Policies — plc_logic_diffs
-- ----------------------------------------------------------------------------
CREATE POLICY "plc_diffs_read"
  ON public.plc_logic_diffs FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "plc_diffs_insert"
  ON public.plc_logic_diffs FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('MAINTENANCE_ENGINEER', 'SUPERVISOR', 'SECURITY_ANALYST', 'ADMIN')
    )
  );

-- ----------------------------------------------------------------------------
-- 8. Schema init notice
-- ----------------------------------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE 'PLC simulator tables created. Run seed_plc_baseline.py to load CNC-01 v17 baseline.';
END $$;
