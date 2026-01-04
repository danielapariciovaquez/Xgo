import pygame
import serial
import time

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
SEND_PERIOD = 0.05
DEADZONE = 0.01

# =====================================================
# MAPEO DEL MANDO
# =====================================================
BUTTON_START = 7
BUTTON_HEIGHT_UP = 3
BUTTON_HEIGHT_DOWN = 0
BUTTON_PAW = 1            # Botón B

AXIS_FORWARD = 1
AXIS_LATERAL = 0
AXIS_ROTATE  = 3
AXIS_INCLINE = 4

# =====================================================
# ACCIONES XGO
# =====================================================
ACTION_GIVE_PAW = 12      # escribir 12 en 0x3E

# =====================================================
# ALTURA (SE QUEDA IGUAL)
# =====================================================
HEIGHT_STEP = 4
HEIGHT_MIN = 0x00
HEIGHT_MAX = 0xFF

# =====================================================
# LEDs RGB
# =====================================================
LED_ADDRS = (0x69, 0x6A, 0x6B)

# =====================================================
# PUERTO SERIE
# =====================================================
ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0)

# =====================================================
# PYGAME
# =====================================================
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise RuntimeError("No se ha detectado ningún mando")

joy = pygame.joystick.Joystick(0)
joy.init()

# =====================================================
# FUNCIONES DE TRAMA
# =====================================================
def build_frame(address, value):
    length = 0x09
    command = 0x00
    checksum = (length + command + address + value) & 0xFF
    checksum = (~checksum) & 0xFF

    return bytes([
        0x55, 0x00,
        length,
        command,
        address,
        value,
        checksum,
        0x00, 0xAA
    ])

def build_frame_rgb(address, r, g, b):
    length = 0x0B
    command = 0x00
    checksum = (length + command + address + r + g + b) & 0xFF
    checksum = (~checksum) & 0xFF

    return bytes([
        0x55, 0x00,
        length,
        command,
        address,
        r, g, b,
        checksum,
        0x00, 0xAA
    ])

def set_leds(r, g, b):
    for addr in LED_ADDRS:
        ser.write(build_frame_rgb(addr, r, g, b))

# =====================================================
# TRAMAS DE STOP
# =====================================================
FRAME_STOP_FORWARD = build_frame(0x30, 0x80)
FRAME_STOP_LATERAL = build_frame(0x31, 0x80)
FRAME_STOP_ROTATE  = build_frame(0x32, 0x80)

# =====================================================
# ARRANQUE SEGURO
# =====================================================
for _ in range(10):
    ser.write(FRAME_STOP_FORWARD)
    ser.write(FRAME_STOP_LATERAL)
    ser.write(FRAME_STOP_ROTATE)
    set_leds(255, 0, 0)   # rojo = desarmado
    time.sleep(0.05)

# =====================================================
# ESTADOS
# =====================================================
armed = False
height_value = 0x80
prev_start = 0
prev_paw = 0

# =====================================================
# BUCLE PRINCIPAL
# =====================================================
try:
    while True:
        pygame.event.pump()

        # ---------------------------------------------
        # START → ARMAR / DESARMAR
        # ---------------------------------------------
        start_pressed = joy.get_button(BUTTON_START)
        if start_pressed and not prev_start:
            armed = not armed
            if armed:
                set_leds(10, 50, 0)   # verde suave
            else:
                set_leds(50, 10, 0)   # rojo suave
        prev_start = start_pressed

        # ---------------------------------------------
        # DESARMADO → SOLO STOP
        # ---------------------------------------------
        if not armed:
            ser.write(FRAME_STOP_FORWARD)
            ser.write(FRAME_STOP_LATERAL)
            ser.write(FRAME_STOP_ROTATE)
            time.sleep(SEND_PERIOD)
            continue

        # ---------------------------------------------
        # BOTÓN B → DAR LA PATA (0x3E = 12)
        # ---------------------------------------------
        paw_pressed = joy.get_button(BUTTON_PAW)
        if paw_pressed and not prev_paw:
            ser.write(build_frame(0x3E, ACTION_GIVE_PAW))
        prev_paw = paw_pressed

        # ---------------------------------------------
        # ALTURA (SIN CAMBIOS)
        # ---------------------------------------------
        if joy.get_button(BUTTON_HEIGHT_UP):
            height_value = min(HEIGHT_MAX, height_value + HEIGHT_STEP)
        if joy.get_button(BUTTON_HEIGHT_DOWN):
            height_value = max(HEIGHT_MIN, height_value - HEIGHT_STEP)

        ser.write(build_frame(0x35, height_value))

        # ---------------------------------------------
        # EJES DE MOVIMIENTO
        # ---------------------------------------------
        f = -joy.get_axis(AXIS_FORWARD) / 2
        l = -joy.get_axis(AXIS_LATERAL) / 2
        r = -joy.get_axis(AXIS_ROTATE)  / 2

        f = 0.0 if abs(f) < DEADZONE else f
        l = 0.0 if abs(l) < DEADZONE else l
        r = 0.0 if abs(r) < DEADZONE else r

        ser.write(build_frame(0x30, int(0x80 + f * 0x7F)))
        ser.write(build_frame(0x31, int(0x80 + l * 0x7F)))
        ser.write(build_frame(0x32, int(0x80 + r * 0x7F)))

        # ---------------------------------------------
        # INCLINACIÓN (EJE 3 → 0x37)
        # ---------------------------------------------
        i = joy.get_axis(AXIS_INCLINE)
        i = 0.0 if abs(i) < DEADZONE else i

        incline_value = int(0x80 + i * 0x7F)
        incline_value = max(0x00, min(0xFF, incline_value))

        ser.write(build_frame(0x37, incline_value))

        time.sleep(SEND_PERIOD)

finally:
    set_leds(255, 0, 0)
    ser.close()
    pygame.quit()
