import time

from pymavlink import mavutil

def send_rc(self, rcin1=65535, rcin2=65535, rcin3=65535, rcin4=65535,
            rcin5=65535, rcin6=65535, rcin7=65535, rcin8=65535,
            rcin9=65535, rcin10=65535, rcin11=65535, rcin12=65535,
            rcin13=65535, rcin14=65535, rcin15=65535, rcin16=65535,
            rcin17=65535, rcin18=65535, *,  # keyword-only from here
            pitch=None, roll=None, throttle=None, yaw=None, forward=None,
            lateral=None, camera_pan=None, camera_tilt=None, lights1=None,
            lights2=None, video_switch=None):
    ''' Sets all 18 rc channels as specified.
    Values should be between 1100-1900, or left as 65535 to ignore.
    Can specify values:
        positionally,
        or with rcinX (X=1-18),
        or with default RC Input channel mapping names
          -> see https://ardusub.com/developers/rc-input-and-output.html
    It's possible to mix and match specifier types (although generally
      not recommended). Default channel mapping names override positional
      or rcinX specifiers.
    '''
    rc_channel_values = (
        pitch or rcin1,
        roll or rcin2,
        throttle or rcin3,
        yaw or rcin4,
        forward or rcin5,
        lateral or rcin6,
        camera_pan or rcin7,
        camera_tilt or rcin8,
        lights1 or rcin9,
        lights2 or rcin10,
        video_switch or rcin11,
        rcin12, rcin13, rcin14, rcin15, rcin16, rcin17, rcin18
    )
    print(f'send_rc')
    print(rc_channel_values)
    self.target = (self.vehicle.target_system,
                   self.vehicle.target_component)
    self.vehicle.mav.rc_channels_override_send(
        *self.target,
        *rc_channel_values
    )


def clear_motion(self, stopped_pwm=1500):
    ''' Sets all 6 motion direction RC inputs to 'stopped_pwm'. '''
    print ('clear_motion')
    self.send_rc(*[stopped_pwm] * 6)


def get_thruster_outputs(self):
    ''' Returns (and notes) the first 'self.thrusters' servo PWM values.
    Offset by 1500 to make it clear how each thruster is active.
    '''
    print ('get_thruster_outputs')
    servo_outputs = self.vehicle.recv_match(type='SERVO_OUTPUT_RAW',
                                    blocking=True).to_dict()
    thruster_outputs = [servo_outputs[f'servo{i + 1}_raw'] - 1500
                        for i in range(6)]
    print(f'{thruster_outputs=}')
    return thruster_outputs


def status_loop(self, duration, delay=0.05):
    ''' Loop for 'duration', with 'delay' between iterations. [s]
    Useful for debugging.
    '''
    start = time.time()
    while time.time() - start < duration:
        self.get_thruster_outputs()
        time.sleep(delay)

