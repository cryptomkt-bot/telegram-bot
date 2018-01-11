from models import session, Alert, Chat, Market
from telegram import error, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

MAX_ALERT_NUMBER = 5


def start(bot, update):
    chat_id = update.message.chat.id
    chat = session.query(Chat).get(chat_id)
    if chat is None:
        chat = Chat(id=chat_id)
        session.add(chat)
        session.commit()
        text = "Hola! Por favor, seleccione un mercado:"
        market_list(bot, update, text)
    else:
        help_me(bot, update)


def help_me(bot, update):
    text = '¿En qué puedo ayudarte?\n\n'
    text += '/precio - Ver precio actual\n\n'
    text += '/alerta - Añadir alerta de precio\n\n'
    text += '/alertas - Mostrar alertas activas\n\n'
    text += '/mercado - Cambiar mercado\n\n'
    text += '/ayuda - Mostrar este menú\n\n'
    text += '_Para eliminar una alerta debe seleccionarla previamente en el listado._'
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def text_handler(bot, update):
    words = update.message.text.split()
    if len(words) != 1:
        text = "Lo siento, no te entiendo. ¿Necesitas /ayuda?"
        return update.message.reply_text(text)
    return add_alert(bot, update, words[0])


def query_handler(bot, update):
    query = update.callback_query
    data_list = query.data.split()
    command = data_list[0]
    try:
        arg = data_list[1]
    except IndexError:
        pass
    if command == 'price_detail':
        price_detail(bot, query)
    elif command == 'update_price':
        price(bot, query, edit_message=True)
        query.answer("Precio actualizado")
    elif command == 'update_price_detail':
        price_detail(bot, query)
        query.answer("Valores actualizados")
    elif command == 'alert_detail':
        alert_detail(query, arg)
        query.answer()
    elif command == 'alert_list':
        alert_list(bot, query, edit_message=True)
        query.answer()
    elif command == 'remove_alert':
        remove_alert(bot, query, arg)
        query.answer("Alerta eliminada")
    elif command == 'market_selected':
        market_selected(bot, query, int(arg))
        query.answer("Mercado configurado")


def price(bot, update, edit_message=False):
    send = update.edit_message_text if edit_message else update.message.reply_text
    market = get_market(bot, update)
    if market is None:
        return
    keyboard = [[InlineKeyboardButton("Actualizar", callback_data='update_price'),
                 InlineKeyboardButton("Más información", callback_data='price_detail')]]
    text = "*{price}*\n_{time}_".format(price=market.formatted_price(), time=market.time())
    try:
        send(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    except error.BadRequest:  # Message is not modified
        pass


def price_detail(bot, update):
    market = get_market(bot, update)
    spread = market.ask - market.bid
    spread_pct = spread / market.ask * 100
    text = "*Compra:* ${ask}\n*Venta:* ${bid}\n".format(ask=market.ask, bid=market.bid)
    text += "*Spread:* ${spread} ({pct}%)\n\n".format(spread=spread, pct=round(spread_pct, 2))
    text += "_{time}_".format(price=market.formatted_price(), time=market.time())
    keyboard = [[InlineKeyboardButton("Actualizar", callback_data='update_price_detail')]]
    try:
        update.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    except error.BadRequest:  # Message is not modified
        pass


def add_alert(bot, update, price=None):
    chat = get_chat(update)
    market = get_market(bot, update, chat)
    if market is None:
        return
    if chat.alert_count() == MAX_ALERT_NUMBER:
        text = "Lo siento, sólo puedes agregar un máximo de {} /alertas.".format(MAX_ALERT_NUMBER)
        return update.message.reply_text(text)
    if price is None:
        return update.message.reply_text("Ingrese el precio:")
    try:
        price = int(price)
    except ValueError:
        return update.message.reply_text("El precio debe ser un número entero.")
    if price <= 0:
        return update.message.reply_text("El precio debe ser un número mayor a 0.")
    alert = chat.get_alert(price)
    if alert is None:  # Create alert only if it doesn't exist
        trigger_on_lower = price <= chat.market.ask
        alert_data = {
            'chat_id': chat.id,
            'price': price,
            'trigger_on_lower': trigger_on_lower
        }
        alert = Alert(**alert_data)
        session.add(alert)
        session.commit()
    sign = 'menor' if alert.trigger_on_lower else 'mayor'
    text = "Perfecto, te enviaré una alerta cuando el precio sea _{}_ a *${}*.".format(sign, price)
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def remove_alert(bot, update, alert_id):
    session.query(Alert).filter_by(id=alert_id).delete()
    alert_list(bot, update, edit_message=True)


def alert_list(bot, update, edit_message=False):
    send = update.edit_message_text if edit_message else update.message.reply_text
    chat_id = update.message.chat.id
    alerts = session.query(Alert).filter_by(chat_id=chat_id).order_by(Alert.price)
    if alerts.count() == 0:
        text = "No tiene ninguna alerta configurada.\n¿Desea agregar una /alerta?"
        return send(text)
    keyboard = []
    for alert in alerts:
        data = 'alert_detail {}'.format(alert.id)
        button = InlineKeyboardButton(str(alert), callback_data=data)
        keyboard.append([button])
    text = "*Listado de alertas*"
    text_setting = {
        'parse_mode': ParseMode.MARKDOWN,
        'reply_markup': InlineKeyboardMarkup(keyboard),
    }
    send(text, **text_setting)


def alert_detail(query, alert_id):
    alert = session.query(Alert).get(alert_id)
    keyboard = [[InlineKeyboardButton("Volver al listado", callback_data='alert_list'),
                 InlineKeyboardButton("Eliminar alerta", callback_data='remove_alert {}'.format(alert.id))]]
    query.edit_message_text(str(alert), reply_markup=InlineKeyboardMarkup(keyboard))


def market_list(bot, update, text=None):
    if text is None:
        text = "Seleccione un mercado:"
    markets = session.query(Market).all()
    keyboard = []
    for market in markets:
        data = 'market_selected {}'.format(market.id)
        keyboard.append([InlineKeyboardButton(market.code[3:], callback_data=data)])
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


def market_selected(bot, update, market_id):
    chat_id = update.message.chat.id
    chat = session.query(Chat).get(chat_id)
    previous_market_id = chat.market_id
    if previous_market_id != market_id:
        chat.market_id = market_id
        session.commit()
        if previous_market_id is None:  # Show the help menu if it's a new user
            help_me(bot, update)
        else:
            session.query(Alert).filter_by(chat_id=chat.id).delete()  # Delete alerts of previous market


def get_chat(update):
    chat_id = update.message.chat.id
    return session.query(Chat).get(chat_id)


def get_market(bot, update, chat=None):
    if chat is None:
        chat = get_chat(update)
    if chat.market is None:
        text = "Por favor, seleccione un mercado y vuelva a intentarlo:"
        market_list(bot, update, text)
    return chat.market
