import logging
import os
import requests
import threading

from telegram import error, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, Filters, MessageHandler, Updater

from models import session, Market

BOT_TOKEN = os.environ.get('BOT_TOKEN')
DEV = os.environ.get('DEV') == '1'
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID'))
admin_filter = Filters.chat(ADMIN_CHAT_ID)
WARNING_UNICODE = u'\U000026A0'

# Enable logger
log_level = logging.DEBUG if DEV else logging.INFO
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    updater = Updater(token=BOT_TOKEN)
    dispatcher = updater.dispatcher
    update_price(dispatcher)
    register_handlers(dispatcher)
    start_server(updater)
    updater.idle()


def update_price(dispatcher):
    markets = session.query(Market).all()
    changed_markets = []  # Markets with price change
    tickers = get_tickers()
    if tickers is not None:
        for market in markets:
            ticker = tickers[market.code]
            if market.ask != ticker['ask']:
                changed_markets.append(market)
            ticker_data = ('ask', 'bid', 'low', 'high', 'volume', 'timestamp')
            for attr in ticker_data:
                setattr(market, attr, ticker[attr])
            session.add(market)
        session.commit()
        alert(changed_markets, dispatcher)
    threading.Timer(60, update_price, [dispatcher]).start()  # Execute every 60 seconds.


def alert(markets, dispatcher):
    for market in markets:
        for alert in market.valid_alerts():
            text = "{} *¡ALERTA!*\n\n".format(WARNING_UNICODE)
            text += "*{}*\n_Valor actual = {} {}_".format(alert, market.ask, market.currency)
            callback_data = 'add_alert {}'.format(market.id)
            keyboard = [[InlineKeyboardButton("Añadir otra alerta", callback_data=callback_data)]]
            message = {
                'chat_id': alert.chat_id,
                'text': text,
                'parse_mode': ParseMode.MARKDOWN,
                'reply_markup': InlineKeyboardMarkup(keyboard),
            }
            try:
                dispatcher.bot.send_message(**message)
            except error.Unauthorized:  # User blocked the bot
                session.delete(alert.chat)
            else:
                session.delete(alert)
    session.commit()


def get_tickers():
    endpoint = 'https://api.cryptomkt.com/v1/ticker'
    try:
        response = requests.get(endpoint)
        tickers = response.json()['data']
    except:
        return None
    tickers_indexed = {}
    for ticker in tickers:
        tickers_indexed[ticker['market']] = ticker
    return tickers_indexed


def register_handlers(dispatcher):
    import handlers

    dispatcher.add_handler(CommandHandler("start", handlers.start))
    dispatcher.add_handler(CommandHandler("ayuda", handlers.help_me))
    dispatcher.add_handler(CommandHandler("precio", handlers.price))
    dispatcher.add_handler(CommandHandler("alerta", handlers.add_alert))
    dispatcher.add_handler(CommandHandler("alertas", handlers.alert_list))
    dispatcher.add_handler(CommandHandler("broadcast", handlers.broadcast, filters=admin_filter, pass_args=True))
    dispatcher.add_handler(CallbackQueryHandler(handlers.query_handler))
    dispatcher.add_handler(MessageHandler(Filters.text, handlers.text_handler))


def start_server(updater):
    if DEV:
        updater.start_polling()
    else:
        SERVER_URL = os.environ.get('SERVER_URL')
        updater.start_webhook(listen='0.0.0.0',
                              port=8443,
                              url_path=BOT_TOKEN,
                              key='private.key',
                              cert='cert.pem',
                              webhook_url=SERVER_URL + BOT_TOKEN)


if __name__ == '__main__':
    main()
