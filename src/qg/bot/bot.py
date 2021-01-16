import functools
import itertools
import re
import sys
from pathlib import Path

from dynaconf import settings
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      InlineQueryResultArticle, InputTextMessageContent,
                      LabeledPrice, ParseMode, Update)
from telegram.error import Unauthorized
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          ChosenInlineResultHandler, CommandHandler, Filters,
                          InlineQueryHandler, MessageHandler,
                          PreCheckoutQueryHandler, Updater)
from telegram.utils.helpers import create_deep_linked_url

from qg.db import DB
from qg.logger import logger
from qg.utils.helpers import escape_md, mention_md

from .decorators import handler
from .settings import SettingsMenu
from .stats import StatisticsMenu

logger.remove()
logger.add(settings.LOGGER.filename, rotation='10 MB', compression='zip')
logger.add(
    sys.stderr,
    level=settings.LOGGER.console_level,
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
        # custom entry points (have to be registered before regular /start)
        invoice_filter = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', re.I)
        self.dispatcher.add_handler(
            CommandHandler('start', self.on_start_with_invoice, Filters.regex(invoice_filter), pass_args=True)
        )
        self.dispatcher.add_handler(
            CommandHandler('start', self.on_start_to_donate, Filters.regex(r'donate-(\d+)'), pass_args=True)
        )

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
        self.dispatcher.add_handler(CallbackQueryHandler(self.on_invoice_request, pattern=r'^((stripe|liqpay) (\d+)|cancel)$'))
        self.dispatcher.add_handler(PreCheckoutQueryHandler(self.on_pre_checkout))
        self.dispatcher.add_handler(MessageHandler(Filters.successful_payment, self.on_paid))
        self.dispatcher.add_handler(CommandHandler('donate_stats', self.on_donate_stats))

        # inline mode
        self.dispatcher.add_handler(InlineQueryHandler(self.on_inline_query))
        self.dispatcher.add_handler(ChosenInlineResultHandler(self.on_chosen_inline_query))

        # voting buttons
        self.dispatcher.add_handler(CallbackQueryHandler(self.on_vote, pattern=r'^(up|down)$'))

        # error handling
        self.dispatcher.add_error_handler(self.error)

    def run(self, websocket=True):
        if websocket:
            logger.info('Opening a websocket…')
            self.updater.start_webhook(
                listen='0.0.0.0',
                port=settings.BOT.ws_port,
                url_path=settings.BOT.token
            )
            self.updater.bot.set_webhook(
                f'{settings.BOT.base_url}/{settings.BOT.token}'
            )
        else:
            logger.info('Starting polling…')
            self.updater.start_polling()
        self.updater.idle()

    def _initDB(self):
        if uri := settings.DB.get('FULL_URI', None):
            self.db = DB(full_uri=uri, echo=True)
        else:
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
        '''Fallback handler to log the errors caused by Updates.'''
        logger.error(f'Update: "{update}" caused an error: "{context.error}"')

    @logger.catch
    def on_start(self, update: Update, context: CallbackContext):
        '''
        /start command. Shows general information
        '''
        update.message.reply_markdown_v2(
            escape_md(
                'Welcome! I’m the “quality gate” bot for voting. '
                'Think of me as a kind of @like, but with adjustable categories.\n\n'
                'Check /help for more information.'
            )
        )

    @logger.catch
    @handler
    def on_help(self, update: Update, context: CallbackContext, is_admin):
        '''
        /help command. Shows available commands, etc.
        '''
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

    @functools.lru_cache
    def _inline_keyboard(self, up=0, down=0):
        '''
        Build inline buttons with vote counters.
        '''
        up_title = f'✅ {up}' if up > 0 else '✅'
        down_title = f'❌ {down}' if down > 0 else '❌'

        keyboard = [[
            InlineKeyboardButton(up_title, callback_data='up'),
            InlineKeyboardButton(down_title, callback_data='down')
        ]]
        return InlineKeyboardMarkup(keyboard)

    @logger.catch
    def on_inline_query(self, update: Update, context: CallbackContext):
        '''
        Suggest categories for the vote request.
        '''
        query = update.inline_query.query

        if not query:
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
        update.inline_query.answer(results, cache_time=0)

    @logger.catch
    def on_chosen_inline_query(self, update: Update, context: CallbackContext):
        '''
        Store the vote request to the database.
        '''
        res = update.chosen_inline_result
        logger.info(f'User {res.from_user} has submitted a new request with id "{res.inline_message_id}" '
                    f'under "{res.result_id}" category. The message: {res.query}')
        with self.db.session():
            self.db.add_request(request_id=res.inline_message_id, user=res.from_user, category_tag=res.result_id, text=res.query)

    @logger.catch
    def on_vote(self, update: Update, context: CallbackContext):
        '''
        Handle press on a vote button (inline message button).
        '''

        def group_votes(votes):
            '''Partition all votes by the actual vote and collect the list of voters' usernames'''
            all_votes = {}
            for v, vs in itertools.groupby(votes, key=lambda v: v.upvote):
                all_votes[v] = [v.user.mention_md() for v in vs]
            logger.debug(f'all_votes: {all_votes}')

            upvotes = all_votes.get(True, [])
            downvotes = all_votes.get(False, [])

            logger.info(f'{upvotes = }, {downvotes = }')

            return upvotes, downvotes

        def prepare_votes_string(upvotes: list[str], downvotes: list[str]) -> str:
            '''Generate the string with the list of voters (to be appended to the message)'''
            votes_string = ''
            if upvotes:
                votes_string += f'✅: {", ".join(upvotes)}\n'
            if downvotes:
                votes_string += f'❌: {", ".join(downvotes)}\n'
            if votes_string:
                votes_string = '\n\n*Votes:*\n' + votes_string
            return votes_string

        query = update.callback_query
        message_id = query.inline_message_id
        user = query.from_user
        is_upvote = query.data == 'up'

        logger.debug(f'Inline message id {message_id}')

        with self.db.session():
            r = self.db.get_request(message_id)
            if r is None:
                logger.error(f'A request with id "{message_id}" is not found although it should exist.')
                return

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
                escape_md(f'#{r.category_tag}_request {r.text}') + votes_string,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=self._inline_keyboard(up=len(upvotes), down=len(downvotes))
            )

    @logger.catch
    def on_terms(self, update: Update, context: CallbackContext):
        '''
        /terms command. Sends the Terms & Conditions.
        '''
        with open(Path('../img/marcus.png'), 'rb') as f:
            update.message.reply_photo(f, caption='NO REFUNDS!')

    @logger.catch
    def on_donate(self, update: Update, context: CallbackContext):
        '''
        /donate command. Shows the price list with inline buttons.
        '''
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
                    InlineKeyboardButton('10€', callback_data='stripe 10'),
                    InlineKeyboardButton('25€', callback_data='stripe 25'),
                    InlineKeyboardButton('50€', callback_data='stripe 50'),
                    InlineKeyboardButton('100€', callback_data='stripe 100')
                ],
                [InlineKeyboardButton('⭐️ 500€ ⭐️', callback_data='stripe 500')],
                [InlineKeyboardButton('Cancel', callback_data='cancel')]
            ])
        )

    @functools.lru_cache(maxsize=5)
    def generate_prices(self, price):
        '''
        Calculate discount and make a list of `LabeledPrice`s
        '''
        discount = -int(price * 0.1) if price == 500 else 0
        total = price + discount

        prices = [LabeledPrice('Donation', price * 100)]
        if discount != 0:
            prices.append(LabeledPrice('Discount', discount * 100))

        return prices, total

    @functools.lru_cache(maxsize=5)
    def generate_invoice(self, price, currency):
        '''
        Create invoice template without any payload.
        '''
        provider_token = settings.PAYMENT.stripe_token
        prices, total = self.generate_prices(price)
        return {
            'title': 'A gift for the bot’s author',
            'description': 'Your support is appreciated!',
            'provider_token': provider_token,
            'currency': currency,
            'prices': prices,
            'start_parameter': f'donate-{price}'
        }, total

    @logger.catch
    def on_invoice_request(self, update: Update, context: CallbackContext):
        '''
        Create invoice after clicking the inline button in the price list.
        The most common case for donation.
        '''
        query = update.callback_query

        if (data := query.data) == 'cancel':
            query.delete_message()
            return

        provider, price = data.split(' ')

        currency = 'EUR'
        try:
            price = int(price)
        except ValueError:
            query.delete_message()
            return

        invoice_template, total = self.generate_invoice(price, currency)

        user = update.effective_user
        chat = update.effective_chat
        with self.db.session():
            invoice_id = self.db.create_invoice(
                user=user,
                price=price,
                total=total,
                currency=currency
            )

        try:
            user.send_invoice(
                payload=invoice_id,
                **invoice_template
            )
        except Unauthorized:  # User has never communicated to the bot directly
            query.answer(
                'Check you private chat!',
                url=create_deep_linked_url(context.bot.get_me().username, invoice_id)
            )
        else:
            logger.debug(f'{chat.id = }')
            logger.debug(f'{user.id = }')
            if chat.id == user.id:
                query.answer('The invoice is created!')
            else:
                query.answer('I’ve dropped you an invoice into the private chat.', show_alert=True)

    @logger.catch
    def on_start_with_invoice(self, update: Update, context: CallbackContext):
        '''
        /start command with deep-link (Invoice ID).
        This situation occurs when a user hasn't allowed the bot to send messages in private chat yet,
        but triggered the invoice creation in some group chat.
        '''
        if not context.args:
            logger.warning('Got no payload while it was expected')
            return

        invoice_id = context.args[0]
        with self.db.session():
            invoice = self.db.get_invoice(invoice_id)

        if invoice is None:
            logger.error(f'The invoice "{invoice_id}" does not exist in the database!')
            return

        if invoice.user_id != update.effective_user.id:
            logger.error(
                f'The user does not match. The invoice was created for {invoice.user.username_or_name()} while '
                f'while the current chat is with {update.effective_user.name}.'
            )
            return

        invoice_template, total = self.generate_invoice(int(invoice.price), invoice.currency)
        update.effective_user.send_invoice(
            payload=invoice_id,
            **invoice_template
        )

    @logger.catch
    def on_start_to_donate(self, update: Update, context: CallbackContext):
        '''
        /start command with deep-link (donation amount).
        The rarest situation which occurs when someone has paid and then forwards the receipt to someone else.
        For that person the receipt will look like an invoice. If that user then comes to the bot's private chat.
        this method will be called.
        '''
        if not context.args:
            logger.warning('Got no payload while it was expected')
            return

        logger.debug(f'{context.args = }')

        _, price = context.args[0].split('-')

        currency = 'EUR'
        try:
            price = int(price)
        except ValueError:
            logger.exception(f'{price} can not be cast to int')
            return

        invoice_template, total = self.generate_invoice(price, currency)

        user = update.effective_user
        with self.db.session():
            invoice_id = self.db.create_invoice(
                user=user,
                price=price,
                total=total,
                currency=currency
            )

        user.send_message(
            'Welcome! I’m the “quality gate” bot for voting. '
            'Think of me as a kind of @like, but with adjustable categories.\n\n'
            'It seems that someone has shown you a way to donate me. Although I appreciate it a lot, '
            'I still recommend to try me out first. Check /help for more information.'
        )
        user.send_message('Here is your invoice if you change your mind:')
        user.send_invoice(
            payload=invoice_id,
            **invoice_template
        )

    @logger.catch
    def on_pre_checkout(self, update: Update, context: CallbackContext):
        '''
        Process the request from the payment provider.
        '''
        query = update.pre_checkout_query
        invoice_id = query.invoice_payload
        with self.db.session():
            invoice = self.db.get_invoice(invoice_id)
        if invoice and not invoice.is_paid():
            query.answer(ok=True)
        else:
            logger.error(f'Got pre-checkout on non-existing invoice: {invoice_id}')
            query.answer(ok=False, error_message='This invoice does not exist or was paid already')

    @logger.catch
    def on_paid(self, update: Update, context: CallbackContext):
        '''
        The invoice is fulfilled. Need to store the data.
        '''
        payment = update.message.successful_payment
        with self.db.session():
            self.db.update_invoice(
                invoice_id=payment.invoice_payload,
                tg_charge_id=payment.telegram_payment_charge_id,
                provider_charge_id=payment.provider_payment_charge_id
            )

        update.message.reply_markdown_v2(
            '*Thanks*\n' +
            escape_md(f'You have successfully donated me {payment.total_amount / 100 :.2f}€')
        )
        context.bot.send_message(
            settings.BOT.owner,
            mention_md(
                update.message.from_user.id,
                update.message.from_user.name
            ) + escape_md(f' has just donated {payment.total_amount / 100 :.2f}€'),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    @logger.catch
    def on_donate_stats(self, update: Update, context: CallbackContext):
        '''
        Print list of people and the donated total
        '''
        response = 'Here are the people who donated the most:\n'
        with self.db.session():
            response += '\n'.join(donators := [
                f'{user.mention_md()} donated *{escape_md(f"{total:.2f}")}€*'
                for user, total in self.db.get_donators()
            ])
        logger.info(f'{donators = }')
        update.message.reply_markdown_v2(response)
