import re

from telegram import MessageEntity, ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext, Dispatcher, MessageHandler
from telegram.ext.commandhandler import CommandHandler
from telegram.ext.filters import Filters
from telegram.forcereply import ForceReply

from qg.logger import logger
from qg.utils.helpers import escape_md, mention_md

from .decorators import handler
from .handlers import CancellableConversationBuilder
from .menu import (BackButton, CancelButton, Menu, MenuConversationItem,
                   MenuHandler, MenuItem, MenuItemProxy)


class AddAdminConversation(CancellableConversationBuilder):
    '''Dialog for adding new admin'''

    def __init__(self, bot):
        self.bot = bot
        self.db = self.bot.db

    def build_entry_handlers(self):
        return [
            MessageHandler(Filters.contact, self.add_from_contact),
            MessageHandler(
                Filters.entity(MessageEntity.MENTION) | Filters.entity(MessageEntity.TEXT_MENTION),
                self.add_from_mention
            )
        ]

    def welcome(self):
        return escape_md('Choose the person by sending the contact or mentioning. Otherwise, /cancel the operation.')

    @logger.catch
    @handler(admin_only=True)
    def add_from_contact(self, update: Update, context: CallbackContext):
        '''
        Extract a user information from the sent contact and add as a bot's admin.
        This is a less preferable method of specifying an admin as it doesn't give a username.
        '''
        contact = update.message.contact

        # I couldn't reproduce this use-case, but according to the API it's possible
        if contact.user_id is None:
            update.message.reply_markdown_v2(
                escape_md(
                    'Sorry, the contact you’ve sent doesn’t appear to be a Telegram user. Stopping the operation.'
                ),
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            with self.db.session():
                self.db.add_user(
                    id=contact.user_id,
                    first_name=contact.first_name,
                    last_name=contact.last_name,
                    is_admin=True
                )
            fullname = contact.first_name
            if (lm := contact.last_name) is not None and lm != '':
                fullname += f' {lm}'
            update.message.reply_markdown_v2(
                mention_md(contact.user_id, fullname) + escape_md(' is now admin of myself.'),
                reply_markup=ReplyKeyboardRemove()
            )

        return self.States.STOPPING

    @logger.catch
    @handler(admin_only=True)
    def add_from_mention(self, update: Update, context: CallbackContext):
        '''
        Extract a user information from the mention and add as a bot's admin.
        This method is preferable although it doesn't always give a chance to get the user's id. I couldn't compe up
        with some reasonable solution.
        '''

        # TODO: Refactor this and other similar functions to use exceptions instead of a bunch of `if`s
        message = update.message
        assert len(message.entities) > 0

        # if we are in this function, there is at least one mention in the entities,
        # so it's safe to index the first one
        mention = [
            e for e in message.entities
                if e.type in [MessageEntity.MENTION, MessageEntity.TEXT_MENTION]
        ][0]

        with self.db.session():
            if (u := mention.user) is not None:
                user_id = u.id
                user_name = u.username
                self.db.add_user(u.id, u.first_name, u.last_name, u.username, is_admin=True)
            else:
                user_name = message.parse_entity(mention)[1:]
                user = self.db.find_user_by_username(user_name)
                if user is None:
                    logger.error(f'Can‘t get an id for a user with username "{user_name}"')
                    message.reply_markdown_v2(
                        escape_md('Sorry, can’t determine the user’s id.'),
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return self.States.STOPPING

                else:
                    user_id = user.id
                    self.db.add_user(user_id, first_name=user_name, username=user_name, is_admin=True)

        message.reply_markdown_v2(
            mention_md(user_id, f'@{user_name}') + escape_md(' is now admin of myself.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.STOPPING


class AddCategoryConversation(CancellableConversationBuilder):
    '''Dialog for adding new category'''

    def __init__(self, bot):
        self.bot = bot
        self.db = self.bot.db
        self.max_error_count = 3

    def build_entry_handlers(self):
        return [
            MessageHandler(Filters.entity(MessageEntity.HASHTAG), self.remember_tag),
            MessageHandler(Filters.all & ~Filters.entity(MessageEntity.HASHTAG) & ~Filters.command, self.no_tag)
        ]

    def build_additional_states(self):
        return {
            'NAME': [
                CommandHandler('skip', self.skip_name),
                MessageHandler(Filters.text & ~Filters.command, self.remember_name)
            ],
            'URL': [
                CommandHandler('skip', self.skip_url),
                MessageHandler(
                    Filters.entity(MessageEntity.URL) | Filters.entity(MessageEntity.TEXT_LINK),
                    self.remember_url
                )
            ]
        }

    def welcome(self):
        return escape_md(
            'Please, send the #hastag for the new category. '
            'You can always stop the process with the /cancel command.'
        )

    @logger.catch
    @handler(admin_only=True)
    def remember_tag(self, update: Update, context: CallbackContext):
        message = update.message
        hashtag = [
            e for e in message.entities
                if e.type == MessageEntity.HASHTAG
        ][0]

        self.category_tag = message.parse_entity(hashtag)[1:]

        message.reply_markdown_v2(
            escape_md(
                'Okay, now send me the name of the new category. '
                'You can /skip it and I’ll use the hashtag instead.'
            ),
            reply_markup=ForceReply(selective=True)
        )
        return 'NAME'

    @logger.catch
    @handler(admin_only=True)
    def no_tag(self, update: Update, context: CallbackContext):
        self.max_error_count -= 1
        if self.max_error_count <= 0:
            update.message.reply_markdown_v2(
                escape_md('Okay, whatever. I’m aborting the operation.')
            )
            return self.States.STOPPING
        else:
            update.message.reply_markdown_v2(
                escape_md('I need a #hashtag. Try again.'),
                reply_markup=ForceReply(selective=True)
            )
            return

    @logger.catch
    @handler(admin_only=True)
    def skip_name(self, update: Update, context: CallbackContext):
        self.category_name = self.category_tag.capitalize()
        update.message.reply_markdown_v2(
            escape_md(
                f'Fine, I’ll use “{self.category_name}” as the name. '
                'Now send me URL of the corresponding playlist or choose to /skip.'
            ),
            reply_markup=ForceReply(selective=True)
        )
        return 'URL'

    @logger.catch
    @handler(admin_only=True)
    def remember_name(self, update: Update, context: CallbackContext):
        self.category_name = update.message.text
        update.message.reply_markdown_v2(
            escape_md('Now send me URL of the corresponding playlist or choose to /skip.'),
            reply_markup=ForceReply(selective=True)
        )
        return 'URL'

    @logger.catch
    @handler(admin_only=True)
    def skip_url(self, update: Update, context: CallbackContext):
        self.category_url = ''
        update.message.reply_markdown_v2(
            escape_md('A category with no playlist URL? Does it make any sense? Whatever…')
        )
        return self.save_category(update, context)

    @logger.catch
    @handler(admin_only=True)
    def remember_url(self, update: Update, context: CallbackContext):
        message = update.message
        hyperlink = [
            e for e in message.entities
                if e.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]
        ][0]
        self.category_url = hyperlink.url if hyperlink.url is not None else message.parse_entity(hyperlink)
        return self.save_category(update, context)

    @logger.catch
    @handler(admin_only=True)
    def save_category(self, update: Update, context: CallbackContext):
        with self.db.session():
            self.db.add_category(
                self.category_tag,
                self.category_name,
                self.category_url
            )
        update.message.reply_markdown_v2(
            escape_md('Thanks. The new category has been added. Now you can use it in the inline mode.')
        )
        return self.States.STOPPING


class SettingsMenu(object):
    '''Hierarchical menu which responds to /settings'''

    def __init__(self, bot, dispatcher: Dispatcher):
        self.bot = bot
        self.db = self.bot.db
        self.menu = MenuHandler(self.build_menu(), dispatcher=dispatcher)

    def build_menu(self):
        menu = Menu('settings', 'What are you interested in?',
        [
            [
                Menu('Categories', 'Ah, categories! Okay, what’s next?',
                [
                    [ MenuItem('Show all categories', self.show_categories) ],
                    [
                        MenuConversationItem('Add category… ', AddCategoryConversation(self.bot)),
                        Menu('Remove category', 'Which category do you want to remove?',
                        [
                            MenuItemProxy(self.populate_categories),
                            [ CancelButton(), BackButton() ]
                        ])
                    ],
                    [ CancelButton(), BackButton() ]
                ]),
                Menu('Admins', 'And what do you want to do here?',
                [
                    [
                        MenuConversationItem('Promote to admin…', AddAdminConversation(self.bot)),
                        Menu('Demote admin', 'Choose the victim!',
                        [
                            MenuItemProxy(self.populate_admins),
                            [ CancelButton(), BackButton() ]
                        ])
                    ],
                    [ CancelButton(), BackButton() ]
                ])
            ],
            [ CancelButton() ]
        ])
        return menu

    @logger.catch
    def show_categories(self, update: Update, context: CallbackContext):
        '''Print list of categories with the hashtag and URL'''
        response = ''
        with self.db.session():
            for tag, (name, url) in self.db.get_categories().items():
                response += f'{escape_md(f"#{tag}")}: [{escape_md(name)}]({url})\n'
        update.message.reply_markdown_v2(
            response,
            reply_markup=ReplyKeyboardRemove(),
            disable_web_page_preview=True
        )
        return Menu.States.STOPPING

    @logger.catch
    @handler(admin_only=True)
    def remove_category(self, update: Update, context: CallbackContext):
        '''
        Remove the chosen category from the database. All previous links to it are replaced with NULL.
        '''
        first_hashtag = update.message.entities[0]
        if first_hashtag.type != MessageEntity.HASHTAG:
            logger.error(f'Expected hashtag, but got {first_hashtag.type}')
            return
        hashtag = update.message.parse_entity(first_hashtag)
        logger.debug(f'Parsed hashtag: {hashtag}')
        tag = hashtag[1:]

        with self.db.session():
            self.db.remove_category(tag)

        update.message.reply_markdown_v2(
            escape_md(f'Removed {hashtag}.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING

    def populate_categories(self):
        return [
            MenuItem(f'#{tag}', self.remove_category, accept_all=True)
            for tag in self.db.get_categories()
        ]

    @logger.catch
    @handler(admin_only=True)
    def remove_admin(self, update: Update, context: CallbackContext):
        if (message := update.message).entities and (mention := message.entities[0]).type == MessageEntity.MENTION:
            user_name = message.parse_entity(mention)[1:]
            with self.db.session():
                user = self.db.find_user_by_username(user_name)
                if user is None:
                    logger.error(f'User with username "{user_name}" hasn’t been found though it should be there')
                    message.reply_markdown_v2(
                        escape_md('Some weird error happened. Tell admins, please.'),
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return Menu.States.STOPPING

                user_id = user.id
            logger.debug(f'Parsed user "{user_name}" from mention: id={user_id}')
        else:
            match = re.match(r'(\d+) - (.+)', message.text)
            user_id = int(match[1])
            user_name = match[2]
            logger.debug(f'Parsed user "{user_name}" from text: id={user_id}')

        with self.db.session():
            self.db.remove_admin(user_id)

        message.reply_markdown_v2(
            mention_md(user_id, user_name) + escape_md(' is not admin anymore.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING

    def populate_admins(self):
        return [
            MenuItem(user.username_or_id_and_name(), self.remove_admin, accept_all=True)
            for user in self.db.get_admins()
        ]
