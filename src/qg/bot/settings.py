from enum import auto, Enum
from typing import Dict, List

from telegram import Update, KeyboardButton, MessageEntity, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, Dispatcher, Handler, MessageHandler
from telegram.ext.filters import Filters
from telegram.replykeyboardremove import ReplyKeyboardRemove

from qg.bot.handlers import ChoiceHandler

class SettingsConversation(object):
    '''
    Handles /settings command
    '''

    class States(Enum):
        MAIN_MENU = auto()
        ADMINS = auto()
        CATEGORIES = auto()
        CONTACT = auto()

    def __init__(self, command):
        self.command = command

    def register(self, dispatcher: Dispatcher):
        dispatcher.add_handler(self._build_conversation())

    def _build_entries(self) -> List[Handler]:
        return [
            CommandHandler(self.command, self.on_entry)
        ]

    def _build_fallbacks(self) -> List[Handler]:
        return [
            CommandHandler('cancel', self.on_cancel)
        ]

    def _build_states(self) -> Dict[int, Handler]:
        self.main_menu = ChoiceHandler([['Categories', 'Admins']], self.on_main_menu_choice)
        self.admins_menu = ChoiceHandler([['Add admin…', 'Remove admin…']], self.on_add_remove_admin)
        self.categories_menu = ChoiceHandler([['Add category…', 'Remove category…']], self.on_add_remove_category)

        return {
            self.States.MAIN_MENU: [
                self.main_menu,
                self.admins_menu,
                self.categories_menu
            ],
            self.States.CONTACT: [
                MessageHandler(Filters.contact, self.on_contact),
                MessageHandler(
                    Filters.entity(MessageEntity.MENTION)
                    | Filters.entity(MessageEntity.TEXT_MENTION),
                    self.on_mention
                )
            ]
        }

    def _build_conversation(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=self._build_entries(),
            fallbacks=self._build_fallbacks(),
            states=self._build_states()
        )

    def on_entry(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            'What do you want to change?',
            reply_markup=self.main_menu.reply_keyboard(
                one_time_keyboard=True,
                selective=True
            )
        )
        return self.States.MAIN_MENU

    def on_main_menu_choice(self, update: Update, context: CallbackContext):
        submenu = self.admins_menu if update.message.text == 'Admins' else self.categories_menu
        update.message.reply_markdown_v2(
            'What’s next?',
            reply_markup=submenu.reply_keyboard()
        )
        return self.States.MAIN_MENU

    def on_add_remove_category(self, update: Update, context: CallbackContext):
        pass

    def on_add_remove_admin(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            'Please, send me the contact of the person whom you would like to make an admin of myself',
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.CONTACT

    def on_contact(self, update: Update, context: CallbackContext):
        return

    def on_mention(self, update: Update, context: CallbackContext):
        return

    def on_cancel(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            'Cancelled.',
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.MAIN_MENU
