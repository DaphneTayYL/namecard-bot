# Set up Namecard Bot with Codex

When the user shares this repository link for setup, treat it as a request to install and run the bot. Clone into their workspace if needed. Do not stop at a plan or ask them to run installation commands themselves. Complete the local setup and guide the user through account steps. Read SETUP_WITH_CODEX.md before starting.

1. Inspect the OS and Python. Use Python 3.10+ and a project-local .venv. Run `python3 setup.py` (Windows: `py setup.py`). Preserve existing .env and credential files; never print their contents or values.
2. Ask whether the user wants Google Sheets, HubSpot, both, or preview only. Explain that preview only does not persist contacts. Leave skipped integration values empty.
3. Open .env in the user's local editor for them to enter TELEGRAM_TOKEN, ANTHROPIC_API_KEY, and ALLOWED_USER_IDS. Guide BotFather and account creation using SETUP_WITH_CODEX.md and README.md. Do not request keys in chat or put them in command arguments, logs, source, screenshots, or commits. Do not read .env into tool output.
4. For Sheets, guide the user to place their downloaded service-account key at google-creds.json and share their selected sheet with the service account as Editor. For HubSpot, guide their own app/token setup. Do not claim these integrations are verified by local checks.
5. Run `.venv/bin/python doctor.py` (Windows: `.venv\Scripts\python.exe doctor.py`). Report field names and fixes only. Resolve installation errors. If account setup is pending, give the precise next step without claiming completion.
6. Once checks pass, run one instance in a visible terminal, using `bash run.sh` on macOS/Linux or `.venv\Scripts\python.exe namecard_bot.py` on Windows. Explain that the computer must remain awake and the process running. Do not deploy or create background services unless requested.
7. Ask the user to send /start and a sample card to their own bot, add notes or skip, and select a priority. This uses their Anthropic API account and writes to configured destinations. Verify their observed result, including each enabled destination, before calling the setup fully tested. Do not invent contacts or send messages on their behalf.

Never commit .env, credentials, .venv, or logs. Config checks must not make network requests. Run `python3 -m unittest discover -s tests` after changing setup validation.
