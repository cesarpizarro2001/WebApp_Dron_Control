import threading
import time
from pymavlink import mavutil

def _inGeofence (self, position = None):
    if position == None:
        position = self.position
    print ('position ', position)
    print ('geofence ', self.localGeofence)
    if abs(position[0]) < self.localGeofence[0] // 2 and \
        abs(position[1]) < self.localGeofence[1] // 2 :
            '''     and \
            position[2] < self.localGeofence[2] and position[2] > 0:
            '''
            return True
    else:
            print ('BREACHHHHHHHH')
            return False

def _goToLastPositionBeforeLocalGeofenceBreach (self):
    self.vehicle.mav.send(
        mavutil.mavlink.MAVLink_set_position_target_local_ned_message(
            10, self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,  # frame
            0b110111111000,
            0,
            0,
            self.position[2],
            0, 0, 0, 0, 0, 0, 0, 0))


def setLocalGeofence (self, dimN_S, dimE_O, altura):
    # el geofence local se define en términos de las dimensiones
    # del espacio, es este orden: Norte-sur, Este-oeste, altura

    self.localGeofence = [dimN_S, dimE_O, altura]

def _localGeofenceCheck (self):

    while self.localGeofenceEnabled:
        if self.state != 'disconnected':
            if not self._inGeofence():
                print ('breachhhhh ', self.localGeofenceBreachAction)
                if self.localGeofenceBreachAction == 2:
                    # para aterrizar tengo que cambiar el modo via RC_override
                    # Asumo que Land está configurado como modo 6 en los modos de vuelo
                    self.send_rc(rcin5=1800)
                    self.status_loop(3)

                elif self.localGeofenceBreachAction == 3:

                    print ('OOOOOOOOOOOOOOOOOOOOOOOOOOOOO')
                    '''self.clear_motion ()
                    self.status_loop(3)'''
                    self._goToLastPositionBeforeLocalGeofenceBreach()

                    #self.RTL (blocking = False)
                if self.localGeofenceBreachCallback != None:
                    if self.id == None:
                        if  self.localGeofenceBreachCallbackParams == None:
                            self.localGeofenceBreachCallback()
                        else:
                            self.localGeofenceBreachCallback( self.localGeofenceBreachCallbackParams)
                    else:
                        if  self.localGeofenceBreachCallbackParams == None:
                            self.localGeofenceBreachCallback(self.id)
                        else:
                            self.localGeofenceBreachCallback(self.id,  self.localGeofenceBreachCallbackParams)
            else:
                self.lastPositionBeforeLocalGeofenceBreach = self.position
        time.sleep (0.25)


def enableLocalGeofence (self, callback = None, params = None):
    self.localGeofenceEnabled = True
    self.localGeofenceBreachCallback = callback
    self.localGeofenceBreachCallbackParams = params

    localGoefenceCheckThread = threading.Thread(target=self._localGeofenceCheck)
    localGoefenceCheckThread.start()
    self.localGeofenceChecking = True

def disableLocalGeofence (self):
    self.localGeofenceEnabled = False

def setLocalGeofenceBreachAction (self,action):
    self.localGeofenceBreachAction = action

def startLocalGeofenceChecking (self):
    self.localGeofenceChecking = True

def stopLocalGeofenceChecking (self):
    self.localGeofenceChecking = False
