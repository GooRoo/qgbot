from enum import auto, Enum
from typing import Dict, List

from telegram import Update, MessageEntity, ReplyKeyboardRemove
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, Dispatcher, Handler, MessageHandler
from telegram.ext.filters import Filters

from qg.logger import logger
from qg.utils.helpers import escape_md, flatten

from .menu import MenuHandler, Menu, MenuItem, MenuItemProxy, BackButton, CancelButton


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
                            MenuItemProxy(self.populate_categories, self.remove_category),
                            [ CancelButton(), BackButton() ]
                        ])
                    ],
                    [ CancelButton(), BackButton() ]
                ]),
                Menu('Admins', 'And what do you want to do here?',
                [
                    [
                        MenuItem('Promote to admin…', None),
                        Menu('Demote admin', 'Choose the victim!',
                        [
                            MenuItemProxy(self.populate_admins, self.remove_admin),
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

    def add_category(self):
        pass

    def remove_category(self):
        pass

    def populate_categories(self):
        return [
            MenuItem(name, self.remove_admin)
            for _, (name, _) in self.bot.db.get_categories().items()
        ]

    def add_admin(self):
        pass

    def remove_admin(self):
        pass

    def populate_admins(self):
        return []


# class SettingsConversation(object):
#     '''
#     Handle /settings command
#     '''

#     class States(Enum):
#         MAIN_MENU = auto()
#         ADMINS = auto()
#         CATEGORIES = auto()
#         CONTACT = auto()

#     def __init__(self, command='settings', dispatcher=None):
#         self.command = command
#         if dispatcher is not None:
#             self.register(dispatcher)

#     def register(self, dispatcher: Dispatcher):
#         dispatcher.add_handler(self._build_conversation())

#     def _build_entries(self) -> List[Handler]:
#         return [
#             CommandHandler(self.command, self.on_entry)
#         ]

#     def _build_fallbacks(self, sublevel=False) -> List[Handler]:
#         handlers = [
#             CommandHandler('cancel', self.on_cancel),
#             MessageHandler(Filters.text(['Cancel']), self.on_cancel)
#         ]
#         if sublevel:
#             handlers.append(MessageHandler(Filters.text(['Back'], self.on_back)))
#         return handlers

#     def _build_main_menu(self) -> Dict[int, Handler]:
#         self.main_menu = ChoiceHandler([['Categories', 'Admins']], self.on_main_menu_choice)
#         self.admins_menu = ChoiceHandler([['Add admin…', 'Remove admin…']], self.on_add_remove_admin)
#         self.categories_menu = ChoiceHandler([['Add category…', 'Remove category…']], self.on_add_remove_category)

#         return {
#             self.States.MAIN_MENU: [
#                 self.main_menu,
#                 self.admins_menu,
#                 self.categories_menu
#             ],
#             self.States.CATEGORIES: [],
#             self.States.ADMINS: [],
#             self.States.CONTACT: [
#                 MessageHandler(Filters.contact, self.on_contact),
#                 MessageHandler(
#                     Filters.entity(MessageEntity.MENTION)
#                     | Filters.entity(MessageEntity.TEXT_MENTION),
#                     self.on_mention
#                 )
#             ]
#         }

#     def _build_conversation(self) -> ConversationHandler:
#         return ConversationHandler(
#             entry_points=self._build_entries(),
#             fallbacks=self._build_fallbacks(),
#             states=self._build_main_menu()
#         )

#     def on_entry(self, update: Update, context: CallbackContext):
#         update.message.reply_markdown_v2(
#             escape_md('What do you want to change?'),
#             reply_markup=self.main_menu.reply_keyboard(
#                 one_time_keyboard=True,
#                 selective=True,
#                 with_cancel=True
#             )
#         )
#         return self.States.MAIN_MENU

#     def on_main_menu_choice(self, update: Update, context: CallbackContext):
#         submenu = self.admins_menu if update.message.text == 'Admins' else self.categories_menu
#         update.message.reply_markdown_v2(
#             escape_md('What’s next?'),
#             reply_markup=submenu.reply_keyboard(with_back=True, with_cancel=True)
#         )
#         return self.States.MAIN_MENU

#     def on_add_remove_category(self, update: Update, context: CallbackContext):
#         return self.States.CATEGORIES

#     def on_add_remove_admin(self, update: Update, context: CallbackContext):
#         update.message.reply_markdown_v2(
#             'Please, send me the contact of the person whom you would like to make an admin of myself',
#             reply_markup=ReplyKeyboardRemove()
#         )
#         return self.States.CONTACT

#     def on_contact(self, update: Update, context: CallbackContext):
#         return

#     def on_mention(self, update: Update, context: CallbackContext):
#         return

#     @logger.catch
#     def on_cancel(self, update: Update, context: CallbackContext):
#         update.message.reply_markdown_v2(
#             escape_md('Cancelled.'),
#             reply_markup=ReplyKeyboardRemove()
#         )
#         return ConversationHandler.END

#     def on_back(self, update: Update, context: CallbackContext):
#         pass
