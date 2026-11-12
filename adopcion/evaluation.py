"""Reglas explícitas v1. El puntaje se calcula en el servidor, nunca en el navegador."""


def calcular(respuestas):
    horas = respuestas["horas_disponibles"]
    tiempo = 25 if horas >= 3 else 20 if horas >= 2 else 10 if horas >= 1 else 5 if horas > 0 else 0
    disponible = respuestas["ingresos_mensuales"] - respuestas["gastos_mensuales"]
    presupuesto = respuestas["presupuesto_mascota"]
    capacidad = 0
    if presupuesto > 0 and disponible >= presupuesto:
        capacidad = 25 if disponible >= presupuesto * 2 else 20
    desglose = [
        {"criterio": "Tiempo diario de cuidado", "puntos": tiempo, "maximo": 25,
         "regla": "3 h o más: 25; 2 h: 20; 1 h: 10; menos de 1 h: 5; sin tiempo: 0."},
        {"criterio": "Presupuesto sostenible", "puntos": capacidad, "maximo": 25,
         "regla": "Ingresos menos gastos cubren el doble del presupuesto: 25; cubren el presupuesto: 20; no lo cubren o presupuesto cero: 0."},
        {"criterio": "Vivienda apta", "puntos": 10 if respuestas["vivienda_apta"] else 0, "maximo": 10, "regla": "Sí: 10; no: 0."},
        {"criterio": "Permiso para tener mascotas", "puntos": 10 if respuestas["permiso_vivienda"] else 0, "maximo": 10, "regla": "Sí: 10; no: 0."},
        {"criterio": "Acceso a atención veterinaria", "puntos": 10 if respuestas["acceso_veterinario"] else 0, "maximo": 10, "regla": "Sí: 10; no: 0."},
        {"criterio": "Experiencia con mascotas", "puntos": 5 if respuestas["experiencia"] else 0, "maximo": 5, "regla": "Sí: 5; no: 0."},
        {"criterio": "Apoyo durante ausencias", "puntos": 5 if respuestas["apoyo_ausencias"] else 0, "maximo": 5, "regla": "Sí: 5; no: 0."},
        {"criterio": "Compromiso de cuidado permanente", "puntos": 10 if respuestas["compromiso_cuidado"] else 0, "maximo": 10, "regla": "Sí: 10; no: 0."},
    ]
    puntaje = sum(item["puntos"] for item in desglose)
    return puntaje, puntaje > 70, desglose
