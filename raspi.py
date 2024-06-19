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

"""
def read_tamb():
    response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/TAMB")
    data = response.json()
    value_tamb = float(data["value"])  # Para que me de solo el valor del sensor
    return value_tamb
def read_hamb():
    response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/HAMB")
    data = response.json()
    value_hamb = float(data["value"])  # Para que me de solo el valor del sensor
    return value_hamb
def read_ph():
    response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/PH")
    data = response.json()
    value_ph = float(data["value"])  # Para que me de solo el valor del sensor
    return value_ph
def read_lux():
    response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/LUX")
    data = response.json()
    value_lux = float(data["value"])  # Para que me de solo el valor del sensor
    return value_lux
def read_tds():
    response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/TDS")
    data = response.json()
    value_tds = float(data["value"])  # Para que me de solo el valor del sensor
    return value_tds
def read_tsol():
    response = requests.get(f"{API_URL}/metrics/get-last-metric-from-sensor/TSOL")
    data = response.json()
    value_tsol = float(data["value"])  # Para que me de solo el valor del sensor
    return value_tsol
"""

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
    ph = ctrl.Antecedent(np.arange(0, 14, 0.1), 'ph')
    tds = ctrl.Antecedent(np.arange(0, 3000, 1), 'tds')
    pump_time = ctrl.Consequent(np.arange(0, 10, 0.1), 'pump_time')

    # Definir conjuntos difusos para cada variable
    ph['low'] = fuzz.trimf(ph.universe, [0, 0, 7])
    ph['high'] = fuzz.trimf(ph.universe, [7, 14, 14])

    tds['low'] = fuzz.trimf(tds.universe, [0, 0, 1500])
    tds['high'] = fuzz.trimf(tds.universe, [1500, 3000, 3000])

    pump_time['short'] = fuzz.trimf(pump_time.universe, [0, 0, 5])
    pump_time['long'] = fuzz.trimf(pump_time.universe, [5, 10, 10])

    # Reglas difusas
    rule1 = ctrl.Rule(ph['low'] & tds['low'], pump_time['short'])
    rule2 = ctrl.Rule(ph['high'] | tds['high'], pump_time['long'])

    # Crear sistema difuso
    pump_ctrl = ctrl.ControlSystem([rule1, rule2])
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
    temp_water = ctrl.Antecedent(np.arange(0, 50, 1), 'temp_water')
    temp_ambient = ctrl.Antecedent(np.arange(0, 50, 1), 'temp_ambient')
    humidity = ctrl.Antecedent(np.arange(0, 100, 1), 'humidity')
    pump_time_water = ctrl.Consequent(np.arange(0, 10, 0.1), 'pump_time_water')

    # Definir conjuntos difusos para cada variable
    temp_water['low'] = fuzz.trimf(temp_water.universe, [0, 0, 25])
    temp_water['high'] = fuzz.trimf(temp_water.universe, [25, 50, 50])

    temp_ambient['low'] = fuzz.trimf(temp_ambient.universe, [0, 0, 25])
    temp_ambient['high'] = fuzz.trimf(temp_ambient.universe, [25, 50, 50])

    humidity['low'] = fuzz.trimf(humidity.universe, [0, 0, 50])
    humidity['high'] = fuzz.trimf(humidity.universe, [50, 100, 100])

    pump_time_water['short'] = fuzz.trimf(pump_time_water.universe, [0, 0, 5])
    pump_time_water['long'] = fuzz.trimf(pump_time_water.universe, [5, 10, 10])

    # Reglas difusas
    rule3 = ctrl.Rule(temp_water['low'] & temp_ambient['low'] & humidity['low'], pump_time_water['short'])
    rule4 = ctrl.Rule(temp_water['high'] | temp_ambient['high'] | humidity['high'], pump_time_water['long'])

    # Crear sistema difuso
    water_pump_ctrl = ctrl.ControlSystem([rule3, rule4])
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
    temp_ambient = ctrl.Antecedent(np.arange(0, 50, 1), 'temp_ambient')
    light_intensity = ctrl.Antecedent(np.arange(0, 1000, 1), 'light_intensity')
    pwm = ctrl.Consequent(np.arange(0, 100, 1), 'pwm')

    # Definir conjuntos difusos para cada variable
    temp_water['low'] = fuzz.trimf(temp_water.universe, [0, 0, 25])
    temp_water['high'] = fuzz.trimf(temp_water.universe, [25, 50, 50])

    temp_ambient['low'] = fuzz.trimf(temp_ambient.universe, [0, 0, 25])
    temp_ambient['high'] = fuzz.trimf(temp_ambient.universe, [25, 50, 50])

    light_intensity['low'] = fuzz.trimf(light_intensity.universe, [0, 0, 500])
    light_intensity['high'] = fuzz.trimf(light_intensity.universe, [500, 1000, 1000])

    pwm['dim'] = fuzz.trimf(pwm.universe, [0, 0, 50])
    pwm['bright'] = fuzz.trimf(pwm.universe, [50, 100, 100])

    # Reglas difusas
    rule5 = ctrl.Rule(light_intensity['low'], pwm['dim'])
    rule6 = ctrl.Rule(light_intensity['high'], pwm['bright'])

    light_ctrl = ctrl.ControlSystem([rule5, rule6])
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
            sensor_tamb = read_tamb()
            sensor_hamb = read_hamb()
            sensor_ph = read_ph()
            sensor_lux = read_lux()
            sensor_tds = read_tds()
            sensor_tsol = read_tsol()

            tiempo_dosificadora_b = fuzzy_logic_control_1(sensor_ph,sensor_tds)
            tiempo_bomba = fuzzy_logic_control_2(sensor_tamb,sensor_hamb,sensor_tsol)
            pwm_leds_value = fuzzy_logic_control_3(sensor_tamb,sensor_hamb,sensor_lux)

            control_bomba(tiempo_bomba)
            
            control_dosificadora_b(tiempo_dosificadora_b)
            tiempo_dosificadora_a = (tiempo_dosificadora_b)*5/2
            control_dosificadora_a(tiempo_dosificadora_a)

            control_leds(pwm_leds_value, 6, 18)  # Ejemplo: LEDs encendidos de 6 AM a 6 PM
            time.sleep(60)  # Espera de un minuto antes de la siguiente lectura

# Tiempo tiene que ser 
# 140 ml -> 84 sec

    except KeyboardInterrupt:
        GPIO.cleanup()

if __name__ == "__main__":
    main()



"""
    # Definir las variables difusas de entrada
    ph = ctrl.Antecedent(np.arange(5, 8, 0.1), 'ph')
    conductividad = ctrl.Antecedent(np.arange(0, 2000, 1), 'conductividad')
    humedad_ambiente = ctrl.Antecedent(np.arange(0, 100, 1), 'humedad_ambiente')
    temperatura_ambiente = ctrl.Antecedent(np.arange(0, 50, 1), 'temperatura_ambiente')
    temperatura_solucion = ctrl.Antecedent(np.arange(0, 50, 1), 'temperatura_solucion')

    # Definir las funciones de membresía para las variables de entrada
    ph['bajo'] = fuzz.trimf(ph.universe, [5, 5, 6])
    ph['medio'] = fuzz.trimf(ph.universe, [5.5, 6, 6.5])
    ph['alto'] = fuzz.trimf(ph.universe, [6, 7, 7])

    conductividad['baja'] = fuzz.trimf(conductividad.universe, [0, 0, 1000])
    conductividad['media'] = fuzz.trimf(conductividad.universe, [500, 1000, 1500])
    conductividad['alta'] = fuzz.trimf(conductividad.universe, [1000, 2000, 2000])

    humedad_ambiente['baja'] = fuzz.trimf(humedad_ambiente.universe, [0, 0, 50])
    humedad_ambiente['media'] = fuzz.trimf(humedad_ambiente.universe, [25, 50, 75])
    humedad_ambiente['alta'] = fuzz.trimf(humedad_ambiente.universe, [50, 100, 100])

    temperatura_ambiente['baja'] = fuzz.trimf(temperatura_ambiente.universe, [0, 0, 25])
    temperatura_ambiente['media'] = fuzz.trimf(temperatura_ambiente.universe, [20, 25, 30])
    temperatura_ambiente['alta'] = fuzz.trimf(temperatura_ambiente.universe, [25, 50, 50])

    temperatura_solucion['baja'] = fuzz.trimf(temperatura_solucion.universe, [0, 0, 25])
    temperatura_solucion['media'] = fuzz.trimf(temperatura_solucion.universe, [20, 25, 30])
    temperatura_solucion['alta'] = fuzz.trimf(temperatura_solucion.universe, [25, 50, 50])

    # Definir las variables de salida para el tiempo de las bombas (Sugeno)
    tiempo_dosificadora = ctrl.Consequent(np.arange(0, 300, 1), 'tiempo_dosificadora', defuzzify_method='sugeno')
    tiempo_nutrientes = ctrl.Consequent(np.arange(0, 300, 1), 'tiempo_nutrientes', defuzzify_method='sugeno')

    # Agregar las funciones de salida de Sugeno (constantes)
    tiempo_dosificadora['corto'] = lambda x: 100  # Constante
    tiempo_dosificadora['medio'] = lambda x: 200  # Constante
    tiempo_dosificadora['largo'] = lambda x: 300  # Constante

    tiempo_nutrientes['corto'] = lambda x: 100  # Constante
    tiempo_nutrientes['medio'] = lambda x: 200  # Constante
    tiempo_nutrientes['largo'] = lambda x: 300  # Constante

    # Definir las reglas difusas de Sugeno para la bomba dosificadora
    regla1 = ctrl.Rule(ph['bajo'] & conductividad['baja'], tiempo_dosificadora['corto'])
    regla2 = ctrl.Rule(ph['medio'] & conductividad['media'], tiempo_dosificadora['medio'])
    regla3 = ctrl.Rule(ph['alto'] & conductividad['alta'], tiempo_dosificadora['largo'])

    # Definir las reglas difusas de Sugeno para la bomba de nutrientes
    regla4 = ctrl.Rule(humedad_ambiente['baja'] & temperatura_ambiente['baja'] & temperatura_solucion['baja'], tiempo_nutrientes['corto'])
    regla5 = ctrl.Rule(humedad_ambiente['media'] & temperatura_ambiente['media'] & temperatura_solucion['media'], tiempo_nutrientes['medio'])
    regla6 = ctrl.Rule(humedad_ambiente['alta'] & temperatura_ambiente['alta'] & temperatura_solucion['alta'], tiempo_nutrientes['largo'])

    # Crear el sistema de control difuso
    sistema_dosificadora = ctrl.ControlSystem([regla1, regla2, regla3])
    control_dosificadora = ctrl.ControlSystemSimulation(sistema_dosificadora)

    sistema_nutrientes = ctrl.ControlSystem([regla4, regla5, regla6])
    control_nutrientes = ctrl.ControlSystemSimulation(sistema_nutrientes)

    # Probar el sistema con valores de entrada
    control_dosificadora.input['ph'] = sensor_ph
    control_dosificadora.input['conductividad'] = sensor_tds

    control_nutrientes.input['humedad_ambiente'] = sensor_hamb
    control_nutrientes.input['temperatura_ambiente'] = sensor_tamb
    control_nutrientes.input['temperatura_solucion'] = sensor_tsol

    # Computar la salida
    control_dosificadora.compute()
    control_nutrientes.compute()

    print(f"Tiempo de la bomba dosificadora: {control_dosificadora.output['tiempo_dosificadora']}")
    print(f"Tiempo de la bomba de nutrientes: {control_nutrientes.output['tiempo_nutrientes']}")

    tiempo_bomba = 1
    tiempo_dosificadora_a = 1
    tiempo_dosificadora_b = 1
    pwm_led = 1
    
    return tiempo_bomba, tiempo_dosificadora_a, tiempo_dosificadora_b, pwm_led
"""




