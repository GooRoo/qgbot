import itertools
from typing import Any, List

import telegram.utils.helpers


def flatten(l: List[List[Any]]) -> List[Any]:
    return list(itertools.chain.from_iterable(l))


def escape_md(text):
    return telegram.utils.helpers.escape_markdown(text, version=2)
