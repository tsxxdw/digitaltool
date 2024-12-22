from flask import Blueprint, render_template

bp = Blueprint('sync', __name__)

@bp.route('/sync')
def sync():
    return render_template('sync.html') 