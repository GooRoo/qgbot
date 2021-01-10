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
    level='INFO',
    colorize=True,
    backtrace=True,
    diagnose=True)


class QGBot(object):
    def __init__(self, token=None):
        self._initDB()

        self.updater = Updater(token, use_context=True)
        self.updater.bot.set_my_commands([
            ('/start', 'Show welcome information'),
            ('/help', 'Show the info on bot usage'),
            ('/settings', 'Open settings menu'),
            ('/cancel', 'Cancel the current operation')
        ])
        self.dispatcher = self.updater.dispatcher

        self._register_handlers()

    def _register_handlers(self):
        echo_user_handler = MessageHandler(Filters.forwarded, self.echo_user_id)
        self.dispatcher.add_handler(echo_user_handler)

        # basic commands
        self.dispatcher.add_handler(CommandHandler('start', self.on_start))
        self.dispatcher.add_handler(CommandHandler('help', self.on_help))

        # settings menu
        self.settings = SettingsConversation('settings')
        self.settings.register(self.dispatcher)

        # inline mode
        self.dispatcher.add_handler(InlineQueryHandler(self.on_inline_query))
        self.dispatcher.add_handler(ChosenInlineResultHandler(self.on_chosen_inline_query))

        # voting buttons
        self.dispatcher.add_handler(CallbackQueryHandler(self.on_vote))

        # error handling
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
            '/help — This message\n'
        )
        if is_admin:
            reply += '\n*Administration:*\n'
            reply += '/settings — Various settings for admins'

        update.message.reply_markdown(reply)

    @handler(admin_only=True)
    def on_settings(self, update: Update, context: CallbackContext):
        settings
        update.message.reply_markdown('Settings')

        return self.SettingsStates.CHOICE

    def on_inline_query(self, update: Update, context: CallbackContext):
        query = update.inline_query.query

        if len(query) == 0:
            return

        keyboard = [[
            InlineKeyboardButton('✅', callback_data='up'),
            InlineKeyboardButton('❌', callback_data='down')
        ]]

        results = [
            InlineQueryResultArticle(
                id=tag,
                title=name,
                description=f'#{tag}_request',
                input_message_content=InputTextMessageContent(
                    f'#{tag}_request {query}',

                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            for tag, name in self.db.get_categories().items()
        ]

        update.inline_query.answer(results)

    def on_chosen_inline_query(self, update: Update, context: CallbackContext):
        res = update.chosen_inline_result
        logger.info('User {} has submitted a new request with id "{}" under "{}" category. The message: {}',
                    res.from_user, res.inline_message_id, res.result_id, res.query)
        self.db.add_request(message_id=res.inline_message_id, user=res.from_user, category_tag=res.result_id, text=res.query)

    def on_vote(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if query.data == 'up':
            query.answer('+2')
        else:
            query.answer('-2')
        logger.warning('inline message id {}', query.inline_message_id)
