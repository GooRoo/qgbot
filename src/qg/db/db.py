from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .common import Base
from .categories import Category
from .users import User

class DB(object):
    def __init__(self, user='', password='', db='', host='localhost', port=5432, *, full_uri='', echo=False):
        if full_uri:
            self.engine = create_engine(full_uri, echo=echo)
        else:
            self.engine = create_engine(
                f'postgresql://{user}:{password}@{host}:{port}/{db}',
                echo=echo
            )

        self.session_factory = sessionmaker(bind=self.engine)
        self.scoped_session = scoped_session(self.session_factory)

    def session(self):
        return self.scoped_session()

    def end_session(self):
        self.scoped_session.remove()

    def create_all(self, admins=[], categories=[]):
        Base.metadata.create_all(self.engine)

        s = self.session()

        for admin in admins:
            s.merge(User(**admin, is_admin=True))
        s.commit()

        for category in categories:
            s.merge(Category(**category))
        s.commit()

        self.end_session()

    def get_user(self, user_id):
        s = self.session()
        return s.query(User).get(user_id)

    def add_user(self, id, first_name, last_name=None, username=None, is_admin=False):
        s = self.session()
        s.add(User(
            id=id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_admin=is_admin
        ))
        s.commit()

    def add_category(self, tag, name):
        s = self.session()
        s.add(Category(tag=tag, name=name))
        s.commit()

    def remove_category(self, category_id):
        s = self.session()
        s.query(Category).get(category_id).delete()
        s.commit()
