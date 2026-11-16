# jaime0_servicio.estado: estado global (evaluar, funcion pura), resumen de privacidad del
# instante y el anillo de muestras. Depende de: base y privacidad.

from .base import DURACION_ANILLO, UMBRALES
from .privacidad import leer_conf_ufw, politicas_ufw, puertos_expuestos

__all__ = [
    "evaluar", "resumen_privacidad", "muestra_desde_instante", "anillo_agregar"
]


# ---------------------------------------------------------------------------
# Estado global (funcion pura) y privacidad
# ---------------------------------------------------------------------------

def evaluar(inst, u=None):
    """(estado, motivos) a partir de un instante y los umbrales. Motivos: lista de
    {"gravedad","componente","texto"}; por componente solo se informa lo mas grave."""
    u = u or UMBRALES
    motivos = []

    def nuevo(gravedad, componente, texto):
        motivos.append({"gravedad": gravedad, "componente": componente, "texto": texto})

    temp = (inst.get("cpu") or {}).get("temp")
    if temp is not None:
        if temp >= u["temp_critico"]:
            nuevo("CRITICAL", "cpu", f"Temperatura de la CPU a {temp:.0f} °C")
        elif temp >= u["temp_aviso"]:
            nuevo("WARNING", "cpu", f"Temperatura de la CPU a {temp:.0f} °C")
    for d in inst.get("disco") or []:
        if d.get("total"):
            pct = 100.0 * d["usado"] / d["total"]
            if pct >= u["disco_critico"]:
                nuevo("CRITICAL", "disco", f"Disco {d['punto']} al {pct:.0f} %")
            elif pct >= u["disco_aviso"]:
                nuevo("WARNING", "disco", f"Disco {d['punto']} al {pct:.0f} %")
    bat = inst.get("bateria")
    if bat and bat.get("nivel") is not None and bat.get("estado") == "descargando":
        if bat["nivel"] <= u["bateria_critico"]:
            nuevo("CRITICAL", "bateria", f"Batería al {bat['nivel']} %")
        elif bat["nivel"] <= u["bateria_aviso"]:
            nuevo("WARNING", "bateria", f"Batería al {bat['nivel']} %")
    ram = inst.get("ram")
    if ram:
        if ram.get("total"):
            libre = 100.0 * (ram["total"] - ram["usada"]) / ram["total"]
            if libre < u["ram_libre_critico"]:
                nuevo("CRITICAL", "ram", f"Memoria disponible al {libre:.0f} %")
        if ram.get("swap_total", 0) > 0 and 100.0 * ram["swap"] / ram["swap_total"] > u["swap_aviso"]:
            nuevo("WARNING", "swap", f"Swap usada al {100.0 * ram['swap'] / ram['swap_total']:.0f} %")
        if ram.get("presion") is not None and ram["presion"] > u["presion_aviso"]:
            nuevo("WARNING", "ram", f"Presión de memoria alta ({ram['presion']:.1f})")
    fallidas = inst.get("fallidas")
    if fallidas:
        nuevo("WARNING", "systemd", f"Unidades fallidas: {', '.join(fallidas[:3])}"
              + ("…" if len(fallidas) > 3 else ""))
    if any(m["gravedad"] == "CRITICAL" for m in motivos):
        return "CRITICAL", motivos
    return ("WARNING" if motivos else "ONLINE"), motivos


def resumen_privacidad(unidad_activa=None, puertos=None):
    """Resumen de cortafuegos y puertos. No afirma que el sistema este protegido, solo lo
    que se comprobo. unidad_activa: True/False segun ActiveState de ufw.service, None si no
    se pudo saber. puertos: lista de puertos en escucha (consultar_puertos) o None si no se
    pudo mirar (entonces no se dice nada de ellos). Devuelve estado, detalles (lo que se
    comprobo) y motivos (por que no es SECURE)."""
    conf = leer_conf_ufw()
    if conf is None:
        texto = "El cortafuegos (UFW) no está instalado"
        return {"estado": "UNAVAILABLE", "detalles": [texto], "motivos": [texto]}
    activado = conf.get("ENABLED", "").lower() == "yes"
    entrante = politicas_ufw()["entrante"]
    denegado = entrante in ("DROP", "REJECT")
    detalles, motivos = [], []
    if activado and unidad_activa:
        if entrante == "ACCEPT":
            texto = "Cortafuegos activo: entrante permitido por defecto"
            motivos.append(texto)
        else:
            texto = ("Cortafuegos activo: entrante denegado por defecto" if denegado
                     else "Cortafuegos activo")
        detalles.append(texto)
    elif not activado:
        texto = "El cortafuegos (UFW) está desactivado"
        detalles.append(texto)
        motivos.append(texto)
    else:
        texto = "El cortafuegos (UFW) está configurado pero su servicio no está activo"
        detalles.append(texto)
        motivos.append(texto)
    if puertos is not None:
        expuestos = puertos_expuestos(puertos)
        if not expuestos:
            detalles.append("Ningún puerto abierto a la red")
        else:
            detalles.append(f"{len(expuestos)} puerto(s) abierto(s) a la red")
            aclaracion = ("UFW bloquea la entrada salvo que una regla lo permita" if activado and unidad_activa and denegado
                          else "no hay un bloqueo de entrada por defecto que lo filtre")
            for (puerto, proto), proceso in sorted(expuestos.items())[:5]:
                motivos.append(f"Puerto {puerto}/{proto} abierto a la red "
                               f"({proceso or 'proceso no identificado'}): {aclaracion}")
            if len(expuestos) > 5:
                motivos.append(f"Y {len(expuestos) - 5} puerto(s) más abiertos a la red")
    return {"estado": "WARNING" if motivos else "SECURE", "detalles": detalles, "motivos": motivos}


def muestra_desde_instante(inst):
    """Muestra reducida para el anillo y el historico: una por metrica, None si no hay dato.
    ram, swap y disco son % usado; presion es avg10; lectura/escritura en MB/s del disco '/'."""
    cpu, ram = inst.get("cpu") or {}, inst.get("ram") or {}
    bat, gpu = inst.get("bateria") or {}, inst.get("gpu") or {}
    raiz_disco = next((d for d in inst.get("disco") or [] if d.get("punto") == "/"), None) or {}

    def pct(a, b):
        return round(100.0 * a / b, 1) if a is not None and b else None

    return {"t": int(inst["t"]), "cpu": cpu.get("total"),
            "ram": pct(ram.get("usada"), ram.get("total")),
            "swap": pct(ram.get("swap"), ram.get("swap_total")),
            "presion": ram.get("presion"), "temp": cpu.get("temp"), "gpu_temp": gpu.get("temp"),
            "bateria": bat.get("nivel"), "vatios": bat.get("vatios"),
            "lectura": raiz_disco.get("lectura"), "escritura": raiz_disco.get("escritura"),
            "disco": pct(raiz_disco.get("usado"), raiz_disco.get("total")),
            # 1 conectado, 0 no; la media de un minuto es la fraccion del minuto con cargador.
            "cargador": {True: 1, False: 0}.get(inst.get("cargador"))}


def anillo_agregar(anillo, inst):
    """Anade la muestra al anillo en RAM y descarta lo que pase de una hora."""
    m = muestra_desde_instante(inst)
    anillo.append(m)
    while anillo and anillo[0]["t"] < m["t"] - DURACION_ANILLO:
        anillo.popleft()
    return m
