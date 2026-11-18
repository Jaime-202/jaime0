# jaime0_servicio.reglas: motor de reglas CUANDO -> SI -> HACER (catalogos, validacion,
# Acciones, MotorReglas) y sus fuentes de eventos (Bluetooth, red, Hyprland). Depende de: base,
# medicion (bateria y cargador), historico (JSONL), sistema (D-Bus, programa_hermano, Hyprland) y
# perfiles (PERFILES, normalizar_perfil).

import collections
import datetime
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
import traceback
import unicodedata

from .base import PRODUCTO
from .base import VERSION_DATOS, carpeta_config, registrar, protegido
from .medicion import leer_bateria, leer_cargador
from .historico import leer_jsonl, anexar_jsonl, reescribir_jsonl
from .sistema import programa_hermano, _gi, _llamar, ruta_socket2, firma_hyprland, entorno_hyprland
from .perfiles import PERFILES, normalizar_perfil

__all__ = [
    "MAX_EJECUCIONES", "MAX_REGLAS", "MAX_ACCIONES", "MAX_CONDICIONES", "ENFRIAMIENTO",
    "TOPE_GLOBAL", "TOPE_REGLA", "HISTERESIS_BATERIA", "DIAS_MINIATURAS", "TIMEOUT_SCRIPT",
    "SILENCIO_APLICACION", "REINTENTOS_SINK", "VALIDEZ_APLICACIONES", "VALIDEZ_DISPONIBILIDAD",
    "LIMITE_PERFIL", "REINTENTO_HYPRLAND", "MENSAJE_PRIVILEGIADA", "ACCIONES_PRIVILEGIADAS",
    "IDS_PERFIL", "RE_HORA", "RE_ID_REGLA", "RE_ID_APP", "UUID_AUDIO", "NOMBRES_DIA", "_p",
    "EVENTOS", "CONDICIONES", "ACCIONES", "EVENTOS_POR_ID", "tiene_control", "validar_valor",
    "validar_bloque", "validar_regla", "slug_regla", "id_unico", "regla_ejecutable",
    "texto_evento", "coincide", "minutos_de", "evaluar_condicion", "PRIORIDADES", "NIVEL_PRIORIDAD",
    "recurso_accion", "NOMBRES_RECURSO", "resolver_conflictos", "huella_regla", "posibles_choques",
    "proxima_hora", "MAX_CONFLICTOS",
    "estado_bateria_baja", "info_bluez", "cambio_bluez", "estado_red", "AnalizadorHyprland",
    "parsear_sinks_wpctl", "limpiar_miniaturas", "comprobar_script", "limpiar_detalle",
    "AplicacionesDisponibles", "ejecutar_grupo", "Acciones", "HistorialEjecuciones",
    "MotorReglas", "nombre_en_bus", "disponibilidad_sistema", "vigilar_bluetooth", "NM",
    "PROPS", "vigilar_red", "FuenteHyprland"
]


# ---------------------------------------------------------------------------
# Reglas (Fase 6): motor CUANDO -> SI -> HACER. Modulo propio: no depende de la salud, de
# los perfiles ni de la API. Todo lo que toca el sistema (subprocesos, reloj, hilos, GLib,
# aplicaciones, perfiles) entra por argumentos del motor, asi que se prueba sin D-Bus ni
# sockets. Proteccion contra bucles: origen en cada cambio (los eventos causados por una
# regla no disparan reglas), disparo por flanco, enfriamiento de 30 s por regla, tope por
# regla (la regla se desactiva y queda una incidencia), tope global (las ejecuciones de
# sobra se omiten, sin desactivar ninguna regla, y queda una incidencia por ventana),
# "perfil -> perfil" rechazado y reglas importadas desactivadas hasta que el usuario las active.
# Conflictos (evolucion, fase 3): si un mismo evento dispara reglas que piden valores
# distintos para el mismo recurso, gana la de prioridad mas alta (o la que va antes en la
# lista) y a la otra se le omite esa accion, con el motivo en el historial; no se guardan
# reglas repetidas.
# ---------------------------------------------------------------------------

MAX_EJECUCIONES = 1000              # lineas de ejecuciones.jsonl
MAX_CONFLICTOS = 20                 # conflictos recientes que se recuerdan (en memoria)
MAX_REGLAS = 100
MAX_ACCIONES = 5
MAX_CONDICIONES = 10
ENFRIAMIENTO = 30                   # segundos entre dos disparos de la misma regla
TOPE_GLOBAL = (20, 60)              # mas de 20 ejecuciones en 60 s en total
TOPE_REGLA = (5, 300)               # la misma regla 5 veces en 5 min
HISTERESIS_BATERIA = 5              # puntos por encima del umbral para rearmar
DIAS_MINIATURAS = 30
TIMEOUT_SCRIPT = 60
SILENCIO_APLICACION = 15            # s sin eventos "aplicacion abierta" tras abrir una una regla
REINTENTOS_SINK = 6                 # el sink Bluetooth tarda un poco en aparecer
VALIDEZ_APLICACIONES = 60           # s que se recuerda la lista de jaime0-anclar
VALIDEZ_DISPONIBILIDAD = 60         # s que se recuerda que eventos y acciones hay (D-Bus)
LIMITE_PERFIL = 60                  # s que una regla espera a que se aplique un perfil
REINTENTO_HYPRLAND = 10             # s entre intentos de conectar con socket2
MENSAJE_PRIVILEGIADA = "Esta acción necesita autorización de administrador: no se puede automatizar"
ACCIONES_PRIVILEGIADAS = ()         # acciones que necesitarian root: el motor las rechaza
IDS_PERFIL = tuple(p["id"] for p in PERFILES) + ("custom",)
RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
RE_ID_REGLA = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
RE_ID_APP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@-]{0,127}$")
UUID_AUDIO = ("110a", "110b", "1108", "111e", "111f")     # A2DP (origen y destino), HSP y HFP
NOMBRES_DIA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _p(clave, tipo, texto, requerido=True, defecto=None, opciones=None, minimo=None, maximo=None):
    """Un parametro del catalogo. tipo: opcion, perfil, entero, texto, hora, dias, bool,
    aplicacion o script. Para texto, min y max son longitudes."""
    d = {"clave": clave, "tipo": tipo, "texto": texto, "requerido": requerido, "defecto": defecto}
    if opciones is not None:
        d["opciones"] = list(opciones)
    if minimo is not None:
        d["min"] = minimo
    if maximo is not None:
        d["max"] = maximo
    return d


EVENTOS = (
    {"id": "bateria_baja", "nombre": "Batería baja",
     "descripcion": "La batería baja del umbral con el equipo descargándose (se rearma 5 puntos por encima "
                    "o al conectar el cargador)",
     "parametros": (_p("umbral", "entero", "Porcentaje", False, 20, minimo=5, maximo=95),)},
    {"id": "cargador", "nombre": "Cargador", "descripcion": "Se conecta o se desconecta el cargador",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("conectado", "desconectado")),)},
    {"id": "bluetooth", "nombre": "Bluetooth", "descripcion": "Un dispositivo Bluetooth se conecta o se desconecta",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("conectado", "desconectado")),
                    _p("tipo", "opcion", "Tipo de dispositivo", False, "cualquiera", opciones=("audio", "cualquiera")),
                    _p("nombre", "texto", "Parte del nombre del dispositivo", False, minimo=1, maximo=60))},
    {"id": "monitor", "nombre": "Monitor", "descripcion": "Se conecta o se desconecta un monitor",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("conectado", "desconectado")),)},
    {"id": "aplicacion", "nombre": "Aplicación",
     "descripcion": "Se abre la primera ventana de una aplicación o se cierra la última",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("abierta", "cerrada")),
                    _p("clase", "texto", "Clase de la ventana (sin distinguir mayúsculas)", minimo=1, maximo=80))},
    {"id": "hora", "nombre": "Hora", "descripcion": "Llega una hora del día",
     "parametros": (_p("hora", "hora", "Hora (HH:MM)"),
                    _p("dias", "dias", "Días de la semana (0 = lunes … 6 = domingo; vacío = todos)", False, []))},
    {"id": "red", "nombre": "Red", "descripcion": "La red se conecta o se desconecta",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("conectada", "desconectada")),
                    _p("wifi", "texto", "Nombre exacto de la red Wi-Fi", False, minimo=1, maximo=64))},
    {"id": "suspension", "nombre": "Suspensión", "descripcion": "El equipo se suspende o se reanuda",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("suspender", "reanudar")),)},
    {"id": "inactividad", "nombre": "Inactividad", "descripcion": "La sesión pasa a inactiva (5 min) o vuelve a estar activa",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("inactivo", "activo")),)},
    {"id": "estado_sistema", "nombre": "Estado del sistema", "descripcion": "Cambia el estado global del sistema",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("WARNING", "CRITICAL", "ONLINE")),)},
    {"id": "servicio_fallido", "nombre": "Servicio fallido",
     "descripcion": "Aparece una unidad nueva entre las fallidas de systemd", "parametros": ()},
    {"id": "perfil", "nombre": "Perfil", "descripcion": f"Cambias de perfil de {PRODUCTO} (los cambios de una regla no cuentan)",
     "parametros": (_p("perfil", "perfil", "Perfil", opciones=IDS_PERFIL),)},
)

CONDICIONES = (
    {"id": "perfil_es", "nombre": "El perfil es", "descripcion": "El perfil activo es el indicado",
     "parametros": (_p("perfil", "perfil", "Perfil", opciones=IDS_PERFIL),)},
    {"id": "cargador", "nombre": "Cargador", "descripcion": "El cargador está conectado o desconectado",
     "parametros": (_p("conectado", "bool", "Conectado"),)},
    {"id": "bateria_menor", "nombre": "Batería por debajo de", "descripcion": "El nivel de batería es menor que el valor",
     "parametros": (_p("valor", "entero", "Porcentaje", minimo=1, maximo=100),)},
    {"id": "bateria_mayor", "nombre": "Batería por encima de", "descripcion": "El nivel de batería es mayor que el valor",
     "parametros": (_p("valor", "entero", "Porcentaje", minimo=0, maximo=99),)},
    {"id": "entre_horas", "nombre": "Entre horas", "descripcion": "La hora actual está en el intervalo (puede pasar de medianoche)",
     "parametros": (_p("desde", "hora", "Desde (HH:MM)"), _p("hasta", "hora", "Hasta (HH:MM)"))},
    {"id": "dias", "nombre": "Días", "descripcion": "Hoy es uno de los días indicados",
     "parametros": (_p("dias", "dias", "Días de la semana (0 = lunes … 6 = domingo)"),)},
)

ACCIONES = (
    {"id": "perfil", "nombre": "Cambiar de perfil", "descripcion": f"Aplica un perfil de {PRODUCTO}",
     "parametros": (_p("perfil", "perfil", "Perfil", opciones=IDS_PERFIL),)},
    {"id": "modo_noche", "nombre": "Modo noche", "descripcion": "Enciende o apaga el modo noche",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("encender", "apagar")),)},
    {"id": "no_molestar", "nombre": "No molestar", "descripcion": "Activa o desactiva No molestar",
     "parametros": (_p("estado", "opcion", "Estado", opciones=("activar", "desactivar")),)},
    {"id": "notificar", "nombre": "Notificar", "descripcion": "Muestra una notificación",
     "parametros": (_p("titulo", "texto", "Título", minimo=1, maximo=80),
                    _p("texto", "texto", "Texto", minimo=1, maximo=300))},
    {"id": "abrir_aplicacion", "nombre": "Abrir aplicación", "descripcion": "Abre una aplicación instalada",
     "parametros": (_p("id", "aplicacion", "Aplicación"),)},
    {"id": "volumen", "nombre": "Volumen", "descripcion": "Fija el volumen de la salida de audio",
     "parametros": (_p("nivel", "entero", "Nivel (%)", minimo=0, maximo=100),)},
    {"id": "silenciar", "nombre": "Silenciar", "descripcion": "Silencia o reactiva el sonido",
     "parametros": (_p("estado", "opcion", "Silenciado", opciones=("si", "no")),)},
    {"id": "salida_audio", "nombre": "Salida de audio",
     "descripcion": "Elige la salida de audio cuyo nombre contiene el texto",
     "parametros": (_p("nombre", "texto", "Parte del nombre de la salida", minimo=1, maximo=80),)},
    {"id": "mantenimiento", "nombre": "Mantenimiento", "descripcion": "Una tarea de mantenimiento sin privilegios",
     "parametros": (_p("tarea", "opcion", "Tarea", opciones=("limpiar_miniaturas", "comprobar_actualizaciones")),)},
    {"id": "script", "nombre": "Script autorizado",
     "descripcion": "Ejecuta un archivo de ~/.config/jaime0/scripts-autorizados (sin argumentos, 60 s como máximo)",
     "parametros": (_p("nombre", "script", "Nombre del archivo", minimo=1, maximo=100),)},
)
EVENTOS_POR_ID = {e["id"]: e for e in EVENTOS}


def tiene_control(texto):
    return any(unicodedata.category(c) == "Cc" for c in texto)


def validar_valor(p, valor, ctx):
    """(valor_limpio, error) de un parametro segun su definicion. ctx: {"apps": dict | None
    o callable que lo devuelve, "estricto": bool} (aplicaciones disponibles; con estricto,
    no poder consultarlas es un error)."""
    t, c = p["tipo"], p["clave"]
    if t == "opcion":
        if not isinstance(valor, str) or valor not in p["opciones"]:
            return None, f"«{c}» debe ser uno de: {', '.join(p['opciones'])}"
        return valor, None
    if t == "perfil":
        if not isinstance(valor, str) or normalizar_perfil(valor) not in IDS_PERFIL:
            return None, f"«{c}» debe ser un perfil conocido: {', '.join(IDS_PERFIL)}"
        return normalizar_perfil(valor), None
    if t == "entero":
        if isinstance(valor, bool) or not isinstance(valor, int) or not p["min"] <= valor <= p["max"]:
            return None, f"«{c}» debe ser un número entero entre {p['min']} y {p['max']}"
        return valor, None
    if t in ("texto", "script"):
        if not isinstance(valor, str):
            return None, f"«{c}» debe ser un texto"
        v = valor.strip()
        if not p.get("min", 1) <= len(v) <= p["max"]:
            return None, f"«{c}» debe tener entre {p.get('min', 1)} y {p['max']} caracteres"
        if tiene_control(v):
            return None, f"«{c}» no puede llevar caracteres de control"
        if t == "script" and (any(x in v for x in "/\\\x00") or ".." in v):
            return None, f"«{c}» no es un nombre de script válido (sin «/» ni «..»)"
        return v, None
    if t == "hora":
        if not isinstance(valor, str) or not RE_HORA.match(valor):
            return None, f"«{c}» debe ser una hora HH:MM (00:00 a 23:59)"
        return valor, None
    if t == "dias":
        ok = (isinstance(valor, list) and len(valor) <= 7
              and all(isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6 for d in valor))
        if not ok:
            return None, f"«{c}» debe ser una lista de días de 0 (lunes) a 6 (domingo)"
        if not valor and p["requerido"]:
            return None, f"«{c}» necesita al menos un día"
        return sorted(set(valor)), None
    if t == "bool":
        if not isinstance(valor, bool):
            return None, f"«{c}» debe ser verdadero o falso"
        return valor, None
    if t == "aplicacion":
        if not isinstance(valor, str) or not RE_ID_APP.match(valor) or valor.isdigit():
            return None, f"«{c}» no es un identificador de aplicación válido"
        apps = ctx["apps"]() if callable(ctx.get("apps")) else ctx.get("apps")
        if apps is None:
            if ctx.get("estricto"):
                return None, "no se pudo comprobar la lista de aplicaciones disponibles"
        elif valor not in apps:
            return None, f"la aplicación «{valor}» no está en la lista de aplicaciones disponibles"
        return valor, None
    return None, f"tipo de parámetro desconocido: {t}"


def validar_bloque(catalogo, clave, doc, ctx, etiqueta):
    """(bloque_limpio, error) de un evento, una condicion o una accion. Estricta: sin
    parametros desconocidos ni tipos distintos."""
    if not isinstance(doc, dict):
        return None, f"{etiqueta}: debe ser un objeto"
    tipo = doc.get(clave)
    entrada = next((e for e in catalogo if e["id"] == tipo), None)
    if entrada is None:
        return None, f"{etiqueta}: {clave} desconocido ({tipo!r})" if tipo is not None else f"{etiqueta}: falta «{clave}»"
    conocidos = {p["clave"] for p in entrada["parametros"]}
    for k in doc:
        if k != clave and k not in conocidos:
            return None, f"{etiqueta}: parámetro desconocido «{k}»"
    limpio = {clave: tipo}
    for p in entrada["parametros"]:
        v = doc.get(p["clave"])
        if v is None:
            if p["requerido"]:
                return None, f"{etiqueta}: falta «{p['clave']}»"
            if p["defecto"] is not None:
                limpio[p["clave"]] = list(p["defecto"]) if isinstance(p["defecto"], list) else p["defecto"]
            continue
        valor, error = validar_valor(p, v, ctx)
        if error:
            return None, f"{etiqueta}: {error}"
        limpio[p["clave"]] = valor
    return limpio, None


def validar_regla(doc, ctx):
    """(regla, error): estricta. La regla limpia lleva id (o None si no venia), nombre,
    activa, prioridad, cuando, si, hacer y revisar. Lo que solo anade el listado (ultima,
    proxima, choca_con) se ignora."""
    if not isinstance(doc, dict):
        return None, "la regla debe ser un objeto"
    for k in doc:
        if k not in ("id", "nombre", "activa", "prioridad", "cuando", "si", "hacer", "revisar",
                     "ultima", "proxima", "choca_con"):
            return None, f"campo desconocido en la regla: «{k}»"
    rid = doc.get("id")
    if rid is not None and (not isinstance(rid, str) or not RE_ID_REGLA.match(rid)):
        return None, "el id de la regla debe usar letras minúsculas, números y guiones (máximo 48)"
    nombre = doc.get("nombre")
    if not isinstance(nombre, str) or not 1 <= len(nombre.strip()) <= 60 or tiene_control(nombre):
        return None, "el nombre de la regla debe tener entre 1 y 60 caracteres"
    for campo, defecto in (("activa", True), ("revisar", False)):
        if not isinstance(doc.get(campo, defecto), bool):
            return None, f"«{campo}» debe ser verdadero o falso"
    prioridad = doc.get("prioridad", "normal")
    if prioridad not in PRIORIDADES:
        return None, "«prioridad» debe ser alta, normal o baja"
    cuando, error = validar_bloque(EVENTOS, "evento", doc.get("cuando"), ctx, "CUANDO")
    if error:
        return None, error
    si_doc = doc.get("si", [])
    if not isinstance(si_doc, list) or len(si_doc) > MAX_CONDICIONES:
        return None, f"«si» debe ser una lista de hasta {MAX_CONDICIONES} condiciones"
    si = []
    for i, c in enumerate(si_doc):
        etiqueta = f"SI, condición {i + 1}"
        limpio, error = validar_bloque(CONDICIONES, "condicion", c, ctx, etiqueta)
        if error:
            return None, error
        if limpio["condicion"] == "entre_horas" and limpio["desde"] == limpio["hasta"]:
            return None, f"{etiqueta}: «desde» y «hasta» no pueden ser iguales"
        si.append(limpio)
    hacer_doc = doc.get("hacer")
    if not isinstance(hacer_doc, list) or not 1 <= len(hacer_doc) <= MAX_ACCIONES:
        return None, f"«hacer» debe ser una lista de 1 a {MAX_ACCIONES} acciones"
    hacer = []
    for i, a in enumerate(hacer_doc):
        etiqueta = f"HACER, acción {i + 1}"
        if isinstance(a, dict) and a.get("accion") in ACCIONES_PRIVILEGIADAS:
            return None, f"{etiqueta}: {MENSAJE_PRIVILEGIADA}"
        limpio, error = validar_bloque(ACCIONES, "accion", a, ctx, etiqueta)
        if error:
            return None, error
        hacer.append(limpio)
    if cuando["evento"] == "perfil" and any(a["accion"] == "perfil" for a in hacer):
        return None, ("Una regla que reacciona a un cambio de perfil no puede cambiar de perfil: "
                      "crearía un bucle")
    return {"id": rid, "nombre": nombre.strip(), "activa": doc.get("activa", True), "prioridad": prioridad,
            "cuando": cuando, "si": si, "hacer": hacer, "revisar": doc.get("revisar", False)}, None


def slug_regla(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40].strip("-")
    return t or "regla"


def id_unico(base, usados):
    if base not in usados:
        return base
    n = 2
    while f"{base}-{n}" in usados:
        n += 1
    return f"{base}-{n}"


def regla_ejecutable(r):
    return bool(r.get("activa")) and not r.get("revisar")


# -- eventos y condiciones (funciones puras) -------------------------------------

def texto_evento(nombre, d):
    """Descripcion legible del evento que dispara (va al historial)."""
    if nombre == "bateria_baja":
        return f"Batería baja ({d.get('nivel')} %)" if d.get("nivel") is not None else "Batería baja"
    if nombre == "cargador":
        return f"Cargador {d.get('estado')}"
    if nombre in ("bluetooth", "monitor"):
        etiqueta = "Bluetooth" if nombre == "bluetooth" else "Monitor"
        return f"{etiqueta} {d.get('estado')}" + (f": {d['nombre']}" if d.get("nombre") else "")
    if nombre == "aplicacion":
        return f"Aplicación {d.get('estado')}: {d.get('clase')}"
    if nombre == "hora":
        return f"Hora: {d.get('hora')}"
    if nombre == "red":
        return f"Red {d.get('estado')}" + (f": {d['wifi']}" if d.get("wifi") else "")
    if nombre == "suspension":
        return "Equipo suspendido" if d.get("estado") == "suspender" else "Equipo reanudado"
    if nombre == "inactividad":
        return "Sesión inactiva" if d.get("estado") == "inactivo" else "Sesión activa de nuevo"
    if nombre == "estado_sistema":
        return f"Estado del sistema: {d.get('estado')}"
    if nombre == "servicio_fallido":
        return f"Servicio fallido: {d.get('unidad')}"
    if nombre == "perfil":
        return f"Perfil cambiado a {d.get('perfil')}"
    return nombre


def coincide(cuando, d):
    """True si el evento (datos d) cumple los parametros de CUANDO de una regla."""
    ev = cuando.get("evento")
    if ev in ("cargador", "monitor", "suspension", "inactividad", "estado_sistema"):
        return cuando.get("estado") == d.get("estado")
    if ev == "bateria_baja":
        return cuando.get("umbral", 20) == d.get("umbral")
    if ev == "bluetooth":
        if cuando.get("estado") != d.get("estado"):
            return False
        if cuando.get("tipo", "cualquiera") == "audio" and not d.get("audio"):
            return False
        patron = cuando.get("nombre")
        return not patron or patron.casefold() in str(d.get("nombre") or "").casefold()
    if ev == "aplicacion":
        return (cuando.get("estado") == d.get("estado")
                and str(cuando.get("clase", "")).casefold() == str(d.get("clase") or "").casefold())
    if ev == "hora":
        dias = cuando.get("dias") or []
        return cuando.get("hora") == d.get("hora") and (not dias or d.get("dia") in dias)
    if ev == "red":
        return cuando.get("estado") == d.get("estado") and (not cuando.get("wifi") or cuando["wifi"] == d.get("wifi"))
    if ev == "servicio_fallido":
        return True
    if ev == "perfil":
        return cuando.get("perfil") == d.get("perfil")
    return False


def minutos_de(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def evaluar_condicion(c, est):
    """est: {"perfil", "cargador", "bateria", "ahora" (datetime)}. Un dato que falta
    (sin bateria, cargador desconocido) hace que la condicion no se cumpla."""
    t = c["condicion"]
    if t == "perfil_es":
        return est.get("perfil") == c["perfil"]
    if t == "cargador":
        return est.get("cargador") is not None and est["cargador"] == c["conectado"]
    if t == "bateria_menor":
        return est.get("bateria") is not None and est["bateria"] < c["valor"]
    if t == "bateria_mayor":
        return est.get("bateria") is not None and est["bateria"] > c["valor"]
    if t == "entre_horas":
        ahora = est["ahora"].hour * 60 + est["ahora"].minute
        desde, hasta = minutos_de(c["desde"]), minutos_de(c["hasta"])
        return desde <= ahora < hasta if desde < hasta else (ahora >= desde or ahora < hasta)
    if t == "dias":
        return est["ahora"].weekday() in c["dias"]
    return False


# -- conflictos y duplicados (funciones puras) --------------------------------------
# Dos reglas chocan si el MISMO evento las dispara a la vez y piden valores distintos para
# el mismo recurso (perfil, volumen, no molestar...). Se resuelve siempre igual: gana la de
# prioridad mas alta y, a igual prioridad, la que va antes en la lista (la mas antigua). A
# la perdedora solo se le omiten las acciones en conflicto, y queda anotado por que.

PRIORIDADES = ("alta", "normal", "baja")
NIVEL_PRIORIDAD = {"alta": 0, "normal": 1, "baja": 2}


def recurso_accion(a):
    """(recurso, valor pedido) de una accion, o None si no puede chocar con otra (notificar,
    abrir una aplicacion, mantenimiento o un script se pueden hacer a la vez)."""
    t = a.get("accion")
    if t == "perfil":
        return "perfil", a.get("perfil")
    if t in ("modo_noche", "no_molestar", "silenciar"):
        return t, a.get("estado")
    if t == "volumen":
        return "volumen", a.get("nivel")
    if t == "salida_audio":
        return "salida_audio", str(a.get("nombre", "")).casefold()
    return None


NOMBRES_RECURSO = {"perfil": "perfil", "modo_noche": "modo noche", "no_molestar": "no molestar",
                   "silenciar": "silencio", "volumen": "volumen", "salida_audio": "salida de audio"}


def resolver_conflictos(reglas):
    """reglas: las que dispara un mismo evento, en el orden de la lista. Devuelve
    (planes, conflictos): planes[i] = (acciones que se ejecutan, [(accion omitida, ganadora)])
    para reglas[i]; conflictos = [{"recurso", "ganadora", "perdedora", "motivo"}]."""
    orden = sorted(range(len(reglas)),
                   key=lambda i: (NIVEL_PRIORIDAD.get(reglas[i].get("prioridad", "normal"), 1), i))
    reservado, planes, conflictos = {}, [None] * len(reglas), []
    for i in orden:
        r, quedan, omitidas = reglas[i], [], []
        for a in r["hacer"]:
            rec = recurso_accion(a)
            if rec is not None:
                previo = reservado.get(rec[0])
                if previo is not None and previo[1] is not r and previo[0] != rec[1]:
                    ganadora = previo[1]
                    omitidas.append((a, ganadora))
                    misma = ganadora.get("prioridad", "normal") == r.get("prioridad", "normal")
                    conflictos.append({"recurso": rec[0], "ganadora": ganadora, "perdedora": r,
                                       "motivo": "va antes en la lista" if misma
                                       else f"prioridad {ganadora.get('prioridad', 'normal')}"})
                    continue
                reservado.setdefault(rec[0], (rec[1], r))
            quedan.append(a)
        planes[i] = (quedan, omitidas)
    return planes, conflictos


def huella_regla(r):
    """Lo que hace una regla (CUANDO, SI y HACER), para detectar reglas repetidas."""
    return json.dumps([r.get("cuando"), r.get("si"), r.get("hacer")], sort_keys=True, ensure_ascii=False)


def posibles_choques(reglas):
    """{id: [{"id", "nombre", "recurso"}]}: reglas activas con el mismo CUANDO que pediran
    valores distintos para un recurso si se disparan juntas (aviso al guardar o listar)."""
    activas = [r for r in reglas if regla_ejecutable(r)]
    salida = {}
    for i, a in enumerate(activas):
        for b in activas[i + 1:]:
            if json.dumps(a["cuando"], sort_keys=True) != json.dumps(b["cuando"], sort_keys=True):
                continue
            pa = {x[0]: x[1] for x in map(recurso_accion, a["hacer"]) if x}
            for x in filter(None, map(recurso_accion, b["hacer"])):
                if x[0] in pa and pa[x[0]] != x[1]:
                    salida.setdefault(a["id"], []).append({"id": b["id"], "nombre": b["nombre"], "recurso": x[0]})
                    salida.setdefault(b["id"], []).append({"id": a["id"], "nombre": a["nombre"], "recurso": x[0]})
    return salida


def proxima_hora(reglas, ahora):
    """Primer instante (datetime sin segundos, posterior a `ahora`) en que vence una regla
    activa de tipo hora; None si no hay ninguna."""
    mejor = None
    for r in reglas:
        if not regla_ejecutable(r) or r["cuando"].get("evento") != "hora":
            continue
        h, m = divmod(minutos_de(r["cuando"]["hora"]), 60)
        dias = r["cuando"].get("dias") or []
        for delta in range(0, 8):
            cand = (ahora + datetime.timedelta(days=delta)).replace(hour=h, minute=m, second=0, microsecond=0)
            if cand > ahora and (not dias or cand.weekday() in dias):
                if mejor is None or cand < mejor:
                    mejor = cand
                break
    return mejor


# -- fuentes de eventos: analizadores puros --------------------------------------

def estado_bateria_baja(armados, nivel, descargando, cargador, umbrales):
    """Flanco con histeresis. armados: {umbral: bool} (se modifica); devuelve los umbrales
    que saltan ahora. Baja = descargando y por debajo del umbral. Salta una vez y no vuelve
    a saltar hasta rearmarse: al subir a umbral + 5 o al conectar el cargador. La primera
    vez que se ve un umbral, si ya estaba por debajo, no salta (no hubo flanco)."""
    saltan = []
    for u in umbrales:
        bajo = bool(descargando) and nivel < u
        if u not in armados:
            armados[u] = not bajo
            continue
        if cargador is True or nivel >= u + HISTERESIS_BATERIA:
            armados[u] = True
        if bajo and armados[u]:
            armados[u] = False
            saltan.append(u)
    return saltan


def info_bluez(props):
    """(nombre, es_audio) de las propiedades de org.bluez.Device1."""
    nombre = str(props.get("Alias") or props.get("Name") or "").strip()
    icono = str(props.get("Icon") or "")
    uuids = [str(u).lower() for u in (props.get("UUIDs") or [])]
    audio = icono.startswith("audio-") or any(u.startswith(f"0000{c}-") for u in uuids for c in UUID_AUDIO)
    return nombre, audio


def cambio_bluez(ruta_dispositivo, cambiadas, previos):
    """'conectado' | 'desconectado' | None segun el Connected de un PropertiesChanged de
    Device1. previos: {ruta: bool} (se modifica); solo cuenta si el valor cambia."""
    if "Connected" not in cambiadas:
        return None
    ahora = bool(cambiadas["Connected"])
    antes = previos.get(ruta_dispositivo)
    previos[ruta_dispositivo] = ahora
    if antes == ahora or (antes is None and not ahora):
        return None
    return "conectado" if ahora else "desconectado"


def estado_red(valor, previo):
    """'conectada' (State = 70), 'desconectada' (<= 20) o None si no hay cambio de categoria
    (los estados intermedios 30-60 no cuentan). previo: 'conectada' | 'desconectada' | None."""
    if not isinstance(valor, int):
        return None
    nuevo = "conectada" if valor == 70 else ("desconectada" if valor <= 20 else None)
    return nuevo if nuevo is not None and nuevo != previo else None


class AnalizadorHyprland:
    """Convierte las lineas de socket2 en eventos de monitor y de aplicacion. 'abierta' solo
    con la primera ventana de una clase y 'cerrada' al cerrarse la ultima (recuerda la clase
    de cada direccion). Hyprland emite monitoradded y monitoraddedv2 (y sus equivalentes al
    quitar) para el mismo hecho: el mismo (estado, nombre) en menos de 2 s cuenta una vez."""

    def __init__(self, reloj=time.monotonic):
        self.reloj = reloj
        self.ventanas = {}              # direccion -> clase en minusculas
        self.clases = {}                # clase en minusculas -> numero de ventanas
        self._visto = {}                # (estado, monitor) -> instante

    def reiniciar(self):
        self.ventanas.clear()
        self.clases.clear()

    def sembrar(self, ventanas):
        """Ventanas que ya existian: [(direccion, clase)]. No genera eventos."""
        for direccion, clase in ventanas:
            direccion, clase = str(direccion).removeprefix("0x"), str(clase or "").lower()
            if clase and direccion not in self.ventanas:
                self.ventanas[direccion] = clase
                self.clases[clase] = self.clases.get(clase, 0) + 1

    def _monitor(self, estado, nombre):
        t = self.reloj()
        previo = self._visto.get((estado, nombre))
        self._visto[(estado, nombre)] = t
        if previo is not None and t - previo < 2.0:
            return []
        return [("monitor", {"estado": estado, "nombre": nombre})]

    def procesar(self, linea):
        evento, _, arg = linea.strip().partition(">>")
        if evento in ("monitoradded", "monitorremoved"):
            return self._monitor("conectado" if evento == "monitoradded" else "desconectado", arg)
        if evento in ("monitoraddedv2", "monitorremovedv2"):
            partes = arg.split(",", 2)
            if len(partes) >= 2:
                return self._monitor("conectado" if evento == "monitoraddedv2" else "desconectado", partes[1])
            return []
        if evento == "openwindow":
            partes = arg.split(",", 3)           # direccion, espacio, clase, titulo (puede llevar comas)
            if len(partes) < 3 or not partes[2].strip():
                return []
            direccion, clase = partes[0].removeprefix("0x"), partes[2].strip()
            if direccion in self.ventanas:
                return []
            clave = clase.lower()
            self.ventanas[direccion] = clave
            self.clases[clave] = self.clases.get(clave, 0) + 1
            return [("aplicacion", {"estado": "abierta", "clase": clase})] if self.clases[clave] == 1 else []
        if evento == "closewindow":
            clave = self.ventanas.pop(arg.strip().removeprefix("0x"), None)
            if clave is None:
                return []
            self.clases[clave] -= 1
            if self.clases[clave] <= 0:
                del self.clases[clave]
                return [("aplicacion", {"estado": "cerrada", "clase": clave})]
        return []


def parsear_sinks_wpctl(texto):
    """Salidas de audio de 'wpctl status': [{"id", "nombre", "defecto"}]. El nombre es la
    descripcion que muestra wpctl (sin el volumen)."""
    sinks, dentro = [], False
    for linea in (texto or "").splitlines():
        if not linea.strip():
            continue
        limpio = linea.lstrip(" │")
        if limpio[:2] in ("├─", "└─") or not linea[0].isspace() and linea[0] not in "│├└":
            dentro = limpio.lstrip("├└─ ").strip() == "Sinks:"
            continue
        if not dentro:
            continue
        m = re.match(r"^(\*)?\s*(\d+)\.\s+(.*?)\s*(?:\[[^\]]*\])?\s*$", limpio)
        if m:
            sinks.append({"id": int(m.group(2)), "nombre": m.group(3).strip(), "defecto": bool(m.group(1))})
    return sinks


def limpiar_miniaturas(carpeta, ahora, dias=DIAS_MINIATURAS):
    """Borra de `carpeta` los archivos regulares con mas de `dias` dias (por fecha de
    modificacion). Nunca sigue enlaces (ni de carpeta ni de archivo), no borra carpetas y no
    toca nada fuera de `carpeta`. Devuelve (archivos, bytes, error)."""
    if os.path.islink(carpeta):
        return 0, 0, "la carpeta de miniaturas es un enlace: no se toca"
    if not os.path.isdir(carpeta):
        return 0, 0, None
    limite = ahora - dias * 86400
    n = tam = 0
    for base, _dirs, archivos in os.walk(carpeta, followlinks=False):
        for nombre in archivos:
            p = os.path.join(base, nombre)
            try:
                st = os.lstat(p)
                if not stat.S_ISREG(st.st_mode) or st.st_mtime >= limite:
                    continue
                os.remove(p)
            except OSError:
                continue
            n += 1
            tam += st.st_size
    return n, tam, None


def comprobar_script(nombre, carpeta, uid=None, lstat=os.lstat, estatus=os.stat):
    """(ruta, error): el script debe estar en `carpeta` (que ha de ser del usuario y no
    escribible por grupo ni otros), ser un archivo regular (no un enlace), del propio usuario,
    ejecutable y sin permiso de escritura para grupo ni otros."""
    if (not isinstance(nombre, str) or not nombre or any(x in nombre for x in "/\\\x00") or ".." in nombre
            or nombre in (".", "..")):
        return None, "nombre de script no válido (sin «/» ni «..»)"
    if uid is None and hasattr(os, "getuid"):
        uid = os.getuid()
    try:
        d = estatus(carpeta)
    except OSError:
        return None, "no existe la carpeta scripts-autorizados"
    if not stat.S_ISDIR(d.st_mode):
        return None, "scripts-autorizados no es una carpeta"
    if d.st_uid != uid or d.st_mode & 0o022:
        return None, "la carpeta scripts-autorizados debe ser tuya y no estar abierta a escritura de otros"
    destino = os.path.join(carpeta, nombre)
    try:
        st = lstat(destino)
    except OSError:
        return None, f"el script «{nombre}» no existe en scripts-autorizados"
    if not stat.S_ISREG(st.st_mode):
        return None, "no es un archivo regular (los enlaces no se admiten)"
    if st.st_uid != uid:
        return None, f"el script no es del usuario que ejecuta {PRODUCTO}"
    if st.st_mode & 0o022:
        return None, "otros usuarios pueden modificar el script (permiso de escritura de grupo u otros)"
    if not st.st_mode & 0o100:
        return None, "el script no es ejecutable"
    return destino, None


def limpiar_detalle(texto, maximo=300):
    t = "".join(c if not unicodedata.category(c) == "Cc" else " " for c in str(texto)).strip()
    return t if len(t) <= maximo else t[:maximo - 1] + "…"


class AplicacionesDisponibles:
    """Lista de `jaime0-anclar disponibles --json`, recordada VALIDEZ_APLICACIONES s."""

    def __init__(self, ejecutar=None, reloj=time.monotonic):
        self.ejecutar = ejecutar or subprocess.run
        self.reloj = reloj
        self._cache, self._t = None, 0.0

    def obtener(self):
        """{id: nombre} o None si no se pudo consultar."""
        if self._cache is not None and self.reloj() - self._t < VALIDEZ_APLICACIONES:
            return self._cache
        try:
            r = self.ejecutar([programa_hermano("jaime0-anclar") or "jaime0-anclar", "disponibles", "--json"],
                              capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return None
            lista = json.loads(r.stdout)
            apps = {a["id"]: str(a.get("nombre") or a["id"]) for a in lista
                    if isinstance(a, dict) and isinstance(a.get("id"), str)}
        except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
            return None
        self._cache, self._t = apps, self.reloj()
        return apps


def ejecutar_grupo(orden, timeout=None, stdin=None, **_):
    """Como subprocess.run para los scripts autorizados, sin esperar a sus hijos: el script
    corre en una sesion propia (grupo de procesos), la salida estandar se descarta y el error
    va a un archivo temporal (con tuberias, run() esperaria a que un hijo en segundo plano las
    cerrase). Al agotar el tiempo se mata el GRUPO entero. Devuelve un CompletedProcess con
    el principio de stderr."""
    with tempfile.TemporaryFile() as err:
        p = subprocess.Popen(orden, stdin=stdin, stdout=subprocess.DEVNULL, stderr=err, start_new_session=True)
        try:
            p.wait(timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, getattr(signal, "SIGKILL", 9))
            except (OSError, AttributeError):
                p.kill()                    # sin killpg (no es Linux) o el grupo ya no existe
            p.wait()
            raise
        err.seek(0)
        texto = err.read(65536).decode("utf-8", "replace")
    return subprocess.CompletedProcess(orden, p.returncode, "", texto)


class Acciones:
    """Lista blanca cerrada de acciones. Cada una devuelve (ok, detalle). Todas con timeout y
    sin shell; ninguna necesita root. Se ejecutan en un hilo de trabajo. El perfil no pasa
    por el bucle de GLib (lo bloquearia mientras se aplica): aplicar_perfil lo encola en el
    hilo de efectos del servicio y espera su resultado."""

    def __init__(self, ejecutar, apps, aplicar_perfil, en_bucle, dir_miniaturas, dir_scripts, reloj=time.time,
                 dormir=time.sleep, uid=None, estatus_script=None, ejecutar_script=None):
        self.ejecutar = ejecutar
        # Los scripts no usan subprocess.run (ver ejecutar_grupo); si se inyecta otro `ejecutar`
        # (pruebas) tambien se usa para ellos.
        self.ejecutar_script = ejecutar_script or (ejecutar_grupo if ejecutar is subprocess.run else ejecutar)
        self.apps = apps                    # callable -> {id: nombre} | None
        self.aplicar_perfil = aplicar_perfil
        self.en_bucle = en_bucle
        self.dir_miniaturas, self.dir_scripts = dir_miniaturas, dir_scripts
        self.reloj, self.dormir, self.uid = reloj, dormir, uid
        self.estatus_script = estatus_script or {}

    def _correr(self, orden, timeout, ejecutar=None, captura=True, **k):
        """(proceso, error): error es un texto si no se pudo ejecutar o se agoto el tiempo."""
        if captura:
            k.update(capture_output=True, text=True)
        try:
            return (ejecutar or self.ejecutar)(orden, timeout=timeout, **k), None
        except FileNotFoundError:
            return None, f"{os.path.basename(orden[0])} no está instalado"
        except subprocess.TimeoutExpired:
            return None, f"{os.path.basename(orden[0])} superó el tiempo máximo ({timeout} s)"
        except OSError as e:
            return None, f"no se pudo ejecutar {os.path.basename(orden[0])}: {e.strerror or e}"

    @staticmethod
    def _fin(proc, error, bien):
        if error:
            return False, error
        if proc.returncode != 0:
            primera = next((l.strip() for l in (proc.stderr or "").splitlines() if l.strip()), "")
            return False, limpiar_detalle(f"terminó con código {proc.returncode}" + (f": {primera}" if primera else ""))
        return True, bien

    def ejecutar_accion(self, a):
        nombre = a.get("accion")
        if nombre in ACCIONES_PRIVILEGIADAS:
            return False, MENSAJE_PRIVILEGIADA
        f = getattr(self, "_a_" + str(nombre), None)
        if f is None:
            return False, f"acción desconocida: {nombre}"
        return f(a)

    def _a_perfil(self, a):
        r = self.aplicar_perfil(a["perfil"])
        if not r.get("ok"):
            return False, limpiar_detalle(r.get("error") or "no se pudo aplicar el perfil")
        if r.get("fallos"):
            return False, limpiar_detalle(f"Perfil {r.get('nombre')} aplicado con avisos: " + "; ".join(r["fallos"]))
        return True, f"Perfil {r.get('nombre') or a['perfil']} aplicado"

    def _a_modo_noche(self, a):
        programa = programa_hermano("modo-noche")
        if not programa:
            return False, "modo-noche no está instalado"
        proc, error = self._correr([programa, a["estado"]], 10)
        return self._fin(proc, error, "Modo noche " + ("encendido" if a["estado"] == "encender" else "apagado"))

    def _a_no_molestar(self, a):
        on = a["estado"] == "activar"
        proc, error = self._correr(["swaync-client", "--dnd-on" if on else "--dnd-off", "--skip-wait"], 5)
        return self._fin(proc, error, "No molestar " + ("activado" if on else "desactivado"))

    def _a_notificar(self, a):
        proc, error = self._correr(["notify-send", f"--app-name={PRODUCTO}", "--", a["titulo"], a["texto"]], 5)
        return self._fin(proc, error, "Notificación enviada")

    def _a_abrir_aplicacion(self, a):
        apps = self.apps()
        if apps is None:
            return False, "no se pudo comprobar la lista de aplicaciones disponibles"
        if a["id"] not in apps:
            return False, f"la aplicación «{a['id']}» ya no está en la lista de aplicaciones disponibles"
        programa = programa_hermano("jaime0-anclar") or "jaime0-anclar"
        proc, error = self._correr([programa, "abrir", a["id"]], 15)
        return self._fin(proc, error, f"Aplicación abierta: {apps[a['id']]}")

    def _a_volumen(self, a):
        proc, error = self._correr(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{a['nivel']}%"], 5)
        return self._fin(proc, error, f"Volumen al {a['nivel']} %")

    def _a_silenciar(self, a):
        si = a["estado"] == "si"
        proc, error = self._correr(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if si else "0"], 5)
        return self._fin(proc, error, "Sonido silenciado" if si else "Sonido activado")

    def _a_salida_audio(self, a):
        patron = a["nombre"].casefold()
        elegido = None
        for intento in range(REINTENTOS_SINK + 1):
            proc, error = self._correr(["wpctl", "status"], 5)
            if error:
                return False, error
            if proc.returncode != 0:
                return False, f"wpctl status terminó con código {proc.returncode}"
            elegido = next((s for s in parsear_sinks_wpctl(proc.stdout) if patron in s["nombre"].casefold()), None)
            if elegido or intento == REINTENTOS_SINK:
                break
            self.dormir(1.0)
        if not elegido:
            return False, limpiar_detalle(f"No hay ninguna salida de audio cuyo nombre contenga «{a['nombre']}»")
        proc, error = self._correr(["wpctl", "set-default", str(elegido["id"])], 5)
        return self._fin(proc, error, limpiar_detalle(f"Salida de audio: {elegido['nombre']}"))

    def _a_mantenimiento(self, a):
        if a["tarea"] == "comprobar_actualizaciones":
            programa = programa_hermano("actualizaciones") or "actualizaciones"
            proc, error = self._correr([programa, "comprobar", "--notificar", "--silencioso"], 120)
            return self._fin(proc, error, "Comprobación de actualizaciones hecha")
        n, tam, error = limpiar_miniaturas(self.dir_miniaturas(), self.reloj())
        if error:
            return False, error
        return True, f"Miniaturas: {n} archivo(s) de más de {DIAS_MINIATURAS} días borrados ({tam / 1048576:.1f} MiB)"

    def _a_script(self, a):
        carpeta = self.dir_scripts()
        ruta_script, error = comprobar_script(a["nombre"], carpeta, self.uid, **self.estatus_script)
        if error:
            return False, error
        proc, err = self._correr([ruta_script], TIMEOUT_SCRIPT, ejecutar=self.ejecutar_script, captura=False,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        if err:
            return False, err
        lineas = [l.strip() for l in (proc.stderr or "").splitlines() if l.strip()][:3]
        detalle = f"código de salida {proc.returncode}" + (f"; error: {' | '.join(lineas)}" if lineas else "")
        return proc.returncode == 0, limpiar_detalle(detalle)


class HistorialEjecuciones:
    """ejecuciones.jsonl, recortado a `maximo` lineas."""

    def __init__(self, archivo, maximo=MAX_EJECUCIONES):
        self.archivo, self.maximo = archivo, maximo
        self.n = None
        self.cerrojo = threading.Lock()

    def anotar(self, entrada):
        with self.cerrojo:
            archivo = self.archivo()
            anexar_jsonl(archivo, [entrada])
            self.n = len(leer_jsonl(archivo)) if self.n is None else self.n + 1
            if self.n > self.maximo:
                docs = leer_jsonl(archivo)[-self.maximo:]
                reescribir_jsonl(archivo, docs)
                self.n = len(docs)

    def ultimos(self, limite):
        """Los `limite` mas recientes, el ultimo primero."""
        with self.cerrojo:
            return [d for d in leer_jsonl(self.archivo()) if "regla" in d][-limite:][::-1]

    def ultima_por_regla(self):
        with self.cerrojo:
            return {d["regla"]: d for d in leer_jsonl(self.archivo()) if isinstance(d.get("regla"), str)}


class MotorReglas:
    """Reglas CUANDO -> SI -> HACER. Todo el estado se toca desde el bucle de GLib; solo las
    acciones corren en hilos de trabajo (lanzador), y su resultado vuelve con `fin`.

    archivo_reglas y archivo_ejecuciones: callables que devuelven la ruta. estado(): dict
    {"perfil","cargador","bateria"} actuales. disponibilidad(): {"eventos": {id: (bool,
    motivo)}, "acciones": {...}}. incidencia(linea), evento(texto, tipo, gravedad, proceso,
    origen) y notificar() son los ganchos del servicio. lanzador(trabajo, fin) ejecuta
    trabajo() y llama a fin(resultado); en_bucle(fn) ejecuta fn en el bucle principal y
    devuelve su resultado; temporizador(segundos, fn) -> id y cancelar(id) programan la hora.
    Por defecto todo es sincrono (pruebas)."""

    def __init__(self, archivo_reglas, archivo_ejecuciones, reloj=time.time, ejecutar=None, estado=None,
                 aplicar_perfil=None, apps=None, disponibilidad=None, incidencia=None, evento=None,
                 notificar=None, lanzador=None, en_bucle=None, temporizador=None, cancelar=None,
                 dormir=time.sleep, dir_miniaturas=None, dir_scripts=None, uid=None, ejecutar_script=None):
        self.archivo_reglas = archivo_reglas
        self.reloj = reloj
        self.estado = estado or (lambda: {})
        self.apps = apps or (lambda: None)
        self.disponibilidad = disponibilidad or (lambda: {"eventos": {}, "acciones": {}})
        self.incidencia = incidencia or (lambda linea: None)
        self.evento_actividad = evento or (lambda *a, **k: None)
        self.notificar = notificar or (lambda: None)
        self.lanzador = lanzador or (lambda trabajo, fin: fin(trabajo()))
        self.en_bucle = en_bucle or (lambda fn: fn())
        self.temporizador, self.cancelar = temporizador, cancelar
        self.historial = HistorialEjecuciones(archivo_ejecuciones)
        self.acciones = Acciones(
            ejecutar or subprocess.run, self.apps, aplicar_perfil or (lambda pid: {"ok": False, "error": "perfiles no disponibles"}),
            lambda fn: self.en_bucle(fn), dir_miniaturas or (lambda: os.path.join(
                os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"), "thumbnails")),
            dir_scripts or (lambda: os.path.join(carpeta_config(), "scripts-autorizados")),
            reloj=reloj, dormir=dormir, uid=uid, ejecutar_script=ejecutar_script)
        self.reglas, self.invalidas, self.errores = [], [], []
        self.cargado = False
        self._ultimo = {}                   # id -> instante del ultimo disparo (enfriamiento)
        self._por_regla = {}                # id -> instantes de ejecucion (tope por regla)
        self._global = collections.deque()  # instantes de ejecucion (tope global)
        self._tope_global_avisado = False   # ya hay aviso del tope global en esta ventana
        self._archivo_roto = False          # la ultima lectura de reglas.json fallo: no pisarlo sin copia
        self._en_curso = set()
        self._silencio = {}                 # evento -> instante hasta el que no dispara
        self._armados = {}                  # umbral de bateria -> armado
        self._cargador = None
        self._timer = None
        self.proxima = None
        self.conflictos = collections.deque(maxlen=MAX_CONFLICTOS)

    # -- carga y guardado ------------------------------------------------------------
    def _ctx(self, estricto):
        return {"apps": self.apps, "estricto": estricto}

    def _asegurar(self):
        if not self.cargado:
            self.cargar()

    def cargar(self):
        """Lee reglas.json. Una regla invalida no se carga y su error se informa; un archivo
        ilegible conserva las reglas que ya habia cargadas."""
        self.cargado = True
        self._archivo_roto = False
        try:
            with open(self.archivo_reglas(), encoding="utf-8") as f:
                doc = json.load(f)
        except FileNotFoundError:
            self.reglas, self.invalidas, self.errores = [], [], []
            self._reprogramar_hora()
            return
        except (OSError, ValueError) as e:
            self._archivo_roto = True
            self.errores = [{"indice": None, "error": f"no se pudo leer reglas.json: {e}"}]
            return
        if not isinstance(doc, dict) or doc.get("v") != 1 or not isinstance(doc.get("reglas"), list):
            self._archivo_roto = True
            self.errores = [{"indice": None, "error": "reglas.json no tiene el formato esperado (v 1)"}]
            return
        ctx, reglas, invalidas, errores, ids = self._ctx(False), [], [], [], set()
        for i, entrada in enumerate(doc["reglas"]):
            regla, error = validar_regla(entrada, ctx)
            if error is None and (regla["id"] is None or regla["id"] in ids):
                error = "falta el id de la regla" if regla["id"] is None else "el id de la regla está repetido"
            if error is None and len(reglas) >= MAX_REGLAS:
                error = f"hay demasiadas reglas (máximo {MAX_REGLAS})"
            if error:
                rid = entrada.get("id") if isinstance(entrada, dict) and isinstance(entrada.get("id"), str) else None
                errores.append({"id": rid, "error": error} if rid else {"indice": i, "error": error})
                invalidas.append({"id": rid, "bruta": entrada})
                continue
            if regla["activa"] and regla["revisar"]:
                regla["activa"] = False             # una regla por revisar no se ejecuta
            ids.add(regla["id"])
            reglas.append(regla)
        self.reglas, self.invalidas, self.errores = reglas, invalidas, errores
        for d in (self._ultimo, self._por_regla):
            for k in [k for k in d if k not in ids]:
                del d[k]
        self._reprogramar_hora()

    def _guardar(self):
        """Escritura atomica; conserva tal cual las reglas invalidas del archivo."""
        destino = self.archivo_reglas()
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if self._archivo_roto:
            self._copiar_roto(destino)          # si falla, no se guarda (OSError): no se pierde la edicion
        doc = {"v": VERSION_DATOS, "reglas": list(self.reglas) + [i["bruta"] for i in self.invalidas]}
        tmp = destino + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, destino)

    def _copiar_roto(self, destino):
        """Antes de sobrescribir un reglas.json ilegible, lo copia a reglas.json.roto (o, si ya
        hay una copia, a reglas.json.roto.AAAAMMDD-HHMMSS[-N]) sin pisar copias anteriores."""
        if not os.path.exists(destino):
            self._archivo_roto = False          # ya no esta: nada que conservar
            return
        copia = destino + ".roto"
        if os.path.exists(copia):
            base = f"{copia}.{datetime.datetime.fromtimestamp(self.reloj()).strftime('%Y%m%d-%H%M%S')}"
            copia, n = base, 1
            while os.path.exists(copia):
                n += 1
                copia = f"{base}-{n}"
        shutil.copy2(destino, copia)
        self._archivo_roto = False
        self.evento_actividad(f"reglas.json estaba dañado: copia guardada en {os.path.basename(copia)}",
                              None, "WARNING", None, "regla")

    def _buscar(self, rid):
        return next((r for r in self.reglas if r["id"] == rid), None)

    def _ids_usados(self):
        return {r["id"] for r in self.reglas} | {i["id"] for i in self.invalidas if i["id"]}

    # -- API ------------------------------------------------------------------------
    def catalogo(self):
        disp = self.disponibilidad() or {}

        def tabla(entradas, clave):
            salida = []
            for e in entradas:
                ok, motivo = (disp.get(clave) or {}).get(e["id"], (True, None))
                salida.append({"id": e["id"], "nombre": e["nombre"], "descripcion": e["descripcion"],
                               "parametros": [dict(p) for p in e["parametros"]],
                               "disponible": bool(ok), "motivo": None if ok else motivo})
            return salida

        return {"eventos": tabla(EVENTOS, "eventos"), "condiciones": tabla(CONDICIONES, "condiciones"),
                "acciones": tabla(ACCIONES, "acciones")}

    def _con_ultima(self, regla, ultimas, choques=None):
        proxima = None
        if regla_ejecutable(regla) and regla["cuando"].get("evento") == "hora":
            p = proxima_hora([regla], datetime.datetime.fromtimestamp(self.reloj()))
            proxima = int(time.mktime(p.timetuple())) if p else None
        if choques is None:
            choques = posibles_choques(self.reglas)
        return dict(regla, ultima=ultimas.get(regla["id"]), proxima=proxima,
                    choca_con=choques.get(regla["id"], []))

    def resumen(self, ultimas=None):
        ultimas = self.historial.ultima_por_regla() if ultimas is None else ultimas
        return {"activas": sum(1 for r in self.reglas if regla_ejecutable(r)),
                "desactivadas": sum(1 for r in self.reglas if not r["activa"] and not r["revisar"]),
                "por_revisar": sum(1 for r in self.reglas if r["revisar"]),
                "con_fallo": sum(1 for r in self.reglas if (ultimas.get(r["id"]) or {}).get("resultado") == "fallo"),
                "invalidas": len(self.errores), "conflictos": len(self.conflictos)}

    def listar(self):
        self._asegurar()
        ultimas = self.historial.ultima_por_regla()
        choques = posibles_choques(self.reglas)
        apps = self.apps()
        return {"ok": True, "v": VERSION_DATOS, "reglas": [self._con_ultima(r, ultimas, choques) for r in self.reglas],
                "errores": list(self.errores), "resumen": self.resumen(ultimas),
                "conflictos": list(self.conflictos)[::-1], "catalogo": self.catalogo(),
                "aplicaciones": [{"id": i, "nombre": n} for i, n in sorted((apps or {}).items(), key=lambda x: x[1].lower())]}

    def _duplicada(self, regla, excepto=None):
        """La regla ya existente que hace exactamente lo mismo (otro id), o None."""
        h = huella_regla(regla)
        return next((r for r in self.reglas if r["id"] != excepto and huella_regla(r) == h), None)

    def guardar(self, doc):
        """Crea o actualiza una regla (valida de forma estricta). Si no trae id, o el id no
        existe, es una regla nueva con un id unico. 'revisar' solo se quita al activarla."""
        self._asegurar()
        regla, error = validar_regla(doc, self._ctx(True))
        if error:
            return {"ok": False, "error": error}
        igual = self._duplicada(regla, excepto=regla["id"])
        if igual is not None:
            return {"ok": False, "error": f"Ya hay una regla que hace exactamente lo mismo: «{igual['nombre']}»"}
        previa = self._buscar(regla["id"]) if regla["id"] else None
        if previa is None:
            if len(self.reglas) >= MAX_REGLAS:
                return {"ok": False, "error": f"hay demasiadas reglas (máximo {MAX_REGLAS})"}
            usados = self._ids_usados()
            if regla["id"] is None:
                regla["id"] = id_unico(slug_regla(regla["nombre"]), usados)
            elif regla["id"] in usados:
                return {"ok": False, "error": "ya hay una regla con ese id que no es válida: bórrala o cambia el id"}
            regla["revisar"] = False
            copia = list(self.reglas)
            self.reglas.append(regla)
        else:
            regla["revisar"] = bool(previa["revisar"]) and not regla["activa"]
            copia = list(self.reglas)
            self.reglas[self.reglas.index(previa)] = regla
            if regla["activa"] and not previa["activa"]:
                self._por_regla.pop(regla["id"], None)
        try:
            self._guardar()
        except OSError as e:
            self.reglas = copia
            return {"ok": False, "error": f"no se pudo guardar reglas.json: {e.strerror or e}"}
        self._reprogramar_hora()
        return {"ok": True, "regla": self._con_ultima(regla, self.historial.ultima_por_regla())}

    def activar(self, rid, activa):
        self._asegurar()
        r = self._buscar(rid)
        if r is None:
            return {"ok": False, "error": "no existe esa regla"}
        antes = dict(r)
        r["activa"] = bool(activa)
        if activa:
            r["revisar"] = False            # activarla es revisarla
            self._por_regla.pop(rid, None)
        try:
            self._guardar()
        except OSError as e:
            r.update(antes)
            return {"ok": False, "error": f"no se pudo guardar reglas.json: {e.strerror or e}"}
        self._reprogramar_hora()
        return {"ok": True, "regla": self._con_ultima(r, self.historial.ultima_por_regla())}

    def borrar(self, rid):
        self._asegurar()
        r = self._buscar(rid)
        invalida = next((i for i in self.invalidas if i["id"] == rid), None) if r is None else None
        if r is None and invalida is None:
            return {"ok": False, "error": "no existe esa regla"}
        reglas, invalidas = list(self.reglas), list(self.invalidas)
        if r is not None:
            self.reglas.remove(r)
        else:
            self.invalidas.remove(invalida)
            self.errores = [e for e in self.errores if e.get("id") != rid]
        try:
            self._guardar()
        except OSError as e:
            self.reglas, self.invalidas = reglas, invalidas
            return {"ok": False, "error": f"no se pudo guardar reglas.json: {e.strerror or e}"}
        for d in (self._ultimo, self._por_regla):
            d.pop(rid, None)
        self._reprogramar_hora()
        return {"ok": True}

    def importar(self, lista):
        """Todas entran desactivadas y por revisar. Devuelve cuantas y los errores."""
        self._asegurar()
        if not isinstance(lista, list):
            return {"ok": False, "error": "«reglas» debe ser una lista"}
        if len(lista) > MAX_REGLAS:
            return {"ok": False, "error": f"demasiadas reglas para importar de una vez (máximo {MAX_REGLAS})"}
        ctx, errores, nuevas = self._ctx(True), [], []
        usados = self._ids_usados()
        antes = list(self.reglas)
        for i, entrada in enumerate(lista):
            regla, error = validar_regla(entrada, ctx)
            if error is None and len(self.reglas) >= MAX_REGLAS:
                error = f"hay demasiadas reglas (máximo {MAX_REGLAS})"
            igual = self._duplicada(regla) if error is None else None
            if igual is not None:
                error = f"repite la regla «{igual['nombre']}»"
            if error:
                errores.append({"indice": i, "error": error})
                continue
            if regla["id"] is None or regla["id"] in usados:
                regla["id"] = id_unico(slug_regla(regla["nombre"]), usados)
            usados.add(regla["id"])
            regla["activa"], regla["revisar"] = False, True
            self.reglas.append(regla)
            nuevas.append(regla)
        if nuevas:
            try:
                self._guardar()
            except OSError as e:
                self.reglas = antes
                return {"ok": False, "error": f"no se pudo guardar reglas.json: {e.strerror or e}"}
        return {"ok": True, "importadas": len(nuevas), "errores": errores, "ids": [r["id"] for r in nuevas]}

    def historial_doc(self, limite):
        return {"ok": True, "v": VERSION_DATOS, "ejecuciones": self.historial.ultimos(limite)}

    # -- ejecucion ---------------------------------------------------------------------
    def _anotar(self, regla, texto, resultado, detalle, acciones=None):
        entrada = {"v": VERSION_DATOS, "t": int(self.reloj()), "regla": regla["id"], "nombre": regla["nombre"],
                   "evento": texto, "resultado": resultado, "detalle": detalle, "acciones": acciones or []}
        try:
            self.historial.anotar(entrada)
        except OSError:
            registrar("no se pudo escribir ejecuciones.jsonl:\n" + traceback.format_exc())
        return entrada

    def _desactivar_por_tope(self, regla, texto, motivo):
        regla["activa"] = False
        try:
            self._guardar()
        except OSError:
            registrar("no se pudo guardar la regla desactivada:\n" + traceback.format_exc())
        detalle = f"Tope de ejecuciones superado ({motivo}): regla desactivada"
        self._anotar(regla, texto, "omitida", detalle)
        self.evento_actividad(f"Regla «{regla['nombre']}» desactivada: demasiadas ejecuciones", None, "WARNING", None, "regla")
        try:
            self.incidencia({
                "v": VERSION_DATOS, "t": int(self.reloj()), "gravedad": "WARNING", "componente": "reglas",
                "descripcion": f"La regla «{regla['nombre']}» se ha desactivado: demasiadas ejecuciones ({motivo})",
                "diagnostico": "Una regla que se dispara sin parar suele indicar un bucle entre sus eventos y sus acciones",
                "recomendacion": "Revisa la regla en AUTOMATION (o con jaime0-reglas) y vuelve a activarla cuando esté corregida",
                "valor": regla["id"]})
        except Exception:
            registrar("no se pudo abrir la incidencia de reglas:\n" + traceback.format_exc())
        self._reprogramar_hora()
        self.notificar()
        return detalle

    def _omitir_por_tope_global(self, regla, texto, motivo):
        """Tope global: la ejecucion se omite y la regla sigue activa (el exceso no es culpa
        suya). El evento y la incidencia se registran una sola vez por ventana."""
        detalle = f"omitida (tope global): {motivo}"
        self._anotar(regla, texto, "omitida", detalle)
        if not self._tope_global_avisado:
            self._tope_global_avisado = True
            self.evento_actividad("Reglas: ejecuciones omitidas por el tope global", None, "WARNING", None, "regla")
            try:
                self.incidencia({
                    "v": VERSION_DATOS, "t": int(self.reloj()), "gravedad": "WARNING", "componente": "reglas",
                    "descripcion": f"Se han omitido ejecuciones de reglas: {motivo}",
                    "diagnostico": "Hay demasiadas reglas disparándose a la vez; ninguna se ha desactivado",
                    "recomendacion": "Revisa en AUTOMATION si hay un bucle entre eventos y acciones",
                    "valor": None})
            except Exception:
                registrar("no se pudo abrir la incidencia de reglas:\n" + traceback.format_exc())
            self.notificar()
        return detalle

    def _bloqueo(self, regla):
        """Por que no se puede lanzar ahora (ya en curso o enfriamiento), o None. Sin efectos."""
        rid, ahora = regla["id"], self.reloj()
        if rid in self._en_curso:
            return "omitida (ya se está ejecutando)", "la regla ya se está ejecutando"
        ultimo = self._ultimo.get(rid)
        if ultimo is not None and ahora - ultimo < ENFRIAMIENTO:
            espera = int(ENFRIAMIENTO - (ahora - ultimo)) + 1
            return (f"omitida (enfriamiento): se ejecutó hace menos de {ENFRIAMIENTO} s",
                    f"enfriamiento: espera {espera} s antes de volver a ejecutarla")
        return None

    def _intentar(self, regla, texto, cb=None, acciones=None, omitidas=()):
        """Enfriamiento, tope y lanzamiento. Devuelve (estado, mensaje): 'lanzada', 'omitida'
        (enfriamiento, ya en curso o tope global: la regla sigue activa) o 'tope' (tope por
        regla: la regla se desactiva). acciones: las que se ejecutan (por defecto todas);
        omitidas: [(accion, ganadora)] que un conflicto ha dejado fuera."""
        rid, ahora = regla["id"], self.reloj()
        bloqueo = self._bloqueo(regla)
        if bloqueo is not None:
            self._anotar(regla, texto, "omitida", bloqueo[0])
            return "omitida", bloqueo[1]
        while self._global and self._global[0] <= ahora - TOPE_GLOBAL[1]:
            self._global.popleft()
        propias = [t for t in self._por_regla.get(rid, []) if t > ahora - TOPE_REGLA[1]]
        self._por_regla[rid] = propias
        if len(self._global) < TOPE_GLOBAL[0]:
            self._tope_global_avisado = False
        else:
            motivo = f"más de {TOPE_GLOBAL[0]} ejecuciones en {TOPE_GLOBAL[1]} s en total"
            return "omitida", self._omitir_por_tope_global(regla, texto, motivo)
        if len(propias) + 1 >= TOPE_REGLA[0]:
            motivo = f"{TOPE_REGLA[0]} ejecuciones de esta regla en {TOPE_REGLA[1] // 60} min"
            return "tope", self._desactivar_por_tope(regla, texto, motivo)
        self._ultimo[rid] = ahora
        self._global.append(ahora)
        propias.append(ahora)
        self._en_curso.add(rid)
        if any(a["accion"] == "abrir_aplicacion" for a in regla["hacer"]):
            self._silencio["aplicacion"] = ahora + SILENCIO_APLICACION
        acciones = list(regla["hacer"] if acciones is None else acciones)
        notas = [{"accion": a["accion"], "resultado": "omitida",
                  "detalle": f"conflicto con «{g['nombre']}» ({NOMBRES_RECURSO.get(recurso_accion(a)[0])})"}
                 for a, g in omitidas]
        self.lanzador(lambda: self._trabajo(acciones),
                      lambda res: self._terminar(regla, texto, notas + res, cb))
        return "lanzada", ""

    def _trabajo(self, acciones):
        """En un hilo de trabajo: ejecuta las acciones en orden; una que falla no impide las demas."""
        salida = []
        for a in acciones:
            try:
                ok, detalle = self.acciones.ejecutar_accion(a)
            except Exception:
                registrar("error en la acción " + str(a.get("accion")) + ":\n" + traceback.format_exc())
                ok, detalle = False, "error interno"
            salida.append({"accion": a["accion"], "resultado": "ok" if ok else "fallo",
                           "detalle": limpiar_detalle(detalle)})
        return salida

    def _terminar(self, regla, texto, resultados, cb):
        """En el bucle principal: historial, actividad y aviso."""
        self._en_curso.discard(regla["id"])
        omitidas = [r for r in resultados if r["resultado"] == "omitida"]
        hechas = [r for r in resultados if r["resultado"] != "omitida"]
        malas = [r for r in hechas if r["resultado"] != "ok"]
        resultado = "fallo" if malas else "ok"
        detalle = (f"{len(hechas) - len(malas)} de {len(hechas)} acciones correctas: {malas[0]['detalle']}"
                   if malas else f"{len(hechas)} acción(es) correcta(s)")
        if omitidas:
            detalle += f"; {len(omitidas)} omitida(s): {omitidas[0]['detalle']}"
        entrada = self._anotar(regla, texto, resultado, limpiar_detalle(detalle), resultados)
        self.evento_actividad(f"Regla «{regla['nombre']}»: {resultado}", None, "INFO" if not malas else "WARNING",
                              None, "regla")
        self.notificar()
        if cb:
            cb({"ok": True, "ejecucion": entrada})

    def probar(self, rid, cb):
        """Ejecuta las acciones ahora (sin evento ni condiciones, pero con enfriamiento y
        tope). cb(respuesta) se llama una vez, cuando acaba."""
        self._asegurar()
        r = self._buscar(rid)
        if r is None:
            cb({"ok": False, "error": "no existe esa regla"})
        elif r["revisar"]:
            cb({"ok": False, "error": "La regla está pendiente de revisión: actívala antes de probarla"})
        else:
            estado, mensaje = self._intentar(r, "prueba manual", cb)
            if estado != "lanzada":
                cb({"ok": False, "error": mensaje})

    def _condiciones_ok(self, regla):
        est = dict(self.estado() or {})
        est["ahora"] = datetime.datetime.fromtimestamp(self.reloj())
        return all(evaluar_condicion(c, est) for c in regla["si"])

    def evento(self, nombre, datos):
        """Un evento ocurrido: lo recibe cada regla ejecutable que lo espera. Devuelve cuantas
        reglas dispararon (o se omitieron por enfriamiento o tope)."""
        self._asegurar()
        ahora = self.reloj()
        if nombre == "aplicacion" and datos.get("estado") == "abierta" and ahora < self._silencio.get("aplicacion", 0):
            return 0                        # lo ha abierto una regla: no dispara reglas
        texto, disparadas = texto_evento(nombre, datos), []
        for r in list(self.reglas):
            if not regla_ejecutable(r) or r["cuando"]["evento"] != nombre:
                continue
            try:
                if coincide(r["cuando"], datos) and self._condiciones_ok(r):
                    disparadas.append(r)
            except Exception:
                registrar(f"error al evaluar la regla {r.get('id')}:\n" + traceback.format_exc())
        # Las que no pueden lanzarse (en curso o enfriamiento) no cuentan para los conflictos.
        candidatas = []
        for r in disparadas:
            bloqueo = self._bloqueo(r)
            if bloqueo is not None:
                self._anotar(r, texto, "omitida", bloqueo[0])
            else:
                candidatas.append(r)
        planes, conflictos = resolver_conflictos(candidatas)
        for c in conflictos:
            self._anotar_conflicto(c, texto)
        for r, (acciones, omitidas) in zip(candidatas, planes):
            try:
                if not acciones:
                    g = omitidas[0][1]
                    self._anotar(r, texto, "omitida", f"omitida (conflicto): «{g['nombre']}» tiene preferencia",
                                 [{"accion": a["accion"], "resultado": "omitida",
                                   "detalle": f"conflicto con «{g['nombre']}»"} for a, g in omitidas])
                else:
                    self._intentar(r, texto, acciones=acciones, omitidas=omitidas)
            except Exception:
                registrar(f"error al lanzar la regla {r.get('id')}:\n" + traceback.format_exc())
        return len(disparadas)

    def _anotar_conflicto(self, c, texto):
        recurso = NOMBRES_RECURSO.get(c["recurso"], c["recurso"])
        entrada = {"t": int(self.reloj()), "evento": texto, "recurso": c["recurso"],
                   "ganadora": {"id": c["ganadora"]["id"], "nombre": c["ganadora"]["nombre"]},
                   "perdedora": {"id": c["perdedora"]["id"], "nombre": c["perdedora"]["nombre"]},
                   "motivo": c["motivo"]}
        self.conflictos.append(entrada)
        self.evento_actividad(f"Conflicto de reglas ({recurso}): gana «{c['ganadora']['nombre']}» "
                              f"sobre «{c['perdedora']['nombre']}» ({c['motivo']})", None, "WARNING", None, "regla")

    def perfil_cambiado(self, perfil, origen):
        """Gancho del motor de perfiles: solo los cambios del usuario disparan reglas."""
        if origen == "usuario":
            self.evento("perfil", {"perfil": perfil})

    def muestra(self, inst):
        """Bateria y cargador salen de las muestras que ya toma el servicio (sin sondeo nuevo)."""
        self._asegurar()
        cargador = inst.get("cargador")
        if cargador is not None:
            previo, self._cargador = self._cargador, cargador
            if previo is not None and previo != cargador:
                self.evento("cargador", {"estado": "conectado" if cargador else "desconectado"})
        bat = inst.get("bateria") or {}
        nivel = bat.get("nivel")
        if nivel is None:
            return
        umbrales = sorted({r["cuando"].get("umbral", 20) for r in self.reglas
                           if regla_ejecutable(r) and r["cuando"]["evento"] == "bateria_baja"})
        for u in estado_bateria_baja(self._armados, nivel, bat.get("estado") == "descargando", cargador, umbrales):
            self.evento("bateria_baja", {"umbral": u, "nivel": nivel})

    # -- hora ----------------------------------------------------------------------------
    def _reprogramar_hora(self, desde=None):
        """Un solo temporizador, al proximo instante en que vence alguna regla de hora (sin
        sondeo por minuto). Se recalcula al cambiar las reglas, tras cada disparo y al
        reanudar de una suspension."""
        if self.temporizador is None:
            return
        if self._timer is not None:
            self.cancelar(self._timer)
            self._timer = None
        ahora = datetime.datetime.fromtimestamp(self.reloj())
        self.proxima = proxima_hora(self.reglas, max(ahora, desde) if desde else ahora)
        if self.proxima is not None:
            espera = time.mktime(self.proxima.timetuple()) - self.reloj()
            self._timer = self.temporizador(max(1.0, espera), self._vence_hora)

    def _vence_hora(self):
        self._timer = None
        objetivo = self.proxima
        ahora = datetime.datetime.fromtimestamp(self.reloj())
        if objetivo is not None and ahora < objetivo - datetime.timedelta(seconds=1):
            self._reprogramar_hora()        # el temporizador (monotonico) se adelanto
            return False
        try:
            if objetivo is not None:
                self.evento("hora", {"hora": objetivo.strftime("%H:%M"), "dia": objetivo.weekday()})
        finally:
            self._reprogramar_hora(desde=objetivo)
        return False

    def tras_reanudar(self):
        self._reprogramar_hora()

    # -- GLib --------------------------------------------------------------------------------
    def conectar_glib(self):
        """Hilos de trabajo, paso al bucle y temporizadores reales."""
        GLib, _Gio = _gi()

        def lanzar(trabajo, fin):
            @protegido(False)
            def terminar(res):
                fin(res)
                return False

            def hilo():
                try:
                    res = trabajo()
                except Exception:
                    registrar("error en una ejecución de reglas:\n" + traceback.format_exc())
                    res = [{"accion": "regla", "resultado": "fallo", "detalle": "error interno"}]
                GLib.idle_add(terminar, res)

            threading.Thread(target=hilo, daemon=True).start()

        def en_bucle(fn):
            hecho, caja = threading.Event(), []

            def correr():
                try:
                    caja.append(fn())
                except Exception as e:
                    caja.append(e)
                hecho.set()
                return False

            GLib.idle_add(correr)
            if not hecho.wait(30):
                raise OSError("el servicio no respondió a tiempo")
            if isinstance(caja[0], Exception):
                raise caja[0]
            return caja[0]

        def temporizador(segundos, fn):
            return GLib.timeout_add(int(segundos * 1000), protegido(False)(fn))

        self.lanzador, self.en_bucle = lanzar, en_bucle
        self.temporizador, self.cancelar = temporizador, GLib.source_remove


# -- disponibilidad de eventos y de acciones ---------------------------------------

def nombre_en_bus(nombre):
    """True si el nombre existe (con dueño o activable) en el bus de sistema, False si no
    existe, None si el bus no responde."""
    try:
        GLib, Gio = _gi()
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        bus = ("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus")
        r = con.call_sync(bus[0], bus[1], bus[2], "NameHasOwner", GLib.Variant("(s)", (nombre,)), None,
                          Gio.DBusCallFlags.NONE, 1000, None)
        if r.unpack()[0]:
            return True
        r = con.call_sync(bus[0], bus[1], bus[2], "ListActivatableNames", None, None,
                          Gio.DBusCallFlags.NONE, 1000, None)
        return nombre in r.unpack()[0]
    except Exception:
        return None


def disponibilidad_sistema(en_bus=nombre_en_bus, entorno=None, cual=shutil.which, bateria=None, cargador=None,
                           hermano=programa_hermano):
    """{"eventos": {id: (disponible, motivo)}, "acciones": {...}} segun lo que hay en este equipo."""
    entorno = os.environ if entorno is None else entorno
    bateria = bateria or leer_bateria
    cargador = cargador or leer_cargador
    ev, ac = {}, {}

    def poner(destino, ident, ok, motivo):
        destino[ident] = (bool(ok), None if ok else motivo)

    poner(ev, "bateria_baja", bateria() is not None, "Este equipo no tiene batería")
    poner(ev, "cargador", cargador() is not None, "No se detecta ningún cargador (fuente de alimentación) en este equipo")
    bluez = en_bus("org.bluez")
    poner(ev, "bluetooth", bluez is True,
          "BlueZ (org.bluez) no está disponible: este equipo no tiene Bluetooth o el servicio está desinstalado"
          if bluez is False else "No se pudo consultar el bus del sistema")
    hypr = firma_hyprland(entorno) is not None
    for ident in ("monitor", "aplicacion"):
        poner(ev, ident, hypr, "No hay una sesión de Hyprland: los eventos de ventanas y monitores vienen de ella")
    poner(ev, "hora", True, None)
    nm = en_bus("org.freedesktop.NetworkManager")
    poner(ev, "red", nm is True,
          "NetworkManager no está disponible" if nm is False else "No se pudo consultar el bus del sistema")
    logind = en_bus("org.freedesktop.login1")
    poner(ev, "suspension", logind is True,
          "logind no está disponible" if logind is False else "No se pudo consultar el bus del sistema")
    poner(ev, "inactividad", cual("hypridle") is not None, "hypridle no está instalado")
    for ident in ("estado_sistema", "servicio_fallido", "perfil"):
        poner(ev, ident, True, None)
    poner(ac, "perfil", True, None)
    poner(ac, "modo_noche", hermano("modo-noche") is not None and cual("hyprsunset") is not None,
          "Faltan modo-noche o hyprsunset")
    poner(ac, "no_molestar", cual("swaync-client") is not None, "swaync no está instalado")
    poner(ac, "notificar", cual("notify-send") is not None, "notify-send no está instalado")
    poner(ac, "abrir_aplicacion", hermano("jaime0-anclar") is not None or cual("jaime0-anclar") is not None,
          "jaime0-anclar no está instalado")
    for ident in ("volumen", "silenciar", "salida_audio"):
        poner(ac, ident, cual("wpctl") is not None, "wpctl (PipeWire) no está instalado")
    poner(ac, "mantenimiento", True, None)
    poner(ac, "script", True, None)
    return {"eventos": ev, "acciones": ac, "condiciones": {}}


# -- fuentes de eventos con D-Bus y socket2 (con GLib; sin pruebas automaticas) ------------

def vigilar_bluetooth(cb):
    """Conexion y desconexion de dispositivos Bluetooth por BlueZ (senales PropertiesChanged
    de Device1, sin sondeo): cb(estado, nombre, audio). Si BlueZ no existe, la suscripcion
    no recibe nada."""
    GLib, Gio = _gi()
    try:
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception:
        return None
    previos = {}

    def cambio(_con, _emisor, objeto, _iface, _senal, params, _datos):
        try:
            _interfaz, cambiadas, _inval = params.unpack()
            estado = cambio_bluez(objeto, cambiadas, previos)
            if estado is None:
                return

            def con_props(valor):
                props = (valor[0] if valor else None) or cambiadas
                nombre, audio = info_bluez(props)
                cb(estado, nombre, audio)

            _llamar(con, "org.bluez", objeto, "org.freedesktop.DBus.Properties", "GetAll",
                    GLib.Variant("(s)", ("org.bluez.Device1",)), con_props)
        except Exception:
            registrar("error en una senal de BlueZ:\n" + traceback.format_exc())

    return con, con.signal_subscribe("org.bluez", "org.freedesktop.DBus.Properties", "PropertiesChanged", None,
                                     "org.bluez.Device1", Gio.DBusSignalFlags.NONE, cambio, None)


NM = ("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
PROPS = "org.freedesktop.DBus.Properties"


def vigilar_red(cb):
    """Estado de la red por NetworkManager (senal PropertiesChanged, sin sondeo): cb(estado,
    wifi) con estado 'conectada' o 'desconectada' y wifi el SSID de la conexion primaria si es
    Wi-Fi (o None). Solo avisa cuando cambia la categoria; el estado inicial no genera evento."""
    GLib, Gio = _gi()
    try:
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception:
        return None
    previo = [None]

    def ssid(entregar):
        """SSID de la conexion primaria si es Wi-Fi: cadena de consultas asincronas."""
        def con_primaria(v):
            ruta_activa = v[0] if v else "/"
            if not ruta_activa or ruta_activa == "/":
                return entregar(None)
            _llamar(con, NM[0], ruta_activa, PROPS, "GetAll",
                    GLib.Variant("(s)", ("org.freedesktop.NetworkManager.Connection.Active",)), con_activa)

        def con_activa(v):
            p = v[0] if v else {}
            if p.get("Type") != "802-11-wireless" or p.get("SpecificObject") in (None, "/"):
                return entregar(None)
            _llamar(con, NM[0], p["SpecificObject"], PROPS, "Get",
                    GLib.Variant("(ss)", ("org.freedesktop.NetworkManager.AccessPoint", "Ssid")), con_ap)

        def con_ap(v):
            try:
                entregar(bytes(v[0]).decode("utf-8", "replace") or None)
            except Exception:
                entregar(None)

        _llamar(con, NM[0], NM[1], PROPS, "Get", GLib.Variant("(ss)", (NM[0], "PrimaryConnection")), con_primaria)

    def cambio(_con, _emisor, _objeto, _iface, _senal, params, _datos):
        try:
            _interfaz, cambiadas, _inval = params.unpack()
            if "State" not in cambiadas:
                return
            nuevo = estado_red(cambiadas["State"], previo[0])
            if nuevo is None:
                return
            previo[0] = nuevo
            if nuevo == "desconectada":
                cb(nuevo, None)
            else:       # la conexion primaria tarda un poco en publicarse
                GLib.timeout_add(1500, lambda: (ssid(lambda s: cb(nuevo, s)), False)[1])
        except Exception:
            registrar("error en una senal de NetworkManager:\n" + traceback.format_exc())

    def inicial(v):
        if v:
            previo[0] = "conectada" if v[0] == 70 else ("desconectada" if v[0] <= 20 else None)

    sub = con.signal_subscribe(NM[0], PROPS, "PropertiesChanged", NM[1], NM[0], Gio.DBusSignalFlags.NONE, cambio, None)
    _llamar(con, NM[0], NM[1], PROPS, "Get", GLib.Variant("(ss)", (NM[0], "State")), inicial)
    return con, sub


class FuenteHyprland:
    """Eventos de ventanas y monitores por el socket2 de Hyprland. Si el socket no existe aun
    o se cierra (Hyprland se reinicia), reintenta cada REINTENTO_HYPRLAND s sin bloquear."""

    def __init__(self, analizador, al_evento, ejecutar=None):
        self.analizador, self.al_evento = analizador, al_evento
        self.ejecutar = ejecutar or subprocess.run
        self.sock = None
        self.buf = b""
        self.fuente = None

    def iniciar(self):
        GLib, _Gio = _gi()
        if firma_hyprland() is None:
            return False                    # sin Hyprland: no hay nada que escuchar
        self._conectar()
        GLib.timeout_add_seconds(REINTENTO_HYPRLAND, self._reintentar)
        return True

    @protegido(True)
    def _reintentar(self):
        if self.sock is None:
            self._conectar()
        return True

    def _conectar(self):
        import socket
        GLib, _Gio = _gi()
        destino = ruta_socket2()
        if destino is None:
            return
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.settimeout(1.0)
            s.connect(destino)
            s.setblocking(False)
        except OSError:
            s.close()
            return
        self.sock, self.buf = s, b""
        self.analizador.reiniciar()
        self.fuente = GLib.io_add_watch(s.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                                        self._leer)
        threading.Thread(target=self._sembrar, daemon=True).start()

    def _sembrar(self):
        """Ventanas que ya existian, para contar bien la primera y la ultima de cada clase."""
        GLib, _Gio = _gi()
        try:
            extra = {} if (env := entorno_hyprland(firma_hyprland())) is None else {"env": env}
            r = self.ejecutar(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=5, **extra)
            ventanas = [(c["address"], c.get("class") or "") for c in json.loads(r.stdout)] if r.returncode == 0 else []
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            return
        GLib.idle_add(protegido(False)(lambda: (self.analizador.sembrar(ventanas), False)[1]))

    def _cerrar(self):
        s, self.sock = self.sock, None
        if s is not None:
            try:
                s.close()
            except OSError:
                pass

    @protegido(False)
    def _leer(self, _fd, _cond):
        try:
            datos = self.sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            return True
        except OSError:
            datos = b""
        if not datos:
            self._cerrar()                  # Hyprland se cerro: _reintentar vuelve a conectar
            return False
        self.buf += datos
        *lineas, self.buf = self.buf.split(b"\n")
        for linea in lineas:
            for evento, d in self.analizador.procesar(linea.decode("utf-8", "replace")):
                try:
                    self.al_evento(evento, d)
                except Exception:
                    registrar("error en un evento de Hyprland:\n" + traceback.format_exc())
        return True
