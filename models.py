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
    market_id = Column(ForeignKey('market.id'), nullable=False)
    market = relationship('Market', backref='chats')


class Market(Base):
    code = Column(String, nullable=False, unique=True)
    price = Column(Integer)
    timestamp = Column(String)

    def valid_alerts(self):
        """Return those alerts that satisfy its conditions."""
        filters = [
            and_(Market.price < Alert.price, Alert.trigger_on_lower == True),
            and_(Market.price > Alert.price, Alert.trigger_on_lower == False),
        ]
        query = session.query(Alert).join(Chat).join(Market).filter(Market.id == self.id).filter(or_(*filters))
        return query.all()


class Alert(Base):
    """A user price alert

    If the coin price at the moment the alarm is set is lower than alert.price,
    the alarm will trigger when the coin price becomes higher than alert.price.
    Otherwise, it will trigger when the coin price becomes lower.
    """
    chat_id = Column(ForeignKey('chat.id'), nullable=False)
    chat = relationship('Chat', backref='alerts')
    price = Column(Integer)
    trigger_on_lower = Column(Boolean, nullable=False)

    def __str__(self):
        sign = 'menor' if self.trigger_on_lower else 'mayor'
        return "Precio {} a ${}".format(sign, self.price)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
