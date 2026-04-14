"""
==============================================
  TELEGRAM REFERRAL BOT - 500 Naira Per Referral
==============================================
"""

import sqlite3
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8687604270:AAFauRixQN-HKMQEjbJymW_2wvY3K78eqkE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8683185394"))
REWARD_PER_REFERRAL = 500

REQUIRED_TASKS = [
    {"label": "📺 Subscribe on YouTube", "url": "https://youtube.com/@financial_hub_money"},
    {"label": "🐦 Follow on X", "url": "https://x.com/Prechy520902"},
    {"label": "🔁 Repost & Comment on X", "url": "https://x.com/i/status/2043981238436827236"},
    {"label": "💬 Join Main Telegram Group", "url": "https://t.me/+tk61BCP4bX8xYTlk"},
    {"label": "💰 Join Payment Telegram Group", "url": "https://t.me/+L_629pE5kpVhYzc0"},
    {"label": "📱 Join WhatsApp Group", "url": "https://chat.whatsapp.com/BWVoJpO4JpQJLE2UWeBE4L"},
]

# Telegram group chat IDs for auto-verification
TELEGRAM_GROUP_IDS = [
    -5286415224,  # Main Telegram Group
    -5004346575,  # Payment Telegram Group
]

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
DB_FILE = "referral_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        referred_by INTEGER,
        balance INTEGER DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        bank_name TEXT,
        account_number TEXT,
        account_name TEXT,
        status TEXT DEFAULT 'pending',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def register_user(user_id, username, full_name, referred_by=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by) VALUES (?,?,?,?)",
              (user_id, username, full_name, referred_by))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_balance(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_referral_count(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND verified=1", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def add_referral(referrer_id, referred_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM referrals WHERE referred_id=?", (referred_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)", (referrer_id, referred_id))
    conn.commit()
    conn.close()
    return True

def verify_referral(referred_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE referrals SET verified=1 WHERE referred_id=?", (referred_id,))
    conn.commit()
    conn.close()

def get_referrer(referred_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM referrals WHERE referred_id=?", (referred_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def save_withdrawal(user_id, amount, bank_name, account_number, account_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO withdrawals (user_id, amount, bank_name, account_number, account_name) VALUES (?,?,?,?,?)",
              (user_id, amount, bank_name, account_number, account_name))
    conn.commit()
    conn.close()

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT w.id, w.user_id, u.full_name, u.username, w.amount,
                        w.bank_name, w.account_number, w.account_name, w.requested_at
                 FROM withdrawals w JOIN users u ON w.user_id=u.user_id
                 WHERE w.status='pending' ORDER BY w.requested_at""")
    rows = c.fetchall()
    conn.close()
    return rows

def mark_paid(withdrawal_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE withdrawals SET status='paid' WHERE id=?", (withdrawal_id,))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
#  MEMBERSHIP CHECK
# ─────────────────────────────────────────────
async def check_telegram_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not TELEGRAM_GROUP_IDS:
        return True  # Skip if no group IDs configured yet
    for group_id in TELEGRAM_GROUP_IDS:
        try:
            member = await context.bot.get_chat_member(group_id, user_id)
            if member.status in ("left", "kicked", "banned"):
                return False
        except Exception:
            return False
    return True

# ─────────────────────────────────────────────
#  CONVERSATION STATES
# ─────────────────────────────────────────────
BANK_NAME, ACCOUNT_NUMBER, ACCOUNT_NAME, CONFIRM = range(4)

# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referred_by = None

    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].replace("ref_", ""))
            if referred_by == user.id:
                referred_by = None
        except ValueError:
            referred_by = None

    is_new = get_user(user.id) is None
    register_user(user.id, user.username or "", user.full_name, referred_by)

    if is_new and referred_by:
        add_referral(referred_by, user.id)

    keyboard = []
    for task in REQUIRED_TASKS:
        keyboard.append([InlineKeyboardButton(task["label"], url=task["url"])])
    keyboard.append([InlineKeyboardButton("✅ I've Done All — Verify Me", callback_data="verify")])

    await update.message.reply_text(
        f"👋 Welcome to *Referral Pay*, {user.first_name}!\n\n"
        f"💰 *Earn ₦500 for every person you refer!*\n\n"
        f"📌 *Complete ALL tasks below first:*\n"
        f"1️⃣ Subscribe to YouTube channel\n"
        f"2️⃣ Follow on X (Twitter)\n"
        f"3️⃣ Repost & comment on X\n"
        f"4️⃣ Join Main Telegram group\n"
        f"5️⃣ Join Payment Telegram group\n"
        f"6️⃣ Join WhatsApp group\n\n"
        f"👇 Tap each button, complete the task, then tap *Verify Me*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    is_member = await check_telegram_membership(user.id, context)

    if not is_member:
        await query.edit_message_text(
            "❌ You haven't joined the required Telegram groups yet!\n\n"
            "Please join both groups then tap Verify again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ I've Done All — Verify Me", callback_data="verify")
            ]])
        )
        return

    referrer_id = get_referrer(user.id)
    if referrer_id:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT verified FROM referrals WHERE referred_id=?", (user.id,))
        row = c.fetchone()
        conn.close()

        if row and row[0] == 0:
            verify_referral(user.id)
            update_balance(referrer_id, REWARD_PER_REFERRAL)
            try:
                await context.bot.send_message(
                    referrer_id,
                    f"🎉 *You just earned ₦{REWARD_PER_REFERRAL}!*\n"
                    f"{user.full_name} completed all tasks using your link!\n"
                    f"Use /balance to check your earnings.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    await query.edit_message_text(
        f"✅ *Welcome to Referral Pay!*\n\n"
        f"🔗 *Your referral link:*\n`{ref_link}`\n\n"
        f"Share this link and earn ₦500 for each person who completes all tasks!\n\n"
        f"📊 /balance — Check earnings\n"
        f"💸 /withdraw — Request payout\n"
        f"🔗 /referral — Get your link",
        parse_mode="Markdown"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bal = get_balance(user.id)
    ref_count = get_referral_count(user.id)
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    await update.message.reply_text(
        f"💰 *Your Earnings*\n\n"
        f"Balance: ₦{bal:,}\n"
        f"Successful Referrals: {ref_count}\n\n"
        f"🔗 *Your referral link:*\n`{ref_link}`\n\n"
        f"Use /withdraw to request a payout.",
        parse_mode="Markdown"
    )


async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    ref_count = get_referral_count(user.id)

    await update.message.reply_text(
        f"🔗 *Your Referral Link:*\n`{ref_link}`\n\n"
        f"👥 Total referrals: {ref_count}\n"
        f"💰 Reward: ₦500 per referral\n\n"
        f"Share and earn!",
        parse_mode="Markdown"
    )


async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_balance(update.effective_user.id)
    if bal < 500:
        await update.message.reply_text(
            f"❌ Your balance is ₦{bal}. Minimum withdrawal is ₦500."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"💸 *Withdrawal Request*\n\n"
        f"Your balance: ₦{bal:,}\n\n"
        f"Enter your *Bank Name* (e.g. GTBank, Opay, Palmpay):",
        parse_mode="Markdown"
    )
    return BANK_NAME


async def get_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bank_name"] = update.message.text.strip()
    await update.message.reply_text("Enter your *Account Number*:", parse_mode="Markdown")
    return ACCOUNT_NUMBER


async def get_account_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_number"] = update.message.text.strip()
    await update.message.reply_text("Enter your *Account Name*:", parse_mode="Markdown")
    return ACCOUNT_NAME


async def get_account_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["account_name"] = update.message.text.strip()
    bal = get_balance(update.effective_user.id)

    await update.message.reply_text(
        f"📋 *Confirm Withdrawal*\n\n"
        f"Amount: ₦{bal:,}\n"
        f"Bank: {context.user_data['bank_name']}\n"
        f"Account No: {context.user_data['account_number']}\n"
        f"Account Name: {context.user_data['account_name']}\n\n"
        f"Is this correct?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Submit", callback_data="confirm_withdraw"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]
        ])
    )
    return CONFIRM


async def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if query.data == "cancel_withdraw":
        await query.edit_message_text("❌ Withdrawal cancelled.")
        return ConversationHandler.END

    bal = get_balance(user.id)
    save_withdrawal(
        user.id, bal,
        context.user_data["bank_name"],
        context.user_data["account_number"],
        context.user_data["account_name"]
    )
    deduct_balance(user.id, bal)

    await query.edit_message_text(
        f"✅ *Withdrawal request submitted!*\n\n"
        f"Amount: ₦{bal:,}\n"
        f"The admin will process your payment shortly. 🙏",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *New Withdrawal Request!*\n\n"
        f"User: {user.full_name} (@{user.username})\n"
        f"Amount: ₦{bal:,}\n"
        f"Bank: {context.user_data['bank_name']}\n"
        f"Acct No: {context.user_data['account_number']}\n"
        f"Acct Name: {context.user_data['account_name']}\n\n"
        f"Use /pending to see all requests.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return

    rows = get_pending_withdrawals()
    if not rows:
        await update.message.reply_text("✅ No pending withdrawals.")
        return

    for row in rows:
        wid, uid, name, uname, amount, bank, acct_no, acct_name, req_at = row
        await update.message.reply_text(
            f"💸 *Withdrawal #{wid}*\n\n"
            f"Name: {name} (@{uname})\n"
            f"Amount: ₦{amount:,}\n"
            f"Bank: {bank}\n"
            f"Acct No: `{acct_no}`\n"
            f"Acct Name: {acct_name}\n"
            f"Requested: {req_at}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ Mark #{wid} as Paid", callback_data=f"paid_{wid}_{uid}")
            ]])
        )


async def mark_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    parts = query.data.split("_")
    wid = int(parts[1])
    uid = int(parts[2])
    mark_paid(wid)

    try:
        await context.bot.send_message(
            uid,
            "🎉 *Your withdrawal has been processed!*\n\n"
            "Your payment has been sent to your bank account.\n"
            "Keep referring to earn more! 💪",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await query.edit_message_text(f"✅ Withdrawal #{wid} marked as paid.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE verified=1")
    total_refs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
    pending_count = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM withdrawals WHERE status='paid'")
    total_paid = c.fetchone()[0] or 0
    conn.close()

    await update.message.reply_text(
        f"📊 *Referral Pay Statistics*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔗 Verified Referrals: {total_refs}\n"
        f"⏳ Pending Withdrawals: {pending_count}\n"
        f"💰 Total Paid Out: ₦{total_paid:,}",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    init_db()
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    withdraw_conv = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_name)],
            ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_account_number)],
            ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_account_name)],
            CONFIRM: [CallbackQueryHandler(confirm_withdraw, pattern="^(confirm|cancel)_withdraw$")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("pending", pending))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(withdraw_conv)
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(mark_paid_callback, pattern="^paid_"))

    print("✅ Referral Pay Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
