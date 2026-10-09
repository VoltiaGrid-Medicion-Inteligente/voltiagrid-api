import random
from datetime import timedelta

#* T-02.1: Catálogo de defectos y su configuración
class DefectCatalog:
    def __init__(self, base_rate: float = 0.02):
        """
        Toma DEFECT_RATE como valor por defecto, 
        pero permite ajustar cada tipo por separado.
        """
        self.null_rate = base_rate
        self.duplicate_rate = base_rate
        self.offset_clock_rate = base_rate
        self.out_of_bounds_rate = base_rate
        self.missing_day_rate = base_rate

#* T-02.2: Una función por defecto
# Todas reciben el objeto 'rng' (random.Random) para asegurar la reproducibilidad.

def inject_null(reading: dict, rng: random.Random) -> dict:
    """
    Inyecta lecturas nulas.
    Elige aleatoriamente entre inyectar el valor None o el texto "Null".
    """
    reading['energy_kwh'] = rng.choice([None, "Null"])
    return reading

def inject_duplicate(reading: dict, rng: random.Random) -> list:
    """
    Genera duplicados del mismo medidor e intervalo.
    El duplicado tiene valores de energía distintos.
    Retorna una lista con la lectura original y la duplicada.
    """
    duplicate = reading.copy()
    # Si la lectura tiene un valor numérico válido, lo alteramos
    if isinstance(reading.get('energy_kwh'), (int, float)):
        # Multiplicamos por un factor aleatorio para que el valor sea distinto
        duplicate['energy_kwh'] = round(reading['energy_kwh'] * rng.uniform(0.5, 1.5), 2)
    return [reading, duplicate]

def inject_offset_clock(reading: dict, rng: random.Random) -> dict:
    """
    Desfasa el reloj.
    Suma o resta minutos para que la hora no caiga en :00 ni en :30.
    """
    # Elegimos un desfase aleatorio entre 1 y 14 minutos (positivo o negativo)
    offset = rng.choice(list(range(1, 15)) + list(range(-14, 0)))
    reading['timestamp'] = reading['timestamp'] + timedelta(minutes=offset)
    return reading

def inject_out_of_bounds(reading: dict, rng: random.Random) -> dict:
    """
    Inyecta valores negativos o picos físicamente imposibles.
    Elige entre un valor negativo o un pico mayor a 25 kWh.
    """
    if rng.choice([True, False]):
        # Valor negativo entre -5 y -0.1
        reading['energy_kwh'] = round(rng.uniform(-5.0, -0.1), 2) 
    else:
        # Pico mayor a 25 kWh
        reading['energy_kwh'] = round(rng.uniform(25.1, 50.0), 2) 
    return reading

def should_skip_day(rng: random.Random, missing_day_rate: float) -> bool:
    """
    Determina si un día completo sin reporte de un medidor debe ocurrir.
    Esta función se llamaría desde el ciclo principal que genera los días.
    """
    return rng.random() < missing_day_rate