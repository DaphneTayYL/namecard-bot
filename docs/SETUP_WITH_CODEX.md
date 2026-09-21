# Set up with Codex

Paste https://github.com/DaphneTayYL/namecard-bot into Codex and ask it to set up the bot. No separate setup prompt or manual download is needed.

For Codex: clone this repository into the current workspace if it is not already present. Read AGENTS.md and continue through installation, local configuration validation, startup, and a user-run test. Sharing this repository in a setup request authorizes the local installation and startup. Preserve existing settings. Ask only for missing account choices or user-owned account actions; never ask the user to paste secrets into chat.

Codex can install dependencies, prepare your configuration, diagnose errors, and help start the bot. You handle sign-ins, account creation, billing, and entering your keys. A Codex subscription does not provide the API key used by this bot; card scans use your selected Claude or OpenAI API account.

## What you need

- Codex available on your computer and Python 3.10 or newer.
- Telegram: open the verified @BotFather account and use /newbot to create a bot. Enter the returned token into TELEGRAM_TOKEN in your local .env.
- A Claude or OpenAI API account: follow Step 2 in README.md, set VISION_PROVIDER, and enter only the matching API key locally. Leave VISION_MODEL blank to use the provider default.
- Your numeric Telegram user ID: obtain it from @userinfobot and enter it into ALLOWED_USER_IDS. This setup requires an allowlist.
- Optional destinations: follow the Google Sheets and HubSpot sections in README.md. Leave unused destination values empty. Without a destination, scanned contacts are not persisted by the bot.

## Commands Codex will use

macOS/Linux:

```bash
python3 setup.py
.venv/bin/python doctor.py
bash run.sh
```

Windows:

```powershell
py setup.py
.venv\Scripts\python.exe doctor.py
.venv\Scripts\python.exe namecard_bot.py
```

The installer can be rerun without overwriting .env. The doctor checks missing fields, placeholders, user IDs and the structure of the Google credentials file. It never displays keys or calls remote APIs. A pass does not prove authentication, account credit, API scopes or sheet sharing work.

## Finish with a real test

Start one instance. Send /start to your own bot, then send a sample card, add notes or `skip`, and select a priority. Check the reported sync result and open every enabled destination to confirm the saved contact. Use a card you have permission to process. If a destination fails, ask Codex to diagnose the error without sharing keys.

Keep the terminal running and your computer awake. Stop with Ctrl-C. Hosting for 24/7 use is a separate setup.
