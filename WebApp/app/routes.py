from flask import Blueprint, render_template, send_from_directory
import os

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

# Ruta para servir fotos capturadas desde EstacionTierra
@main.route('/static/captured_photos/<path:filename>')
def captured_photos(filename):
    # Construir ruta relativa a EstacionTierra/captured_photos
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    photos_dir = os.path.join(base_dir, 'EstacionTierra', 'captured_photos')
    print(f"Sirviendo foto desde: {photos_dir}/{filename}")
    return send_from_directory(photos_dir, filename)

# Ruta para servir videos grabados desde EstacionTierra
@main.route('/static/captured_videos/<path:filename>')
def captured_videos(filename):
    # Construir ruta relativa a EstacionTierra/captured_videos
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    videos_dir = os.path.join(base_dir, 'EstacionTierra', 'captured_videos')
    return send_from_directory(videos_dir, filename, mimetype='video/mp4')
