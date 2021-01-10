from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from qg.logger import logger

from .common import Base
from .categories import Category
from .users import User
from .requests import Request
from .votes import Vote

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

    def start_session(self):
        return self.scoped_session()

    def end_session(self):
        self.scoped_session.remove()

    def session(self):
        class _DbSession(object):
            def __enter__(this):
                return self.start_session()

            def __exit__(this, type, value, traceback):
                self.end_session()
        return _DbSession()

    def create_all(self, admins=[], categories=[]):
        Base.metadata.create_all(self.engine)

        s = self.start_session()

        for admin in admins:
            s.merge(User(**admin, is_admin=True))
        s.commit()

        for category in categories:
            s.merge(Category(**category))
        s.commit()

        self.end_session()

    def _get_user(self, user_id):
        s = self.start_session()
        return s.query(User).filter(User.id == user_id).one()

    def _add_user(self, id, first_name, last_name=None, username=None, is_admin=False):
        s = self.start_session()
        new_user = User(
            id=id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_admin=is_admin
        )
        s.add(new_user)
        s.commit()
        logger.success('User has been added: {}', new_user)
        return new_user

    def _get_or_add_user(self, id, first_name, last_name=None, username=None, is_admin=False):
        try:
            user = self._get_user(id)
            logger.info('User has been found')
        except NoResultFound as e:
            logger.warning('No such user has been found in the database. Adding…')
            user = self._add_user(
                id=id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                is_admin=is_admin
            )
        return user

    def find_user(self, user_id):
        s = self.start_session()
        return s.query(User).filter(User.id == user_id).one_or_none()

    def add_category(self, tag, name):
        s = self.start_session()
        s.add(Category(tag=tag, name=name))
        s.commit()

    def remove_category(self, category_id):
        s = self.start_session()
        s.query(Category).get(category_id).delete()
        s.commit()

    def get_categories(self):
        with self.session() as s:
            return {
                tag: name
                for tag, name in s.query(Category.tag, Category.name).order_by(Category.name)
            }

    def add_request(self, message_id, user, category_tag, text):
        with self.session() as s:
            u = self._get_or_add_user(user.id, user.first_name, user.last_name, user.username)

            request = Request(
                id=message_id,
                user_id=u.id,
                category_tag=category_tag,
                text=text
            )
            s.add(request)
            s.commit()
            logger.success('New request has been registered: {}', request)

    def add_vote(self, message_id, user, upvote):
        with self.session() as s:
            u = self._get_or_add_user(user.id, user.first_name, user.last_name, user.username)

            vote = Vote(
                request_id=message_id,
                user_id=u.id,
                upvote=upvote
            )
