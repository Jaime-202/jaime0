# jaime0_servicio.medicion: lectura de /proc y /sys (CPU, RAM, presion, temperaturas,
# GPU NVIDIA, discos, bateria, procesos), el Muestreador y armar_instante. Sin subprocesos salvo
# la temperatura de NVIDIA. Depende de: base.

import glob
import os
import subprocess
import time

from .base import VERSION_DATOS, ruta

__all__ = [
    "leer", "leer_ruta", "leer_entero", "parsear_cpu_stat", "porcentaje_cpu", "frecuencia_mhz",
    "leer_ram", "presion_memoria", "leer_temperaturas", "temperatura_cpu", "dispositivo_nvidia",
    "estado_nvidia", "nvidia_activa", "temperatura_nvidia", "uso_disco", "puntos_de_disco",
    "parsear_diskstats", "io_disco", "dispositivo_raiz", "ESTADOS_BATERIA", "leer_bateria",
    "leer_cargador", "leer_uptime", "tics_por_segundo", "leer_procesos", "ram_proceso",
    "procesos_top", "carga_media", "tamano_pagina", "ESTADOS_PROCESO", "lista_procesos", "detalle_proceso", "parsear_net_dev", "io_red",
    "Muestreador", "armar_instante"
]


# ---------------------------------------------------------------------------
# Medicion: solo lee /proc y /sys, sin subprocesos
# ---------------------------------------------------------------------------

def leer(*partes):
    try:
        with open(ruta(*partes), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def leer_ruta(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return None


def leer_entero(p):
    t = leer_ruta(p)
    try:
        return int(t) if t is not None else None
    except ValueError:
        return None


def parsear_cpu_stat(texto):
    """Devuelve ((inactivo, total), {n: (inactivo, total)}) en jiffies acumulados."""
    total, nucleos = None, {}
    for linea in (texto or "").splitlines():
        if not linea.startswith("cpu"):
            continue
        c = linea.split()
        try:
            v = [int(x) for x in c[1:]]
        except ValueError:
            continue
        if len(v) < 4:
            continue
        par = (v[3] + (v[4] if len(v) > 4 else 0), sum(v[:8]))  # inactivo+iowait; sin guest
        if c[0] == "cpu":
            total = par
        elif c[0][3:].isdigit():
            nucleos[int(c[0][3:])] = par
    return total, nucleos


def porcentaje_cpu(antes, ahora):
    """% de uso entre dos lecturas (inactivo, total); None si no hay diferencia."""
    if not antes or not ahora:
        return None
    dt = ahora[1] - antes[1]
    if dt <= 0:
        return None
    uso = 100.0 * (1.0 - (ahora[0] - antes[0]) / dt)
    return round(min(100.0, max(0.0, uso)), 1)


def frecuencia_mhz(n):
    kh = leer_entero(ruta("sys", "devices", "system", "cpu", f"cpu{n}", "cpufreq", "scaling_cur_freq"))
    return None if kh is None else int(round(kh / 1000.0))


def leer_ram():
    texto = leer("proc", "meminfo")
    if texto is None:
        return None
    kb = {}
    for linea in texto.splitlines():
        partes = linea.replace(":", " ").split()
        if len(partes) >= 2 and partes[1].isdigit():
            kb[partes[0]] = int(partes[1])
    if "MemTotal" not in kb or "MemAvailable" not in kb:
        return None
    mib = lambda k: int(round(kb[k] / 1024.0))
    return {"usada": int(round((kb["MemTotal"] - kb["MemAvailable"]) / 1024.0)),
            "total": mib("MemTotal"),
            "swap": int(round((kb.get("SwapTotal", 0) - kb.get("SwapFree", 0)) / 1024.0)),
            "swap_total": mib("SwapTotal") if "SwapTotal" in kb else 0,
            "presion": presion_memoria()}


def presion_memoria():
    """avg10 de la linea 'some' de /proc/pressure/memory, o None."""
    for linea in (leer("proc", "pressure", "memory") or "").splitlines():
        c = linea.split()
        if c and c[0] == "some":
            for campo in c[1:]:
                if campo.startswith("avg10="):
                    try:
                        return float(campo[6:])
                    except ValueError:
                        return None
    return None


def leer_temperaturas():
    """Lista [{"id": "<name>/<etiqueta>", "c": grados}] de todos los hwmon."""
    salida = []
    for entrada in sorted(glob.glob(ruta("sys", "class", "hwmon", "hwmon*", "temp*_input"))):
        carpeta, archivo = os.path.split(entrada)
        n = archivo[len("temp"):-len("_input")]
        mili = leer_entero(entrada)
        if mili is None:
            continue
        nombre = leer_ruta(os.path.join(carpeta, "name")) or os.path.basename(carpeta)
        etiqueta = leer_ruta(os.path.join(carpeta, f"temp{n}_label")) or f"temp{n}"
        salida.append({"id": f"{nombre}/{etiqueta}", "c": round(mili / 1000.0, 1)})
    return salida


def temperatura_cpu(temps):
    """Package id 0 de coretemp, o Tctl de k10temp, o el maximo de coretemp; None si no hay."""
    por_id = {t["id"]: t["c"] for t in temps}
    if "coretemp/Package id 0" in por_id:
        return por_id["coretemp/Package id 0"]
    if "k10temp/Tctl" in por_id:
        return por_id["k10temp/Tctl"]
    nucleos = [t["c"] for t in temps if t["id"].startswith("coretemp/")]
    return max(nucleos) if nucleos else None


def dispositivo_nvidia():
    """Carpeta de sysfs de la primera GPU NVIDIA (clase 3D o VGA), o None."""
    for dev in sorted(glob.glob(ruta("sys", "bus", "pci", "devices", "*"))):
        if leer_ruta(os.path.join(dev, "vendor")) != "0x10de":
            continue
        clase = (leer_ruta(os.path.join(dev, "class")) or "")[:6]
        if clase in ("0x0300", "0x0302"):
            return dev
    return None


def estado_nvidia():
    """'activa' | 'suspendida' | 'sin-driver' | None (no hay GPU NVIDIA). Nunca ejecuta
    nvidia-smi: leer su temperatura despertaria la grafica."""
    dev = dispositivo_nvidia()
    if dev is None:
        return None
    if not os.path.exists(os.path.join(dev, "driver")):
        return "sin-driver"
    return "suspendida" if leer_ruta(os.path.join(dev, "power", "runtime_status")) == "suspended" else "activa"


def nvidia_activa():
    """True solo si power/runtime_status vale exactamente 'active' (y hay driver)."""
    dev = dispositivo_nvidia()
    return (dev is not None and os.path.exists(os.path.join(dev, "driver"))
            and leer_ruta(os.path.join(dev, "power", "runtime_status")) == "active")


def temperatura_nvidia(ejecutar=None):
    """Temperatura de la GPU NVIDIA con nvidia-smi, SOLO si esta activa: con la GPU
    suspendida devuelve None sin ejecutar nada (nvidia-smi la despertaria)."""
    if not nvidia_activa():
        return None
    ejecutar = ejecutar or subprocess.run
    try:
        r = ejecutar(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                     capture_output=True, text=True, timeout=3)
        if r.returncode != 0:
            return None
        return float((r.stdout or "").strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def uso_disco(punto):
    """{"punto","usado","total"} en GiB con 1 decimal, o None si no se puede leer."""
    try:
        v = os.statvfs(ruta(punto))
    except (OSError, AttributeError):
        return None
    gib = 1024.0 ** 3
    total = v.f_blocks * v.f_frsize
    return {"punto": punto, "usado": round((v.f_blocks - v.f_bfree) * v.f_frsize / gib, 1),
            "total": round(total / gib, 1)}


def puntos_de_disco():
    """'/' y, si es otro sistema de archivos (por st_dev), '/home'."""
    puntos = ["/"]
    try:
        if os.stat(ruta("home")).st_dev != os.stat(ruta()).st_dev:
            puntos.append("/home")
    except OSError:
        pass
    return puntos


def parsear_diskstats(texto):
    """{dispositivo: (sectores_leidos, sectores_escritos)}."""
    d = {}
    for linea in (texto or "").splitlines():
        c = linea.split()
        if len(c) >= 10 and c[5].isdigit() and c[9].isdigit():
            d[c[2]] = (int(c[5]), int(c[9]))
    return d


def io_disco(antes, ahora, dt):
    """(lectura, escritura) en MB/s (1 MB = 10^6 B, sectores de 512 B) o (None, None)."""
    if not antes or not ahora or dt <= 0:
        return None, None
    mb = lambda s: round(max(0, s) * 512 / 1e6 / dt, 2)
    return mb(ahora[0] - antes[0]), mb(ahora[1] - antes[1])


def dispositivo_raiz():
    """Nombre del dispositivo de bloque que contiene '/', o None si no se puede saber."""
    try:
        dev = os.stat(ruta()).st_dev
        enlace = os.path.realpath(ruta("sys", "dev", "block", f"{os.major(dev)}:{os.minor(dev)}"))
        return os.path.basename(enlace) or None
    except (OSError, AttributeError):
        return None


ESTADOS_BATERIA = {"Charging": "cargando", "Discharging": "descargando", "Full": "llena",
                   "Not charging": "sin-cargar"}


def leer_bateria():
    """Primera BAT* de tipo Battery como dict, o None si no hay bateria."""
    base = ruta("sys", "class", "power_supply")
    for d in sorted(glob.glob(os.path.join(base, "BAT*"))):
        if leer_ruta(os.path.join(d, "type")) != "Battery":
            continue
        e = lambda nombre: leer_entero(os.path.join(d, nombre))
        estado = ESTADOS_BATERIA.get(leer_ruta(os.path.join(d, "status")) or "", "desconocido")
        pot, corr, volt = e("power_now"), e("current_now"), e("voltage_now")
        vatios = None
        if pot is not None and pot > 0:
            vatios = round(pot / 1e6, 1)
        elif corr and volt:
            vatios = round(abs(corr) * volt / 1e12, 1)
        minutos = None
        if estado == "descargando" and vatios:
            if pot is not None and pot > 0 and e("energy_now") is not None:
                minutos = int(round(e("energy_now") / pot * 60))
            elif corr and e("charge_now") is not None:
                minutos = int(round(e("charge_now") / abs(corr) * 60))
        salud = None
        for lleno, diseno in (("energy_full", "energy_full_design"), ("charge_full", "charge_full_design")):
            if e(lleno) is not None and e(diseno):
                salud = round(100.0 * e(lleno) / e(diseno), 1)
                break
        return {"nivel": e("capacity"), "estado": estado, "vatios": vatios,
                "minutos_estimados": minutos, "salud": salud, "estimado": True}
    return None


def leer_cargador():
    """True/False si hay alguna fuente Mains; None si no hay ninguna."""
    hay = False
    for d in sorted(glob.glob(ruta("sys", "class", "power_supply", "*"))):
        if leer_ruta(os.path.join(d, "type")) == "Mains":
            hay = True
            if leer_ruta(os.path.join(d, "online")) == "1":
                return True
    return False if hay else None


def leer_uptime():
    try:
        return int(float((leer("proc", "uptime") or "").split()[0]))
    except (IndexError, ValueError):
        return None


def tics_por_segundo():
    try:
        return os.sysconf("SC_CLK_TCK")
    except (AttributeError, ValueError, OSError):
        return 100


def leer_procesos():
    """{pid: (tics_cpu, nombre, estado, hilos, rss_paginas)} de /proc/[pid]/stat. Tolera
    procesos que desaparecen."""
    d = {}
    for p in glob.glob(ruta("proc", "[0-9]*")):
        pid = os.path.basename(p)
        if not pid.isdigit():
            continue
        try:
            with open(os.path.join(p, "stat"), encoding="utf-8", errors="replace") as f:
                t = f.read()
            nombre = t[t.index("(") + 1:t.rindex(")")]
            c = t[t.rindex(")") + 1:].split()
            entero = lambda i: int(c[i]) if len(c) > i else None
            d[int(pid)] = (int(c[11]) + int(c[12]), nombre, c[0], entero(17), entero(21))   # utime + stime
        except (OSError, ValueError, IndexError):
            continue
    return d


def ram_proceso(pid):
    """VmRSS en MiB o None."""
    for linea in (leer("proc", str(pid), "status") or "").splitlines():
        if linea.startswith("VmRSS:"):
            try:
                return int(round(int(linea.split()[1]) / 1024.0))
            except (IndexError, ValueError):
                return None
    return None


def procesos_top(antes, ahora, dt, cuantos=5):
    """Los de mas CPU entre dos muestras (100 % = un nucleo entero)."""
    if not antes or dt <= 0:
        return None
    tics = tics_por_segundo()
    lista = []
    for pid, p in ahora.items():
        t, nombre = p[0], p[1]
        if pid in antes:
            cpu = (t - antes[pid][0]) / tics / dt * 100.0
            if cpu > 0:
                lista.append((cpu, pid, nombre))
    lista.sort(reverse=True)
    return [{"pid": pid, "nombre": nombre, "cpu": round(cpu, 1), "ram": ram_proceso(pid)}
            for cpu, pid, nombre in lista[:cuantos]]


def carga_media():
    """[1, 5, 15] minutos de /proc/loadavg (procesos ejecutandose o esperando), o None."""
    try:
        return [float(x) for x in (leer("proc", "loadavg") or "").split()[:3]] or None
    except ValueError:
        return None


def tamano_pagina():
    try:
        return os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return 4096


ESTADOS_PROCESO = {"R": "ejecutando", "S": "esperando", "D": "esperando disco", "Z": "zombi",
                   "T": "parado", "t": "parado", "I": "inactivo"}


def lista_procesos(antes, ahora, dt):
    """Todos los procesos con su CPU entre dos muestras (100 % = un nucleo), RAM en MiB (RSS),
    hilos y estado, de mas a menos CPU. Un proceso nuevo (sin muestra previa) sale con CPU None."""
    if not ahora:
        return []
    tics, pagina = tics_por_segundo(), tamano_pagina()
    salida = []
    for pid, p in ahora.items():
        t, nombre, estado, hilos, rss = (tuple(p) + (None,) * 5)[:5]
        cpu = None
        if antes and pid in antes and dt > 0:
            cpu = round(max(0.0, (t - antes[pid][0]) / tics / dt * 100.0), 1)
        salida.append({"pid": pid, "nombre": nombre, "cpu": cpu,
                       "ram": None if rss is None else round(rss * pagina / 1048576.0, 1),
                       "hilos": hilos, "estado": ESTADOS_PROCESO.get(estado, estado)})
    salida.sort(key=lambda x: (x["cpu"] if x["cpu"] is not None else -1, x["ram"] or 0), reverse=True)
    return salida


def detalle_proceso(pid):
    """Orden completa, usuario, padre, hilos, memoria e inicio de un proceso, o None si ya no
    existe. Solo lee /proc: nada se cambia."""
    status = leer("proc", str(pid), "status")
    if status is None:
        return None
    campos = {}
    for linea in status.splitlines():
        if ":" in linea:
            k, v = linea.split(":", 1)
            campos[k] = v.strip()
    orden = (leer("proc", str(pid), "cmdline") or "").replace("\x00", " ").strip()
    uid = (campos.get("Uid") or "").split()
    usuario = uid[0] if uid else None
    try:
        import pwd
        usuario = pwd.getpwuid(int(uid[0])).pw_name
    except (ImportError, KeyError, ValueError, IndexError):
        pass
    inicio = None
    stat = leer("proc", str(pid), "stat")
    if stat and ")" in stat:
        c = stat[stat.rindex(")") + 1:].split()
        try:
            arranque = leer_uptime()
            if arranque is not None:
                inicio = int(time.time() - arranque + int(c[19]) / tics_por_segundo())
        except (IndexError, ValueError):
            pass
    def numero(clave):
        primero = (campos.get(clave) or "").split()[:1]
        return int(primero[0]) if primero and primero[0].isdigit() else None

    mib = lambda kb: None if kb is None else round(kb / 1024.0, 1)
    return {"pid": int(pid), "nombre": campos.get("Name"), "orden": orden or None, "usuario": usuario,
            "padre": numero("PPid"), "hilos": numero("Threads"), "estado": campos.get("State"),
            "ram_mib": mib(numero("VmRSS")), "swap_mib": mib(numero("VmSwap")), "inicio": inicio}


def parsear_net_dev(texto):
    """{interfaz: (bytes_recibidos, bytes_enviados)} de /proc/net/dev, sin 'lo'."""
    d = {}
    for linea in (texto or "").splitlines()[2:]:
        if ":" not in linea:
            continue
        nombre, resto = linea.split(":", 1)
        c = resto.split()
        if nombre.strip() != "lo" and len(c) >= 9 and c[0].isdigit() and c[8].isdigit():
            d[nombre.strip()] = (int(c[0]), int(c[8]))
    return d


def io_red(antes, ahora, dt):
    """{"rx", "tx"} en KB/s (10^3 B) sumando las interfaces comunes, o None."""
    if not antes or not ahora or dt <= 0:
        return None
    comunes = set(antes) & set(ahora)
    if not comunes:
        return None
    kb = lambda i: round(max(0, sum(ahora[n][i] - antes[n][i] for n in comunes)) / 1000.0 / dt, 1)
    return {"rx": kb(0), "tx": kb(1)}


class Muestreador:
    """Guarda la lectura anterior para calcular los porcentajes por diferencias."""

    def __init__(self):
        self.previa = None
        self.lista = []             # todos los procesos de la ultima muestra (orden "procesos")

    def crudo(self):
        return {"mono": time.monotonic(),
                "cpu": parsear_cpu_stat(leer("proc", "stat")),
                "procs": leer_procesos(),
                "disk": parsear_diskstats(leer("proc", "diskstats")),
                "net": parsear_net_dev(leer("proc", "net", "dev"))}

    def base(self):
        self.previa = self.crudo()

    def muestrear(self, completa=True):
        """completa: calcula tambien la lista de todos los procesos (la que usa PERFORMANCE con
        el Control Center abierto). Sin ella solo se calculan los 5 que mas gastan."""
        ahora = self.crudo()
        antes, self.previa = self.previa, ahora
        dt = ahora["mono"] - antes["mono"] if antes else 0
        total_a, nuc_a = antes["cpu"] if antes else (None, {})
        total_b, nuc_b = ahora["cpu"]
        indices = sorted(nuc_b)
        mhz = [frecuencia_mhz(n) for n in indices]
        temps = leer_temperaturas()
        cpu = {"total": porcentaje_cpu(total_a, total_b),
               "nucleos": [porcentaje_cpu(nuc_a.get(n), nuc_b[n]) for n in indices] if antes else None,
               "mhz": mhz if any(m is not None for m in mhz) else None,
               "temp": temperatura_cpu(temps), "carga": carga_media()}
        dev = dispositivo_raiz()
        lectura = escritura = None
        if antes and dev:
            lectura, escritura = io_disco(antes["disk"].get(dev), ahora["disk"].get(dev), dt)
        discos = []
        for punto in puntos_de_disco():
            u = uso_disco(punto)
            if u:
                u["lectura"], u["escritura"] = (lectura, escritura) if punto == "/" else (None, None)
                discos.append(u)
        self.lista = lista_procesos(antes["procs"] if antes else None, ahora["procs"], dt) if completa else []
        return {"cpu": cpu, "ram": leer_ram(), "temp": temps,
                "red": io_red(antes.get("net") if antes else None, ahora["net"], dt),
                "gpu": {"nvidia": estado_nvidia(), "temp": None},
                "disco": discos or None, "bateria": leer_bateria(), "cargador": leer_cargador(),
                "uptime": leer_uptime(),
                "procesos": procesos_top(antes["procs"], ahora["procs"], dt) if antes else None}


def armar_instante(med, t, intervalo, fallidas=None, smart=None):
    """Instante en el formato de docs/control-center.md. 'fallidas' (lista de unidades
    systemd fallidas o None) y 'smart' (lista de discos o None) son campos extra para que
    evaluar() siga siendo puro."""
    inst = {"v": VERSION_DATOS, "t": int(t), "intervalo": intervalo}
    inst.update(med)
    inst["fallidas"] = fallidas
    inst["smart"] = smart
    inst["estado"], inst["alertas"] = "ONLINE", 0
    return inst
