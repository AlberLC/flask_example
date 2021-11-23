from dataclasses import dataclass

from bson import ObjectId


@dataclass
class User:
    _id: str | ObjectId = None
    name: str = ''
    phone: str = ''  # No need for `int`. Best `str` to manage future manipulations (area codes, etc)

    def __init__(self, _id: ObjectId = None, name: str = '', phone: str = ''):
        """
        Construct the User object.

        If _id is None, it create automatically a unique ObjectId.
        If _id is not None try to create an ObjectId. It can raise ValueError.
        """

        match _id:
            case str(id) if id:
                self._id = ObjectId(id)
            case str() | None:
                self._id = ObjectId()
            case ObjectId() as object_id:
                self._id = object_id
            case _:
                raise ValueError('bad ObjectId')

        self.name = name
        self.phone = phone

    @property
    def id(self):
        return self._id
