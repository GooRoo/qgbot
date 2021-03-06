from abc import abstractmethod
from enum import Enum, auto
from typing import Callable

from telegram import (KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
                      Update)
from telegram.ext import (CallbackContext, CommandHandler, ConversationHandler,
                          Dispatcher, MessageHandler)
from telegram.ext.filters import Filters

from qg.logger import logger
from qg.utils.helpers import escape_md, flatten

from .common import STOPPING as cSTOPPING

BACK_BUTTON_TEXT = '◂ Back'
CANCEL_BUTTON_TEXT = '⎋ Cancel'
MENU_SUFFIX = ' ▸'


class BaseMenu(object):
    '''
    Abstract base class for menu entities.

    Defines a simple interface with default implementations. Maybe not the best
    but it does the job.
    '''

    def __init__(self, name: str = ''):
        self.name = name
        self.parent = None
        super().__init__()

    def root(self):
        return self.parent is None

    def set_parent(self, parent):
        self.parent = parent

    @abstractmethod
    def _build_fallbacks(self):
        return []

    @abstractmethod
    def _build_entry_points(self):
        return []

    @abstractmethod
    def _build_states(self):
        return []

    def _build_keyboard(self):
        return [KeyboardButton(self.name)]


class Menu(BaseMenu):
    '''A collection of other menu entities'''

    class States(Enum):
        STOPPING = cSTOPPING
        END = ConversationHandler.END
        CHOICE = auto()

    def __init__(self, name: str, question: str, children: list[list[BaseMenu]]):
        super().__init__(name)
        self.question = question
        self.children = children
        self.flattened_children = flatten(self.children)

        # FIXME: I've just realized that the logic below is incorrect but seems to work
        for child in self.flattened_children:
            child.set_parent(self)

    def set_parent(self, parent):
        if parent is not None:
            self.name += MENU_SUFFIX
        return super().set_parent(parent)

    def _build_child_keyboard(self):
        keyboard = []
        for row in self.children:
            keyboard_row = []
            for child in row:
                if isinstance(row, MenuItemProxy):  # HACK: this is the ugliest hack! need to rewrite it
                    keyboard.append(child._build_keyboard())
                else:
                    keyboard_row.extend(child._build_keyboard())
            if keyboard_row:
                keyboard.append(keyboard_row)
        return keyboard

    def on_cancel(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md('Cancelled.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.STOPPING

    def on_back(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md('Going back.'),
            reply_markup=ReplyKeyboardMarkup(self.parent._build_child_keyboard(), selective=True)
        )
        return self.States.END

    def on_enter(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md(self.question),
            reply_markup=ReplyKeyboardMarkup(self._build_child_keyboard(), selective=True)
        )
        return self.States.CHOICE

    def _build_own_entry_point(self):
        if self.root():
            return [CommandHandler(self.name, self.on_enter)]
        else:
            return [MessageHandler(Filters.text(self.name), self.on_enter)]

    def _build_map_to_parent(self):
        map_to_parent = {
            self.States.END: self.States.CHOICE,
            self.States.STOPPING: self.States.STOPPING
        }
        return None if self.root() else map_to_parent

    def _build_fallbacks(self):
        return flatten(
            child._build_fallbacks()
            for child in self.flattened_children
            if type(child) is not Menu
        )

    def _build_entry_points(self):
        return [ConversationHandler(
            entry_points=self._build_own_entry_point(),
            fallbacks=self._build_fallbacks(),
            states=self._build_states(),
            map_to_parent=self._build_map_to_parent()
        )]

    def _build_states(self):
        return {
            self.States.CHOICE: flatten(
                child._build_entry_points()
                for child in self.flattened_children
            ),
            self.States.STOPPING: self._build_own_entry_point()
        }

    def __repr__(self):
        return f'''<Menu(name={self.name}, children={
            [
                [child.name for child in row]
                for row in self.children
            ]})>'''


class MenuItem(BaseMenu):
    '''
    Just a menu item which triggers a callback when chosen.

    Also, it can be used in conjunction with `MenuItemProxy`.
    '''

    def __init__(self, name: str, action_callback, accept_all = False):
        assert name is not None and name != ''
        super().__init__(name)
        self.callback = action_callback
        self.accept_all = accept_all

    def _build_entry_points(self):
        logger.debug(f'MenuItem: {self.name}')
        if self.accept_all:
            filters = (Filters.text
                       & ~Filters.text(BACK_BUTTON_TEXT)
                       & ~Filters.text(CANCEL_BUTTON_TEXT)
                       & ~Filters.command)
        else:
            filters = Filters.text([self.name])
        return [MessageHandler(filters, self.callback)]

    def _build_fallbacks(self):
        return super()._build_fallbacks()

    def _build_states(self):
        return super()._build_states()

    def __repr__(self):
        return f'<MenuItem(name={self.name})>'


class MenuConversationItem(BaseMenu):
    '''Menu item which enters a conversation when chosen'''

    def __init__(self, name: str, conversation):
        assert name is not None and name != ''
        super().__init__(name=name)
        self.conversation_builder = conversation
        self.conversation_builder.set_name(self.name)

    def on_cancel(self, update: Update, context: CallbackContext):
        return self.parent.on_cancel(update, context)

    def _build_entry_points(self):
        return [
            self.conversation_builder.build()
        ]

    def _build_fallbacks(self):
        return super()._build_fallbacks()

    def _build_states(self):
        return super()._build_states()

    def __repr__(self):
        return f'<MenuConversationItem(name={self.name})>'


class CancelButton(BaseMenu):
    '''Menu item to exit the menu completely'''

    def __init__(self):
        super().__init__(CANCEL_BUTTON_TEXT)

    def _build_fallbacks(self):
        return [
            CommandHandler('cancel', self.parent.on_cancel),
            MessageHandler(Filters.text([self.name]), self.parent.on_cancel)
        ]

    def _build_entry_points(self):
        return super()._build_entry_points()

    def _build_states(self):
        return super()._build_states()

    def __repr__(self):
        return f'<CancelButton()>'


class BackButton(BaseMenu):
    '''Menu item to exit the current level of hierarchy'''

    def __init__(self):
        super().__init__(BACK_BUTTON_TEXT)

    def _build_fallbacks(self):
        return [
            CommandHandler('back', self.parent.on_back),
            MessageHandler(Filters.text([self.name]), self.parent.on_back)
        ]

    def _build_entry_points(self):
        return super()._build_entry_points()

    def _build_states(self):
        return super()._build_states()

    def __repr__(self):
        return f'<BackButton()>'


class MenuItemProxy(BaseMenu):
    '''
    A placeholder which is expanded into a list of, for example, `MenuItem`s depending on
    the result of a `populate_callback`.
    '''

    def __init__(self, populate_callback: Callable[[], list[MenuItem]], action_callback=None):
        super().__init__()
        self.populate = populate_callback
        self.callback = action_callback

    def _build_entry_points(self):
        return super()._build_entry_points()

    def _build_states(self):
        return super()._build_states()

    def _build_fallbacks(self):
        return super()._build_fallbacks()

    def __iter__(self):
        for i in self.populate():
            yield i


class MenuHandler(object):
    '''A handler for the `Dispatcher` to manage the menu'''

    def __init__(self, menu: Menu = None, dispatcher: Dispatcher = None):
        self.set_menu(menu)
        self.dispatcher = dispatcher
        self.register()

    def register(self):
        if self.menu is not None and self.dispatcher is not None:
            self.dispatcher.add_handler(self.menu._build_entry_points()[0])

    def set_menu(self, menu: Menu):
        self.menu = menu
