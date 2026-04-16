from flask import Flask
from flask_login import LoginManager

from auth import get_user_by_id
from config import Config
from routes import main_bp

login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Sign in to access your dashboard."


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)


def create_app(test_config=None):
    flask_app = Flask(__name__)
    flask_app.config["SECRET_KEY"] = Config.SECRET_KEY
    flask_app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER
    flask_app.config["RUNTIME_FOLDER"] = Config.RUNTIME_FOLDER

    if test_config:
        flask_app.config.update(test_config)

    login_manager.init_app(flask_app)
    flask_app.register_blueprint(main_bp)

    return flask_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
