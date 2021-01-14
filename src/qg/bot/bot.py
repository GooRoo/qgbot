import itertools
import sys
from pathlib import Path
from typing import List

from dynaconf import settings
from qg.db import DB
from qg.logger import logger
from qg.utils.helpers import escape_md
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      InlineQueryResultArticle, InputTextMessageContent,
                      LabeledPrice, ParseMode, Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          ChosenInlineResultHandler, CommandHandler, Filters,
                          InlineQueryHandler, MessageHandler,
                          PreCheckoutQueryHandler, Updater)
from telegram.utils.helpers import escape_markdown

from .decorators import handler
from .settings import SettingsMenu
from .stats import StatisticsMenu

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
            ('/stats', 'Show various statistics'),
            ('/settings', 'Open settings menu'),
            ('/donate', 'Gift for author'),
            ('/cancel', 'Cancel the current operation'),
            ('/terms', 'Terms & Conditions')
        ])
        self.dispatcher = self.updater.dispatcher

        self._register_handlers()

    def _register_handlers(self):
        # basic commands
        self.dispatcher.add_handler(CommandHandler('start', self.on_start))
        self.dispatcher.add_handler(CommandHandler('help', self.on_help))

        # settings menu
        self.settings = SettingsMenu(self, self.dispatcher)

        # statistics menu
        self.stats = StatisticsMenu(self, self.dispatcher)

        # donation
        self.dispatcher.add_handler(CommandHandler('donate', self.on_donate))
        self.dispatcher.add_handler(CommandHandler('terms', self.on_terms))
        self.dispatcher.add_handler(CallbackQueryHandler(self.on_donate_amount, pattern=r'^(\d+|cancel)$'))
        self.dispatcher.add_handler(CallbackQueryHandler(self.on_payment_provider, pattern=r'^((stripe|liqpay) (\d+)|cancel)$'))
        self.dispatcher.add_handler(PreCheckoutQueryHandler(self.on_pre_checkout))
        self.dispatcher.add_handler(MessageHandler(Filters.successful_payment, self.on_paid))

        # inline mode
        self.dispatcher.add_handler(InlineQueryHandler(self.on_inline_query))
        self.dispatcher.add_handler(ChosenInlineResultHandler(self.on_chosen_inline_query))

        # voting buttons
        self.dispatcher.add_handler(CallbackQueryHandler(self.on_vote, pattern=r'^(up|down)$'))

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

    def on_start(self, update: Update, context: CallbackContext):
        '''/start command. Shows general information'''
        update.message.reply_markdown_v2(
            escape_md(
                'Welcome! I’m the “quality gate” bot for voting. '
                'Think of me as a kind of @like, but with adjustable categories.\n\n'
                'Check /help for more information.'
            )
        )

    @handler
    def on_help(self, update: Update, context: CallbackContext, is_admin):
        '''/help command. Shows available commands, etc.'''
        reply = escape_md('The main usage is in the inline mode.\n\n')
        reply += (
            '*Available commands:\n*'
            '/start — General information\n'
            '/help — This message\n'
            '/stats — Various statistics on bot’s users\n'
            '/donate — Give the author of this bot some money\n'
        )
        if is_admin:
            reply += '\n*Administration:*\n'
            reply += '/settings — Various settings for admins'

        update.message.reply_markdown_v2(
            reply,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('Try me inline', switch_inline_query_current_chat='')]
            ])
        )

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

    def on_vote(self, update: Update, context: CallbackContext):
        '''Handle press on a vote button (inline message button)'''

        def group_votes(votes):
            '''Partition all votes by the actual vote and collect the list of voters' usernames'''
            all_votes = {}
            for v, vs in itertools.groupby(votes, key=lambda v: v.upvote):
                all_votes[v] = [v.user.mention_md() for v in vs]
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
                votes_string = '\n\n*Votes:*\n' + votes_string
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

    def on_terms(self, update: Update, context: CallbackContext):
        with open(Path('../img/marcus.png'), 'rb') as f:
            update.message.reply_photo(f, caption='NO REFUNDS!')

    def on_donate(self, update: Update, context: CallbackContext):
        response = escape_md(
            'You are willing to donate me for supporting my great job, aren’t you? Awesome!\n\n'
            'Now choose the amount. '
        )
        response += '*Only today:* '
        response += escape_md('choose the ⭐️ option, get -10% discount and receive nothing in return!')
        update.message.reply_markdown_v2(
            response,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('10€', callback_data='10'),
                    InlineKeyboardButton('25€', callback_data='25'),
                    InlineKeyboardButton('50€', callback_data='50'),
                    InlineKeyboardButton('100€', callback_data='100')
                ],
                [InlineKeyboardButton('⭐️ 500€ ⭐️', callback_data='500')],
                [InlineKeyboardButton('Cancel', callback_data='cancel')]
            ])
        )

    def on_donate_amount(self, update: Update, context: CallbackContext):
        query = update.callback_query
        data = query.data

        if data == 'cancel':
            query.delete_message()
            return

        price = data
        price_text = f'~500€~ 450' if price == '500' else price
        query.edit_message_text(
            escape_md('You are willing to donate me for supporting my great job, aren’t you? Awesome!\n\n') +
                f'You will pay {price_text}€' +
                escape_md('. Which payment system would you prefer?'),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('Stripe 🇪🇺', callback_data=f'stripe {price}'),
                    InlineKeyboardButton('LiqPay 🇺🇦', callback_data=f'liqpay {price}'),
                ],
                [InlineKeyboardButton('Cancel', callback_data='cancel')]
            ])
        )

    @logger.catch
    def on_payment_provider(self, update: Update, context: CallbackContext):
        query = update.callback_query

        if query.data == 'cancel':
            query.delete_message()
            return

        provider, price = query.data.split(' ')

        try:
            price = int(price)
            discount = -int(price * 0.1) if price == 500 else 0
            prices = [LabeledPrice('Donation', price * 100)]
            if discount != 0:
                prices.append(LabeledPrice('Discount', discount * 100))
            provider_token = settings.PAYMENT.liqpay_token if provider == 'liqpay' else settings.PAYMENT.stripe_token
            context.bot.send_invoice(
                chat_id=query.from_user.id,
                title='A gift for the bot’s author',
                description='Your support is appreciated!',
                payload=f'{price}',
                start_parameter='donate',
                provider_token=provider_token,
                currency='EUR',
                prices=prices,
                reply_to_message_id=query.message.message_id,
                allow_sending_without_reply=True
            )
            if query.message.chat_id == settings.BOT.id:
                query.answer('The invoice is created!')
            else:
                logger.critical(f'https://t.me/{context.bot.username}')
                query.answer(
                    'The invoice is sent to you in the private chat',
                    show_alert=True,
                    url=f'https://t.me/{context.bot.username}?start=invoice'
                )
            query.delete_message()
        except ValueError:
            query.delete_message()

    def on_pre_checkout(self, update: Update, context: CallbackContext):
        update.pre_checkout_query.answer(ok=True)

    def on_paid(self, update: Update, context: CallbackContext):
        payment = update.message.successful_payment
        update.message.reply_markdown_v2(
            '*Thanks*\n' +
            escape_md(f'You have successfully donated me {payment.total_amount / 100}€')
        )
