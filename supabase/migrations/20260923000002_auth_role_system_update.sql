-- ==============================================================================
-- Migration: 20260923000002_auth_role_system_update.sql
-- Description: Allow service_role to manage roles & initialize admin role
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.prevent_role_escalation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.role <> OLD.role THEN
    -- Allow if executed by service_role (authoritative backend) or an authenticated ADMIN user
    IF coalesce(current_setting('request.jwt.claim.role', true), '') = 'service_role' 
       OR public.get_auth_role() = 'ADMIN' 
       OR auth.uid() IS NULL THEN
      NULL;
    ELSE
      RAISE EXCEPTION 'Only administrators or service role can modify user roles';
    END IF;
  END IF;
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- Allow handle_new_user to set ADMIN if explicitly specified in metadata or for designated admin accounts
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
      WHEN new.email = 'admin@maintx.internal' THEN 'ADMIN'
      WHEN new.raw_user_meta_data->>'role' IN ('ADMIN', 'MAINTENANCE_ENGINEER', 'SUPERVISOR', 'SECURITY_ANALYST', 'AUDITOR') 
      THEN new.raw_user_meta_data->>'role'
      ELSE 'MAINTENANCE_ENGINEER'
    END,
    coalesce(new.raw_user_meta_data->>'department', 'Operations')
  )
  ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role,
    full_name = coalesce(EXCLUDED.full_name, profiles.full_name);
  RETURN new;
END;
$$;

-- Ensure admin@maintx.internal profile is updated to ADMIN
UPDATE public.profiles
SET role = 'ADMIN'
WHERE email = 'admin@maintx.internal';
