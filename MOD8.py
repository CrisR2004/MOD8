from flask import Flask, request, render_template_string, redirect, url_for
from flask_mail import Mail, Message
from celery import Celery
import redis
import json

app = Flask(__name__)

# Configuración de la base de datos Redis
client = redis.Redis(host='localhost', port=6379, db=0)

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'tu_email@gmail.com'  # Cambiar por tu email
app.config['MAIL_PASSWORD'] = 'tu_contraseña'      # Cambiar por tu contraseña
app.config['MAIL_DEFAULT_SENDER'] = 'tu_email@gmail.com'

mail = Mail(app)

# Configuración de Celery
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Tarea asíncrona para enviar correos electrónicos
@celery.task
def enviar_correo(asunto, destinatario, cuerpo):
    with app.app_context():
        msg = Message(subject=asunto, recipients=[destinatario], body=cuerpo)
        mail.send(msg)

# Página principal que lista todas las recetas
@app.route('/')
def index():
    recetas = []
    for key in client.scan_iter("receta:*"):
        receta_id = key.decode().split(":")[1]
        receta_data = json.loads(client.get(key).decode())
        receta_data['id'] = receta_id
        recetas.append(receta_data)
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recetario</title>
    </head>
    <body>
        <h1>Recetario</h1>
        <a href="{{ url_for('agregar_receta_form') }}">Agregar nueva receta</a>
        <ul>
            {% for receta in recetas %}
                <li>
                    <a href="{{ url_for('ver_receta', receta_id=receta.id) }}">{{ receta.nombre }}</a>
                    <form action="{{ url_for('eliminar_receta', receta_id=receta.id) }}" method="post" style="display:inline;">
                        <button type="submit">Eliminar</button>
                    </form>
                </li>
            {% else %}
                <li>No hay recetas disponibles.</li>
            {% endfor %}
        </ul>
    </body>
    </html>
    ''', recetas=recetas)

# Formulario para agregar una nueva receta
@app.route('/agregar', methods=['GET'])
def agregar_receta_form():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Agregar receta</title>
    </head>
    <body>
        <h1>Agregar una nueva receta</h1>
        <form action="{{ url_for('agregar_receta') }}" method="post">
            <label for="nombre">Nombre:</label>
            <input type="text" name="nombre" required><br>

            <label for="ingredientes">Ingredientes:</label>
            <textarea name="ingredientes" required></textarea><br>

            <label for="pasos">Pasos:</label>
            <textarea name="pasos" required></textarea><br>

            <button type="submit">Agregar receta</button>
        </form>

        <a href="{{ url_for('index') }}">Volver a la lista de recetas</a>
    </body>
    </html>
    ''')

# Ruta para procesar la adición de una nueva receta
@app.route('/agregar', methods=['POST'])
def agregar_receta():
    nombre = request.form['nombre']
    ingredientes = request.form['ingredientes']
    pasos = request.form['pasos']
    receta_id = client.incr('receta_id')

    nueva_receta = {
        "nombre": nombre,
        "ingredientes": ingredientes,
        "pasos": pasos
    }

    client.set(f"receta:{receta_id}", json.dumps(nueva_receta))

    # Enviar correo de confirmación de manera asíncrona
    asunto = "Nueva receta añadida"
    destinatario = "usuario@ejemplo.com"  # Cambiar por el destinatario real
    cuerpo = f"Se ha añadido la receta '{nombre}' al recetario."
    enviar_correo.delay(asunto, destinatario, cuerpo)

    return redirect(url_for('index'))

# Ver una receta específica por ID
@app.route('/receta/<int:receta_id>')
def ver_receta(receta_id):
    receta_key = f"receta:{receta_id}"
    if client.exists(receta_key):
        receta = json.loads(client.get(receta_key).decode())
        return render_template_string('''
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ receta.nombre }}</title>
        </head>
        <body>
            <h1>{{ receta.nombre }}</h1>
            <p><strong>Ingredientes:</strong> {{ receta.ingredientes }}</p>
            <p><strong>Pasos:</strong> {{ receta.pasos }}</p>
            <a href="{{ url_for('index') }}">Volver a la lista de recetas</a>
        </body>
        </html>
        ''', receta=receta)
    else:
        return "Receta no encontrada", 404

# Eliminar una receta
@app.route('/eliminar/<int:receta_id>', methods=['POST'])
def eliminar_receta(receta_id):
    receta_key = f"receta:{receta_id}"
    if client.exists(receta_key):
        client.delete(receta_key)
        return redirect(url_for('index'))
    else:
        return "Receta no encontrada", 404

# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)
