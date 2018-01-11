from datetime import datetime
from sqlalchemy import create_engine, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, sessionmaker
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
    market = relationship('Market', backref='chats')

    def get_alert(self, price):
        return session.query(Alert).filter_by(chat_id=self.id, price=price).first()

    def alert_count(self):
        return session.query(Alert).filter_by(chat_id=self.id).count()


class Market(Base):
    code = Column(String, nullable=False, unique=True)
    ask = Column(Integer)
    bid = Column(Integer)
    low = Column(Integer)
    high = Column(Integer)
    timestamp = Column(String)

    @property
    def spread(self):
        return self.ask - self.bid

    @property
    def spread_pct(self):
        return round(self.spread / self.ask * 100, 2)

    def time(self):
        time = datetime.strptime(self.timestamp, '%Y-%m-%dT%H:%M:%S.%f')
        return time.strftime('%d/%m/%Y - %H:%M (UTC)')

    def formatted_price(self):
        return "${value} ({code})".format(value=self.ask, code=self.code[3:])

    def valid_alerts(self):
        """Return those alerts that satisfy its conditions."""
        filters = [
            and_(Market.ask < Alert.price, Alert.trigger_on_lower == True),
            and_(Market.ask > Alert.price, Alert.trigger_on_lower == False),
        ]
        query = session.query(Alert).join(Chat).join(Market).filter(Market.id == self.id).filter(or_(*filters))
        return query.all()


class Alert(Base):
    """A user price alert"""
    chat_id = Column(ForeignKey('chat.id', ondelete='CASCADE'), nullable=False)
    chat = relationship('Chat', backref='alerts')
    price = Column(Integer)
    trigger_on_lower = Column(Boolean, nullable=False)

    def __str__(self):
        sign = 'menor' if self.trigger_on_lower else 'mayor'
        return "Precio {} a ${}".format(sign, self.price)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
