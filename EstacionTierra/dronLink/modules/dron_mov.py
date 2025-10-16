'''
Coleccion de métodos para la navegación según los puntos cardinales.
El dron debe estar en estado 'volando'
Para iniciar la navegación debe ejecutarse el método startGo,
que pone en marcha el thread que mantiene el rumbo.
El rumbo puede cambiar mediante el método go que recibe como parámetro
el nuevo rumbo (north, south, etc).
Para acabar la navegación hay que ejecutar el método stopGo

'''
import math
import threading
import time
from pymavlink import mavutil
import pymavlink.dialects.v20.all as dialect


def _prepare_command_mov(self, step_x, step_y, step_z):

    msg =  mavutil.mavlink.MAVLink_set_position_target_local_ned_message(
        10,  # time_boot_ms (not used)
        self.vehicle.target_system,
        self.vehicle.target_component,
        mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,  # frame
        0b110111111000,  # type_mask (only speeds enabled)
        step_x,
        step_y,
        step_z,  # x, y, z positions (not used)
        0,
        0,
        0,  # x, y, z velocity in m/s
        0,
        0,
        0,  # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
        0,
        0,
    )  # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)

    return msg


def _prepare_command_movto(self, position):

    msg =  mavutil.mavlink.MAVLink_set_position_target_local_ned_message(
        10,  # time_boot_ms (not used)
        self.vehicle.target_system,
        self.vehicle.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,  # frame
        0b110111111000,  # type_mask (only speeds enabled)
        position[0],
        position[1],
        -position[2],  # x, y, z positions (not used)
        0,
        0,
        0,  # x, y, z velocity in m/s
        0,
        0,
        0,  # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
        0,
        0,
    )  # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)

    return msg


def setStep (self, step):
    self.step = step # en metros


def _destination(self, posX, posY, distancia, angulo):
    # Convertir el ángulo a radianes
    angulo_rad = math.radians(angulo)

    # Atencion porque al tratarse de posiciones NED la posX
    # esta en la dirección vertical

    delta_x = distancia * math.cos(angulo_rad)
    delta_y = distancia * math.sin(angulo_rad)

    # Calcular la nueva posición
    nueva_x = posX + delta_x
    nueva_y = posY + delta_y

    return nueva_x, nueva_y

def _move(self, direction, callback=None, params = None):
    self._stopGo()
    step = self.step
    destZ = self.position[2]
    if direction == "Forward":
        destX,destY = self._destination (self.position[0], self.position[1], step, self.heading)
        self.cmd = self._prepare_command_mov(step, 0, 0)
    if direction == "Back":
        destX, destY = self._destination(self.position[0], self.position[1], step, self.heading + 180)
        self.cmd = self._prepare_command_mov(-step, 0, 0)
    if direction == "Left":
        destX, destY = self._destination(self.position[0], self.position[1], step, self.heading - 90)
        self.cmd = self._prepare_command_mov(0, -step, 0)
    if direction == "Right":
        destX, destY = self._destination(self.position[0], self.position[1], step, self.heading + 90)
        self.cmd = self._prepare_command_mov(0, step, 0)
    if direction == "Up":
        destX = self.position[0]
        destY = self.position[1]
        destZ = self.position[2] - step
        self.cmd = self._prepare_command_mov(0, 0, -step)
    if direction == "Down":
        destX = self.position[0]
        destY = self.position[1]
        destZ = self.position[2] + step
        self.cmd = self._prepare_command_mov(0, 0, step)
    if direction == "Stop":
        destX = self.position[0]
        destY = self.position[1]
        destZ = self.position[2]
        self.cmd = self._prepare_command_mov(0, 0, 0)

    self.vehicle.mav.send(self.cmd)

    arrived = False
    while not arrived:
        distance = self._distance(destX,destY,destZ, self.position[0], self.position[1], self.position[2])
        if distance < 0.2:
            arrived = True
        time.sleep(1)

    # meter aqui un bucle esperando hasta que haya llegado
    if callback != None:
        if self.id == None:
            if params == None:
                callback()
            else:
                callback(params)
        else:
            if params == None:
                callback(self.id)
            else:
                callback(self.id, params)


def _recover(self):
    print ('recover')
    step = 1
    if self.lastDirection == "Forward":
        self.cmd = self._prepare_command_mov(-step, 0, 0)
    if self.lastDirection == "Back":
        self.cmd = self._prepare_command_mov(step, 0, 0)
    if self.lastDirection == "Left":
        self.cmd = self._prepare_command_mov(0, step, 0)
    if self.lastDirection == "Right":
        self.cmd = self._prepare_command_mov(0, -step, 0)
    if self.lastDirection == "Up":
        self.cmd = self._prepare_command_mov(0, 0, step)
    if self.lastDirection == "Down":
        self.cmd = self._prepare_command_mov(0, 0, -step)

    self.stopLocalGeofenceChecking()
    self.vehicle.mav.send(self.cmd)


    while not self._inGeofence():
        time.sleep(1)
    self._move ('Stop')
    self.startLocalGeofenceChecking()




def move(self, direction, blocking=True, callback=None, params = None):
    if self.localGeofenceEnabled and self.localGeofenceBreachAction == 1:
        print ('voy a comproar ', direction)
        if self.check (direction):
            if blocking:
                self._move(direction)
            else:
                moveThread = threading.Thread(target=self._move, args=[direction, callback, params,])
                moveThread.start()
            return True

        else:
            if self.localGeofenceBreachCallback != None:
                if self.id == None:
                    if self.localGeofenceBreachCallbackParams == None:
                        self.localGeofenceBreachCallback()
                    else:
                        self.localGeofenceBreachCallback(self.localGeofenceBreachCallbackParams)
                else:
                    if self.localGeofenceBreachCallbackParams == None:
                        self.localGeofenceBreachCallback(self.id)
                    else:
                        self.localGeofenceBreachCallback(self.id, self.localGeofenceBreachCallbackParams)



    else:
        if blocking:
            self._move(direction)
        else:
            moveThread = threading.Thread(target=self._move, args=[direction, callback, params, ])
            moveThread.start()


def move2(self, direction, blocking=True, callback=None, params = None):
    if blocking:
        self._move(direction)
    else:
        moveThread = threading.Thread(target=self._move, args=[direction, callback, params, ])
        moveThread.start()
    return True


def _distance(self, destX, destY, destZ, posX, posY, posZ):

    dx = destX - posX
    dy = destY - posY
    dz = destZ - posZ
    return math.sqrt((dx*dx) + (dy*dy))


def _moveto (self, destination, callback=None, params = None):
    self._stopGo()
    self.cmd = self._prepare_command_movto (destination)
    destX = destination [0]
    destY= destination[1]
    destZ = destination[2]
    print ('2 vamos a ', destination)
    self.vehicle.mav.send(self.cmd)
    arrived = False
    while not arrived:
        #msg = self.vehicle.recv_match(type='LOCAL_POSITION_NED', blocking=True)
        distance = self._distance(destX,destY,destZ, self.position[0], self.position[1], self.position[2])
        #distance = self._distance (position[0], position[1], position[2], msg.x, msg.y, msg.z)
        if distance < 0.2:
            arrived = True
        time.sleep (1)

    if callback != None:
        if self.id == None:
            if params == None:
                callback()
            else:
                callback(params)
        else:
            if params == None:
                callback(self.id)
            else:
                callback(self.id, params)


def moveto(self, position, blocking=True, callback=None, params = None):
# Esto hay que arreglarlo. Debería comprobar que el dron está flying
# Además, debería compronar que hay un geofence antes de hacer el chequeo

    if blocking:
        self._moveto(position)
    else:
        moveThread = threading.Thread(target=self._moveto, args=[position, callback, params, ])
        moveThread.start()



def inGeofence2 (self,position):
    print ('posicion ', position)
    print ('geofence ', self.localGeofence)
    # la posición a la que queremos ir está en formato NED (excepto la altura, que está en positivo)
    if  abs(position[0]) < self.localGeofence[0]//2 and \
        abs(position[1]) < self.localGeofence[1] // 2 and \
        position[2] < self.localGeofence[2] and position[2] > 0:
        return True
    else:
        print (position)
        print (self.localGeofence)
        print ('NOOOO')
        return False


def _futurePosition (self,  angulo):
    # Convertir el ángulo a radianes
    posN_S = self.position[0]
    posE_O = self.position[1]
    distancia = self.step
    angulo_rad = math.radians(angulo)

    # Calcular los desplazamientos
    desplazamiento_E_O = distancia * math.sin(angulo_rad)
    desplazamiento_N_S = distancia * math.cos(angulo_rad)

    # Calcular las nuevas coordenadas
    nueva_PosE_O = posE_O  + desplazamiento_E_O
    nueva_PosN_S = posN_S + desplazamiento_N_S

    return nueva_PosN_S, nueva_PosE_O

def check (self, direction):
    if direction == "Up":
        futureAlt = -self.position[2] + self.step
        return futureAlt < self.localGeofence[2]
    if direction == "Down":
        futureAlt = -self.position[2] - self.step
        return futureAlt > 0
    if direction == "Forward":
        angle = self.heading
    if direction == "Back":
        angle = self.heading + 180
    if direction == "Left":
        angle = self.heading + 270
    if direction == "Right":
        angle = self.heading + 90
    futureN_S, futureE_O = self._futurePosition (angle)
    futureAlt = -self.position[2]
    if self._inGeofence ([futureN_S, futureE_O, futureAlt]):
        return True
    else:
        return False

def setNavSpeed (self, speed):
    print ('fijamos la velocidad ya ', speed)
    msg = self.vehicle.mav.command_long_encode(
        0, 0,  # Sistema y componente (0 para sistema no tripulado)
        mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,  # Comando para cambiar la velocidad de navegación
        0,  # Confirmando
        0,  # Velocidad vertical (sin cambios)
        speed,  # Velocidad de navegación (m/s)
        -1,  # Velocidad máxima (-1 para no limitar)
        0, 0, 0, 0)  # Parámetros adicionales (no utilizados)
    self.vehicle.mav.send(msg)

