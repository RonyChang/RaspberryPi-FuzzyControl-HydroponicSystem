import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def setup_fuzzy_systems(sensor_ph, sensor_tds):
    # Primer sistema difuso: pH y TDS
    ph = ctrl.Antecedent(np.arange(0, 14, 0.1), 'ph')
    tds = ctrl.Antecedent(np.arange(0, 3000, 1), 'tds')
    pump_time = ctrl.Consequent(np.arange(0, 10, 0.1), 'pump_time')

       # Primer sistema difuso: pH y TDS
    ph = ctrl.Antecedent(np.arange(2.5, 10, 0.1), 'ph')
    tds = ctrl.Antecedent(np.arange(0, 5, 0.1), 'tds')
    pump_time = ctrl.Consequent(np.arange(0, 10, 0.1), 'pump_time')

    # Definir conjuntos difusos para cada variable
    ph['bajo'] = fuzz.trapmf(ph.universe, [2.5, 2.5, 5.5, 6])
    ph['normal'] = fuzz.trapmf(ph.universe, [5.5, 5.75, 6.75, 7.0])
    ph['alto'] = fuzz.trapmf(ph.universe, [6.5, 7, 10, 10])

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
    pump_sim = ctrl.ControlSystemSimulaion(pump_ctrl)

    # Probar el sistema con valores de entrada
    pump_sim.input['ph'] = sensor_ph
    pump_sim.input['tds'] = sensor_tds

    # Computar la salida
    pump_sim.compute()
    return pump_sim.output['pump_time']

# Valores de entrada
sensor_ph = 10.0
sensor_tds = 3.0

# Obtener el valor procesado
pump_time_value = setup_fuzzy_systems(sensor_ph, sensor_tds)
print(f"Tiempo de la bomba dosificadora: {pump_time_value}")

