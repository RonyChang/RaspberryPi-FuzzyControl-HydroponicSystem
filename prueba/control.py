import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def setup_fuzzy_systems(sensor_ph, sensor_tds):
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
    return pump_sim.output['pump_time']

# Valores de entrada
sensor_ph = 6.5
sensor_tds = 1200

# Obtener el valor procesado
pump_time_value = setup_fuzzy_systems(sensor_ph, sensor_tds)
print(f"Tiempo de la bomba dosificadora: {pump_time_value}")