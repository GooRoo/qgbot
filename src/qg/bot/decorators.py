import functools
from loguru import logger


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
                        logger.info('Unknown user with id={} has invoked the command', user_id)
                        is_admin = False
                    else:
                        logger.info('User "{}" has invoked the command', user)
                        is_admin = user.is_admin

                    logger.info('User is admin' if is_admin else 'User is not admin')

                    kwargs['is_admin'] = is_admin

                handler_result = func(bot, update, *args, **kwargs)
            return handler_result
        return wrapped

    def only_admin(func):
        '''Invokes the decorated handler only if the user is admin'''
        @functools.wraps(func)
        def wrapped(bot, update, *args, **kwargs):
            handler_result = None
            with bot.db.session():
                if update.effective_user:
                    user_id = update.effective_user.id
                    user = bot.db.find_user(user_id)
                    if user is None:
                        logger.info('Unknown user with id={} has invoked the command', user_id)
                        is_admin = False
                    else:
                        logger.info('User "{}" has invoked the command', user)
                        is_admin = user.is_admin

                    logger.info('User is admin' if is_admin else 'User is not admin')

                    if is_admin:
                        handler_result = func(bot, update, *args, **kwargs)
            return handler_result
        return wrapped

    if admin_only:
        return only_admin
    else:
        if len(args) == 1 and callable(args[0]):
            return restricted(args[0])
        else:
            return restricted
