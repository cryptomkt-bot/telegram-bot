from datetime import datetime
from sqlalchemy import create_engine, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.sql.expression import and_, or_

engine = create_engine('sqlite:///bot.db', connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)
session = Session()


class Base():
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True)


Base = declarative_base(cls=Base)


class Chat(Base):
    market_id = Column(ForeignKey('market.id'))
    market = relationship('Market')

    def __repr__(self):
        return '<Chat({})>'.format(self.id)

    def get_alert(self, market, price):
        return session.query(Alert).filter_by(chat_id=self.id, market=market, price=price).first()

    def alert_count(self):
        return session.query(Alert).filter_by(chat_id=self.id).count()


class Market(Base):
    coin = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    ask = Column(String)
    bid = Column(String)
    low = Column(String)
    high = Column(String)
    volume = Column(String)
    timestamp = Column(String)
    decimals = Column(Integer)

    def __repr__(self):
        return '<Market({})>'.format(self.code)

    @property
    def code(self):
        return self.coin + self.currency

    @property
    def spread(self):
        spread = float(self.ask) - float(self.bid)
        if spread % 1 == 0:
            return int(spread)
        return round(spread, 2)

    @property
    def spread_pct(self):
        spread = float(self.ask) - float(self.bid)
        return round(spread / float(self.ask) * 100, 2)

    @property
    def time(self):
        time = datetime.strptime(self.timestamp, '%Y-%m-%dT%H:%M:%S.%f')
        return time.strftime('%d/%m/%Y - %H:%M (UTC)')

    def valid_alerts(self):
        """Return those alerts that satisfy its conditions."""
        filters = [
            and_(Market.ask < Alert.price, Alert.trigger_on_lower == True),
            and_(Market.ask > Alert.price, Alert.trigger_on_lower == False),
        ]
        query = session.query(Alert).join(Market).filter(Market.id == self.id).filter(or_(*filters))
        return query.all()


class Alert(Base):
    """A user price alert"""
    chat_id = Column(ForeignKey('chat.id'), nullable=False)
    chat = relationship('Chat', backref=backref('alerts', cascade='all, delete-orphan'))
    market_id = Column(ForeignKey('market.id'), nullable=False)
    market = relationship('Market')
    price = Column(String)
    trigger_on_lower = Column(Boolean, nullable=False)

    def __str__(self):
        values = {
            'coin': self.market.coin,
            'sign': '<' if self.trigger_on_lower else '>',
            'price': self.price,
            'currency': self.market.currency,
        }
        return "1 {coin} {sign} {price} {currency}".format(**values)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
