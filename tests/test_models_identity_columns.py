from app import create_app
from app.extensions import db
from app.models import User


def _app():
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
    })


def test_user_table_has_identity_columns():
    app = _app()
    with app.app_context():
        db.create_all()
        columns = {column.name for column in User.__table__.columns}

    assert "identity_source" in columns
    assert "nidn" in columns


def test_identity_columns_default_to_null():
    app = _app()
    with app.app_context():
        db.create_all()
        user = User(full_name="Uji", email="uji@test.local", role="student")
        user.set_password("password-uji-123")
        db.session.add(user)
        db.session.commit()

        assert user.identity_source is None
        assert user.nidn is None
