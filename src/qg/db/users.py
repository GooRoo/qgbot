from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from .common import Base

class User(Base):
    __tablename__ = 'Users'

    id = Column(Integer, primary_key=True, autoincrement=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    username = Column(String)
    is_admin = Column(Boolean, default=False)

    requests = relationship('Request')
    # votes = relationship('Vote')

    def __repr__(self):
        return f'<User(id={self.id}, first_name="{self.first_name}", last_name="{self.last_name}", ' \
               f'username="{self.username}", is_admin={self.is_admin})>'
