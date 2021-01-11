from abc import abstractmethod
from enum import auto, Enum
from typing import List

import telegram.ext.handler as tgh
from telegram import ForceReply, ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Filters

from qg.utils.helpers import escape_md

from .menu import Menu


class AddingConversationHandler(object):
    class States(Enum):
        CHOICE = auto()
        STOPPING = auto()

    def __init__(self):
        self.name = None

    def set_name(self, name):
        self.name = name

    def build(self) -> ConversationHandler:
        entry_points = [MessageHandler(Filters.text(self.name), self._on_start)]
        fallbacks = [CommandHandler('cancel', self._on_cancel)]
        states = {
            self.States.CHOICE: self.build_choice_handlers()
        }
        map_to_parent = { self.States.STOPPING: Menu.States.STOPPING }
        return ConversationHandler(
            entry_points=entry_points,
            fallbacks=fallbacks,
            states=states,
            map_to_parent=map_to_parent
        )

    def _on_start(self, update: Update, context: CallbackContext):
        update.message.reply_markdown_v2(
            self.welcome(),
            reply_markup=ForceReply()
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
    def build_choice_handlers(self) -> List[tgh.Handler]:
        raise NotImplementedError
