from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('control.html')

@main.route('/piloto')
def piloto():
    return render_template('piloto.html')

