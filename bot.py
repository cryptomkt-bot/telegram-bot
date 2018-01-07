import logging
import os

from cryptomkt import Cryptomkt
from telegram.ext import CommandHandler, Updater

from models import session, Chat, Market

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Enable logger
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
market_code = 'ETHARS'  # TODO: User configured market
cryptomkt = Cryptomkt(market_code=market_code)
updater = Updater(token=BOT_TOKEN)
dispatcher = updater.dispatcher


def start(bot, update):
    market = session.query(Market).filter_by(code=market_code).first()
    chat_id = update.message.chat.id
    chat = session.query(Chat).get(chat_id)
    if chat is None:
        chat = Chat(id=chat_id, market=market)
        session.add(chat)
        session.commit()
    update.message.reply_text("Hola!, ¿en qué puedo ayudarte?")


dispatcher.add_handler(CommandHandler("start", start))
updater.start_webhook(listen='0.0.0.0',
                      port=8443,
                      url_path=BOT_TOKEN,
                      key='private.key',
                      cert='cert.pem',
                      webhook_url='https://104.236.232.252:8443/' + BOT_TOKEN)
