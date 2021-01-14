from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import MONEY
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime

from .common import CATEGORY_TAG_MAX_LEN, Base


class Donation(Base):
    __tablename__ = 'Donations'

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey('Users.id'))
    created_on = Column(DateTime)
    total_amount = Column(MONEY)
    currency = Column(String(3))
    paid_on = Column(DateTime)
    telegram_charge_id = Column(String)
    provider_charge_id = Column(String)

    user = relationship('User', back_populates='donations')

    def __repr__(self):
        return f'<Donation(id={self.id}, user_id={self.user_id})>'
