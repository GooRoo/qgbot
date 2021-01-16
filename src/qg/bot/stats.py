from telegram import ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext, Dispatcher

from qg.logger import logger
from qg.utils.helpers import escape_md

from .menu import CancelButton, Menu, MenuHandler, MenuItem


class StatisticsMenu(object):
    '''Menu which responds to /stats'''

    def __init__(self, bot, dispatcher: Dispatcher):
        self.bot = bot
        self.db = self.bot.db
        self.menu = MenuHandler(self.build_menu(), dispatcher=dispatcher)

    def _leaderboard(self, iterable):
        return zip(
            ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'],
            iterable
        )

    def build_menu(self):
        menu = Menu('stats', 'Here are the TOP-5s. What do you want to see?',
        [
            [ MenuItem('Top Committers', self.show_top_committers) ],
            [ MenuItem('Top Reviewers', self.show_top_reviewers) ],
            [ MenuItem('Top Influencers', self.show_best_committers) ],
            [ CancelButton() ]
        ])
        return menu

    @logger.catch
    def show_top_committers(self, update: Update, context: CallbackContext):
        response = 'Here are the people who make the biggest amount of proposals:\n'
        with self.db.session():
            response += '\n'.join([
                f'''{n} {user.mention_md()} {escape_md(f'({count} submission{"s" if count != 1 else ""})')}'''
                for n, (user, count) in self._leaderboard(self.db.get_top_committers())
            ])
        update.message.reply_markdown_v2(
            response,
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING

    @logger.catch
    def show_top_reviewers(self, update: Update, context: CallbackContext):
        response = 'Here are the people who vote the most:\n'
        with self.db.session():
            response += '\n'.join([
                f'''{n} {user.mention_md()} {escape_md(f'({count} vote{"s" if count != 1 else ""})')}'''
                for n, (user, count) in self._leaderboard(self.db.get_top_reviewers())
            ])
        update.message.reply_markdown_v2(
            response,
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING

    @logger.catch
    def show_best_committers(self, update: Update, context: CallbackContext):
        response = 'Here are the people whose proposals got the highest amount of upvotes in total:\n'
        with self.db.session():
            response += '\n'.join([
                f'{n} {user.mention_md()} got {upvotes} upvote{"s" if upvotes != 1 else ""}'
                for n, (user, upvotes) in self._leaderboard(self.db.get_best_committers())
            ])
        update.message.reply_markdown_v2(
            response,
            reply_markup=ReplyKeyboardRemove()
        )
        return Menu.States.STOPPING
