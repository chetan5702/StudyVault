"""Fail closed on unchanged production placeholders before Docker touches data."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED = [
    'SITE_DOMAIN', 'SECRET_KEY', 'POSTGRES_PASSWORD', 'RESEND_API_KEY',
    'PUBLIC_FRONTEND_URL', 'CORS_ORIGINS', 'EMAIL_FROM',
]

def validate(path: Path) -> list[str]:
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    problems = []
    for key in REQUIRED:
        if not values.get(key) or 'REPLACE' in values[key] or 'your-verified-domain' in values[key]:
            problems.append(f'Configure {key} with a real value')
    domain = values.get('SITE_DOMAIN', '')
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', domain) or domain.endswith(('.example', '.example.com', '.test', '.localhost')):
        problems.append('SITE_DOMAIN must be a real public DNS name')
    if values.get('PUBLIC_FRONTEND_URL') != f'https://{domain}':
        problems.append('PUBLIC_FRONTEND_URL must match https://SITE_DOMAIN')
    if values.get('CORS_ORIGINS') != f'https://{domain}':
        problems.append('CORS_ORIGINS must match https://SITE_DOMAIN')
    if len(values.get('SECRET_KEY','')) < 40:
        problems.append('SECRET_KEY must be at least 40 characters of fresh random data')
    if not re.fullmatch(r'[A-Za-z0-9]{40,}', values.get('POSTGRES_PASSWORD', '')):
        problems.append('POSTGRES_PASSWORD must be a fresh alphanumeric secret of at least 40 characters')
    if values.get('ENVIRONMENT') != 'production':
        problems.append('ENVIRONMENT must be production')
    if values.get('REQUIRE_EMAIL_VERIFICATION','').lower() != 'true':
        problems.append('REQUIRE_EMAIL_VERIFICATION must be true')
    if values.get('PUBLIC_AUTH_LIMIT_ENABLED', '').lower() != 'true':
        problems.append('PUBLIC_AUTH_LIMIT_ENABLED must be true')
    if values.get('EMAIL_PROVIDER') != 'resend':
        problems.append('EMAIL_PROVIDER must be resend')
    if values.get('STUDYVAULT_DEBUG','').lower() != 'false' or values.get('SEED_DEMO','').lower() != 'false':
        problems.append('Debug and demo seeding must be disabled')
    return problems

if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.env.production')
    if not path.is_file():
        print(f'Missing {path}', file=sys.stderr)
        sys.exit(1)
    problems = validate(path)
    if problems:
        print('Production configuration rejected:\n- ' + '\n- '.join(problems), file=sys.stderr)
        sys.exit(1)
    print('Release configuration structure passed. Secrets, DNS, email and TLS must still be verified.')
