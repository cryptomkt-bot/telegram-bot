from models import session, Alert, Chat, Market
from telegram import error, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

MAX_ALERT_NUMBER = 10
ALERT_INPUT_TEXT = "Enviame el precio para la alerta"


def start(bot, update):
    chat_id = update.message.chat.id
    chat = session.query(Chat).get(chat_id)
    if chat is not None:
        return help_me(bot, update)
    chat = Chat(id=chat_id)
    session.add(chat)
    session.commit()
    update.message.reply_text("Hola!, ¿necesitas /ayuda?\n")


def help_me(bot, update):
    text = '¿En qué puedo ayudarte?\n\n'
    text += '/precio - Ver precio de monedas\n\n'
    text += '/alerta - Añadir alerta de precio\n\n'
    text += '/alertas - Mostrar alertas activas\n\n'
    text += '/ayuda - Mostrar este menú\n\n'
    text += '_Para eliminar una alerta debes seleccionarla previamente en el listado._'
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def text_handler(bot, update):
    message = update.message
    reply_to_message = message.reply_to_message
    if reply_to_message is not None and ALERT_INPUT_TEXT in reply_to_message.text:
        chat = get_chat(update)
        return add_alert(bot, update, market_id=chat.market_id, price=message.text)
    text = "Lo siento, no te entiendo. ¿Necesitas /ayuda?"
    return message.reply_text(text)


def query_handler(bot, update):
    query = update.callback_query
    data_list = query.data.split()
    command = data_list[0]
    try:
        arg = data_list[1]
    except IndexError:
        pass
    answer = ""
    if command == 'price':
        price(bot, query, market_id=arg)
    elif command == 'update_price':
        price(bot, query, market_id=arg, edit_message=True)
        answer = "Precio actualizado"
    elif command == 'price_detail':
        price_detail(bot, query, arg)
        answer = "Valores actualizados"
    elif command == 'add_alert':
        add_alert(bot, query, market_id=arg)
    elif command == 'alert_detail':
        alert_detail(bot, query, arg)
    elif command == 'alert_list':
        alert_list(bot, query, edit_message=True)
    elif command == 'remove_alert':
        remove_alert(bot, query, arg)
        answer = "Alerta eliminada"
    try:
        query.answer(answer)
    except error.BadRequest:
        pass


def market_list(update, method):
    markets = session.query(Market).order_by(Market.currency)
    keyboard, row = [], []
    for i, market in enumerate(markets):
        data = '{method} {market_id}'.format(method=method, market_id=market.id)
        row.append(InlineKeyboardButton(market.code, callback_data=data))
        if i % 2 == 1:
            keyboard.append(row)
            row = []
    update.message.reply_text(text="Seleccione un mercado", reply_markup=InlineKeyboardMarkup(keyboard))


def price(bot, update, market_id=None, edit_message=False):
    if market_id is None:
        return market_list(update, 'price')
    market = session.query(Market).get(market_id)
    send = update.message.edit_text if edit_message else update.message.reply_text
    keyboard = [[InlineKeyboardButton("Actualizar", callback_data='update_price {}'.format(market_id)),
                 InlineKeyboardButton("Añadir alerta", callback_data='add_alert {}'.format(market_id))],
                [InlineKeyboardButton("Más información", callback_data='price_detail {}'.format(market_id))]]
    text = "*1 {coin} = {ask} {currency}*".format(coin=market.coin, ask=market.ask, currency=market.currency)
    text += "\n\n_{time}_".format(time=market.time)
    try:
        send(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    except error.BadRequest:  # Message is not modified
        pass


def price_detail(bot, update, market_id):
    market = session.query(Market).get(market_id)
    text = "*### {code} ###*\n\n"
    text += "*COMPRA:* {ask} {currency}\n"
    text += "*VENTA:* {bid} {currency}\n"
    text += "*SPREAD:* {spread} {currency} ({spread_pct}%)\n"
    text += "*MÁS BAJO:* {low} {currency}\n"
    text += "*MÁS ALTO:* {high} {currency}\n"
    text += "*VOLUMEN*: {volume} {coin}\n"
    text += "\n_{time}_"
    values = {
        'code': market.code,
        'spread': market.spread,
        'spread_pct': market.spread_pct,
        'time': market.time,
    }
    values.update(market.__dict__)
    text = text.format(**values)
    keyboard = [[InlineKeyboardButton("Actualizar", callback_data='price_detail {}'.format(market_id)),
                 InlineKeyboardButton("Añadir alerta", callback_data='add_alert {}'.format(market_id))]]
    try:
        update.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    except error.BadRequest:  # Message is not modified
        pass


def add_alert(bot, update, market_id=None, price=None):
    if market_id is None:
        return market_list(update, 'add_alert')
    chat = get_chat(update)
    if chat.market_id != market_id:
        chat.market_id = market_id
        session.commit()
    if price is None:
        market = chat.market
        text = "_Precio actual = {} {}_".format(market.ask, market.currency)
        update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return update.message.reply_text(ALERT_INPUT_TEXT, reply_markup=ForceReply())
    try:
        price = str_to_num(price)
        if price <= 0:
            raise ValueError
    except ValueError:
        update.message.reply_text("El precio debe ser un número mayor a 0.")
        return update.message.reply_text(ALERT_INPUT_TEXT, reply_markup=ForceReply())
    if chat.alert_count() == MAX_ALERT_NUMBER:
        text = "Lo siento, sólo puedes agregar un máximo de {} /alertas.".format(MAX_ALERT_NUMBER)
        return update.message.reply_text(text)
    market = chat.market
    alert = chat.get_alert(market, str(price))
    if alert is None:  # Create alert only if it doesn't exist
        alert_data = {
            'chat': chat,
            'market': market,
            'price': str(price),
            'trigger_on_lower': price <= float(market.ask)
        }
        alert = Alert(**alert_data)
        session.add(alert)
        session.commit()
    values = {
        'coin': market.coin,
        'sign': '<' if alert.trigger_on_lower else '>',
        'price': price,
        'currency': market.currency,
    }
    text = "Perfecto, te enviaré una alerta si\n*1 {coin} {sign} {price} {currency}*".format(**values)
    keyboard = [[InlineKeyboardButton("Añadir otra alerta", callback_data='add_alert'.format(market.id)),
                 InlineKeyboardButton("Ver alertas", callback_data='alert_list')]]
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))


def remove_alert(bot, update, alert_id):
    session.query(Alert).filter_by(id=alert_id).delete()
    alert_list(bot, update, edit_message=True)


def alert_list(bot, update, edit_message=False):
    send = update.message.edit_text if edit_message else update.message.reply_text
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
    text = "*### Listado de alertas ###*"
    send(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))


def alert_detail(bot, update, alert_id):
    alert = session.query(Alert).get(alert_id)
    if alert is None:
        update.answer("La alerta no existe")
        return alert_list(bot, update, edit_message=True)
    keyboard = [[InlineKeyboardButton("Volver al listado", callback_data='alert_list'),
                 InlineKeyboardButton("Eliminar alerta", callback_data='remove_alert {}'.format(alert.id))]]
    update.message.edit_text("*{}*".format(alert), parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    update.answer()


def broadcast(bot, update, args):
    text = " ".join(args).replace("\\n", "\n")
    chats = session.query(Chat).all()
    for chat in chats:
        try:
            bot.send_message(chat_id=chat.id, text=text, parse_mode=ParseMode.MARKDOWN)
        except error.Unauthorized:  # User blocked the bot
            session.delete(chat)
    session.commit()


def get_chat(update):
    chat_id = update.message.chat.id
    chat = session.query(Chat).get(chat_id)
    if chat is None:
        chat = Chat(id=chat_id)
        session.add(chat)
        session.commit()
    return chat


def str_to_num(value):
    value = float(value)
    if value % 1 == 0:
        return int(value)
    return round(value, 2)
