from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

CATEGORY_NAME_MAX_LEN = 256
CATEGORY_TAG_MAX_LEN = 256 - len('_request')
