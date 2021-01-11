import re

from telegram import MessageEntity, ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext, Dispatcher, MessageHandler
from telegram.ext.filters import Filters

from qg.logger import logger
from qg.utils.helpers import escape_md, mention_md

from .menu import BackButton, CancelButton, Menu, MenuConversationItem, MenuHandler, MenuItem, MenuItemProxy
from .handlers import AddingConversationHandler


class AddAdminConversation(AddingConversationHandler):
    def __init__(self, bot):
        self.bot = bot

    def build_choice_handlers(self):
        return [
            MessageHandler(Filters.contact, self.add_from_contact),
            MessageHandler(
                Filters.entity(MessageEntity.MENTION) | Filters.entity(MessageEntity.TEXT_MENTION),
                self.add_from_mention
            )
        ]

    def welcome(self):
        return escape_md('Choose the person by sending the contact or mentioning. Otherwise, /cancel the operation.')

    def add_from_contact(self, update: Update, context: CallbackContext):
        logger.critical('add_from_contact')
        contact = update.message.contact

        if contact.user_id is None:
            update.message.reply_markdown_v2(
                escape_md(
                    'Sorry, the contact you’ve sent doesn’t appear to be a Telegram user. Stopping the operation.'
                ),
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            with self.bot.db.session():
                self.bot.db.add_user(
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

    def add_from_mention(self, update: Update, context: CallbackContext):
        message = update.message
        assert len(message.entities) > 0

        mention = [
            e for e in message.entities
                if e.type in [MessageEntity.MENTION, MessageEntity.TEXT_MENTION
        ]][0]

        with self.bot.db.session():
            if (u := mention.user) is not None:
                user_id = u.id
                user_name = u.username
                self.bot.db.add_user(u.id, u.first_name, u.last_name, u.username, is_admin=True)
            else:
                user_name = update.message.parse_entity(mention)[1:]
                user = self.bot.db.find_user_by_username(user_name)
                if user is None:
                    logger.critical(f'Can‘t get an id for a user with username "{user_name}"')
                    update.message.reply_markdown_v2(
                        escape_md('Sorry, can’t determine the user’s id.'),
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return self.States.STOPPING

                else:
                    user_id = user.id
                    self.bot.db.add_user(user_id, first_name=user_name, username=user_name, is_admin=True)

        update.message.reply_markdown_v2(
            mention_md(user_id, f'@{user_name}') + escape_md(' is now admin of myself.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.STOPPING


class SettingsMenu(object):
    def __init__(self, bot, dispatcher: Dispatcher):
        self.bot = bot
        self.menu = MenuHandler(self.build_menu(), dispatcher=dispatcher)

    def build_menu(self):
        menu = Menu('settings', 'What are you interested in?',
        [
            [
                Menu('Categories', 'Ah, categories! Okay, what’s next?',
                [
                    [ MenuItem('Show all categories', self.show_categories) ],
                    [
                        MenuItem('Add category… ', None),
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

    def show_categories(self, update: Update, context: CallbackContext):
        response = ''
        for tag, (name, url) in self.bot.db.get_categories().items():
            response += f'{escape_md(f"#{tag}")}: [{escape_md(name)}]({url})\n'
        update.message.reply_markdown_v2(
            response,
            reply_markup=ReplyKeyboardRemove(),
            disable_web_page_preview=True
        )
        return Menu.States.STOPPING

    def add_category(self):
        pass

    def remove_category(self, update: Update, context: CallbackContext):
        first_hashtag = update.message.entities[0]
        if first_hashtag.type != MessageEntity.HASHTAG:
            logger.error(f'Expected hashtag, but got {first_hashtag.type}')
            return
        hashtag = update.message.parse_entity(first_hashtag)
        logger.debug(f'Parsed hashtag: {hashtag}')
        tag = hashtag[1:]

        with self.bot.db.session():
            self.bot.db.remove_category(tag)

        update.message.reply_markdown_v2(
            escape_md(f'Removed {hashtag}.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING

    def populate_categories(self):
        return [
            MenuItem(f'#{tag}', self.remove_category, accept_all=True)
            for tag in self.bot.db.get_categories()
        ]

    def remove_admin(self, update: Update, context: CallbackContext):
        if len(update.message.entities) > 0 and (mention := update.message.entities[0]).type == MessageEntity.MENTION:
            user_name = update.message.parse_entity(mention)[1:]
            with self.bot.db.session():
                user = self.bot.db.find_user_by_username(user_name)
                if user is None:
                    logger.critical(f'User with username "{user_name}" hasn’t been found though it should be there')
                    update.message.reply_markdown_v2(
                        escape_md('Some weird error happened. Tell admins, please.'),
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return Menu.States.STOPPING

                user_id = user.id
            logger.debug(f'Parsed user "{user_name}" from mention: id={user_id}')
        else:
            match = re.match(r'(\d+) - (.+)', update.message.text)
            user_id = int(match[1])
            user_name = match[2]
            logger.debug(f'Parsed user "{user_name}" from text: id={user_id}')

        with self.bot.db.session():
            self.bot.db.remove_admin(user_id)

        update.message.reply_markdown_v2(
            mention_md(user_id, user_name) + escape_md(' is not admin anymore.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING

    def populate_admins(self):
        return [
            MenuItem(user.username_or_id_and_name(), self.remove_admin, accept_all=True)
            for user in self.bot.db.get_admins()
        ]
