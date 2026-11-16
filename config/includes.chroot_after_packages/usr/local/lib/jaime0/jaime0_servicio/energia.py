# jaime0_servicio.energia: POWER (evolucion, fase 6). Lee y explica el estado energetico: bateria
# en detalle, graficas (integrada, dedicada, PRIME y quien usa la NVIDIA), CPU, suspension e
# inactividad, y resume el historico (tiempo con cargador y consumo por perfil de energia).
# Solo lee: no cambia nada. Cada ajuste tiene un unico dueno (ver docs/energia.md): el perfil de
# energia lo pone el perfil de Jaime0 (PROFILES), la inactividad son ajustes de jaime0-ajustes y
# lo que necesita root (logind, limites de carga, gobernador) solo se muestra.
# Cada dato va como {"valor", "origen"}: origen "medido" (lo da el hardware), "calculado" (a
# partir de datos medidos), "estimado" (supone que el consumo sigue igual) o "no_disponible".
# Depende de: base y medicion.

import glob
import os
import re
import subprocess

from .base import ruta
from .medicion import ESTADOS_BATERIA, leer_ruta, leer_entero

__all__ = [
    "VALORES_ENERGIA", "EVENTOS_ENERGIA", "CONDICIONES_ENERGIA", "MIN_DESCARGA", "MIN_COMPARAR",
    "FABRICANTES", "VIRTUALES", "RE_NVIDIA", "LOGIND_DEFECTO",
    "dato", "carpeta_bateria", "detalle_bateria", "descarga_por_hora", "graficas", "procesos_nvidia",
    "medidas_nvidia", "cpu_energia", "leer_logind", "suspension", "inactividad", "tiempo_con_cargador",
    "comparar_perfiles", "reglas_energia",
]

VALORES_ENERGIA = ("balanced", "performance", "power-saver")
EVENTOS_ENERGIA = ("bateria_baja", "cargador", "suspension", "perfil")
CONDICIONES_ENERGIA = ("cargador", "bateria_menor", "bateria_mayor")
MIN_DESCARGA = 600          # s de descarga seguida para estimar la velocidad
MIN_COMPARAR = 10           # minutos en bateria con un perfil para dar su consumo medio
FABRICANTES = {"0x8086": "Intel", "0x10de": "NVIDIA", "0x1002": "AMD", "0x15ad": "VMware",
               "0x80ee": "VirtualBox", "0x1234": "QEMU", "0x1b36": "QEMU", "0x1af4": "virtio"}
VIRTUALES = ("0x15ad", "0x80ee", "0x1234", "0x1b36", "0x1af4")
RE_NVIDIA = re.compile(r"^/dev/nvidia\d+$")
LOGIND_DEFECTO = {"HandleLidSwitch": "suspend", "HandleLidSwitchDocked": "ignore",
                  "HandlePowerKey": "poweroff"}


def dato(valor, origen="medido"):
    return {"valor": valor, "origen": origen if valor is not None else "no_disponible"}


# ---------------------------------------------------------------------------
# Bateria
# ---------------------------------------------------------------------------

def carpeta_bateria():
    for d in sorted(glob.glob(ruta("sys", "class", "power_supply", "BAT*"))):
        if leer_ruta(os.path.join(d, "type")) == "Battery":
            return d
    return None


def descarga_por_hora(muestras):
    """%/h perdidos en la descarga seguida mas reciente (muestras del anillo: t, bateria,
    cargador). None si no hay al menos MIN_DESCARGA s sin cargador o el nivel no ha bajado."""
    tramo = []
    for m in reversed(list(muestras)):
        if m.get("cargador") != 0 or m.get("bateria") is None:
            break
        tramo.append(m)
    if len(tramo) < 2:
        return None
    ultimo, primero = tramo[0], tramo[-1]
    dt = ultimo["t"] - primero["t"]
    caida = primero["bateria"] - ultimo["bateria"]
    if dt < MIN_DESCARGA or caida <= 0:
        return None
    return round(caida * 3600.0 / dt, 1)


def detalle_bateria(muestras=()):
    """Todo lo que la bateria cuenta en sysfs, o None si no hay. Las capacidades van en Wh
    (energy_*) o en mAh (charge_*), segun lo que de el firmware."""
    d = carpeta_bateria()
    if d is None:
        return None
    e = lambda nombre: leer_entero(os.path.join(d, nombre))
    # "Unknown" es lo que pone el kernel cuando el firmware no lo dice: no es un dato.
    t = lambda nombre: (leer_ruta(os.path.join(d, nombre)) or "").replace("Unknown", "") or None
    estado = ESTADOS_BATERIA.get(t("status") or "", "desconocido")
    if e("energy_full_design") is not None or e("energy_now") is not None:
        unidad, div, decimales = "Wh", 1e6, 1
        diseno, lleno, ahora = e("energy_full_design"), e("energy_full"), e("energy_now")
    else:
        unidad, div, decimales = "mAh", 1e3, 0
        diseno, lleno, ahora = e("charge_full_design"), e("charge_full"), e("charge_now")
    conv = lambda x: None if x is None else round(x / div, decimales)
    pot, corr, volt = e("power_now"), e("current_now"), e("voltage_now")
    if pot is not None:
        potencia = dato(round(pot / 1e6, 1))
    elif corr is not None and volt:
        potencia = dato(round(abs(corr) * volt / 1e12, 1), "calculado")
    else:
        potencia = dato(None)
    # Ritmo actual de vaciado o llenado en las unidades de la capacidad (Wh/h = W, mAh/h = mA).
    ritmo = pot if unidad == "Wh" else (abs(corr) if corr else None)
    autonomia = hasta_llena = None
    if ritmo and ahora is not None:
        if estado == "descargando":
            autonomia = int(round(ahora / ritmo * 60))
        elif estado == "cargando" and lleno is not None and lleno > ahora:
            hasta_llena = int(round((lleno - ahora) / ritmo * 60))
    salud = round(100.0 * lleno / diseno, 1) if lleno is not None and diseno else None
    ciclos = e("cycle_count")
    limite = e("charge_control_end_threshold")
    return {
        "nivel": dato(e("capacity")), "estado": estado, "unidad": unidad,
        "capacidad_diseno": dato(conv(diseno)), "capacidad_actual": dato(conv(lleno)),
        "carga_actual": dato(conv(ahora)), "salud": dato(salud, "calculado"),
        # Muchos firmwares no cuentan los ciclos y dan 0: se muestra con la nota.
        "ciclos": dato(ciclos), "ciclos_sin_contar": ciclos == 0,
        "potencia": potencia, "voltaje": dato(None if volt is None else round(volt / 1e6, 2)),
        "autonomia_min": dato(autonomia, "estimado"), "hasta_llena_min": dato(hasta_llena, "estimado"),
        "descarga_pct_h": dato(descarga_por_hora(muestras), "estimado"),
        "limite_carga": dato(limite),
        "tecnologia": t("technology"), "fabricante": t("manufacturer"), "modelo": t("model_name"),
    }


# ---------------------------------------------------------------------------
# Graficas
# ---------------------------------------------------------------------------

def procesos_nvidia():
    """Procesos con /dev/nvidiaN abierto (los que usan la NVIDIA y no la dejan dormir). Sin
    root solo se ven los del usuario: 'parcial' lo dice."""
    vistos, parcial = [], False
    for carpeta in glob.glob(ruta("proc", "[0-9]*")):
        try:
            fds = os.listdir(os.path.join(carpeta, "fd"))
        except OSError:
            parcial = True
            continue
        for fd in fds:
            try:
                destino = os.readlink(os.path.join(carpeta, "fd", fd))
            except OSError:
                continue
            if RE_NVIDIA.match(destino):
                vistos.append({"pid": int(os.path.basename(carpeta)),
                               "nombre": leer_ruta(os.path.join(carpeta, "comm")) or "?"})
                break
    vistos.sort(key=lambda p: p["pid"])
    return {"procesos": vistos, "parcial": parcial}


def medidas_nvidia(ejecutar=None):
    """Consumo, temperatura y uso con nvidia-smi. Solo se llama con la grafica ya despierta
    (nvidia-smi la despertaria). Un campo que no da devuelve None."""
    ejecutar = ejecutar or subprocess.run
    try:
        r = ejecutar(["nvidia-smi", "--query-gpu=power.draw,temperature.gpu,utilization.gpu",
                      "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None

    campos = [c.strip() for c in r.stdout.strip().splitlines()[0].split(",")]
    campos += [""] * (3 - len(campos))
    return {"vatios": dato(num(campos[0])), "temp": dato(num(campos[1])), "uso": dato(num(campos[2]))}


def graficas(ejecutar=None, ver_procesos=procesos_nvidia):
    """Las graficas de PCI y como se reparten el trabajo. Nunca despierta la NVIDIA."""
    lista = []
    for dev in sorted(glob.glob(ruta("sys", "bus", "pci", "devices", "*"))):
        clase = (leer_ruta(os.path.join(dev, "class")) or "")[:6]
        if not clase.startswith("0x03"):
            continue
        fab = leer_ruta(os.path.join(dev, "vendor")) or ""
        drv = os.path.join(dev, "driver")
        g = {"pci": os.path.basename(dev), "fabricante": FABRICANTES.get(fab, fab or "?"),
             "principal": leer_ruta(os.path.join(dev, "boot_vga")) == "1",
             "driver": os.path.basename(os.path.realpath(drv)) if os.path.exists(drv) else None,
             "energia": leer_ruta(os.path.join(dev, "power", "runtime_status")),
             "control": leer_ruta(os.path.join(dev, "power", "control"))}
        if fab in VIRTUALES:
            g["rol"] = "virtual"
        elif fab == "0x10de":
            g["rol"] = "dedicada"
        elif fab == "0x8086":
            g["rol"] = "integrada"
        else:
            g["rol"] = "integrada" if g["principal"] else "dedicada"
        if fab == "0x10de":
            g["modulo"] = leer_ruta(ruta("sys", "module", "nvidia", "version"))
            g["modeset"] = leer_ruta(ruta("sys", "module", "nvidia_drm", "parameters", "modeset"))
            despierta = g["driver"] is not None and g["energia"] == "active"
            g["medidas"] = medidas_nvidia(ejecutar) if despierta else None
            g["uso"] = ver_procesos() if g["driver"] is not None else None
        lista.append(g)
    nvidia = next((g for g in lista if g["fabricante"] == "NVIDIA"), None)
    if nvidia is None:
        prime = None
    elif nvidia["driver"] is None:
        prime = "sin_driver"
    elif nvidia["principal"] or len(lista) == 1:
        prime = "nvidia_principal"
    else:
        prime = "offload"
    return {"graficas": lista, "prime": prime}


# ---------------------------------------------------------------------------
# CPU, suspension e inactividad (solo lectura)
# ---------------------------------------------------------------------------

def cpu_energia():
    c = lambda *p: leer_ruta(ruta("sys", "devices", "system", "cpu", *p)) or None
    epps = c("cpu0", "cpufreq", "energy_performance_available_preferences")
    perfiles = leer_ruta(ruta("sys", "firmware", "acpi", "platform_profile_choices"))
    return {"driver": c("cpu0", "cpufreq", "scaling_driver"),
            "gobernador": c("cpu0", "cpufreq", "scaling_governor"),
            "epp": c("cpu0", "cpufreq", "energy_performance_preference"),
            "epp_opciones": epps.split() if epps else [],
            "pstate": c("intel_pstate", "status"),
            "turbo": {"0": True, "1": False}.get(c("intel_pstate", "no_turbo") or ""),
            "perfil_plataforma": leer_ruta(ruta("sys", "firmware", "acpi", "platform_profile")) or None,
            "perfil_plataforma_opciones": perfiles.split() if perfiles else []}


def leer_logind():
    """Claves de [Login] de logind.conf y sus .d (los de /etc mandan sobre /usr/lib; dentro
    de cada nivel, por nombre). Lo que nadie fija vale lo predeterminado de systemd."""
    archivos = [ruta("usr", "lib", "systemd", "logind.conf"), ruta("etc", "systemd", "logind.conf")]
    extra = {}
    for base in (("usr", "lib", "systemd"), ("etc", "systemd")):
        for f in glob.glob(ruta(*base, "logind.conf.d", "*.conf")):
            extra[os.path.basename(f)] = f
    archivos += [extra[n] for n in sorted(extra)]
    valores, fijados = {}, set()
    for f in archivos:
        try:
            with open(f, encoding="utf-8", errors="replace") as h:
                lineas = h.read().splitlines()
        except OSError:
            continue
        seccion = None
        for linea in lineas:
            linea = linea.strip()
            if not linea or linea[0] in "#;":
                continue
            if linea.startswith("["):
                seccion = linea.strip("[]")
                continue
            if seccion == "Login" and "=" in linea:
                k, v = (x.strip() for x in linea.split("=", 1))
                valores[k] = v
                fijados.add(k)
    for k, v in LOGIND_DEFECTO.items():
        valores.setdefault(k, v)
    valores.setdefault("HandleLidSwitchExternalPower", valores["HandleLidSwitch"])
    return {"valores": valores, "fijados": sorted(fijados)}


def suspension():
    texto = leer_ruta(ruta("sys", "power", "mem_sleep")) or ""
    modos = [m.strip("[]") for m in texto.split()]
    actual = next((m.strip("[]") for m in texto.split() if m.startswith("[")), None)
    estados = (leer_ruta(ruta("sys", "power", "state")) or "").split()
    logind = leer_logind()["valores"]
    return {"modo": actual, "modos": modos, "puede_suspender": "mem" in estados,
            "puede_hibernar": "disk" in estados,
            "tapa": logind["HandleLidSwitch"], "tapa_cargador": logind["HandleLidSwitchExternalPower"],
            "boton": logind["HandlePowerKey"]}


def inactividad(ajustes, inicio=None):
    """Tiempos de inactividad de jaime0-ajustes ('ver --json') y si se aplican: si el usuario
    ha cambiado su ~/.config/hypr/hypridle.conf, manda el suyo (ver el programa inactividad)."""
    valores = {a.get("clave"): a.get("valor") for a in (ajustes or {}).get("ajustes") or [] if isinstance(a, dict)}

    def minutos(clave):
        try:
            return int(valores[clave])
        except (KeyError, TypeError, ValueError):
            return None

    inicio = inicio or os.path.expanduser("~")
    propio = os.path.join(inicio, ".config", "hypr", "hypridle.conf")
    try:
        with open(propio, "rb") as f:
            suyo = f.read()
        with open(ruta("etc", "skel", ".config", "hypr", "hypridle.conf"), "rb") as f:
            personalizado = suyo != f.read()
    except FileNotFoundError:
        personalizado = os.path.exists(propio)
    except OSError:
        personalizado = None
    return {"bloqueo": minutos("inactividad_bloqueo"), "pantalla": minutos("inactividad_pantalla"),
            "suspender": minutos("inactividad_suspender"),
            "con_cargador": {"si": True, "no": False}.get(valores.get("suspender_con_cargador")),
            "personalizado": personalizado}


# ---------------------------------------------------------------------------
# Historico: solo con los minutos guardados (nada se rellena)
# ---------------------------------------------------------------------------

def tiempo_con_cargador(minutos, desde):
    """Minutos medidos desde 'desde' y cuantos con el cargador conectado (la media del minuto
    es la fraccion conectada). Solo cuentan los minutos que tienen el dato."""
    con = [a for a in minutos if a["t"] >= desde and a.get("cargador") is not None]
    return {"minutos": len(con), "conectado": int(round(sum(a["cargador"][1] for a in con)))}


def comparar_perfiles(minutos):
    """Consumo medio y descarga por perfil de energia, con los minutos enteros en bateria. El
    perfil de cada minuto sale de los eventos 'perfil' con 'valor' (cambios de ppd); los
    minutos con un cambio dentro, o antes del primer evento, no cuentan."""
    perfil, previo, acc = None, None, {}
    for a in sorted(minutos, key=lambda x: x["t"]):
        cambios = [e for e in a.get("eventos") or [] if e.get("tipo") == "perfil" and e.get("valor") in VALORES_ENERGIA]
        if cambios:
            perfil, previo = max(cambios, key=lambda e: e["t"])["valor"], None
            continue
        c, v, b = a.get("cargador"), a.get("vatios"), a.get("bateria")
        if perfil is None or not c or c[2] != 0:
            previo = None
            continue
        r = acc.setdefault(perfil, {"minutos": 0, "vatios": [], "caida": 0.0, "tramo": 0})
        r["minutos"] += 1
        if v:
            r["vatios"].append(v[1])
        if b and previo and previo[0] == perfil and a["t"] - previo[1] == 60:
            r["caida"] += previo[2] - b[1]
            r["tramo"] += 60
        previo = (perfil, a["t"], b[1]) if b else None
    salida = []
    for p in VALORES_ENERGIA:
        r = acc.get(p)
        if not r:
            continue
        basta = r["minutos"] >= MIN_COMPARAR
        salida.append({"perfil": p, "minutos": r["minutos"],
                       "vatios": dato(round(sum(r["vatios"]) / len(r["vatios"]), 1) if basta and r["vatios"] else None,
                                      "calculado"),
                       "descarga_pct_h": dato(round(r["caida"] * 3600.0 / r["tramo"], 1)
                                              if basta and r["tramo"] >= MIN_DESCARGA and r["caida"] > 0 else None,
                                              "calculado")})
    return salida


def reglas_energia(reglas):
    """Las reglas que reaccionan a la energia (eventos o condiciones de bateria y cargador)."""
    salida = []
    for r in reglas:
        evento = (r.get("cuando") or {}).get("evento")
        condiciones = [c.get("condicion") for c in r.get("si") or []]
        if evento in EVENTOS_ENERGIA or any(c in CONDICIONES_ENERGIA for c in condiciones):
            salida.append({"id": r.get("id"), "nombre": r.get("nombre"), "activa": r.get("activa"),
                           "evento": evento, "acciones": [a.get("accion") for a in r.get("hacer") or []]})
    return salida
