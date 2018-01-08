import logging
import os
import threading

from cryptomkt import Cryptomkt
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, Filters, MessageHandler, Updater

from models import session, Alert, Chat, Market

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
    if price_changed:
        alert(market)
    threading.Timer(60, update_price).start()


def alert(market):
    for alert in market.valid_alerts():
        sign = 'menor' if alert.trigger_on_lower else 'mayor'
        text = "*ALERTA!*\nEl precio es {} a ${}.\n*Precio actual = ${}*".format(sign, alert.price, market.price)
        dispatcher.bot.send_message(chat_id=alert.chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        session.delete(alert)
    session.commit()


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
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def add_alert(bot, update, price=None):
    if price is None:
        return update.message.reply_text("Ingrese el precio:")
    try:
        price = int(price)
    except ValueError:
        return update.message.reply_text("El precio debe ser un número entero.")
    if price <= 0:
        return update.message.reply_text("El precio debe ser un número mayor a 0.")
    market = session.query(Market).filter_by(code=market_code).first()
    trigger_on_lower = price <= market.price
    alert_data = {
        'chat_id': update.message.chat.id,
        'price': price,
        'trigger_on_lower': trigger_on_lower
    }
    alert = Alert(**alert_data)
    session.add(alert)
    session.commit()
    sign = 'menor' if trigger_on_lower else 'mayor'
    text = "Perfecto, te enviaré una alerta cuando el precio sea _{}_ a *${}*.".format(sign, price)
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def remove_alert(bot, update, alert_id):
    session.query(Alert).filter_by(id=alert_id).delete()
    alert_list(bot, update, edit_message=True)


def text_handler(bot, update):
    words = update.message.text.split()
    if len(words) != 1:
        text = "Lo siento, no te entiendo. ¿Necesitas /ayuda?"
        return update.message.reply_text(text)
    return add_alert(bot, update, words[0])


def alert_list(bot, update, edit_message=False):
    send = update.edit_message_text if edit_message else update.message.reply_text
    chat_id = update.message.chat.id
    alerts = session.query(Alert).filter_by(chat_id=chat_id).order_by(Alert.price)
    if alerts.count() == 0:
        text = "No tiene ninguna alerta configurada.\n¿Desea agregar una /alerta?"
        return send(text)
    keyboard = []
    for alert in alerts:
        button = InlineKeyboardButton(str(alert), callback_data='alert {}'.format(alert.id))
        keyboard.append([button])
    text = "*Listado de alertas*"
    text_setting = {
        'parse_mode': ParseMode.MARKDOWN,
        'reply_markup': InlineKeyboardMarkup(keyboard),
    }
    send(text, **text_setting)


def alert_detail(query, alert_id):
    alert = session.query(Alert).get(alert_id)
    keyboard = [[InlineKeyboardButton("Volver al listado", callback_data='alerts'),
                 InlineKeyboardButton("Quitar alerta", callback_data='remove {}'.format(alert.id))]]
    query.edit_message_text(str(alert), reply_markup=InlineKeyboardMarkup(keyboard))


def button(bot, update):
    query = update.callback_query
    data_list = query.data.split()
    if data_list[0] == 'alert':
        alert_id = data_list[1]
        alert_detail(query, alert_id)
        query.answer()
    elif data_list[0] == 'alerts':
        alert_list(bot, query, edit_message=True)
        query.answer()
    elif data_list[0] == 'remove':
        alert_id = data_list[1]
        remove_alert(bot, query, alert_id)
        query.answer("Alerta eliminada")


update_price()
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("precio", price))
dispatcher.add_handler(CommandHandler("alertas", alert_list))
dispatcher.add_handler(CommandHandler("alerta", add_alert))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text, text_handler))
updater.start_webhook(listen='0.0.0.0',
                      port=8443,
                      url_path=BOT_TOKEN,
                      key='private.key',
                      cert='cert.pem',
                      webhook_url='https://104.236.232.252:8443/' + BOT_TOKEN)
