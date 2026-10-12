from flask import Blueprint, redirect, url_for
from flask_login import current_user
from ..utils import dashboard_endpoint

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role)))
    return redirect(url_for("auth.login"))
