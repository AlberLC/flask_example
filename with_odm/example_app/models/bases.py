"""
Module taken from my personals projects to use MongoBase, an ODM that I have been developing days ago.

See the differences in `routes.py`.
"""

from __future__ import annotations  # todo0 remove in 3.11

import base64
import binascii
import copy
import datetime
import json
import pickle
import pprint
import typing
from enum import Enum
from typing import Any, Type, TypeVar

import pymongo.collection
import pymongo.database
from bson import ObjectId


def find(elements: typing.Iterable, target: Any = None, condition: typing.Callable[..., bool] = None) -> Any:
    """
    Smart function that find anything in a iterable (classes, objects, ...).

    If condition is not None, return the first element that matches it.

    Return None if nothing matches.
    """

    if condition is None:
        if isinstance(target, type) or isinstance(typing.get_origin(target), type | type(typing.Union)):
            def condition(element: Any) -> bool:
                try:
                    return issubclass(element, target)
                except TypeError:
                    return isinstance(element, target)
        else:
            def condition(element: Any) -> bool:
                return element == target

    return next((element for element in elements if condition(element)), None)


class BytesBase:
    """Base class for serialize objects to bytes with pickle."""

    def __bytes__(self):
        return pickle.dumps(self)

    @staticmethod
    def from_bytes(bytes_: bytes) -> Any:
        return pickle.loads(bytes_)

    def to_bytes(self):
        return bytes(self)


class CopyBase:
    """Base class for copy and deepcopy objects."""

    def copy(self) -> CopyBase:
        return copy.copy(self)

    def deep_copy(self) -> CopyBase:
        return copy.deepcopy(self)


class DictBase:
    """Base class for serialize objects to dict."""

    def _dict_repr(self) -> dict:
        """
        Returns the dict representation of your object.

        It is the only method that you would want redefine in most cases to represent data.
        """

        return vars(self).copy()

    @classmethod
    def from_dict(cls, data: dict, lazy=True) -> DictBase:
        def decode_dict(cls_, data_: dict) -> Any:
            new_data = copy.deepcopy(data_)
            type_hints = typing.get_type_hints(cls_)
            for k, v in data_.items():
                try:
                    type_ = type_hints[k]
                except (KeyError, TypeError):
                    continue

                type_origin = typing.get_origin(type_)
                type_args = typing.get_args(type_)
                try:
                    value_type = type_args[-1]
                except (IndexError, TypeError):
                    value_type = type

                match v:
                    case dict() if issubclass(type_, DictBase) and lazy:
                        continue
                    case dict(dict_) if issubclass(type_, DictBase) and not lazy:
                        new_data[k] = decode_dict(type_, dict_)
                    case dict(dict_) if issubclass(type_origin, dict) and issubclass(value_type, DictBase):  # todo1 doesn't work for deep objects within dictionaries
                        new_data[k] = decode_dict(dict, dict_)
                    # case [*_] as list_ if not isinstance(list_, set) and issubclass(type_origin, list) and issubclass(value_type, DictBase):
                    #     new_data[k] = decode_dict(list, list_)  #todo6 revisar esto que es
                    case bytes(bytes_) if type_ is not bytes:
                        new_data[k] = pickle.loads(bytes_)

            return new_data if issubclass(cls_, dict) else cls_(**new_data | {'find_existing': False})

        return decode_dict(cls, data)

    def to_dict(self) -> dict:
        self_vars = self._dict_repr().copy()

        for k, v in self_vars.items():
            match v:
                case DictBase() as obj:  # todo1 if there is an object inside a dictionary look at class type_hints -> if no info then to_bytes
                    self_vars[k] = obj.to_dict()
                case [*_, DictBase()]:
                    self_vars[k] = [obj.to_dict() for obj in v]
                case (set() | Enum()) as obj:
                    self_vars[k] = pickle.dumps(obj)

        return self_vars


class JSONBASE:
    """Base class for serialize objects to json."""

    def _json_repr(self) -> Any:
        """
        Returns the JSON representation of your object.

        It is the only method that you would want redefine in most cases to represent data.
        """

        return vars(self)

    @classmethod
    def from_json(cls, text: str) -> Any:
        def decode_str(obj_: Any) -> Any:
            if not isinstance(obj_, str):
                return obj_
            try:
                bytes_ = base64.b64decode(obj_.encode(), validate=True)
                decoded_obj = pickle.loads(bytes_)
            except (binascii.Error, pickle.UnpicklingError, EOFError):
                return obj_
            return decoded_obj

        def decode_dict(cls_: Any, dict_: dict) -> Any:
            kwargs = {}
            for k, v in dict_.items():
                k = decode_str(k)
                v = decode_str(v)
                if isinstance(v, dict):
                    try:
                        v = decode_dict(typing.get_type_hints(cls_)[k], v)  # todo1 doesn't search for objects within dictionaries
                    except KeyError:
                        pass
                kwargs[k] = v
            return cls_(**kwargs)

        if not isinstance(text, str):
            raise TypeError(f'must be str, not {type(text).__name__}')

        obj = json.loads(text)
        if isinstance(obj, str):
            return decode_str(obj)
        elif isinstance(obj, list):
            return [decode_str(e) for e in obj]
        elif isinstance(obj, dict):
            return decode_dict(cls, obj)
        else:
            return obj

    def to_json(self, indent: int = None) -> str:
        def json_encoder(obj: Any) -> Any:
            if isinstance(obj, bytes):
                return base64.b64encode(obj).decode()

            match obj:
                case set():
                    return list(obj)
                case JSONBASE():
                    # noinspection PyProtectedMember
                    return obj._json_repr()
                case (datetime.date() | datetime.datetime()) as dt:
                    return str(dt)
                case _:
                    try:
                        return json.dumps(obj)
                    except TypeError:
                        return repr(obj)

        return json.dumps(self, default=json_encoder, indent=indent)


class REPRBase(DictBase):
    """Base class for a nicer objects representation."""

    def __repr__(self):
        values = vars(self).values()
        return f"{self.__class__.__name__}({', '.join(repr(v) for v in values)})"

    def __str__(self):
        formatted = pprint.pformat(self.to_dict())
        return f'{self.__class__.__name__} {formatted[0]}\n {formatted[1:-1]}\n{formatted[-1]}'  # todo1 someday improve the internal objects appearance


T = TypeVar('T', bound='MongoBase')


class MongoBase(DictBase):
    """
    Base class for mapping objects to mongo documents and vice versa (Object Document Mapper).

    Dataclass compatible.
    """

    _id: ObjectId = None
    _collection: pymongo.collection.Collection = None
    _database: pymongo.database.Database = None
    find_existing: bool = True

    def __init__(self, _id: str | ObjectId = None, find_existing=True):
        """Automatically generate an ObjectId and store references to the database and collection."""

        match _id:
            case str() if _id:
                self._id = ObjectId(_id)
            case ObjectId() as object_id:
                self._id = object_id
            case _:
                self._id = ObjectId()

        if self._collection is not None:
            super().__setattr__('_collection', self._collection)
            super().__setattr__('_database', self._collection.database)

        super().__setattr__('find_existing', find_existing)

    def __getattribute__(self, attribute_name):
        """
        Advice: Do not redefine this method.

        This very hacky method is called every time an class attribute is accessed. It is very difficult to implement
        since it is called recursively.

        So don't redefine this method if you don't really know how python treats objects internally.
        """

        value = super().__getattribute__(attribute_name)

        match value:
            case ObjectId() as object_id:
                documents = self.find_in_database(object_id)
            case [*_, ObjectId()] as object_ids:
                documents = [self.find_in_database(object_id) for object_id in object_ids]
            case _:
                return value

        try:
            type_ = typing.get_type_hints(self.__class__)[attribute_name]
        except KeyError:
            return value

        match documents:
            case [*_, dict()] if type_arg := find(typing.get_args(type_), MongoBase):
                value = [type_arg.from_dict(document) for document in documents]
            case dict(document) if issubclass(type_, MongoBase):
                value = type_.from_dict(document)
            case _:
                return value

        setattr(self, attribute_name, value)
        return value

    def __post_init__(self):
        if self._id is None:
            MongoBase.__init__(self)

    def _dict_repr(self) -> dict:
        return {k: v for k, v in vars(self).items() if k not in ('_collection', '_database', 'find_existing')}

    def _json_repr(self) -> Any:
        self_vars = vars(self).copy()
        self_vars['_id'] = repr(self_vars['_id'])

        return {k: v for k, v in self_vars.items() if k not in ('_collection', '_database', 'find_existing')}

    def delete(self, cascade=False):
        """
        Delete the object from the database.

        If cascade=True all objects whose classes inherit from MongoBase are also deleted.
        """

        if cascade:
            for referenced_object in self.get_referenced_objects():
                referenced_object.delete(cascade)

        self._collection.delete_one({'_id': self._id})

    def find_in_database(self, object_id: ObjectId) -> dict | None:
        """Find a object in all database collections by its ObjectId."""

        collections = (self._database.get_collection(name) for name in self._database.list_collection_names())
        return next((document for collection in collections if (document := collection.find_one({'_id': object_id}))), None)

    @classmethod
    def get_all(cls: Type[T]) -> list[T]:
        user_documents: pymongo.cursor.Cursor = cls._collection.find({})
        return [cls(**user_document) for user_document in user_documents]

    def get_referenced_objects(self) -> list[MongoBase]:
        """Returns all referenced objects whose classes inherit from MongoBase."""

        self.resolve()

        referenced_objects = []
        for k, v in vars(self).items():
            match v:
                case MongoBase() as obj:
                    referenced_objects.append(obj)
                case [*_, MongoBase()] as objs:
                    referenced_objects.extend(obj for obj in objs if isinstance(obj, MongoBase))

        return referenced_objects

    def resolve(self):
        """Resolve all the ObjectId references (ObjectId -> MongoBase)."""

        for k in vars(self):
            getattr(self, k)

    def save(self, references=True):
        """
        Save (insert or update) the current object in the database.

        If references=True it saves the objects without redundancy (MongoBase -> ObjectId).
        """

        for referenced_object in self.get_referenced_objects():
            referenced_object.save()

        data = self.to_dict()

        if references:
            for k, v in data.items():
                match v:
                    case {'_id': ObjectId() as object_id}:
                        data[k] = object_id
                    case [*_, {'_id': ObjectId()}]:
                        data[k] = [obj_data['_id'] for obj_data in v]

        self._collection.find_one_and_update({'_id': self._id}, {'$set': data}, upsert=True)


class FlanaBase(REPRBase, JSONBASE, CopyBase, BytesBase):
    """Useul mixin."""


# noinspection PyPropertyDefinition
class FlanaEnum(JSONBASE, DictBase, CopyBase, BytesBase, Enum):
    """Useful mixin for enums."""

    def _dict_repr(self):
        return bytes(self)

    def _json_repr(self):
        return bytes(self)

    @classmethod
    @property
    def items(cls) -> list[tuple[str, int]]:
        # noinspection PyTypeChecker
        return [item for item in zip(cls.keys, cls.values)]

    @classmethod
    @property
    def keys(cls) -> list[str]:
        return [element.name for element in cls]

    @classmethod
    @property
    def values(cls) -> list[int]:
        return [element.value for element in cls]
