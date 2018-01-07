import logging
import os
import telegram
import threading

from cryptomkt import Cryptomkt
from datetime import datetime
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


def update_price():
    ticker = cryptomkt.get_ticker()
    market = session.query(Market).filter_by(code=market_code).first()
    price_changed = market.price != ticker['ask']
    if price_changed:
        market.price = ticker['ask']
    market.timestamp = ticker['timestamp']
    session.add(market)
    session.commit()
    threading.Timer(60, update_price).start()


def start(bot, update):
    market = session.query(Market).filter_by(code=market_code).first()
    chat_id = update.message.chat.id
    chat = session.query(Chat).get(chat_id)
    if chat is None:
        chat = Chat(id=chat_id, market=market)
        session.add(chat)
        session.commit()
    update.message.reply_text("Hola!, ¿en qué puedo ayudarte?")


def price(bot, update):
    market = session.query(Market).filter_by(code=market_code).first()
    time = datetime.strptime(market.timestamp, '%Y-%m-%dT%H:%M:%S.%f')
    price = {
        'value': market.price,
        'code': market.code,
        'time': time.strftime('%d/%m/%Y - %H:%M:%S (UTC)'),
    }
    text = "*${value} ({code})*\n_{time}_".format(**price)
    update.message.reply_text(text, parse_mode=telegram.ParseMode.MARKDOWN)


update_price()
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("precio", price))
updater.start_webhook(listen='0.0.0.0',
                      port=8443,
                      url_path=BOT_TOKEN,
                      key='private.key',
                      cert='cert.pem',
                      webhook_url='https://104.236.232.252:8443/' + BOT_TOKEN)
