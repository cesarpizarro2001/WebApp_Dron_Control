from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('control.html')

@main.route('/piloto')
def piloto():
    return render_template('piloto.html')

@main.route('/movimiento')
def movimiento():
    return render_template('movimiento.html')

@main.route('/alumno_control')
def alumno_control():
    return render_template('alumno_control.html')

@main.route('/alumno_piloto')
def alumno_piloto():
    return render_template('alumno_piloto.html')

@main.route('/alumno_movimiento')
def alumno_movimiento():
    return render_template('alumno_movimiento.html')
