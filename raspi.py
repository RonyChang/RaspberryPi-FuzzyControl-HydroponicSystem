import requests
import RPi.GPIO as GPIO
import time
from datetime import datetime
from smbus2 import SMBus
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# Configuración de pines
LED_PIN = 12 # Pin 32
BOMBA_PIN = 25 # Pin 22
DOSIFICADORA_A_PIN = 23 # Pin 16
DOSIFICADORA_B_PIN = 24 # Pin 18

# Configuración de GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(BOMBA_PIN, GPIO.OUT)
GPIO.setup(DOSIFICADORA_A_PIN, GPIO.OUT)
GPIO.setup(DOSIFICADORA_B_PIN, GPIO.OUT)


# URL de la API
API_URL = "http://159.112.136.97:8080"

# Configuración del bus I2C para el sensor BH1750
I2C_BUS = 1
BH1750_ADDRESS = 0x23


def read_sensor(sensor_name, retries=5, backoff_factor=0.5):
    for attempt in range(retries):
        try:
            response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/{sensor_name}")
            response.raise_for_status()  # Generar el HTTPError
            data = response.json()
            return float(data["value"])
        except requests.exceptions.RequestException as e:
            print(f"Error reading {sensor_name}: {e}")
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
            else:
                print(f"Failed to read {sensor_name} after {retries} attempts")
                return None

def read_tamb():
    return read_sensor("TAMB")

def read_hamb():
    return read_sensor("HAMB")

def read_ph():
    return read_sensor("PH")

def read_lux():
    return read_sensor("LUX")

def read_tds():
    return read_sensor("TDS")

def read_tsol():
    return read_sensor("TSOL")


def control_leds(pwm_leds_value, hora_inicio, hora_fin):
    current_hour = datetime.now().hour
    if hora_inicio <= current_hour < hora_fin:
        try:
            pwm = GPIO.PWM(LED_PIN, 1000)
            pwm.start(pwm_leds_value)
        except Exception as e:
            print(f"Error controlling LEDs: {e}")
            GPIO.output(LED_PIN, GPIO.LOW)
    else:
        GPIO.output(LED_PIN, GPIO.LOW)


def control_bomba(action_time_p):
    try:
        GPIO.output(BOMBA_PIN, GPIO.HIGH)
        time.sleep(action_time_p)
        GPIO.output(BOMBA_PIN, GPIO.LOW)
    except Exception as e:
        print(f"Error controlando bomba: {e}")
        GPIO.output(BOMBA_PIN, GPIO.LOW)

def control_dosificadora_a(action_time_sA):
    try:
        GPIO.output(DOSIFICADORA_A_PIN, GPIO.HIGH)
        time.sleep(action_time_sA)
        GPIO.output(DOSIFICADORA_A_PIN, GPIO.LOW)
    except Exception as e:
        print(f"Error controlando dosificadora A: {e}")
        GPIO.output(DOSIFICADORA_A_PIN, GPIO.LOW)

def control_dosificadora_b(action_time_sB):
    try:
        GPIO.output(DOSIFICADORA_B_PIN, GPIO.HIGH)
        time.sleep(action_time_sB)
        GPIO.output(DOSIFICADORA_B_PIN, GPIO.LOW)
    except Exception as e:
        print(f"Error controlando dosificadora B: {e}")
        GPIO.output(DOSIFICADORA_B_PIN, GPIO.LOW)

def fuzzy_logic_control_1(sensor_ph,sensor_tds):
    # Implementar lógica difusa aquí
    # Primer sistema difuso: pH y TDS
    ph = ctrl.Antecedent(np.arange(2.5, 10, 0.1), 'ph')
    tds = ctrl.Antecedent(np.arange(0, 5, 0.1), 'tds')
    pump_time = ctrl.Consequent(np.arange(0, 100, 1), 'pump_time')

    # Definir conjuntos difusos para cada variable
    ph['bajo'] = fuzz.trapmf(ph.universe, [2.5, 2.5, 5.5, 5.75])
    ph['normal'] = fuzz.trapmf(ph.universe, [5.5, 5.75, 6.75, 7.0])
    ph['alto'] = fuzz.trapmf(ph.universe, [6.75, 7, 10, 10])

    tds['bajo'] = fuzz.trapmf(tds.universe, [0, 0, 0.8, 1.3])
    tds['normal'] = fuzz.trapmf(tds.universe, [1, 1.3, 1.7, 2])
    tds['alto'] = fuzz.trapmf(tds.universe, [1.7, 2.2, 5, 5])

    pump_time['off'] = fuzz.trimf(pump_time.universe, [0, 0, 50])
    pump_time['on'] = fuzz.trimf(pump_time.universe, [50, 100, 100])

    # Reglas difusas
    rule1 = ctrl.Rule(ph['bajo'] & tds['alto'], pump_time['off'])
    rule2 = ctrl.Rule(ph['bajo'] & tds['normal'], pump_time['off'])
    rule3 = ctrl.Rule(ph['bajo'] & tds['bajo'], pump_time['on'])
    rule4 = ctrl.Rule(ph['normal'] & tds['alto'], pump_time['off'])
    rule5 = ctrl.Rule(ph['normal'] & tds['normal'], pump_time['off'])
    rule6 = ctrl.Rule(ph['normal'] & tds['bajo'], pump_time['on'])
    rule7 = ctrl.Rule(ph['alto'] & tds['alto'], pump_time['off'])
    rule8 = ctrl.Rule(ph['alto'] & tds['normal'], pump_time['on'])
    rule9 = ctrl.Rule(ph['alto'] & tds['bajo'], pump_time['on'])

    # Crear sistema difuso
    pump_ctrl = ctrl.ControlSystem([rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9])
    pump_sim = ctrl.ControlSystemSimulation(pump_ctrl)

    # Probar el sistema con valores de entrada
    pump_sim.input['ph'] = sensor_ph
    pump_sim.input['tds'] = sensor_tds

    # Computar la salida
    pump_sim.compute()
    #print(f"Tiempo de la bomba dosificadora B: {pump_sim.output['pump_time']}")
    return pump_sim.output['pump_time']

def fuzzy_logic_control_2(sensor_tamb,sensor_hamb,sensor_tsol):

    # Segundo sistema difuso: Temperatura del agua, temperatura ambiente y humedad
    temp_water = ctrl.Antecedent(np.arange(8, 30, 0.1), 'temp_water')
    temp_ambient = ctrl.Antecedent(np.arange(10, 30, 0.1), 'temp_ambient')
    humidity = ctrl.Antecedent(np.arange(40, 95, 1), 'humidity')
    pump_time_water = ctrl.Consequent(np.arange(0, 100, 1), 'pump_time_water')

    # Definir conjuntos difusos para cada variable
    temp_water['baja'] = fuzz.trimf(temp_water.universe, [8, 8, 16])
    temp_water['normal'] = fuzz.trimf(temp_water.universe, [14, 16, 18])
    temp_water['alta'] = fuzz.trimf(temp_water.universe, [16, 30, 30])

    temp_ambient['baja'] = fuzz.trimf(temp_ambient.universe, [10, 10, 16])
    temp_ambient['normal'] = fuzz.trimf(temp_ambient.universe, [17, 19.5, 22])
    temp_ambient['alta'] = fuzz.trimf(temp_ambient.universe, [23, 26.5, 30])

    humidity['baja'] = fuzz.trimf(humidity.universe, [40, 40, 55])
    humidity['normal'] = fuzz.trimf(humidity.universe, [50, 65, 80])
    humidity['alta'] = fuzz.trapmf(humidity.universe, [75, 90, 95, 95])

    pump_time_water['off'] = fuzz.trimf(pump_time_water.universe, [0, 0, 50])
    pump_time_water['on'] = fuzz.trimf(pump_time_water.universe, [50, 100, 100])

   # Reglas Difusas
    rule1 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & humidity['baja'], pump_time_water['off'])
    rule2 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & humidity['normal'], pump_time_water['off'])
    rule3 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & humidity['alta'], pump_time_water['on'])

    rule4 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & humidity['baja'], pump_time_water['off'])
    rule5 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & humidity['normal'], pump_time_water['off'])
    rule6 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & humidity['alta'], pump_time_water['on'])

    rule7 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & humidity['baja'], pump_time_water['off'])
    rule8 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & humidity['normal'], pump_time_water['on'])
    rule9 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & humidity['alta'], pump_time_water['on'])

    rule10 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & humidity['baja'], pump_time_water['off'])
    rule11 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & humidity['normal'], pump_time_water['off'])
    rule12 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & humidity['alta'], pump_time_water['on'])

    rule13 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & humidity['baja'], pump_time_water['off'])
    rule14 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & humidity['normal'], pump_time_water['on'])
    rule15 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & humidity['alta'], pump_time_water['on'])

    rule16 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & humidity['baja'], pump_time_water['off'])
    rule17 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & humidity['normal'], pump_time_water['on'])
    rule18 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & humidity['alta'], pump_time_water['on'])

    rule19 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & humidity['baja'], pump_time_water['off'])
    rule20 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & humidity['normal'], pump_time_water['off'])
    rule21 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & humidity['alta'], pump_time_water['off'])

    rule22 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & humidity['baja'], pump_time_water['off'])
    rule23 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & humidity['normal'], pump_time_water['off'])
    rule24 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & humidity['alta'], pump_time_water['off'])

    rule25 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & humidity['baja'], pump_time_water['off'])
    rule26 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & humidity['normal'], pump_time_water['off'])
    rule27 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & humidity['alta'], pump_time_water['off'])

    # Crear el sistema de control difuso
    water_pump_ctrl = ctrl.ControlSystem([
        rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9, 
        rule10, rule11, rule12, rule13, rule14, rule15, rule16, rule17, rule18, 
        rule19, rule20, rule21, rule22, rule23, rule24, rule25, rule26, rule27
    ])
    water_pump_sim = ctrl.ControlSystemSimulation(water_pump_ctrl)

    water_pump_sim.input['temp_water'] = sensor_tsol
    water_pump_sim.input['temp_ambient'] = sensor_tamb
    water_pump_sim.input['humidity'] = sensor_hamb

    water_pump_sim.compute()
    #print(f"Tiempo de la bomba principal: {water_pump_sim.output['pump_time_water']}")
    return water_pump_sim.output['pump_time_water']


def fuzzy_logic_control_3(sensor_tamb,sensor_hamb,sensor_lux):

    # Tercer sistema difuso: Temperatura ambiente, temperatura del agua e intensidad lumínica
    temp_water = ctrl.Antecedent(np.arange(0, 50, 1), 'temp_water')
    temp_ambient = ctrl.Antecedent(np.arange(10, 30, 0.1), 'temp_ambient')
    light_intensity = ctrl.Antecedent(np.arange(0, 15000, 1), 'light_intensity')
    pwm = ctrl.Consequent(np.arange(0, 100, 1), 'pwm')

    # Definir conjuntos difusos para cada variable
    temp_water['baja'] = fuzz.trimf(temp_water.universe, [8, 8, 16])
    temp_water['normal'] = fuzz.trimf(temp_water.universe, [14, 16, 18])
    temp_water['alta'] = fuzz.trimf(temp_water.universe, [16, 30, 30])

    temp_ambient['baja'] = fuzz.trimf(temp_ambient.universe, [10, 10, 16])
    temp_ambient['normal'] = fuzz.trimf(temp_ambient.universe, [17, 19.5, 22])
    temp_ambient['alta'] = fuzz.trimf(temp_ambient.universe, [23, 26.5, 30])

    light_intensity['muy baja'] = fuzz.trapmf(light_intensity.universe, [0, 0, 4000, 6000])
    light_intensity['baja'] = fuzz.trapmf(light_intensity.universe, [5000, 7000, 9000, 11000])
    light_intensity['normal'] = fuzz.trapmf(light_intensity.universe, [10000, 12000, 13000, 14000])
    light_intensity['alta'] = fuzz.trapmf(light_intensity.universe, [13000, 14000, 15000, 15000])
    light_intensity['muy alta'] = fuzz.trapmf(light_intensity.universe, [14000, 15000, 15000, 15000])

    pwm['bajar'] = fuzz.trimf(pwm.universe, [0, 0, 40])
    pwm['mantener'] = fuzz.trimf(pwm.universe, [25, 50, 75])
    pwm['subir'] = fuzz.trimf(pwm.universe, [60, 100, 100])

    # Reglas difusas
    rule1 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & light_intensity['muy baja'], pwm['subir'])
    rule2 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & light_intensity['baja'], pwm['subir'])
    rule3 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & light_intensity['normal'], pwm['mantener'])
    rule4 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & light_intensity['alta'], pwm['mantener'])
    rule5 = ctrl.Rule(temp_water['baja'] & temp_ambient['baja'] & light_intensity['muy alta'], pwm['bajar'])

    rule6 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & light_intensity['muy baja'], pwm['subir'])
    rule7 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & light_intensity['baja'], pwm['subir'])
    rule8 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & light_intensity['normal'], pwm['mantener'])
    rule9 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & light_intensity['alta'], pwm['mantener'])
    rule10 = ctrl.Rule(temp_water['baja'] & temp_ambient['normal'] & light_intensity['muy alta'], pwm['bajar'])
    
    rule11 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & light_intensity['muy baja'], pwm['subir'])
    rule12 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & light_intensity['baja'], pwm['subir'])
    rule13 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & light_intensity['normal'], pwm['mantener'])
    rule14 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & light_intensity['alta'], pwm['mantener'])
    rule15 = ctrl.Rule(temp_water['baja'] & temp_ambient['alta'] & light_intensity['muy alta'], pwm['bajar'])
    
    rule16 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & light_intensity['muy baja'], pwm['subir'])
    rule17 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & light_intensity['baja'], pwm['subir'])
    rule18 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & light_intensity['normal'], pwm['mantener'])
    rule19 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & light_intensity['alta'], pwm['mantener'])
    rule20 = ctrl.Rule(temp_water['normal'] & temp_ambient['baja'] & light_intensity['muy alta'], pwm['bajar'])
    
    rule21 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & light_intensity['muy baja'], pwm['subir'])
    rule22 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & light_intensity['baja'], pwm['subir'])
    rule23 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & light_intensity['normal'], pwm['mantener'])
    rule24 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & light_intensity['alta'], pwm['mantener'])
    rule25 = ctrl.Rule(temp_water['normal'] & temp_ambient['normal'] & light_intensity['muy alta'], pwm['bajar'])
    
    rule26 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & light_intensity['muy baja'], pwm['subir'])
    rule27 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & light_intensity['baja'], pwm['subir'])
    rule28 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & light_intensity['normal'], pwm['mantener'])
    rule29 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & light_intensity['alta'], pwm['mantener'])
    rule30 = ctrl.Rule(temp_water['normal'] & temp_ambient['alta'] & light_intensity['muy alta'], pwm['bajar'])
    
    rule31 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & light_intensity['muy baja'], pwm['subir'])
    rule32 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & light_intensity['baja'], pwm['subir'])
    rule33 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & light_intensity['normal'], pwm['mantener'])
    rule34 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & light_intensity['alta'], pwm['mantener'])
    rule35 = ctrl.Rule(temp_water['alta'] & temp_ambient['baja'] & light_intensity['muy alta'], pwm['bajar'])
    
    rule36 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & light_intensity['muy baja'], pwm['subir'])
    rule37 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & light_intensity['baja'], pwm['subir'])
    rule38 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & light_intensity['normal'], pwm['mantener'])
    rule39 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & light_intensity['alta'], pwm['mantener'])
    rule40 = ctrl.Rule(temp_water['alta'] & temp_ambient['normal'] & light_intensity['muy alta'], pwm['bajar'])
    rule41 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & light_intensity['muy baja'], pwm['subir'])
    rule42 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & light_intensity['baja'], pwm['subir'])
    rule43 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & light_intensity['normal'], pwm['mantener'])
    rule44 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & light_intensity['alta'], pwm['mantener'])
    rule45 = ctrl.Rule(temp_water['alta'] & temp_ambient['alta'] & light_intensity['muy alta'], pwm['bajar'])

    light_ctrl = ctrl.ControlSystem([
        rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9, rule10,
        rule11, rule12, rule13, rule14, rule15, rule16, rule17, rule18, rule19,
        rule20, rule21, rule22, rule23, rule24, rule25, rule26, rule27, rule28,
        rule29, rule30, rule31, rule32, rule33, rule34, rule35, rule36, rule37,
        rule38, rule39, rule40, rule41, rule42, rule43, rule44, rule45
    ])
    light_sim = ctrl.ControlSystemSimulation(light_ctrl)

    light_sim.input['temp_water'] = sensor_tamb
    light_sim.input['temp_ambient'] = sensor_hamb
    light_sim.input['light_intensity'] = sensor_lux

    light_sim.compute()
    #print(f"Tiempo de la bomba dosificadora B: {pump_sim.output['pump_time']}")
    return light_sim.output['pwm']

def main():
    try:
        while True:
            sensor_tamb = 18
            sensor_hamb = 70
            sensor_ph = 6
            sensor_lux = 12000
            sensor_tds = 0.7
            sensor_tsol = 16.5
            """""
            sensor_tamb = read_tamb()
            sensor_hamb = read_hamb()
            sensor_ph = read_ph()
            sensor_lux = read_lux()
            sensor_tds = read_tds()
            sensor_tsol = read_tsol()
            """""

            # Controlar bombas dosificadoras
            dosificadora = fuzzy_logic_control_1(sensor_ph,sensor_tds)
            if dosificadora > 50:
                tiempo_min = 2
                tiempo_max = 42
                tiempo_dosificadora_b = tiempo_min + (tiempo_max - tiempo_min) * (dosificadora - 50) / (100 - 50)
            else:
                tiempo_dosificadora_b = 0
            control_dosificadora_b(tiempo_dosificadora_b)
            tiempo_dosificadora_a = (tiempo_dosificadora_b)*5/2
            control_dosificadora_a(tiempo_dosificadora_a)
            # aumentar control de bomba principal para revolver


            # Controlar bomba principal
            bomba = fuzzy_logic_control_2(sensor_tamb,sensor_hamb,sensor_tsol)
            if bomba > 50:
                tiempo_min = 60
                tiempo_max = 180
                tiempo_bomba = tiempo_min + (tiempo_max - tiempo_min) * (bomba - 50) / (100 - 50)
            else:
                tiempo_bomba = 0
            control_bomba(tiempo_bomba)


            # Controlar pwm leds
            pwm_leds_value = fuzzy_logic_control_3(sensor_tamb,sensor_hamb,sensor_lux)

            control_leds(pwm_leds_value, 6, 22)  # Ejemplo: LEDs encendidos de 6 AM a 10 PM
            time.sleep(60)  # Espera de un minuto antes de la siguiente lectura

# Tiempo tiene que ser 
# 140 ml -> 84 sec       42   6s -> 10ml ->v
 
    except KeyboardInterrupt:
        GPIO.cleanup()

if __name__ == "__main__":
    main()




