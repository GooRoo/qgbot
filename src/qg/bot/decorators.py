import functools

from telegram.replykeyboardremove import ReplyKeyboardRemove

from qg.logger import logger
from qg.utils.helpers import escape_md

from .common import STOPPING as cSTOPPING


def handler(*args, admin_only=False):
    def restricted(func):
        '''Adds is_admin keyword parameter do a decorated handler'''
        @functools.wraps(func)
        def wrapped(bot, update, *args, **kwargs):
            with bot.db.session():
                if update.effective_user:
                    user_id = update.effective_user.id
                    user = bot.db.find_user(user_id)
                    if user is None:
                        logger.debug(f'Unknown user with id "{user_id}" has invoked the command.')
                        is_admin = False
                    else:
                        logger.debug(f'User "{user}" has invoked the command.')
                        is_admin = user.is_admin

                    logger.info('User is admin.' if is_admin else 'User is not admin.')

                    kwargs['is_admin'] = is_admin

                handler_result = func(bot, update, *args, **kwargs)
            return handler_result
        return wrapped

    def only_admin(func):
        '''Invokes the decorated handler only if the user is admin'''
        @functools.wraps(func)
        def wrapped(bot, update, *args, **kwargs):
            handler_result = cSTOPPING
            if update.effective_user:
                user_id = update.effective_user.id
                with bot.db.session():
                    user = bot.db.find_user(user_id)
                    if user is None:
                        logger.debug(f'Unknown user with id "{user_id}" has invoked the command.')
                        is_admin = False
                    else:
                        logger.debug(f'User "{user}" has invoked the command.')
                        is_admin = user.is_admin

                logger.info('User is admin.' if is_admin else 'User is not admin.')

                if is_admin:
                    handler_result = func(bot, update, *args, **kwargs)
                else:
                    update.message.reply_markdown_v2(
                        escape_md('Sorry, this function is available for admins only. Aborting.'),
                        reply_markup=ReplyKeyboardRemove()
                    )

            return handler_result
        return wrapped

    if admin_only:
        return only_admin
    else:
        if len(args) == 1 and callable(args[0]):
            return restricted(args[0])
        else:
            return restricted
