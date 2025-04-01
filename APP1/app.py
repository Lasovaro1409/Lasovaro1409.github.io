from flask import Flask, request, jsonify, send_file
import json
import os
import random
import xlsxwriter
from itertools import combinations
from twilio.rest import Client

app = Flask(__name__)

# Lista global para almacenar las combinaciones de esta semana
combinaciones_semana = []

# ------------------- CONFIGURACIÓN DE TWILIO --------------------
TWILIO_ACCOUNT_SID = 'ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
TWILIO_AUTH_TOKEN = 'your_auth_token'
TWILIO_PHONE_NUMBER = '+1234567890'  # Número asignado por Twilio
DESTINO_PHONE_NUMBER = '+0987654321'  # Número destino para SMS

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def enviar_sms_recordatorio():
    mensaje = "Recordatorio: confirme la disponibilidad de operarios en la app."
    try:
        message = client.messages.create(
            body=mensaje,
            from_=TWILIO_PHONE_NUMBER,
            to=DESTINO_PHONE_NUMBER
        )
        print(f"SMS enviado, SID: {message.sid}")
    except Exception as e:
        print(f"Error al enviar SMS: {e}")

# ------------------- FUNCIONES DE ASIGNACIÓN --------------------

def generar_parejas(operarios):
    return list(combinations(sorted(operarios), 2))

def generar_trios(operarios):
    return list(combinations(sorted(operarios), 3))

def sub_parejas_de_trio(trio):
    return list(combinations(trio, 2))

def cargar_used_pairs(file_path_json, file_path_txt):
    used_pairs = set()
    if os.path.exists(file_path_json):
        with open(file_path_json, 'r') as f:
            lista = json.load(f)
            used_pairs.update(tuple(sorted(pair)) for pair in lista)
    if os.path.exists(file_path_txt):
        with open(file_path_txt, 'r') as f:
            for line in f:
                pair = tuple(sorted(line.strip().split(", ")))
                used_pairs.add(pair)
    return used_pairs

def guardar_used_pairs(used_pairs, file_path_json, file_path_txt):
    lista = [list(pair) for pair in used_pairs]
    with open(file_path_json, 'w') as f:
        json.dump(lista, f)
    with open(file_path_txt, 'w') as f:
        for pair in used_pairs:
            f.write(", ".join(pair) + "\n")

def asignar_sin_repetir_parejas(equipos, operarios_totales, operarios_ausentes, used_pairs):
    # Se crea una copia local para cada grupo
    combinaciones_local = []
    # Filtra operarios disponibles para el grupo
    disponibles = [op for op in operarios_totales if op not in operarios_ausentes]
    random.shuffle(disponibles)

    parejas_disponibles = generar_parejas(disponibles)
    trios_disponibles = generar_trios(disponibles)
    random.shuffle(parejas_disponibles)
    random.shuffle(trios_disponibles)

    asignaciones = []
    for equipo, num_ops in equipos:
        if num_ops == 2:
            asignado = False
            for idx, par in enumerate(parejas_disponibles):
                if par not in used_pairs and par[0] in disponibles and par[1] in disponibles:
                    asignaciones.append((equipo, [par[0], par[1]]))
                    used_pairs.add(par)
                    combinaciones_local.append((equipo, par))
                    disponibles.remove(par[0])
                    disponibles.remove(par[1])
                    parejas_disponibles.pop(idx)
                    asignado = True
                    break
            if not asignado:
                return [], used_pairs, []
        elif num_ops == 3:
            asignado = False
            for idx, trio in enumerate(trios_disponibles):
                subp = sub_parejas_de_trio(trio)
                if not any(sp in used_pairs for sp in subp) and all(op in disponibles for op in trio):
                    asignaciones.append((equipo, list(trio)))
                    for sp in subp:
                        used_pairs.add(sp)
                    combinaciones_local.append((equipo, trio))
                    for op in trio:
                        disponibles.remove(op)
                    trios_disponibles.pop(idx)
                    asignado = True
                    break
            if not asignado:
                return [], used_pairs, []
    return asignaciones, used_pairs, combinaciones_local

def exportar_a_excel(asignaciones, nombre_archivo="distribucion_semana.xlsx"):
    workbook = xlsxwriter.Workbook(nombre_archivo)
    worksheet = workbook.add_worksheet("Programacion")
    worksheet.write(0, 0, "EQUIPO")
    worksheet.write(0, 1, "OPERARIO 1")
    worksheet.write(0, 2, "OPERARIO 2")
    worksheet.write(0, 3, "OPERARIO 3")
    worksheet.set_column(0, 0, 20)
    worksheet.set_column(1, 3, 20)
    
    fila = 1
    for equipo, ops in asignaciones:
        worksheet.write(fila, 0, equipo)
        for col, operario in enumerate(ops, start=1):
            worksheet.write(fila, col, operario)
        fila += 1
    workbook.close()

# ------------------- ENDPOINTS DE LA API --------------------

@app.route("/confirmar_disponibilidad", methods=["POST"])
def confirmar_disponibilidad():
    data = request.get_json()
    operarios_ausentes = data.get("operarios_ausentes", [])
    return jsonify({"mensaje": "Disponibilidad confirmada", "operarios_ausentes": operarios_ausentes})

@app.route("/generar_asignacion", methods=["GET"])
def generar_asignacion():
    # Se definen las listas de operarios para cada grupo
    operarios_elevadores = [
        "NELSON", "MURCIA", "ROSAS", "MIGUEL", "NOVOA", "ANTONI",
        "OMAR", "PARDO", "OPERARIO X1", "OPERARIO X2", "OPERARIO X3", "OPERARIO X4"
    ]
    operarios_traspallet = [
        "CRISTIAN", "VICTOR", "SERGIO", "YEFERSON", "BRAYAN", "DUVAN",
        "SEBASTIAN", "JOHAN", "IVAN", "EDWIN", "OPERARIO Y1", "OPERARIO Y2", "OPERARIO Y3", "OPERARIO Y4", "OPERARIO Y5"
    ]
    
    # Los operarios ausentes se podrían recibir mediante "/confirmar_disponibilidad"
    operarios_ausentes = []  

    # Definición de equipos y requerimientos
    equipos_y_requerimientos = [
        ("ELEVADOR 11", 3),
        ("ELEVADOR 2", 2),
        ("ELEVADOR 3", 2),
        ("ELEVADOR 16", 2),
        ("TRANSPALLET 6", 3),
        ("TRANSPALLET 7", 3),
        ("TRANSPALLET 9", 2),
        ("TRANSPALLET 10", 2),
        ("TRANSPALLET 12", 2),
        ("TRANSPALLET 13", 2)
    ]
    
    # Se separan los equipos según el tipo
    equipos_elevadores = [e for e in equipos_y_requerimientos if "ELEVADOR" in e[0]]
    equipos_traspallet = [e for e in equipos_y_requerimientos if "TRANSPALLET" in e[0]]
    
    # Cargamos los used_pairs para cada grupo (archivos separados)
    used_pairs_elevadores = cargar_used_pairs('used_pairs_elevadores.json', 'used_pairs_elevadores.txt')
    used_pairs_traspallet = cargar_used_pairs('used_pairs_traspallet.json', 'used_pairs_traspallet.txt')

    # Reiniciamos la lista global de combinaciones de la semana
    global combinaciones_semana
    combinaciones_semana = []

    # Asignación para elevadores
    asignaciones_elevadores, used_pairs_elevadores_actualizado, combinaciones_elevadores = asignar_sin_repetir_parejas(
        equipos_elevadores, operarios_elevadores, operarios_ausentes, used_pairs_elevadores
    )
    if not asignaciones_elevadores:
        return jsonify({"mensaje": "No se pudo generar asignación válida para elevadores."}), 400

    # Asignación para traspallet
    asignaciones_traspallet, used_pairs_traspallet_actualizado, combinaciones_traspallet = asignar_sin_repetir_parejas(
        equipos_traspallet, operarios_traspallet, operarios_ausentes, used_pairs_traspallet
    )
    if not asignaciones_traspallet:
        return jsonify({"mensaje": "No se pudo generar asignación válida para traspallet."}), 400

    # Combina ambas asignaciones y combinaciones
    asignaciones_totales = asignaciones_elevadores + asignaciones_traspallet
    combinaciones_semana = combinaciones_elevadores + combinaciones_traspallet

    # Exporta a Excel y guarda los used_pairs actualizados
    nombre_archivo = "distribucion_semana.xlsx"
    exportar_a_excel(asignaciones_totales, nombre_archivo)
    guardar_used_pairs(used_pairs_elevadores_actualizado, 'used_pairs_elevadores.json', 'used_pairs_elevadores.txt')
    guardar_used_pairs(used_pairs_traspallet_actualizado, 'used_pairs_traspallet.json', 'used_pairs_traspallet.txt')

    return jsonify({
        "mensaje": "Asignación generada con éxito",
        "asignaciones": asignaciones_totales,
        "combinaciones_semana": [
            {"equipo": equipo, "combinacion": list(combo)}
            for equipo, combo in combinaciones_semana
        ]
    })

@app.route("/enviar_recordatorio", methods=["POST"])
def enviar_recordatorio():
    try:
        enviar_sms_recordatorio()
        return jsonify({"mensaje": "SMS enviado correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/historial_combinaciones", methods=["GET"])
def historial_combinaciones():
    return jsonify({
        "combinaciones_semana": [
            {"equipo": equipo, "combinacion": list(combo)}
            for equipo, combo in combinaciones_semana
        ]
    })

# ------------------- EJECUCIÓN DEL SERVIDOR --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
