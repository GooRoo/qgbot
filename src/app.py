from qg.logger import logger

from dynaconf import settings
from qg.bot import QGBot


if __name__ == "__main__":
    bot = QGBot(settings.BOT.token)
    bot.run(websocket=settings.BOT.ws_enabled)
