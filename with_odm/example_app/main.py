import os

from routes import *

if __name__ == '__main__':
    app.run(host=os.getenv('FLASK_ADDRESS'))
