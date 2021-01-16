from abc import abstractmethod
from enum import Enum, auto

import telegram.ext.handler as tgh
from telegram import ForceReply, ReplyKeyboardRemove, Update
from telegram.ext import (CallbackContext, CommandHandler, ConversationHandler,
                          MessageHandler)
from telegram.ext.filters import Filters

from qg.utils.helpers import escape_md

from .common import STOPPING as cSTOPPING
from .decorators import handler
from .menu import Menu


class CancellableConversationBuilder(object):
    '''
    This class simplifies the creation of `ConversationHandler`s just a little bit
    by adding a Cancel button which is compatible with the `Menu`.
    '''

    class States(Enum):
        CHOICE = auto()
        STOPPING = cSTOPPING

    def __init__(self):
        self.name = None

    def set_name(self, name):
        self.name = name

    def build(self) -> ConversationHandler:
        entry_points = [MessageHandler(Filters.text(self.name), self._on_start)]
        fallbacks = [CommandHandler('cancel', self._on_cancel)]
        states = {
            self.States.CHOICE: self.build_entry_handlers()
        }
        states |= self.build_additional_states()
        map_to_parent = {
            self.States.STOPPING: Menu.States.STOPPING,
            cSTOPPING: Menu.States.STOPPING
        }
        return ConversationHandler(
            entry_points=entry_points,
            fallbacks=fallbacks,
            states=states,
            map_to_parent=map_to_parent
        )

    @handler(admin_only=True)
    def _on_start(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            self.welcome(),
            reply_markup=ForceReply(selective=True)
        )
        return self.States.CHOICE

    def _on_cancel(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            escape_md('Cancelled.'),
            reply_markup=ReplyKeyboardRemove()
        )
        return self.States.STOPPING

    @abstractmethod
    def welcome(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_entry_handlers(self) -> list[tgh.Handler]:
        raise NotImplementedError

    def build_additional_states(self):
        return {}
