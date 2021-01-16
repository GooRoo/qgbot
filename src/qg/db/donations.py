from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime

from .common import CATEGORY_TAG_MAX_LEN, Base


class Donation(Base):
    __tablename__ = 'Donations'

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey('Users.id'))
    created_on = Column(DateTime)
    price = Column(Numeric(5))
    total = Column(Numeric(7, 2))
    currency = Column(String(3))
    paid_on = Column(DateTime)
    telegram_charge_id = Column(String)
    provider_charge_id = Column(String)

    user = relationship('User', back_populates='donations')

    def is_paid(self):
        return not (
            self.paid_on is None
            or self.telegram_charge_id is None
            or self.provider_charge_id is None
        )

    def __repr__(self):
        return f'<Donation(id={self.id}, user_id={self.user_id}, price={self.price}, total={self.total})>'
