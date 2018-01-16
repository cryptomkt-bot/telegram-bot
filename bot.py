import logging
import os
import requests
import telegram
import threading

from requests.exceptions import ConnectionError
from telegram.ext import CallbackQueryHandler, CommandHandler, Filters, MessageHandler, Updater

from models import session, Market

BOT_TOKEN = os.environ.get('BOT_TOKEN')
DEBUG = os.environ.get('DEBUG')
WARNING_UNICODE = u'\U000026A0'

# Enable logger
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def get_tickers():
    endpoint = 'https://api.cryptomkt.com/v1/ticker'
    try:
        response = requests.get(endpoint)
        return response.json()['data']
    except (ConnectionError, KeyError):
        return None


def main():
    updater = Updater(token=BOT_TOKEN)
    dispatcher = updater.dispatcher
    update_price(dispatcher)
    register_handlers(dispatcher)
    start_server(updater)
    updater.idle()


def update_price(dispatcher):
    markets = session.query(Market).all()
    tickers = get_tickers()
    if tickers is None:
        return
    changed_markets = []  # Markets with price change
    for market in markets:
        for t in tickers:  # TODO: Avoid nested loop if possible
            if t['market'] == market.code:
                ticker = t
                break
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
            text += "_{}_\n*Precio actual = ${}*".format(str(alert), market.ask)
            message = {
                'chat_id': alert.chat_id,
                'text': text,
                'parse_mode': telegram.ParseMode.MARKDOWN,
            }
            try:
                dispatcher.bot.send_message(**message)
            except telegram.error.Unauthorized:  # User blocked the bot
                session.delete(alert.chat)
            session.delete(alert)
    session.commit()


def register_handlers(dispatcher):
    import handlers

    dispatcher.add_handler(CommandHandler("start", handlers.start))
    dispatcher.add_handler(CommandHandler("ayuda", handlers.help_me))
    dispatcher.add_handler(CommandHandler("precio", handlers.price))
    dispatcher.add_handler(CommandHandler("alerta", handlers.add_alert))
    dispatcher.add_handler(CommandHandler("alertas", handlers.alert_list))
    dispatcher.add_handler(CommandHandler("mercado", handlers.market_list))
    dispatcher.add_handler(CallbackQueryHandler(handlers.query_handler))
    dispatcher.add_handler(MessageHandler(Filters.text, handlers.text_handler))


def start_server(updater):
    if DEBUG:
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
