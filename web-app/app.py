from flask import Flask

from config import Config
from routes import main_bp


def create_app(test_config=None):
    flask_app = Flask(__name__)
    flask_app.config["SECRET_KEY"] = Config.SECRET_KEY
    flask_app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER
    flask_app.config["RUNTIME_FOLDER"] = Config.RUNTIME_FOLDER

    if test_config:
        flask_app.config.update(test_config)

    flask_app.register_blueprint(main_bp)

    return flask_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
