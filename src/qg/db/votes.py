from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from .common import Base

class Vote(Base):
    __tablename__ = 'Votes'

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('Requests.id'))
    user_id = Column(Integer, ForeignKey('Users.id'))
    upvote = Column(Boolean, nullable=False)

    request = relationship('Request', back_populates='votes')

    def __repr__(self):
        return f'<Vote(id={self.id}, request_id={self.request_id}, user_id={self.user_id}, '\
               f'upvote?={self.upvote})>'
