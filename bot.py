import logging
import os
import telegram
import threading

from cryptomkt import Cryptomkt
from telegram.ext import CallbackQueryHandler, CommandHandler, Filters, MessageHandler, Updater

from models import session, Market

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Enable logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    cryptomkt = Cryptomkt()
    updater = Updater(token=BOT_TOKEN)
    dispatcher = updater.dispatcher
    update_price(cryptomkt, dispatcher)
    register_handlers(dispatcher)
    start_server(updater)


def update_price(cryptomkt, dispatcher):
    markets = session.query(Market).all()
    tickers = cryptomkt.get_tickers()
    changed_markets = []  # Markets with price change
    for market in markets:
        for t in tickers:  # TODO: Avoid nested loop if possible
            if t['market'] == market.code:
                ticker = t
                break
        price_changed = market.price != ticker['ask']
        if price_changed:
            changed_markets.append(market)
            market.price = ticker['ask']
        market.timestamp = ticker['timestamp']
        session.add(market)
    session.commit()
    alert(changed_markets, dispatcher)
    threading.Timer(60, update_price, [cryptomkt, dispatcher]).start()  # Execute every 60 seconds.


def alert(markets, dispatcher):
    for market in markets:
        for alert in market.valid_alerts():
            text = "*¡ALERTA!*\n\n_{}_\n*Precio actual = ${}*".format(str(alert), market.price)
            dispatcher.bot.send_message(chat_id=alert.chat_id, text=text, parse_mode=telegram.ParseMode.MARKDOWN)
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
    updater.start_webhook(listen='0.0.0.0',
                          port=8443,
                          url_path=BOT_TOKEN,
                          key='private.key',
                          cert='cert.pem',
                          webhook_url='https://104.236.232.252:8443/' + BOT_TOKEN)


if __name__ == '__main__':
    main()
