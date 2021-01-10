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

    requests = relationship('Request', back_populates='user')
    votes = relationship('Vote', back_populates='user')

    def __repr__(self):
        return f'<User(id={self.id}, first_name="{self.first_name}", last_name="{self.last_name}", ' \
               f'username="{self.username}", is_admin={self.is_admin})>'

    def username_or_name(self):
        if self.username is not None and self.username != '':
            return self.username
        else:
            name = self.first_name
            if self.last_name is not None and self.last_name != '':
                name += f' {self.last_name}'
            return name
