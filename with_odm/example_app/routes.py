__all__ = ['app', 'index', 'list_', 'add', 'edit', 'update', 'delete']

import bson
from flask import jsonify, redirect, render_template, request, url_for

from app import app
from models.user import User


@app.route('/')
def index():
    return redirect(url_for('list_'))


@app.route('/list')
def list_():  # trailing underscore to dont shadow builtins.list (standard)
    return render_template('list.html', users=User.get_all())


@app.route('/add')
def add():
    user = User('New worker', '+34123456789')
    user.save()

    return jsonify(user.to_dict())


@app.route('/edit', methods=['POST'])
def edit():
    return render_template('user.html', user=User(**request.form))


@app.route('/update', methods=['POST'])
def update():
    User(**request.form, find_existing=False).save()
    return redirect(url_for('list_'))


@app.route('/delete')
def delete():
    try:
        User(_id=request.args.get('id')).delete()
    except bson.errors.InvalidId:
        return 'bad ObjectId', 400

    return '', 204
