from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from .common import CATEGORY_NAME_MAX_LEN, CATEGORY_TAG_MAX_LEN, Base


class Category(Base):
    __tablename__ = 'Categories'

    tag = Column(String(CATEGORY_TAG_MAX_LEN), primary_key=True)
    name = Column(String(CATEGORY_NAME_MAX_LEN))
    url = Column(String)

    requests = relationship('Request')

    def __repr__(self):
        return f'<Category(tag={self.tag}, name={self.name}, url={self.url})>'
