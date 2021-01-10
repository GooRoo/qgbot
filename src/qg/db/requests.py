from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from .common import Base, CATEGORY_TAG_MAX_LEN

class Request(Base):
    __tablename__ = 'Requests'

    id = Column(String(256), primary_key=True)
    user_id = Column(Integer, ForeignKey('Users.id'))
    category_tag = Column(String(CATEGORY_TAG_MAX_LEN), ForeignKey('Categories.tag'))
    text = Column(String, nullable=False)

    votes = relationship('Vote', back_populates='request',
                                 cascade='all, delete-orphan',
                                 passive_deletes=True)

    def __repr__(self):
        return f'<Request(id={self.id}, user_id={self.user_id}, category_tag={self.category_tag}, text={self.text})>'
