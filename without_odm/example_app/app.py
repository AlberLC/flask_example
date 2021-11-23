from json import JSONEncoder
from typing import Any

from bson import ObjectId
from flask import Flask


class MongoJSONEncoder(JSONEncoder):
    """
    Custom JSONEncoder for jsonify(). Now it can encode ObjectId to str.
    """

    def default(self, obj: Any) -> Any:
        match obj:
            case ObjectId() as object_id:
                return str(object_id)
            case _:
                return super().default(obj)


app = Flask(__name__)
app.json_encoder = MongoJSONEncoder
