import sys
from dynaconf import settings
from enum import auto, Enum
from uuid import uuid4

from telegram import          \
    Bot,                      \
    InlineKeyboardButton,     \
    InlineKeyboardMarkup,     \
    InlineQueryResultArticle, \
    InlineQueryResultPhoto,   \
    InputMediaPhoto,          \
    InputTextMessageContent,  \
    MessageEntity,            \
    ParseMode,                \
    Update
from telegram.ext import       \
    CallbackContext,           \
    CallbackQueryHandler,      \
    ChosenInlineResultHandler, \
    CommandHandler,            \
    ConversationHandler,       \
    InlineQueryHandler,        \
    MessageHandler,            \
    Updater
from telegram.ext.filters import Filters
from telegram.utils.helpers import escape_markdown
from qg.bot.settings import SettingsConversation

from qg.logger import logger
from qg.db import DB

from .decorators import handler
# from .handlers import ChoiceHandler

logger.remove()
logger.add(settings.LOGGER.filename, rotation='10 MB', compression='zip')
logger.add(
    sys.stderr,
    level='DEBUG',
    colorize=True,
    backtrace=True,
    diagnose=True)


class QGBot(object):
    def __init__(self, token=None):
        self._initDB()

        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        self._register_handlers()

    def _register_handlers(self):
        echo_user_handler = MessageHandler(Filters.forwarded, self.echo_user_id)
        self.dispatcher.add_handler(echo_user_handler)

        self.dispatcher.add_handler(CommandHandler('start', self.on_start))
        self.dispatcher.add_handler(CommandHandler('help', self.on_help))

        self.settings = SettingsConversation('settings')
        self.settings.register(self.dispatcher)
        # self.dispatcher.add_handler(CommandHandler('settings', self.on_settings))

        # self.dispatcher.add_handler(CallbackQueryHandler(self.button))

        # self.dispatcher.add_handler(InlineQueryHandler(self.inline_query))
        # self.dispatcher.add_handler(ChosenInlineResultHandler(self.chosen_inline_query))

        self.dispatcher.add_error_handler(self.error)

    def run(self, websocket=True):
        if websocket:
            pass
        else:
            self.updater.start_polling()
        self.updater.idle()

    def _initDB(self):
        self.db = DB(
            user=settings.DB.user,
            password=settings.DB.password,
            db=settings.DB.name,
            host=settings.DB.host,
            port=settings.DB.port,
            echo=True
        )
        self.db.create_all(settings.DB.admins, settings.DB.categories)

    def error(self, update, context):
        """Log Errors caused by Updates."""
        logger.error(f'Update: "{update}" caused an error: "{context.error}"')

    def echo_user_id(self, update: Update, context: CallbackContext):
        update.message.reply_text(update.message.forward_from.id)

    @handler
    def on_start(self, update: Update, context: CallbackContext, is_admin):
        '''/start command. Shows general information'''
        update.message.reply_markdown(f'Welcome!!! You are {"not " if not is_admin else ""}admin!')

    @handler
    def on_help(self, update: Update, context: CallbackContext, is_admin):
        '''/help command. Shows available commands, etc.'''
        reply = (
            '*Available commands:\n\n*'
            '/start — General information about this bot\n'
            '/help — This message\n')
        if is_admin:
            reply += '\n*Administration:*\n'
            reply += '/settings — Various settings for admins'

        update.message.reply_markdown(reply)

    @handler(admin_only=True)
    def on_settings(self, update: Update, context: CallbackContext):
        settings
        update.message.reply_markdown('Settings')

        return self.SettingsStates.CHOICE
