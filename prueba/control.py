import requests
import time
from datetime import datetime
import RPi.GPIO as GPIO
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# URL de la API
API_URL = "http://159.112.136.97:8080"

DOSIFICADORA_A_PIN = 23 # Pin 16
DOSIFICADORA_B_PIN = 24 # Pin 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(DOSIFICADORA_A_PIN, GPIO.OUT)
GPIO.setup(DOSIFICADORA_B_PIN, GPIO.OUT)

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
def main():
    try:
        while True:

            sensor_tamb = read_tamb()
            sensor_hamb = read_hamb()
            sensor_ph = read_ph()
            sensor_lux = read_lux()
            sensor_tds = read_tds()
            sensor_tsol = read_tsol()

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
    except KeyboardInterrupt:
        GPIO.cleanup()

if __name__ == "__main__":
    main()

