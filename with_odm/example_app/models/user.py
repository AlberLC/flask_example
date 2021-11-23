from dataclasses import dataclass, field

import pymongo
from models.bases import FlanaBase, MongoBase
from models.database import db


@dataclass
class User(MongoBase, FlanaBase):
    _collection: pymongo.collection.Collection = field(init=False, default=db.user)

    name: str = ''
    phone: str = ''  # No need for `int`. Best `str` to manage future manipulations (area codes, etc)

    def __init__(self, name: str = '', phone: str = '', *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.find_existing and (document := self._collection.find_one({'_id': self.id})):
            self.__dict__ |= vars(self.from_dict(document))
        else:
            self.name = name
            self.phone = phone

    @property
    def id(self):
        return self._id
