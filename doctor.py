"""Offline configuration validation. Never prints configuration values or calls APIs."""
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent

def selected_provider(config):
    explicit = config.get('VISION_PROVIDER', '').strip().lower()
    if explicit:
        return explicit
    return 'openai' if config.get('OPENAI_API_KEY', '').strip() and not (config.get('ANTHROPIC_API_KEY', '').strip() or config.get('CLAUDE_API_KEY', '').strip()) else 'anthropic'

def validate(config, root=ROOT):
    issues = []
    def placeholder(value):
        return any(marker in value.lower() for marker in ('...', '…', 'your-', 'replace', 'changeme'))
    provider = selected_provider(config)
    if provider not in ('anthropic', 'openai'):
        issues.append('VISION_PROVIDER: choose anthropic or openai.')
    provider_key = 'OPENAI_API_KEY' if provider == 'openai' else 'ANTHROPIC_API_KEY'
    for key in ('TELEGRAM_TOKEN', provider_key):
        value = config.get(key, '').strip()
        if not value or placeholder(value):
            issues.append(f'{key}: enter your own value in .env.')
    ids = config.get('ALLOWED_USER_IDS', '').strip()
    if not ids or any(not re.fullmatch(r'[1-9][0-9]*', item.strip()) for item in ids.split(',')):
        issues.append('ALLOWED_USER_IDS: enter positive numeric Telegram user IDs, separated by commas.')
    sheet = config.get('GOOGLE_SHEET_ID', '').strip()
    if sheet:
        if placeholder(sheet):
            issues.append('GOOGLE_SHEET_ID: replace the placeholder or leave empty to skip Sheets.')
        path = Path(config.get('GOOGLE_CREDS_PATH', '').strip() or 'google-creds.json')
        if not path.is_absolute():
            path = root / path
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict) or data.get('type') != 'service_account' or not all(data.get(k) for k in ('client_email', 'private_key', 'token_uri')):
                issues.append('Google credentials: use a complete service-account JSON file.')
        except (OSError, ValueError):
            issues.append('Google credentials: file missing, unreadable, or invalid JSON.')
    hubspot = config.get('HUBSPOT_TOKEN', '').strip()
    if hubspot and placeholder(hubspot):
        issues.append('HUBSPOT_TOKEN: replace the placeholder or leave empty to skip HubSpot.')
    return issues

def main():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print('Dependencies missing. Run python3 setup.py (Windows: py setup.py).')
        return 1
    load_dotenv(ROOT / '.env', override=True)
    config = dict(os.environ)
    for canonical, aliases in {
        'TELEGRAM_TOKEN': ('TELEGRAM_BOT_TOKEN', 'TG_BOT_TOKEN', 'BOT_TOKEN'),
        'ANTHROPIC_API_KEY': ('CLAUDE_API_KEY',),
        'HUBSPOT_TOKEN': ('HUBSPOT_ACCESS_TOKEN', 'HUBSPOT_PRIVATE_APP_TOKEN', 'HUBSPOT_API_KEY'),
        'GOOGLE_SHEET_ID': ('NAMECARD_SHEET_ID', 'SHEET_ID'),
        'GOOGLE_CREDS_PATH': ('GOOGLE_APPLICATION_CREDENTIALS',),
    }.items():
        config[canonical] = next((config.get(k, '').strip() for k in (canonical, *aliases) if config.get(k, '').strip()), '')
    issues = validate(config)
    for issue in issues:
        print('FIX: ' + issue)
    if issues:
        return 1
    print('PASS: local configuration checks. Credentials and remote permissions are not verified.')
    for key, name in [('GOOGLE_SHEET_ID', 'Google Sheets'), ('HUBSPOT_TOKEN', 'HubSpot')]:
        print(f'{name}: ' + ('configured; verify with a test card' if config.get(key, '').strip() else 'disabled'))
    if not any(config.get(k, '').strip() for k in ('GOOGLE_SHEET_ID', 'HUBSPOT_TOKEN')):
        print('Preview only: contacts will not be saved to a Sheet or CRM.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
