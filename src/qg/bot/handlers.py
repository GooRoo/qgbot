import itertools
import re
from typing import List

from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, ConversationHandler
from telegram.ext.filters import Filters

from qg.logger import logger
from qg.utils.helpers import flatten

class ChoiceHandler(MessageHandler):
    def __init__(self, choices: List[List[str]], callback, *args, **kwargs):
        if not isinstance(choices, list) or len(choices) == 0:
            raise ValueError("`choices` should be a non-empty list of strings")

        self.choices = choices

        plain_choices = flatten(self.choices)
        logger.debug('Flattened list: {}', plain_choices)

        filter = Filters.regex(self._build_regex(plain_choices)) & ~Filters.command

        super(ChoiceHandler, self).__init__(filter, callback, *args, **kwargs)

    def _build_regex(self, choises):
        escaped = [re.escape(c) for c in choises]
        logger.debug('Choice regex is built: {}', f'^({"|".join(escaped)})$')
        return f'^.*?\s*({"|".join(escaped)})$'

    def reply_keyboard(self, with_back=False, with_cancel=False, *, resize_keyboard=False, one_time_keyboard=False, selective=False):
        # buttons = self.choices
        # navi_row = []
        # if with_cancel:
        #     navi_row.append('🛑 Cancel')
        # if with_back:
        #     navi_row.append('🔙 Back')
        # if len(navi_row) > 0:
        #     buttons.append(navi_row)

        return ReplyKeyboardMarkup(
            self.choices,
            resize_keyboard=resize_keyboard,
            one_time_keyboard=one_time_keyboard,
            selective=selective
        )
