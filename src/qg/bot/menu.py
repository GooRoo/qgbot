from abc import abstractmethod
from enum import auto, Enum
from os import replace
from re import S
from typing import Callable, Dict, List

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, Dispatcher, MessageHandler
from telegram.ext.filters import Filters

from qg.logger import logger
from qg.utils.helpers import escape_md, flatten


class BaseMenu(object):
    def __init__(self, name: str=''):
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
    class States(Enum):
        END = ConversationHandler.END
        CHOICE = auto()
        STOPPING = auto()

    def __init__(self, name: str, question: str, children: List[List[BaseMenu]]):
        super().__init__(name)
        self.question = question
        self.children = children
        self.flattened_children = flatten(self.children)
        for child in self.flattened_children:
            child.set_parent(self)

    def set_parent(self, parent):
        if parent is not None:
            self.name += ' ▸'
        return super().set_parent(parent)

    # @logger.catch
    # def _build_keyboard(self):
    #     keyboard = [
    #         flatten(child._build_keyboard() for child in row) for row in self.children
    #     ]
    #     logger.debug(f'Keyboard: {keyboard}')
    #     return [
    #         flatten(child._build_keyboard() for child in row) for row in self.children
    #     ]

    def _build_child_keyboard(self):
        keyboard = []
        for row in self.children:
            keyboard_row = []
            for child in row:
                if type(row) is MenuItemProxy:  # HACK: this is the ugliest hack! need to rewrite it
                    keyboard.append(child._build_keyboard())
                else:
                    keyboard_row.extend(child._build_keyboard())
            if len(keyboard_row) > 0:
                keyboard.append(keyboard_row)
        return keyboard
        # return [
        #     flatten(child._build_keyboard() for child in row) for row in self.children
        # ]

    def on_cancel(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md('Cancelled.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.STOPPING

    def on_back(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md('Going back.'),
            reply_markup=ReplyKeyboardMarkup(self.parent._build_child_keyboard())
        )
        return self.States.END

    @logger.catch
    def on_enter(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md(self.question),
            reply_markup=ReplyKeyboardMarkup(self._build_child_keyboard())
        )
        return self.States.CHOICE

    @logger.catch
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
    def __init__(self, name: str, action_callback):
        assert name is not None and name != ''
        super().__init__(name)
        self.callback = action_callback

    @logger.catch
    def _build_entry_points(self):
        return [MessageHandler(Filters.text([self.name]), self.callback)]

    def _build_fallbacks(self):
        return super()._build_fallbacks()

    def _build_states(self):
        return super()._build_states()

    def __repr__(self):
        return f'<MenuItem(name={self.name})>'

class CancelButton(BaseMenu):
    def __init__(self):
        super().__init__('⎋ Cancel')

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
    def __init__(self):
        super().__init__('◂ Back')

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
    def __init__(self, populate_callback: Callable[[], List[MenuItem]], action_callback):
        super().__init__('asdfasdfasdf')
        self.populate = populate_callback
        self.callback = action_callback

    # def _build_keyboard(self):
    #     return flatten(i._build_keyboard() for i in self.populate()) if self.populate is not None else []

    # def _build_entry_points(self):
    #     return flatten(i._build_entry_points() for i in self.populate()) if self.populate is not None else []

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
    def __init__(self, menu: Menu = None, dispatcher: Dispatcher = None):
        self.set_menu(menu)
        self.dispatcher = dispatcher
        self.register()

    def register(self):
        if self.menu is not None and self.dispatcher is not None:
            self.dispatcher.add_handler(self.menu._build_entry_points()[0])

    def set_menu(self, menu: Menu):
        self.menu = menu
