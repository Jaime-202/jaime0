# jaime0_servicio.incidencias: eventos de actividad (Detector) e incidencias sostenidas
# (condiciones, textos, Incidencias). Depende de: base.

from .base import (
    VERSION_DATOS, MUESTRAS_INCIDENCIA, MUESTRAS_SIN_DATO, MUESTRAS_PICO_CPU, UMBRAL_PICO_CPU,
    UMBRAL_PICO_RAM, SALTO_TEMPERATURA
)

__all__ = [
    "nuevo_evento", "Detector", "LENTOS", "COMPONENTES_PUNTUALES", "NOMBRES_COMPONENTE",
    "condiciones", "texto_incidencia", "Incidencias"
]


# ---------------------------------------------------------------------------
# Eventos de actividad (marcadores de las graficas)
# ---------------------------------------------------------------------------

def nuevo_evento(t, tipo, gravedad, texto, proceso=None, origen=None):
    """Evento de las graficas. 'origen' (usuario|regla|inicio) solo lo llevan los cambios de perfil."""
    ev = {"t": int(t), "tipo": tipo, "gravedad": gravedad, "texto": texto, "proceso": proceso}
    if origen:
        ev["origen"] = origen
    return ev


class Detector:
    """Detecta picos de CPU y RAM y saltos de temperatura entre muestras consecutivas."""

    def __init__(self):
        self.cpu_altas, self.pico_cpu, self.pico_ram = 0, False, False
        self.temp_previa, self.t_previa = None, None

    def procesar(self, inst):
        eventos = []
        t = int(inst["t"])
        cpu = (inst.get("cpu") or {}).get("total")
        if cpu is not None:
            if cpu >= UMBRAL_PICO_CPU:
                self.cpu_altas += 1
                if self.cpu_altas >= MUESTRAS_PICO_CPU and not self.pico_cpu:
                    self.pico_cpu = True
                    top = next(iter(inst.get("procesos") or []), None)
                    proceso = {"nombre": top["nombre"], "cpu": top["cpu"]} if top else None
                    texto = f"Pico de CPU al {cpu:.0f} %" + (f" ({top['nombre']}, {top['cpu']:.0f} %)" if top else "")
                    eventos.append(nuevo_evento(t, "pico_cpu", "WARNING", texto, proceso))
            else:
                self.cpu_altas, self.pico_cpu = 0, False
        ram = inst.get("ram") or {}
        if ram.get("total"):
            pct = 100.0 * ram["usada"] / ram["total"]
            if pct >= UMBRAL_PICO_RAM:
                if not self.pico_ram:
                    self.pico_ram = True
                    eventos.append(nuevo_evento(t, "pico_ram", "WARNING", f"Pico de RAM al {pct:.0f} %"))
            elif pct < UMBRAL_PICO_RAM - 5:
                self.pico_ram = False
        temp = (inst.get("cpu") or {}).get("temp")
        if temp is not None:
            if (self.temp_previa is not None and temp - self.temp_previa >= SALTO_TEMPERATURA
                    and t - self.t_previa <= 10):
                eventos.append(nuevo_evento(
                    t, "salto_temp", "WARNING",
                    f"Salto de temperatura: {self.temp_previa:.0f} → {temp:.0f} °C"))
            self.temp_previa, self.t_previa = temp, t
        return eventos


# ---------------------------------------------------------------------------
# Incidencias: condicion sostenida durante varias muestras
# ---------------------------------------------------------------------------

LENTOS = ("systemd", "smart")       # vienen del refresco lento: una muestra basta
COMPONENTES_PUNTUALES = ("reglas",)  # incidencias que no tienen cierre automatico
NOMBRES_COMPONENTE = {
    "cpu-temp": "temperatura de la CPU", "gpu": "temperatura de la GPU", "disco": "espacio en disco",
    "bateria": "nivel de batería", "ram": "memoria disponible", "swap": "uso de swap",
    "presion": "presión de memoria", "systemd": "unidades de systemd", "smart": "salud del disco (SMART)",
}


def condiciones(inst, u):
    """{componente: (gravedad, valor, detalle)} de un instante; solo lo que tiene dato. La
    gravedad es NORMAL, WARNING o CRITICAL. Distinta de evaluar(): separa cpu-temp, gpu y
    presion, que son componentes de incidencia propios."""
    def grav(v, aviso, critico):
        return "CRITICAL" if v >= critico else ("WARNING" if v >= aviso else "NORMAL")

    c = {}
    temp = (inst.get("cpu") or {}).get("temp")
    if temp is not None:
        c["cpu-temp"] = (grav(temp, u["temp_aviso"], u["temp_critico"]), temp, None)
    gtemp = (inst.get("gpu") or {}).get("temp")
    if gtemp is not None:
        c["gpu"] = (grav(gtemp, u["temp_aviso"], u["temp_critico"]), gtemp, None)
    discos = [d for d in inst.get("disco") or [] if d.get("total")]
    if discos:
        peor = max(discos, key=lambda d: d["usado"] / d["total"])
        pct = 100.0 * peor["usado"] / peor["total"]
        c["disco"] = (grav(pct, u["disco_aviso"], u["disco_critico"]), round(pct, 1), peor["punto"])
    bat = inst.get("bateria")
    if bat and bat.get("nivel") is not None:
        if bat.get("estado") == "descargando":
            g = ("CRITICAL" if bat["nivel"] <= u["bateria_critico"]
                 else "WARNING" if bat["nivel"] <= u["bateria_aviso"] else "NORMAL")
        else:
            g = "NORMAL"
        c["bateria"] = (g, bat["nivel"], None)
    ram = inst.get("ram")
    if ram:
        if ram.get("total"):
            libre = 100.0 * (ram["total"] - ram["usada"]) / ram["total"]
            c["ram"] = ("CRITICAL" if libre < u["ram_libre_critico"] else "NORMAL", round(libre, 1), None)
        if ram.get("swap_total", 0) > 0:
            pct = 100.0 * ram["swap"] / ram["swap_total"]
            c["swap"] = ("WARNING" if pct > u["swap_aviso"] else "NORMAL", round(pct, 1), None)
        if ram.get("presion") is not None:
            c["presion"] = ("WARNING" if ram["presion"] > u["presion_aviso"] else "NORMAL", ram["presion"], None)
    if inst.get("fallidas") is not None:
        c["systemd"] = ("WARNING" if inst["fallidas"] else "NORMAL", list(inst["fallidas"]), None)
    if inst.get("smart") is not None:
        malos = [s["disco"] for s in inst["smart"] if s.get("estado") == "FALLO"]
        c["smart"] = ("CRITICAL" if malos else "NORMAL", malos, None)
    return c


def texto_incidencia(componente, gravedad, valor, detalle, u):
    """(descripcion, diagnostico, recomendacion) en espanol; prudentes y sin acciones automaticas."""
    critico = gravedad == "CRITICAL"
    if componente in ("cpu-temp", "gpu"):
        que = "la CPU" if componente == "cpu-temp" else "la GPU"
        umbral = u["temp_critico"] if critico else u["temp_aviso"]
        return (f"Temperatura de {que} a {valor:.0f} °C (umbral {umbral:.0f} °C)",
                "Temperatura sostenida por encima del umbral" + (
                    ": cerca del límite térmico, el equipo puede reducir su rendimiento" if critico else ""),
                "Comprueba qué proceso consume CPU (TOP PROCESSES) y que las rejillas de ventilación no estén tapadas"
                + ("; si sigue subiendo, guarda tu trabajo y apaga el equipo" if critico else ""))
    if componente == "disco":
        return (f"Disco {detalle} al {valor:.0f} %",
                "El espacio libre es muy escaso: algunas aplicaciones pueden fallar al guardar" if critico
                else "El espacio libre es escaso",
                "Libera espacio: revisa descargas, papelera y cachés, o mueve archivos grandes a otro disco")
    if componente == "bateria":
        return (f"Batería al {valor} %",
                "La batería se está agotando y el cargador no está conectado" + (
                    ": el equipo puede apagarse en breve" if critico else ""),
                "Conecta el cargador o activa el perfil de ahorro de energía" + (
                    "; guarda tu trabajo" if critico else ""))
    if componente == "ram":
        return (f"Memoria disponible al {valor:.0f} %",
                "Queda muy poca memoria libre: el sistema puede ir lento o cerrar procesos",
                "Cierra las aplicaciones que más memoria usan (TOP PROCESSES) o reinicia las que acumulan memoria")
    if componente == "swap":
        return (f"Swap usada al {valor:.0f} %",
                "El sistema está usando mucho el espacio de intercambio: suele indicar poca RAM para la carga actual",
                "Cierra aplicaciones pesadas (TOP PROCESSES); si es habitual, considera ampliar la RAM")
    if componente == "presion":
        return (f"Presión de memoria alta ({valor:.1f})",
                "Los procesos están esperando por memoria: el sistema puede notarse lento",
                "Cierra aplicaciones pesadas (TOP PROCESSES)")
    if componente == "systemd":
        lista = list(valor)
        return ("Unidades de systemd fallidas: " + ", ".join(lista[:3]) + ("…" if len(lista) > 3 else ""),
                "Hay servicios que han terminado con error",
                "Revisa el motivo con: systemctl --failed y journalctl -u UNIDAD")
    if componente == "smart":
        return ("El disco informa de un fallo SMART: " + ", ".join(valor),
                "El propio disco avisa de que podría fallar",
                "Haz una copia de seguridad de tus datos cuanto antes y valora sustituir el disco")
    return (f"{componente}: {gravedad}", "", "")


class Incidencias:
    """Abre, escala y cierra incidencias con histeresis: una condicion debe mantenerse
    MUESTRAS_INCIDENCIA muestras seguidas para abrirse y otras tantas en NORMAL para cerrarse
    (una sola para systemd y smart). Una muestra suelta no dispara nada. Un componente que
    deja de dar dato MUESTRAS_SIN_DATO muestras seguidas se cierra (sin inventar valores)."""

    def __init__(self):
        self.comp = {}

    def observar(self, inst, u, t):
        """Devuelve las lineas de incidencia nuevas (abrir, escalar, cerrar)."""
        lineas = []
        conds = condiciones(inst, u)
        for nombre, c in self.comp.items():
            if nombre in conds:
                c["sin_dato"] = 0
                continue
            c["sin_dato"] = c.get("sin_dato", 0) + 1
            if c["sin_dato"] < MUESTRAS_SIN_DATO:
                continue
            c["ventana"] = []                   # la ventana vieja no debe reutilizarse al volver el dato
            if c["abierta"] != "NORMAL":
                c["abierta"] = "NORMAL"
                lineas.append({"v": VERSION_DATOS, "t": int(t), "gravedad": "NORMAL", "componente": nombre,
                               "descripcion": "Recuperado: " + NOMBRES_COMPONENTE.get(nombre, nombre),
                               "diagnostico": "Sin datos del sensor", "recomendacion": "", "valor": None})
        for nombre, (grav, valor, detalle) in conds.items():
            c = self.comp.setdefault(nombre, {"abierta": "NORMAL", "ventana": [], "sin_dato": 0})
            n = 1 if nombre in LENTOS else MUESTRAS_INCIDENCIA
            c["ventana"].append(grav)
            del c["ventana"][:-n]
            v = c["ventana"]
            if len(v) < n:
                continue
            nueva = None
            if c["abierta"] == "NORMAL":
                if all(g != "NORMAL" for g in v):
                    nueva = "CRITICAL" if all(g == "CRITICAL" for g in v) else "WARNING"
            elif all(g == "NORMAL" for g in v):
                nueva = "NORMAL"
            elif c["abierta"] == "WARNING" and all(g == "CRITICAL" for g in v):
                nueva = "CRITICAL"
            elif c["abierta"] == "CRITICAL" and all(g != "CRITICAL" for g in v):
                c["abierta"], c["ventana"] = "WARNING", []      # baja de gravedad sin linea nueva
            if nueva is None:
                continue
            if nueva == "NORMAL":
                desc = "Recuperado: " + NOMBRES_COMPONENTE.get(nombre, nombre) + (f" ({detalle})" if detalle else "")
                diag = recom = ""
            else:
                desc, diag, recom = texto_incidencia(nombre, nueva, valor, detalle, u)
            lineas.append({"v": VERSION_DATOS, "t": int(t), "gravedad": nueva, "componente": nombre,
                           "descripcion": desc, "diagnostico": diag, "recomendacion": recom, "valor": valor})
            c["abierta"], c["ventana"] = nueva, []
        return lineas

    def abiertas(self):
        return [{"componente": k, "gravedad": c["abierta"]} for k, c in sorted(self.comp.items())
                if c["abierta"] != "NORMAL"]

    def restaurar(self, docs):
        """Al arrancar, recupera de incidencias.jsonl las que siguen abiertas (la ultima
        linea de cada componente). Asi un reinicio del servicio no vuelve a abrir, duplicada,
        una incidencia que ya estaba registrada."""
        for d in docs or []:
            nombre, grav = d.get("componente"), d.get("gravedad")
            if nombre in COMPONENTES_PUNTUALES:
                continue            # sin cierre automatico: no se recuperan como abiertas
            if nombre and grav in ("NORMAL", "WARNING", "CRITICAL"):
                self.comp[nombre] = {"abierta": grav, "ventana": []}
