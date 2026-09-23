"""
Seed demo accounts in Supabase Auth and link profiles.

Creates all role-based demo users plus the specific demo users
referenced by MNT-2026-1842 (TECH-042 engineer, SUP-001 supervisor).
After creating users, seeds the MNT-2026-1842 maintenance request
by calling the REST API.

Usage:
    python -m app.scripts.seed_users
    # or from backend/
    .venv/Scripts/python.exe -m app.scripts.seed_users
"""
import httpx
import json
import os
import sys

SERVICE_KEY = os.getenv(
    'SUPABASE_SECRET_KEY',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdyZG1veGhmd3Nxa2hjc3JxdmF1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MDE1ODMzNCwiZXhwIjoyMTA1NzM0MzM0fQ.6HWgVMB7n62M6LT18UY-lhtKFbKNMfJWq3jDRF53YkE'
)
BASE_URL = os.getenv('SUPABASE_URL', 'https://grdmoxhfwsqkhcsrqvau.supabase.co')

HEADERS = {
    'apikey': SERVICE_KEY,
    'Authorization': f'Bearer {SERVICE_KEY}',
    'Content-Type': 'application/json',
}

# ---------------------------------------------------------------------------
# Demo user definitions
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {
        'email': 'admin@maintx.internal',
        'password': 'MaintX@2026!Admin',
        'full_name': 'Marcus Vance',
        'role': 'ADMIN',
        'department': 'Plant Operations & IT',
        'engineer_code': 'ADM-001',
    },
    {
        'email': 'engineer@maintx.internal',
        'password': 'MaintX@2026!Engineer',
        'full_name': 'Elena Rostova',
        'role': 'MAINTENANCE_ENGINEER',
        'department': 'Machining & Maintenance',
        'engineer_code': 'ENG-042',
    },
    {
        # Stage 4 demo engineer — TECH-042 — owner of MNT-2026-1842
        'email': 'tech042@maintx.internal',
        'password': 'MaintX@2026!Tech042',
        'full_name': 'Tech Engineer 042',
        'role': 'MAINTENANCE_ENGINEER',
        'department': 'Machining Operations',
        'engineer_code': 'TECH-042',
    },
    {
        'email': 'supervisor@maintx.internal',
        'password': 'MaintX@2026!Supervisor',
        'full_name': 'David Chen',
        'role': 'SUPERVISOR',
        'department': 'Plant Floor Oversight',
        'engineer_code': 'SUP-007',
    },
    {
        # Stage 4 demo supervisor — SUP-001 — approver of MNT-2026-1842
        'email': 'sup001@maintx.internal',
        'password': 'MaintX@2026!Sup001',
        'full_name': 'Sector 4 Supervisor',
        'role': 'SUPERVISOR',
        'department': 'Machining Operations',
        'engineer_code': 'SUP-001',
    },
    {
        'email': 'analyst@maintx.internal',
        'password': 'MaintX@2026!Analyst',
        'full_name': 'Sarah Jenkins',
        'role': 'SECURITY_ANALYST',
        'department': 'Industrial Cybersecurity SOC',
        'engineer_code': 'SEC-101',
    },
    {
        'email': 'auditor@maintx.internal',
        'password': 'MaintX@2026!Auditor',
        'full_name': 'Arthur Pendelton',
        'role': 'AUDITOR',
        'department': 'Compliance & Safety Audit',
        'engineer_code': 'AUD-909',
    },
]


def _create_or_get_user(client: httpx.Client, u: dict, existing: dict) -> str | None:
    """Create auth user if not exists; return user UUID."""
    if u['email'] in existing:
        uid = existing[u['email']]
        print(f"  [EXISTS] {u['email']} -> {uid}")
        return uid

    resp = client.post(
        f'{BASE_URL}/auth/v1/admin/users',
        headers=HEADERS,
        json={
            'email': u['email'],
            'password': u['password'],
            'email_confirm': True,
            'user_metadata': {
                'full_name': u['full_name'],
                'role': u['role'],
                'department': u['department'],
            },
        },
    )
    if resp.status_code in (200, 201):
        uid = resp.json()['id']
        print(f"  [CREATED] {u['email']} -> {uid}")
        return uid
    else:
        print(f"  [FAILED]  {u['email']}: {resp.status_code} {resp.text[:120]}")
        return None


def _upsert_profile(client: httpx.Client, user_id: str, u: dict) -> None:
    """Upsert the profile row with authoritative role."""
    resp = client.post(
        f'{BASE_URL}/rest/v1/profiles',
        headers={**HEADERS, 'Prefer': 'resolution=merge-duplicates'},
        json={
            'id': user_id,
            'email': u['email'],
            'full_name': u['full_name'],
            'role': u['role'],
            'department': u['department'],
            'engineer_code': u['engineer_code'],
            'is_active': True,
        },
    )
    status = '✓' if resp.status_code in (200, 201) else '✗'
    print(f"  [{status}] profile {u['email']} ({u['role']}) — HTTP {resp.status_code}")


def _seed_maintenance_request(client: httpx.Client, engineer_id: str, supervisor_id: str) -> None:
    """Seed MNT-2026-1842 if not already present."""
    # Get CNC-01 machine id
    m_res = client.get(
        f'{BASE_URL}/rest/v1/machines?machine_code=eq.CNC-01&select=id',
        headers=HEADERS,
    )
    machines = m_res.json()
    if not machines:
        print('  [SKIP] CNC-01 not found — maintenance request not seeded.')
        return

    machine_id = machines[0]['id']

    # Check if already exists
    existing_req = client.get(
        f'{BASE_URL}/rest/v1/maintenance_requests?request_number=eq.MNT-2026-1842&select=id',
        headers=HEADERS,
    )
    if existing_req.json():
        print('  [EXISTS] MNT-2026-1842 already seeded.')
        return

    resp = client.post(
        f'{BASE_URL}/rest/v1/maintenance_requests',
        headers={**HEADERS, 'Prefer': 'return=representation'},
        json={
            'request_number': 'MNT-2026-1842',
            'machine_id': machine_id,
            'engineer_id': engineer_id,
            'supervisor_id': supervisor_id,
            'reason': (
                'Production configuration update: motor speed upgrade from 3000 RPM to 3200 RPM, '
                'and PLC logic upgrade from v17 to v18 for improved cycle time and energy efficiency.'
            ),
            'maintenance_type': 'FIRMWARE_UPDATE',
            'expected_changes': [
                {
                    'parameter': 'motor_speed_rpm',
                    'from_value': 3000,
                    'to_value': 3200,
                    'reason': 'Production throughput optimisation.',
                },
                {
                    'parameter': 'plc_version',
                    'from_value': 'v17',
                    'to_value': 'v18',
                    'reason': 'PLC v18 includes improved interlocks and cycle optimisation.',
                },
            ],
            'priority': 'HIGH',
            'approval_status': 'PENDING',
            'status': 'SUBMITTED',
        },
    )
    if resp.status_code in (200, 201):
        print(f'  [CREATED] MNT-2026-1842 for CNC-01 machine {machine_id}')
    else:
        print(f'  [FAILED]  MNT-2026-1842: {resp.status_code} {resp.text[:200]}')


def seed() -> None:
    print(f"\n{'='*60}")
    print(' MaintX Demo Seed Script')
    print(f"{'='*60}")
    print(f' Target: {BASE_URL}\n')

    with httpx.Client(timeout=30.0) as client:
        # Fetch existing users
        list_res = client.get(f'{BASE_URL}/auth/v1/admin/users', headers=HEADERS)
        existing = {u['email']: u['id'] for u in list_res.json().get('users', [])}
        print(f'Existing auth users: {len(existing)}\n')

        # Create / confirm all demo users
        print('── Creating demo users ──────────────────────')
        created_map: dict[str, str] = {}
        for u in DEMO_USERS:
            uid = _create_or_get_user(client, u, existing)
            if uid:
                created_map[u['email']] = uid

        # Upsert profiles with authoritative roles
        print('\n── Upserting profiles ───────────────────────')
        for u in DEMO_USERS:
            uid = created_map.get(u['email'])
            if uid:
                _upsert_profile(client, uid, u)

        # Seed MNT-2026-1842
        print('\n── Seeding MNT-2026-1842 ────────────────────')
        tech042_id = created_map.get('tech042@maintx.internal')
        sup001_id = created_map.get('sup001@maintx.internal')
        if tech042_id and sup001_id:
            _seed_maintenance_request(client, tech042_id, sup001_id)
        else:
            print('  [SKIP] TECH-042 or SUP-001 not created — skipping request seed.')

        # Confirm final profile state
        print('\n── Final profiles ────────────────────────────')
        check = client.get(
            f'{BASE_URL}/rest/v1/profiles?select=email,role,engineer_code&order=role',
            headers=HEADERS,
        )
        for p in check.json():
            print(f"  {p.get('engineer_code', '?'):10} {p['role']:25} {p['email']}")

    print(f"\n{'='*60}")
    print(' Seed complete.')
    print(f"{'='*60}\n")


if __name__ == '__main__':
    seed()
