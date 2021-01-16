from datetime import datetime
from uuid import uuid4

from qg.logger import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from .categories import Category
from .common import Base
from .donations import Donation
from .requests import Request
from .users import User
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
        logger.info('Creating the database scheme…')
        Base.metadata.create_all(self.engine)
        logger.success('Done.')

        s = self.start_session()

        logger.info('Pre-filling the admins…')
        for admin in admins:
            s.merge(User(**admin, is_admin=True))
        s.commit()
        logger.success('Done.')

        logger.info('Pre-filling the categories…')
        for category in categories:
            s.merge(Category(**category))
        s.commit()
        logger.success('Done.')

        self.end_session()

    def _get_user(self, user_id):
        '''Get a User by id or raise an exception otherwise'''
        s = self.start_session()
        logger.info(f'Looking for a user with id "{user_id}')
        return s.query(User).filter(User.id == user_id).one()

    def add_user(self, id, first_name, last_name=None, username=None, is_admin=False):
        '''Add user (overwriting fields if it's already in the database)'''
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
        '''Get a User by id or None otherwise'''
        s = self.start_session()
        return s.query(User).get(user_id)

    def find_user_by_username(self, username):
        '''Get a User by username or None otherwise'''
        s = self.start_session()
        return s.query(User).filter(User.username == username).one_or_none()

    def get_admins(self):
        '''Get admin Users ordered by names'''
        s = self.start_session()
        return s.query(User).filter(User.is_admin == True).order_by(User.first_name, User.username)

    def remove_admin(self, user_id):
        '''Update the is_admin field on a User'''
        s = self.start_session()
        admin_but_not_for_long = s.query(User).get(user_id)
        admin_but_not_for_long.is_admin = False
        s.commit()
        logger.success(f'User {admin_but_not_for_long} is not admin anymore.')

    def add_category(self, tag, name, url):
        '''Add category (overwriting fields if it's already in the database)'''
        s = self.start_session()
        new_category = Category(tag=tag, name=name, url=url)
        s.merge(new_category)
        s.commit()
        logger.success(f'Category is added: {new_category}')

    def remove_category(self, category_id):
        '''Remove category by id'''
        s = self.start_session()
        category = s.query(Category).get(category_id)
        s.delete(category)
        s.commit()
        logger.success(f'Category "{category_id}" is removed.')

    def get_categories(self):
        '''
        Return a dictionary where every key is a hashtag and
        every value is a tuple of a name and a playlist URL
        '''
        s = self.start_session()
        return {
            tag: (name, url)
            for tag, name, url in s.query(Category.tag, Category.name, Category.url).order_by(Category.name)
        }

    def add_request(self, request_id, user, category_tag, text):
        '''
        Create new Request for voting.
        If a creator of the request is not yet in the database,
        s/he is added along with the request.
        '''
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
        '''
        Add a Vote for a particular request (overwriting previous value).
        If a person who left the vote is not yet in the database,
        s/he is added along with the request.
        '''
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
        '''Get Request by id or None otherwise'''
        s = self.start_session()
        return s.query(Request).get(id)

    def has_voted(self, request_id, user, vote):
        '''Check if there is a Vote on this Request by this User in the database'''
        s = self.start_session()
        return (
            s.query(Vote)
            .filter(Vote.request_id == request_id,
                    Vote.user_id == user.id,
                    Vote.upvote == vote)
            .count()
        ) > 0

    def revoke_vote(self, request_id, user):
        '''Remove the vote by the User on the particular Request'''
        s = self.start_session()
        s.query(Vote).filter(Vote.request_id == request_id, Vote.user_id == user.id).delete()
        s.commit()
        logger.success(f'Vote on message "{request_id}" by the user "{user}" has been removed')

    def get_votes(self, request_id):
        '''Get all Votes on a single Request grouped by vote results'''
        s = self.start_session()
        return s.query(Vote).filter(Vote.request_id == request_id).order_by(Vote.upvote)

    def get_top_reviewers(self):
        '''Get Users with maximum numbers of Votes'''
        s = self.start_session()

        # Count votes
        votes = (
            s.query(
                Vote.user_id,
                func.count('*').label('votes_count'))
            .group_by(Vote.user_id)
            .limit(5)
        ).subquery()

        # Return user info
        return (
            s.query(
                User,
                votes.c.votes_count)
            .join(votes, User.id == votes.c.user_id)
            .order_by(
                votes.c.votes_count.desc(),
                User.username,
                User.first_name)
        )

    def get_top_committers(self):
        '''Get Users with maximum number of requests'''
        s = self.start_session()

        # Count requests
        requests = (
            s.query(
                Request.user_id,
                func.count('*').label('requests_count'))
            .group_by(Request.user_id)
            .limit(5)
        ).subquery()

        # Return user info
        return (
            s.query(
                User,
                requests.c.requests_count)
            .join(requests, User.id == requests.c.user_id)
            .order_by(
                requests.c.requests_count.desc(),
                User.username,
                User.first_name)
        )

    def get_best_committers(self):
        '''Get Users with maximum upvotes on all their requests'''
        s = self.start_session()

        # Count upvotes on each request
        votes = (
            s.query(
                Vote.request_id,
                func.count('*').label('votes_count'))
            .filter(Vote.upvote == True)
            .group_by(Vote.request_id)
        ).subquery()

        # Get a total number of votes on all requests of each user
        requests = (
            s.query(
                Request.user_id,
                func.sum(votes.c.votes_count).label('votes_sum'))
            .join(votes, Request.id == votes.c.request_id)
            .group_by(Request.user_id)
            .limit(5)
        ).subquery()

        # Return user info with calculated sum of votes
        return (
            s.query(
                User,
                requests.c.votes_sum)
            .join(requests, User.id == requests.c.user_id)
            .order_by(
                requests.c.votes_sum.desc(),
                User.username,
                User.first_name)
        )

    def create_invoice(self, user, price, total, currency):
        '''Create Donation and return its id'''
        s = self.start_session()
        u = self._get_or_add_user(user.id, user.first_name, user.last_name, user.username)
        d = Donation(
            id=str(uuid4()),
            user_id=u.id,
            created_on=datetime.now(),
            price=price,
            total=total,
            currency=currency
        )
        s.add(d)
        s.commit()
        logger.success(f'New invoice is added: {d}')
        return d.id

    def get_invoice(self, invoice_id):
        '''Get Donation by id or None otherwise'''
        s = self.start_session()
        return s.query(Donation).get(invoice_id)

    def update_invoice(self, invoice_id, tg_charge_id, provider_charge_id):
        '''Add the missing fields to the invoice'''
        s = self.start_session()
        invoice: Donation = s.query(Donation).get(invoice_id)
        invoice.paid_on = datetime.now()
        invoice.telegram_charge_id = tg_charge_id
        invoice.provider_charge_id = provider_charge_id
        s.commit()

    def get_donators(self):
        '''Get list of Users with amount of donations'''
        s = self.start_session()

        # Calculate sum of donations
        donations = (
            s.query(
                Donation.user_id,
                func.sum(Donation.total).label('total_sum'))
            .filter(
                Donation.paid_on != None,
                Donation.telegram_charge_id != None,
                Donation.provider_charge_id != None)
            .group_by(Donation.user_id)
        ).subquery()

        # Return user info
        return (
            s.query(
                User,
                donations.c.total_sum)
            .join(donations, User.id == donations.c.user_id)
            .order_by(
                donations.c.total_sum.desc(),
                User.username,
                User.first_name)
        )
