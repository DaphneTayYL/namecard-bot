# 📇 Namecard Collector Bot

Turn a phone photo of a business card into a clean CRM contact — in about 10 seconds, from Telegram.

> **Snap a card → Claude reads the name / email / company / title / phone → the bot asks you for meeting notes + a priority (🔴/🟡/🟢) → it writes a row to your Google Sheet AND upserts the contact into your CRM, tagged with the event you're at.**

Perfect for conferences, meetups, and sales events where you're collecting a stack of cards and don't want to type them up later.

### 👉 New here? **[Open the click-through setup guide →](https://daphnetayyl.github.io/namecard-bot/)**
A dummy-proof, next-next-next walkthrough that gets you running in ~15 minutes. Or follow the same steps in text below.

---

## ⚠️ Read this first (30 seconds)

This folder is a **template you make your own.** You are going to plug in **your own** accounts — nothing here is pre-connected to anyone else's data. You'll create:

| # | You connect… | Why | Required? |
|---|--------------|-----|-----------|
| 1 | **Your own Telegram bot** | This is *your* private bot. You message it, nobody else. | ✅ Required |
| 2 | **An Anthropic (Claude) API key** | Reads the text off the card photo. | ✅ Required |
| 3 | **A Google Sheet** | One tidy row per contact — your master list. | ⭐ Recommended |
| 4 | **A CRM (HubSpot)** | Auto-creates/updates the contact + logs a note. | ⭐ Recommended |

You can run with just #1 + #2 to try it, then add the Sheet and CRM when ready. **The bot tells you at startup exactly which pieces are connected and which are missing** — so you can't get it silently wrong.

> 💡 **Not technical?** That's fine. Every step below is copy-paste. If you can follow a recipe, you can run this. Total time: ~15 minutes the first time.

---

## 🚀 Quick start (the 3 commands)

```bash
cd namecard-bot-share
bash setup.sh          # installs everything, creates your .env
# → now edit .env and add google-creds.json (steps below)
bash run.sh            # starts the bot
```

Then open Telegram, find your bot, and send it `/start`. That's the whole loop.

Everything below is just *filling in the blanks* that `setup.sh` created.

---

## 🔧 Full setup, step by step

### Step 1 — Create your Telegram bot (2 min)

1. Open Telegram and search for **`@BotFather`** (the one with the blue checkmark).
2. Send `/newbot`.
3. Give it a name (e.g. `My Namecard Bot`) and a username ending in `bot` (e.g. `daphne_namecard_bot`).
4. BotFather replies with a **token** that looks like `8342xxxxxx:AAH...`. **Copy it.**
5. Paste it into your `.env` file on the `TELEGRAM_TOKEN=` line.

> This token *is* your bot. Anyone with it can control the bot — keep it private (it's already gitignored).

### Step 2 — Get a Claude API key (2 min)

1. Go to **https://console.anthropic.com** → sign in → **Settings → API keys → Create key**.
2. Copy the key (starts with `sk-ant-...`).
3. Paste it into `.env` on the `ANTHROPIC_API_KEY=` line.

> Cost is tiny — each card scan is a fraction of a cent on the default fast model. Effectively free for personal use.

### Step 3 — Connect a Google Sheet (5 min) ⭐

This gives you a clean master spreadsheet, one row per card.

**a. Make the sheet.** Create a new blank Google Sheet. Look at its URL:
```
https://docs.google.com/spreadsheets/d/1a2B3cLongStringHere_xxxxxxxxxxxxxxxxxxxxx/edit
                                        └──────────── this is the ID ────────────┘
```
Copy that long ID and paste it into `.env` on `GOOGLE_SHEET_ID=`.

**b. Create a "service account" (the bot's own Google identity).**
1. Go to **https://console.cloud.google.com** → create a new project (top bar) or pick one.
2. Search bar → **"Google Sheets API"** → **Enable**.
3. Left menu → **IAM & Admin → Service Accounts → + Create service account**. Name it `namecard-bot` → **Done**.
4. Click the new service account → **Keys** tab → **Add Key → Create new key → JSON**. A `.json` file downloads.
5. **Rename that file to `google-creds.json`** and drop it in this folder (next to `namecard_bot.py`).

**c. 🔑 Share the sheet with the bot — the one step everyone forgets.**
Open `google-creds.json`, find the `"client_email"` line — it looks like:
```
namecard-bot@your-project-id.iam.gserviceaccount.com
```
Copy that address. In your Google Sheet, click **Share**, paste it, give it **Editor** access, send.

> Without this share step the bot can *see* nothing and writes fail. If you skip everything else, don't skip this.

The bot auto-creates the header row on first write:
`Timestamp | Event | Name | Email | Company | Title | Phone | Priority | Notes`

### Step 4 — Connect your CRM: HubSpot (3 min) ⭐

1. In HubSpot: **Settings ⚙️ → Integrations → Private Apps → Create a private app**. Name it `Namecard Bot`.
2. **Scopes** tab → tick these three:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.notes.write`
3. **Create app** → copy the **access token** (`pat-na1-...`) → paste into `.env` on `HUBSPOT_TOKEN=`.

**Optional but nice:** so you can filter contacts by event/priority inside HubSpot, create two custom contact properties (**Settings → Properties → Contact properties → Create property**), both *Single-line text*:
- internal name `namecard_event`
- internal name `namecard_priority`

If you skip this, the bot still works — it writes event + priority into the contact's note instead, and auto-detects that the properties are missing.

> **Using a different CRM (Salesforce, Pipedrive, Attio…)?** The CRM logic lives in one function, `upsert_hubspot_contact()` in `namecard_bot.py`. Swap that one function for your CRM's API and everything else keeps working. Google Sheets alone is also a perfectly good "CRM" to start.

### Step 5 — Lock it to just you (1 min, strongly recommended)

Otherwise anyone who stumbles onto your bot could push junk into your CRM.
1. On Telegram, message **`@userinfobot`** → it replies with your numeric ID.
2. Put it in `.env`: `ALLOWED_USER_IDS=123456789` (comma-separate for teammates).

---

## ▶️ Running it

```bash
bash run.sh
```

At startup it prints a connection check like this:

```
=== Namecard bot config ===
  ✓ TELEGRAM_TOKEN        = 8342…
  ✓ ANTHROPIC_API_KEY     = sk-ant…
  ✓ HUBSPOT_TOKEN         = pat-na1…
  ✓ GOOGLE_SHEET_ID       = 1a2B…
  ✓ GOOGLE_CREDS_PATH     = google-creds.json
  ✗ ALLOWED_USER_IDS      (optional — not set)
```

A `✓` means it's wired up; a `✗` on a required line means fix your `.env`. Leave the window open — **the bot only runs while this is running.** Stop with `Ctrl-C`.

---

## 📱 How to use it (at an event)

1. **Tag the event once:** `/event LegalTech NYC 2026` — sticks until you change it.
2. **Send a photo** of any business card.
3. Bot shows what it read and asks for **notes** — type them, or send `skip`.
4. Tap **🔴 High / 🟡 Medium / 🟢 Low**.
5. ✅ Bot confirms it saved to your Sheet + CRM. Next card.

Other commands: `/event_status`, `/clear_event`, `/cancel`, `/help`.

---

## 🩹 Troubleshooting

| Symptom | Fix |
|---|---|
| `❌ Missing required env vars` at startup | Open `.env`, fill the flagged line, save, re-run. |
| Rows never appear in the Sheet | You forgot **Step 3c** — share the sheet with the `client_email` from `google-creds.json`. |
| HubSpot contact not created | Cards with **no email** are skipped in HubSpot (we key on email) — the Sheet row is still written. Otherwise check your token scopes. |
| Extraction is wrong | Retake the photo with better light / less glare. For tricky cards set `VISION_MODEL=claude-sonnet-4-6` in `.env`. |
| Bot goes silent when laptop sleeps | Expected — it only runs while `run.sh` is running. For always-on, deploy to Railway or Render (see below). |

---

## ☁️ Making it always-on (optional, later)

Running on your laptop is fine for a single event. For 24/7, deploy to a free/cheap host like **Railway** or **Render**: push this folder to a private GitHub repo, add the same env vars in the host's dashboard, upload `google-creds.json` as a secret file, and set the start command to `python namecard_bot.py`. No code changes needed.

---

## 🗂️ What's in this folder

```
namecard-bot-share/
├── namecard_bot.py           # the bot (one file — read it, it's friendly)
├── requirements.txt          # python dependencies
├── setup.sh                  # one-time installer (creates .venv + .env)
├── run.sh                    # starts the bot
├── .env.example              # template — setup.sh copies this to .env
├── google-creds.json.example # placeholder — replace with YOUR real key (step 3)
├── .gitignore                # keeps .env + google-creds.json from ever being committed
└── README.md                 # this file
```

**Never commit or share `.env` or `google-creds.json`** — those are your live secrets. `.gitignore` already blocks them, but don't paste them into chats or repos.

---

Built with Claude vision + `python-telegram-bot`. One file, no database, no server required to get started.
