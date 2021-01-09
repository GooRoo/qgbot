import functools
from loguru import logger


def handler(*args, admin_only=False):
    def restricted(func):
        '''Adds is_admin keyword parameter do a decorated handler'''
        @functools.wraps(func)
        def wrapped(bot, update, *args, **kwargs):
            # s = bot.db.session()

            try:
                if update.effective_user:
                    user_id = update.effective_user.id
                    user = bot.db.get_user(user_id)
                    logger.success(f'User "{user} invoked command')

                    is_admin = user.is_admin
                    logger.info('User is admin' if is_admin else 'User is not admin')

                    kwargs['is_admin'] = is_admin

                return func(bot, update, *args, **kwargs)
            finally:
                pass # bot.db.end_session()
        return wrapped

    def only_admin(func):
        '''Invokes the decorated handler only if the user is admin'''
        @functools.wraps(func)
        def wrapped(bot, update, *args, **kwargs):
            # s = bot.db.session()

            try:
                if update.effective_user:
                    user_id = update.effective_user.id
                    user = bot.db.get_user(user_id)
                    logger.success(f'User "{user} invoked command')

                    is_admin = user.is_admin
                    logger.info('User is admin' if is_admin else 'User is not admin')

                    if is_admin:
                        return func(bot, update, *args, **kwargs)
            finally:
                pass #bot.db.end_session()
        return wrapped

    if admin_only:
        return only_admin
    else:
        if len(args) == 1 and callable(args[0]):
            return restricted(args[0])
        else:
            return restricted
