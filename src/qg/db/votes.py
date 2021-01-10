from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from .common import Base

class Vote(Base):
    __tablename__ = 'Votes'

    request_id = Column(String(256), ForeignKey('Requests.id'), primary_key=True)
    user_id = Column(Integer, ForeignKey('Users.id'), primary_key=True)
    upvote = Column(Boolean, nullable=False)

    request = relationship('Request', back_populates='votes')
    user = relationship('User', back_populates='votes')

    def __repr__(self):
        return f'<Vote(request_id={self.request_id}, user_id={self.user_id}, upvote?={self.upvote})>'
