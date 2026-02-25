import os
import threading
from flask import Flask

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# ENV (Render -> Environment)
# =========================
TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_CHAT_ID_RAW = os.getenv("ADMIN_GROUP_CHAT_ID")

if not TOKEN:
    raise RuntimeError("TOKEN is missing. Add it in Render Environment variables as TOKEN.")
if not ADMIN_GROUP_CHAT_ID_RAW:
    raise RuntimeError("ADMIN_GROUP_CHAT_ID is missing. Add it in Render Environment variables as ADMIN_GROUP_CHAT_ID.")

ADMIN_GROUP_CHAT_ID = int(ADMIN_GROUP_CHAT_ID_RAW)

# =========================
# BOT STATES
# =========================
NAME, COMMENT = range(2)

# =========================
# TEXTS
# =========================
TEXT = {
    "ru": {
        "lang_title": "Выберите язык / Tilni tanlang / Choose language",
        "menu": "Продолжаем!",
        "apply": "📝 Оставить заявку",
        "change_lang": "🌐 Язык",
        "ask_name": "Как вас зовут?",
        "ask_comment": "Оставьте ваш запрос или проблему!",
        "thanks": "✅ Спасибо! Заявка отправлена.",
        "lead": "📩 Новая заявка",
    },
    "uz": {
        "lang_title": "🌐 Tilni tanlang",
        "menu": "Davom ettiramiz!",
        "apply": "📝 Ariza qoldirish",
        "change_lang": "🌐 Til",
        "ask_name": "Ismingiz?",
        "ask_comment": "So‘rov yoki muammoingizni qoldiring!",
        "thanks": "✅ Rahmat! Ariza yuborildi.",
        "lead": "📩 Yangi ariza",
    },
    "en": {
        "lang_title": "🌐 Choose language",
        "menu": "Let’s continue!",
        "apply": "📝 Submit request",
        "change_lang": "🌐 Language",
        "ask_name": "Your name?",
        "ask_comment": "Write your request or problem!",
        "thanks": "✅ Thank you! Request sent.",
        "lead": "📩 New request",
    },
}


def t(lang, key):
    return TEXT.get(lang, TEXT["ru"]).get(key, key)


def language_bar(selected=None):
    def label(code, text):
        return f"✅ {text}" if selected == code else text

    keyboard = [[
        InlineKeyboardButton(label("ru", "🇷🇺 Русский"), callback_data="lang_ru"),
        InlineKeyboardButton(label("uz", "🇺🇿 O‘zbek"), callback_data="lang_uz"),
        InlineKeyboardButton(label("en", "🇬🇧 English"), callback_data="lang_en"),
    ]]
    return InlineKeyboardMarkup(keyboard)


def main_menu(lang):
    return ReplyKeyboardMarkup(
        [[t(lang, "apply")], [t(lang, "change_lang")]],
        resize_keyboard=True
    )


# =========================
# BOT HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("lang", "ru")
    lang = context.user_data["lang"]
    await update.message.reply_text(
        t(lang, "lang_title"),
        reply_markup=language_bar(lang),
    )


async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang

    await query.edit_message_text(
        t(lang, "lang_title"),
        reply_markup=language_bar(lang),
    )

    await query.message.reply_text(
        t(lang, "menu"),
        reply_markup=main_menu(lang),
    )


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    text = (update.message.text or "").strip()

    if text == t(lang, "change_lang"):
        await update.message.reply_text(
            t(lang, "lang_title"),
            reply_markup=language_bar(lang),
        )
        return ConversationHandler.END

    if text == t(lang, "apply"):
        await update.message.reply_text(
            t(lang, "ask_name"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return NAME

    return ConversationHandler.END


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = (update.message.text or "").strip()
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(t(lang, "ask_comment"))
    return COMMENT


async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    name = context.user_data.get("name", "").strip()
    comment = (update.message.text or "").strip()

    user = update.effective_user
    username = f"@{user.username}" if user.username else "no_username"

    admin_text = (
        f"{t(lang,'lead')}\n\n"
        f"👤 Name: {name}\n"
        f"💬 Comment: {comment}\n"
        f"🌐 Lang: {lang.upper()}\n"
        f"👤 From: {username} (id: {user.id})"
    )

    await context.bot.send_message(chat_id=ADMIN_GROUP_CHAT_ID, text=admin_text)

    await update.message.reply_text(
        t(lang, "thanks"),
        reply_markup=main_menu(lang),
    )

    context.user_data.pop("name", None)
    return ConversationHandler.END


# =========================
# RUN BOT
# =========================
def run_bot():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(change_language, pattern="^lang_"))

    form_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment)],
        },
        fallbacks=[],
    )
    app.add_handler(form_handler)

    print("BOT STARTING...")
    app.run_polling()


# =========================
# WEB SERVER FOR RENDER
# =========================
def run_web():
    web = Flask(__name__)

    @web.get("/")
    def home():
        return "OK"

    port = int(os.environ.get("PORT", "10000"))
    web.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    # 1️⃣ сначала запускаем бота в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()

    # 2️⃣ потом запускаем веб-сервер (главный поток)
    run_web()
