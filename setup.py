"""Cross-platform, repeatable setup: python3 setup.py (Windows: py setup.py)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent

def main():
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 or newer is required.')
    target = ROOT / '.venv'
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
    env = ROOT / '.env'
    if not env.exists():
        shutil.copyfile(ROOT / '.env.example', env)
        if os.name != 'nt':
            env.chmod(0o600)
    print('Setup complete. Existing settings were preserved.')
    print('Open .env locally and fill in the required settings. Do not paste keys into chat.')
    print(f'Check: "{python}" doctor.py')
    print(f'Start: "{python}" namecard_bot.py')

if __name__ == '__main__':
    main()
