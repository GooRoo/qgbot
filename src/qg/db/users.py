from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from qg.utils.helpers import mention_md

from .common import Base

class User(Base):
    __tablename__ = 'Users'

    id = Column(Integer, primary_key=True, autoincrement=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    username = Column(String, unique=True)
    is_admin = Column(Boolean, default=False)

    requests = relationship('Request', back_populates='user')
    votes = relationship('Vote', back_populates='user')

    def __repr__(self):
        return f'<User(id={self.id}, first_name="{self.first_name}", last_name="{self.last_name}", ' \
               f'username="{self.username}", is_admin={self.is_admin})>'

    def username_or_name(self):
        if self.username is not None and self.username != '':
            return f'@{self.username}'
        else:
            name = self.first_name
            if self.last_name is not None and self.last_name != '':
                name += f' {self.last_name}'
            return name

    def username_or_id_and_name(self):
        if self.username is not None and self.username != '':
            return f'@{self.username}'
        else:
            name = f'{self.id} - {self.first_name}'
            if self.last_name is not None and self.last_name != '':
                name += f' {self.last_name}'
            return name

    def mention_md(self):
        return mention_md(self.id, self.username_or_name())
