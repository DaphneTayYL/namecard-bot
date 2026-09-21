"""
Namecard Collector Telegram Bot
--------------------------------
Send a photo of a business card -> bot extracts name/email/company/title,
asks for meeting notes + priority (H/M/L), then saves to:
  1. Google Sheets (one row per contact)
  2. HubSpot CRM (upserts contact + attaches a note tagged with the event)

Run:  python namecard_bot.py
Stop: Ctrl-C
"""

from __future__ import annotations  # enables modern type syntax on Python 3.9
import os
import json
import base64
import asyncio
import logging
from datetime import datetime, timezone

import sys
import httpx

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters,
)

import gspread
from google.oauth2.service_account import Credentials

# -----------------------------------------------------------------------------
# Config — reads from your shell env (export VAR=...) OR a local .env file
# if you happen to have one. Either works. No need to maintain both.
# -----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    # .env is the source of truth — it overrides any stale shell exports
    load_dotenv(override=True)
except ImportError:
    pass

def _first_env(*names: str, default: str = "") -> str:
    """Return the first env var that is set & non-empty, or default."""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default

TELEGRAM_TOKEN = _first_env(
    "TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN", "TG_BOT_TOKEN", "BOT_TOKEN",
)
ANTHROPIC_API_KEY = _first_env(
    "ANTHROPIC_API_KEY", "CLAUDE_API_KEY",
)
HUBSPOT_TOKEN = _first_env(
    "HUBSPOT_TOKEN", "HUBSPOT_ACCESS_TOKEN",
    "HUBSPOT_PRIVATE_APP_TOKEN", "HUBSPOT_API_KEY",
)
def _clean_sheet_id(raw: str) -> str:
    """Accept either a full Sheets URL or just the ID; return just the ID."""
    if not raw:
        return raw
    if "/d/" in raw:
        raw = raw.split("/d/", 1)[1]
    # strip anything after the ID: /, ?, #
    for sep in ("/", "?", "#"):
        if sep in raw:
            raw = raw.split(sep, 1)[0]
    return raw.strip()

GOOGLE_SHEET_ID = _clean_sheet_id(_first_env(
    "GOOGLE_SHEET_ID", "NAMECARD_SHEET_ID", "SHEET_ID",
))
GOOGLE_CREDS_PATH = _first_env(
    "GOOGLE_CREDS_PATH", "GOOGLE_APPLICATION_CREDENTIALS",
    default="google-creds.json",
)

from doctor import main as check_configuration
if check_configuration():
    sys.exit(1)

# Lock the bot to your own Telegram user ID(s), comma-separated
ALLOWED_USER_IDS = {
    int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()
}

from doctor import selected_provider
VISION_PROVIDER = selected_provider(os.environ)
OPENAI_API_KEY = _first_env("OPENAI_API_KEY")
VISION_API_KEY = OPENAI_API_KEY if VISION_PROVIDER == "openai" else ANTHROPIC_API_KEY
VISION_MODEL = _first_env("VISION_MODEL", default=("gpt-4.1-mini" if VISION_PROVIDER == "openai" else "claude-haiku-4-5-20251001"))

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("namecard-bot")


def _check_env_and_print():
    """Show what was loaded so missing vars are obvious at startup."""
    rows = [
        ("TELEGRAM_TOKEN",    TELEGRAM_TOKEN,    True),
        ("OPENAI_API_KEY" if VISION_PROVIDER == "openai" else "ANTHROPIC_API_KEY", VISION_API_KEY, True),
        ("HUBSPOT_TOKEN",     HUBSPOT_TOKEN,     False),
        ("GOOGLE_SHEET_ID",   GOOGLE_SHEET_ID,   False),
        ("GOOGLE_CREDS_PATH", GOOGLE_CREDS_PATH, False),
        ("ALLOWED_USER_IDS",  os.environ.get("ALLOWED_USER_IDS", ""), False),
    ]
    print("\n=== Namecard bot config ===")
    missing_required = []
    for name, val, required in rows:
        if val:
            print(f"  ✓ {name:<22} configured (not remotely verified)")
        else:
            tag = "REQUIRED" if required else "optional"
            print(f"  ✗ {name:<22} ({tag} — not set)")
            if required:
                missing_required.append(name)
    print()
    if missing_required:
        print(f"❌ Missing required env vars: {', '.join(missing_required)}")
        print("   Either export them in your shell or add them to a .env file.")
        sys.exit(1)
    if not GOOGLE_SHEET_ID:
        print("⚠️  Google Sheets disabled (no GOOGLE_SHEET_ID). Sheet rows won't be written.")
    if not HUBSPOT_TOKEN:
        print("⚠️  HubSpot disabled (no HUBSPOT_TOKEN). Contacts won't sync to CRM.")
    print()


_check_env_and_print()


# Conversation states
NOTES, PRIORITY = range(2)


# -----------------------------------------------------------------------------
# Vision: extract namecard fields with Claude or OpenAI
# -----------------------------------------------------------------------------
from vision import extract_namecard as extract_with_provider

def extract_namecard(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    return extract_with_provider(image_bytes, mime_type, provider=VISION_PROVIDER,
                                 api_key=VISION_API_KEY, model=VISION_MODEL)

# -----------------------------------------------------------------------------
# Storage: Google Sheets
# -----------------------------------------------------------------------------
SHEET_HEADERS = [
    "Timestamp", "Event", "Name", "Email", "Company",
    "Title", "Phone", "Priority", "Notes",
]

def _sheet():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(GOOGLE_SHEET_ID).sheet1

def append_to_sheet(row: list) -> None:
    ws = _sheet()
    # Ensure header row exists
    first_row = ws.row_values(1)
    if first_row != SHEET_HEADERS:
        if not first_row:
            ws.append_row(SHEET_HEADERS)
        # if a different header exists we don't overwrite it; just append below
    ws.append_row(row, value_input_option="USER_ENTERED")


# -----------------------------------------------------------------------------
# Storage: HubSpot
# -----------------------------------------------------------------------------
HUBSPOT_BASE = "https://api.hubapi.com"
# Standard association type id for note -> contact
NOTE_TO_CONTACT_ASSOC_ID = 202

async def upsert_hubspot_contact(
    name: str, email: str, company: str, title: str,
    event: str, priority: str, notes: str, phone: str = "",
) -> str | None:
    """Upsert a contact by email and attach a note. Returns the contact id."""
    if not HUBSPOT_TOKEN:
        return None
    if not email:
        log.info("Skipping HubSpot: no email on the namecard")
        return None

    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }

    parts = name.strip().split(None, 1)
    firstname = parts[0] if parts else ""
    lastname  = parts[1] if len(parts) > 1 else ""

    # Standard properties always set
    properties = {
        "email":     email,
        "firstname": firstname,
        "lastname":  lastname,
        "company":   company,
        "jobtitle":  title,
        "phone":     phone,
    }
    # Custom properties: only set if non-empty (HubSpot will reject unknown
    # properties — so create them in HubSpot Settings if you want this enrichment)
    if event:
        properties["namecard_event"] = event
    if priority:
        properties["namecard_priority"] = priority
    if notes:
        properties["namecard_notes"] = notes

    async with httpx.AsyncClient(timeout=20) as client:
        # 1. Try to find by email
        r = await client.post(
            f"{HUBSPOT_BASE}/crm/v3/objects/contacts/search",
            headers=headers,
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }]
                }],
                "limit": 1,
            },
        )
        results = r.json().get("results", []) if r.status_code == 200 else []

        contact_id: str | None = None
        if results:
            contact_id = results[0]["id"]
            r = await client.patch(
                f"{HUBSPOT_BASE}/crm/v3/objects/contacts/{contact_id}",
                headers=headers,
                json={"properties": properties},
            )
            if r.status_code >= 400:
                # Retry without custom properties (in case they don't exist yet)
                clean_props = {k: v for k, v in properties.items()
                               if k not in {"namecard_event", "namecard_priority", "namecard_notes"}}
                await client.patch(
                    f"{HUBSPOT_BASE}/crm/v3/objects/contacts/{contact_id}",
                    headers=headers,
                    json={"properties": clean_props},
                )
        else:
            r = await client.post(
                f"{HUBSPOT_BASE}/crm/v3/objects/contacts",
                headers=headers,
                json={"properties": properties},
            )
            if r.status_code >= 400:
                clean_props = {k: v for k, v in properties.items()
                               if k not in {"namecard_event", "namecard_priority", "namecard_notes"}}
                r = await client.post(
                    f"{HUBSPOT_BASE}/crm/v3/objects/contacts",
                    headers=headers,
                    json={"properties": clean_props},
                )
            r.raise_for_status()
            contact_id = r.json()["id"]

        # 2. Attach a Note with the event + priority + meeting notes (BEST EFFORT)
        # If the private app doesn't have notes scope, this silently skips —
        # the notes are still saved to the contact's namecard_notes property above.
        if contact_id:
            note_body = (
                f"<b>Namecard captured</b><br>"
                f"<b>Event:</b> {event or '(none)'}<br>"
                f"<b>Priority:</b> {priority or '-'}<br>"
                f"<br><b>Notes:</b><br>{notes or '(none)'}"
            )
            ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            try:
                rn = await client.post(
                    f"{HUBSPOT_BASE}/crm/v3/objects/notes",
                    headers=headers,
                    json={
                        "properties": {
                            "hs_note_body":  note_body,
                            "hs_timestamp":  ts,
                        },
                        "associations": [{
                            "to": {"id": contact_id},
                            "types": [{
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": NOTE_TO_CONTACT_ASSOC_ID,
                            }],
                        }],
                    },
                )
                if rn.status_code >= 400:
                    log.warning("HubSpot note skipped (status %s) — likely missing notes scope. Notes saved on contact instead.", rn.status_code)
            except Exception as e:
                log.warning("HubSpot note creation failed (%s) — notes saved on contact instead.", e)

    return contact_id


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
def authorized(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return update.effective_user and update.effective_user.id in ALLOWED_USER_IDS


# -----------------------------------------------------------------------------
# Bot handlers
# -----------------------------------------------------------------------------
def _esc(s: str) -> str:
    """Escape Telegram legacy-Markdown special chars so user data doesn't break parsing."""
    if not s:
        return s
    for ch in ("_", "*", "[", "`"):
        s = s.replace(ch, f"\\{ch}")
    return s

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await update.message.reply_text("Not authorized.")
        return
    await update.message.reply_text(
        "📇 *Namecard collector ready.*\n\n"
        "*Set an event tag (sticks for the session):*\n"
        "`/event LegalTech NYC 2026`\n\n"
        "*Then just send a photo of any business card.*\n"
        "I'll extract name/email/company/title, ask for notes + priority, "
        "and save to Google Sheets + HubSpot.\n\n"
        "Other commands:\n"
        "/event\\_status — show current event tag\n"
        "/clear\\_event — clear current event tag\n"
        "/cancel — cancel an in-progress capture",
        parse_mode="Markdown",
    )

async def cmd_set_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    event = " ".join(ctx.args).strip()
    if not event:
        await update.message.reply_text("Usage: /event <event name>")
        return
    ctx.bot_data["current_event"] = event
    await update.message.reply_text(f"✓ Event tag set: *{event}*", parse_mode="Markdown")

async def cmd_event_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    e = ctx.bot_data.get("current_event") or "(none)"
    await update.message.reply_text(f"Current event: *{e}*", parse_mode="Markdown")

async def cmd_clear_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    ctx.bot_data.pop("current_event", None)
    await update.message.reply_text("Event tag cleared.")

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END

    msg = await update.message.reply_text("📇 Reading namecard…")

    # Photos vs documents (uncompressed images)
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        mime = "image/jpeg"
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        file = await update.message.document.get_file()
        mime = update.message.document.mime_type
    else:
        await msg.edit_text("Please send an image (photo or image file).")
        return ConversationHandler.END

    try:
        image_bytes = bytes(await file.download_as_bytearray())
    except Exception as e:
        log.exception("Photo download failed")
        await msg.edit_text(f"❌ Couldn't download the photo: {e}\nTry sending a smaller photo or as a compressed image.")
        return ConversationHandler.END

    await msg.edit_text("📇 Extracting fields with your selected AI provider…")

    try:
        # Run sync vision call in a thread so it doesn't block the event loop
        data = await asyncio.to_thread(extract_namecard, image_bytes, mime)
    except Exception as e:
        log.exception("Vision extraction failed")
        await msg.edit_text(f"❌ Couldn't read the card: {e}")
        return ConversationHandler.END

    ctx.user_data["namecard"] = data

    summary = (
        f"*Name:* {_esc(data['name']) or '—'}\n"
        f"*Email:* {_esc(data['email']) or '—'}\n"
        f"*Company:* {_esc(data['company']) or '—'}\n"
        f"*Title:* {_esc(data['title']) or '—'}\n"
        f"*Phone:* {_esc(data['phone']) or '—'}"
    )
    await msg.edit_text(
        f"✓ *Extracted:*\n\n{summary}\n\n"
        "📝 Send any notes from the meeting (or type `skip`):",
        parse_mode="Markdown",
    )
    return NOTES

async def handle_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = (update.message.text or "").strip()
    if notes.lower() == "skip":
        notes = ""
    ctx.user_data["notes"] = notes

    keyboard = [[
        InlineKeyboardButton("🔴 High",   callback_data="H"),
        InlineKeyboardButton("🟡 Medium", callback_data="M"),
        InlineKeyboardButton("🟢 Low",    callback_data="L"),
    ]]
    await update.message.reply_text(
        "Priority?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PRIORITY

async def handle_priority(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    priority = query.data  # H / M / L

    data    = ctx.user_data.get("namecard", {})
    notes   = ctx.user_data.get("notes", "")
    event   = ctx.bot_data.get("current_event", "")

    name    = data.get("name", "")
    email   = data.get("email", "")
    company = data.get("company", "")
    title   = data.get("title", "")
    phone   = data.get("phone", "")

    timestamp = datetime.now().isoformat(timespec="seconds")
    errors: list[str] = []
    saved: list[str] = []

    # 1. Google Sheets
    if GOOGLE_SHEET_ID:
        try:
            append_to_sheet([
                timestamp, event, name, email, company,
                title, phone, priority, notes,
            ])
            saved.append("Google Sheets")
        except Exception as e:
            log.exception("Sheets write failed")
            errors.append(f"Sheets: {e}")

    # 2. HubSpot
    if HUBSPOT_TOKEN:
        try:
            cid = await upsert_hubspot_contact(
                name=name, email=email, company=company, title=title,
                event=event, priority=priority, notes=notes, phone=phone,
            )
            if cid:
                saved.append(f"HubSpot (contact {cid})")
            elif not email:
                errors.append("HubSpot: skipped (no email on card)")
        except Exception as e:
            log.exception("HubSpot write failed")
            errors.append(f"HubSpot: {e}")

    pri_label = {"H": "🔴 High", "M": "🟡 Medium", "L": "🟢 Low"}.get(priority, priority)
    status = (
        (f"✅ *Saved.*\n" if saved else f"⚠️ *Not saved to any destination.*\n") +
        f"*Event:* {_esc(event) or '(none)'}\n"
        f"*Contact:* {_esc(name) or '—'}  {_esc(email) or 'no-email'}\n"
        f"*Priority:* {pri_label}\n"
        f"*Synced to:* {_esc(', '.join(saved)) if saved else '(nothing)'}"
    )
    if errors:
        status += "\n\n⚠️ *Issues:*\n" + "\n".join(f"• {_esc(e)}" for e in errors)

    await query.edit_message_text(status, parse_mode="Markdown")
    ctx.user_data.clear()
    return ConversationHandler.END

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    # Bump timeouts — default 5s read is too short for full-res phone photos
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .connect_timeout(30)
        .pool_timeout(30)
        .get_updates_read_timeout(60)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.Document.IMAGE, handle_photo),
        ],
        states={
            NOTES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_notes)],
            PRIORITY: [CallbackQueryHandler(handle_priority)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_start))
    app.add_handler(CommandHandler("event", cmd_set_event))
    app.add_handler(CommandHandler("event_status", cmd_event_status))
    app.add_handler(CommandHandler("clear_event",  cmd_clear_event))
    app.add_handler(conv)

    log.info("Bot starting…  (Ctrl-C to stop)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
