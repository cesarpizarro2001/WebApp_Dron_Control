# WebAppFlask

## 1. Presentación
En este repositorio se describe cómo controlar un dron desde cualquier dispositivo conectado a internet, sin necesidad de instalar ninguna app en el dispositivo. Para ello se utiliza el framework Flask para implementer un servidor web en Python.   
El repositorio proporciona códigos, vídeos y descripciones. 

## 2. Instalación
Paso 1: Para preparar la instalación de la WebApp primero debemos instalar el interprete de Python 3.9 (el instalador de esta interprete se puede encontrar la página web https://www.python.org/downloads/). 
Paso 2: Abrir los archivos importantes (run.py, EstacionDeTierra.py, control.html). En la primera línea del código de run.py y EstacionDeTierra.py explica las librerías que se deben instalar. Si no se instalan estas librerias el código dará errores.
Paso 3: Descargar los certificados https, para ello abrir un Git Bash en la carpeta WebAppMQTT y escribir el siguiente comando: 

	openssl req -newkey rsa:2048 -nodes -keyout private_key.pem -x509 -days 365 -out public_certificate.pem

	Rellenar campos:
	Nombre del país (código de 2 letras) []: ES
	Nombre del estado o provincia (nombre completo) []: Barcelona
	Nombre de la localidad (p. ej., ciudad) []: Castelldefels
	Nombre de la organización (p. ej., empresa) []: UPC
	Nombre de la unidad organizativa (p. ej., sección) []: DAC
	Nombre común (por ejemplo, nombre de host completo) []: localhost
	Dirección de correo electrónico []: -

Paso 4: Una vez hemos realizado los pasos 1, 2 y 3, ejecutamos run.py y EstacionDeTierra.py (importante primero ejecutar run.py).

## 3. Videos disponibles
Video tutorial disponible en: https://www.youtube.com/watch?v=iixXgZBE0gM&ab_channel=DronsEETAC
Video explicación del código disponible en: https://www.youtube.com/watch?v=3-QpJUCHGdY&ab_channel=DronsEETAC


    



