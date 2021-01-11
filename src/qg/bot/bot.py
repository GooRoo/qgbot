import itertools
import sys
from dynaconf import settings
from typing import List

from telegram import          \
    InlineKeyboardButton,     \
    InlineKeyboardMarkup,     \
    InlineQueryResultArticle, \
    InputTextMessageContent,  \
    ParseMode,                \
    Update
from telegram.ext import       \
    CallbackContext,           \
    CallbackQueryHandler,      \
    ChosenInlineResultHandler, \
    CommandHandler,            \
    InlineQueryHandler,        \
    MessageHandler,            \
    Updater
from telegram.ext.filters import Filters
from telegram.utils.helpers import escape_markdown

from qg.db import DB
from qg.logger import logger

from .decorators import handler
from .settings import SettingsMenu

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
        self.settings = SettingsMenu(self, self.dispatcher)

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

    def _inline_keyboard(self, up=0, down=0):
        up_title = f'✅ {up}' if up > 0 else '✅'
        down_title = f'❌ {down}' if down > 0 else '❌'

        keyboard = [[
            InlineKeyboardButton(up_title, callback_data='up'),
            InlineKeyboardButton(down_title, callback_data='down')
        ]]
        return InlineKeyboardMarkup(keyboard)

    def on_inline_query(self, update: Update, context: CallbackContext):
        query = update.inline_query.query

        if len(query) == 0:
            return

        with self.db.session():
            results = [
                InlineQueryResultArticle(
                    id=tag,
                    title=name,
                    description=f'#{tag}_request',
                    input_message_content=InputTextMessageContent(f'#{tag}_request {query}'),
                    reply_markup=self._inline_keyboard()
                )
                for tag, (name, _) in self.db.get_categories().items()
            ]
        update.inline_query.answer(results)

    def on_chosen_inline_query(self, update: Update, context: CallbackContext):
        res = update.chosen_inline_result
        logger.info(f'User {res.from_user} has submitted a new request with id "{res.inline_message_id}" '
                    f'under "{res.result_id}" category. The message: {res.query}')
        self.db.add_request(request_id=res.inline_message_id, user=res.from_user, category_tag=res.result_id, text=res.query)

    # @logger.catch
    def on_vote(self, update: Update, context: CallbackContext):
        '''Handle press on a vote button (inline message button)'''

        def group_votes(votes):
            '''Partition all votes by the actual vote and collect the list of voters' usernames'''
            all_votes = {}
            for v, vs in itertools.groupby(votes, key=lambda v: v.upvote):
                all_votes[v] = [v.user.username_or_name() for v in vs]
            logger.debug(f'all_votes: {all_votes}')

            upvotes = all_votes.get(True, [])
            downvotes = all_votes.get(False, [])

            logger.info(f'Upvotes: {upvotes}, downvotes: {downvotes}')

            return upvotes, downvotes

        def prepare_votes_string(upvotes: List[str], downvotes: List[str]) -> str:
            '''Generate the string with the list of voters (to be appended to the message)'''
            votes_string = ''
            if len(upvotes) > 0:
                votes_string += f'✅: {", ".join(upvotes)}\n'
            if len(downvotes) > 0:
                votes_string += f'❌: {", ".join(downvotes)}\n'
            if len(votes_string) > 0:
                votes_string = '\n\n*Votes:*\n' + escape_markdown(votes_string, version=2)
            return votes_string

        query = update.callback_query
        message_id = query.inline_message_id
        user = query.from_user
        is_upvote = query.data == 'up'

        logger.debug(f'Inline message id {message_id}')

        with self.db.session():
            r = self.db.get_request(message_id)

            already_voted = self.db.has_voted(message_id, user, is_upvote)
            if not already_voted:
                self.db.add_vote(r.id, user, is_upvote)
                query.answer('Thanks for voting!')
            else:
                self.db.revoke_vote(r.id, user)
                query.answer('You have taken you voice back.')

            upvotes, downvotes = group_votes(self.db.get_votes(request_id=message_id))
            votes_string = prepare_votes_string(upvotes, downvotes)

            query.edit_message_text(
                escape_markdown(f'#{r.category_tag}_request {r.text}', version=2) + votes_string,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=self._inline_keyboard(up=len(upvotes), down=len(downvotes))
            )
