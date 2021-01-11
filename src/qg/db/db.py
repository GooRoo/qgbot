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

    def add_user(self, id, first_name, last_name=None, username=None, is_admin=False):
        s = self.start_session()
        new_user = User(
            id=id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_admin=is_admin
        )
        s.merge(new_user)
        s.commit()
        logger.success(f'User has been added: {new_user}')
        return new_user

    def _get_or_add_user(self, id, first_name, last_name=None, username=None, is_admin=False):
        try:
            user = self._get_user(id)
            logger.info('User has been found')
        except NoResultFound:
            logger.warning('No such user has been found in the database. Adding…')
            user = self.add_user(
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

    def find_user_by_username(self, username):
        s = self.start_session()
        return s.query(User).filter(User.username == username).one_or_none()

    def get_admins(self):
        s = self.start_session()
        return s.query(User).filter(User.is_admin == True).order_by(User.first_name, User.username)

    def remove_admin(self, user_id):
        s = self.start_session()
        admin_but_not_for_long = s.query(User).get(user_id)
        admin_but_not_for_long.is_admin = False
        s.commit()

    def add_category(self, tag, name):
        s = self.start_session()
        s.add(Category(tag=tag, name=name))
        s.commit()

    def remove_category(self, category_id):
        s = self.start_session()
        category = s.query(Category).get(category_id)
        s.delete(category)
        s.commit()

    def get_categories(self):
        s = self.start_session()
        return {
            tag: (name, url)
            for tag, name, url in s.query(Category.tag, Category.name, Category.url).order_by(Category.name)
        }

    def add_request(self, request_id, user, category_tag, text):
        s = self.start_session()
        u = self._get_or_add_user(user.id, user.first_name, user.last_name, user.username)

        request = Request(
            id=request_id,
            user_id=u.id,
            category_tag=category_tag,
            text=text
        )
        s.add(request)
        s.commit()
        logger.success(f'New request has been registered: {request}')

    def add_vote(self, request_id, user, upvote):
        s = self.start_session()
        u = self._get_or_add_user(user.id, user.first_name, user.last_name, user.username)

        vote = Vote(
            request_id=request_id,
            user_id=u.id,
            upvote=upvote
        )
        s.merge(vote)
        s.commit()
        logger.success(f'New vote has been registered: {vote}')

    def get_request(self, id):
        s = self.start_session()
        return s.query(Request).filter(Request.id == id).one()

    def has_voted(self, request_id, user, vote):
        s = self.start_session()
        return s.query(Vote).\
            filter(Vote.request_id == request_id,
                   Vote.user_id == user.id,
                   Vote.upvote == vote).\
            count() > 0

    def revoke_vote(self, request_id, user):
        s = self.start_session()
        s.query(Vote).filter(Vote.request_id == request_id, Vote.user_id == user.id).delete()
        s.commit()
        logger.success(f'Vote on message "{request_id}" by the user "{user}" has been removed')

    def get_votes(self, request_id):
        s = self.start_session()
        return s.query(Vote).filter(Vote.request_id == request_id).order_by(Vote.upvote)
