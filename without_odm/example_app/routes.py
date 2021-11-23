__all__ = ['app', 'index', 'list_', 'add', 'edit', 'update', 'delete']

import bson
from bson import ObjectId
from flask import jsonify, redirect, render_template, request, url_for
from pymongo.cursor import Cursor

from app import app
from models.database import db
from models.user import User


@app.route('/')
def index():
    return redirect(url_for('list_'))


@app.route('/list')
def list_():  # trailing underscore to dont shadow builtins.list (standard)
    user_documents: Cursor = db.user.find({})
    users: list[User] = [User(**user_document) for user_document in user_documents]

    return render_template('list.html', users=users)


@app.route('/add')
def add():
    user_dict = vars(User(name='New worker', phone='+34123456789')).copy()
    db.user.insert_one(user_dict)

    return jsonify(user_dict)


@app.route('/edit', methods=['POST'])
def edit():
    user_document = db.user.find_one({'_id': ObjectId(request.form.get('id'))})

    return render_template('user.html', user=User(**user_document))


@app.route('/update', methods=['POST'])
def update():
    user = User(request.form.get('id'), request.form.get('name'), request.form.get('phone'))
    db.user.find_one_and_update({'_id': user.id}, {'$set': vars(user)})

    return redirect(url_for('list_'))


@app.route('/delete')
def delete():
    id = request.args.get('id')
    try:
        db.user.delete_one({'_id': ObjectId(id or '')})
    except bson.errors.InvalidId:
        return 'bad ObjectId', 400

    return '', 204
