# jaime0_servicio.hardware: capa de deteccion de hardware (evolucion, fase 8). Dice, para cada
# componente, si ZYRON puede usarlo en ESTE equipo, para que las vistas se adapten y nunca se
# muestre un dato de algo que no existe. Estados:
#   compatible     esta y ZYRON lo lee o lo usa
#   detectado      esta, pero falta algo para usarlo (controlador, modulo, herramienta)
#   no_disponible  este equipo no lo tiene
#   error_lectura  esta, pero leerlo ha fallado
# Solo lee sysfs y /proc (y comprueba si existen programas): nunca despierta la NVIDIA ni
# ejecuta nada. Un fallo inesperado en un componente da error_lectura en ese componente.
# Depende de: base, medicion y energia.

import glob
import os
import shutil

from .base import ruta, registrar
from .medicion import leer_ruta, leer_entero
from .energia import carpeta_bateria, FABRICANTES, VIRTUALES

__all__ = [
    "ESTADOS_HARDWARE", "componente", "_sensor", "detectar_bateria", "detectar_cargador", "detectar_graficas",
    "leer_hwmon", "detectar_sensores", "detectar_retroiluminacion", "detectar_red_inalambrica",
    "detectar_bluetooth", "detectar_suspension", "detectar_perfiles_energia", "detectar_smart",
    "detectar_hardware",
]

ESTADOS_HARDWARE = ("compatible", "detectado", "no_disponible", "error_lectura")


def componente(ident, nombre, estado, detalle, valores=None):
    return {"id": ident, "nombre": nombre, "estado": estado, "detalle": detalle, "valores": valores or []}


def detectar_bateria():
    d = carpeta_bateria()
    if d is None:
        return componente("bateria", "Batería", "no_disponible", "Sin batería en /sys/class/power_supply")
    nivel = leer_entero(os.path.join(d, "capacity"))
    if nivel is None:
        return componente("bateria", "Batería", "error_lectura", f"{os.path.basename(d)} no da su nivel (capacity)")
    tiene = lambda *n: [x for x in n if os.path.exists(os.path.join(d, x))]
    datos = []
    if tiene("energy_full_design", "charge_full_design"):
        datos.append("capacidad de diseño")
    if tiene("power_now", "current_now"):
        datos.append("consumo")
    if tiene("cycle_count"):
        datos.append("ciclos")
    if tiene("charge_control_end_threshold"):
        datos.append("límite de carga")
    return componente("bateria", "Batería", "compatible",
                      f"{os.path.basename(d)} al {nivel} %; da: " + (", ".join(datos) or "solo el nivel"))


def detectar_cargador():
    hay = [d for d in sorted(glob.glob(ruta("sys", "class", "power_supply", "*")))
           if leer_ruta(os.path.join(d, "type")) == "Mains"]
    if not hay:
        return componente("cargador", "Cargador", "no_disponible", "Sin fuente de alimentación de red (Mains)")
    estado = leer_ruta(os.path.join(hay[0], "online"))
    if estado not in ("0", "1"):
        return componente("cargador", "Cargador", "error_lectura", f"{os.path.basename(hay[0])} no dice si está conectado")
    return componente("cargador", "Cargador", "compatible", "Conectado" if estado == "1" else "Desconectado")


def detectar_graficas():
    """Integrada y dedicada por separado: nunca se supone que haya NVIDIA."""
    integradas, dedicadas = [], []
    for dev in sorted(glob.glob(ruta("sys", "bus", "pci", "devices", "*"))):
        if not (leer_ruta(os.path.join(dev, "class")) or "").startswith("0x03"):
            continue
        fab = leer_ruta(os.path.join(dev, "vendor")) or ""
        drv = os.path.join(dev, "driver")
        driver = os.path.basename(os.path.realpath(drv)) if os.path.exists(drv) else None
        g = {"fab": fab, "nombre": FABRICANTES.get(fab, fab or "?"), "driver": driver,
             "principal": leer_ruta(os.path.join(dev, "boot_vga")) == "1"}
        (dedicadas if fab == "0x10de" or (fab not in ("0x8086",) + VIRTUALES and not g["principal"]) else integradas).append(g)
    salida = []
    if not integradas:
        salida.append(componente("gpu_integrada", "Gráfica integrada", "no_disponible", "No hay gráfica integrada"))
    else:
        g = integradas[0]
        virtual = g["fab"] in VIRTUALES
        salida.append(componente(
            "gpu_integrada", "Gráfica virtual" if virtual else "Gráfica integrada",
            "compatible" if g["driver"] else "detectado",
            f"{g['nombre']} con {g['driver']}" if g["driver"] else f"{g['nombre']} sin controlador: el escritorio va por software"))
    if not dedicadas:
        salida.append(componente("gpu_dedicada", "Gráfica dedicada", "no_disponible",
                                 "Solo hay gráfica integrada: todo funciona igual, sin prime-run"))
        return salida
    g = dedicadas[0]
    if g["fab"] != "0x10de":
        salida.append(componente("gpu_dedicada", "Gráfica dedicada", "compatible" if g["driver"] else "detectado",
                                 f"{g['nombre']} con {g['driver'] or 'ningún controlador'}"))
    elif g["driver"] == "nvidia" and os.path.exists(ruta("sys", "module", "nvidia")):
        smi = "nvidia-smi disponible" if shutil.which("nvidia-smi") else "falta nvidia-smi (sin consumo ni temperatura)"
        salida.append(componente("gpu_dedicada", "NVIDIA", "compatible",
                                 f"Controlador {leer_ruta(ruta('sys', 'module', 'nvidia', 'version')) or '?'}, PRIME offload; {smi}"))
    elif g["driver"] == "nouveau":
        salida.append(componente("gpu_dedicada", "NVIDIA", "detectado",
                                 "Con nouveau: sin prime-run de NVIDIA ni nvidia-smi (ver jaime0-nvidia)"))
    else:
        salida.append(componente("gpu_dedicada", "NVIDIA", "detectado",
                                 "Sin controlador cargado (en vivo, sin firmar o Secure Boot): ver jaime0-nvidia"))
    return salida


def leer_hwmon(prefijo, divisor):
    """[(id, valor)] de los hwmon/<prefijo>*_input y cuantos no se pudieron leer."""
    valores, fallos = [], 0
    for entrada in sorted(glob.glob(ruta("sys", "class", "hwmon", "hwmon*", prefijo + "*_input"))):
        carpeta, archivo = os.path.split(entrada)
        n = archivo[len(prefijo):-len("_input")]
        v = leer_entero(entrada)
        if v is None:
            fallos += 1
            continue
        nombre = leer_ruta(os.path.join(carpeta, "name")) or os.path.basename(carpeta)
        etiqueta = leer_ruta(os.path.join(carpeta, f"{prefijo}{n}_label")) or f"{prefijo}{n}"
        valores.append((f"{nombre}/{etiqueta}", round(v / divisor, 2)))
    return valores, fallos


def _sensor(ident, nombre, valores, fallos, unidad, vacio):
    if valores:
        return componente(ident, nombre, "compatible",
                          f"{len(valores)} sensor(es)" + (f"; {fallos} sin lectura" if fallos else ""),
                          [{"id": i, "valor": v, "unidad": unidad} for i, v in valores])
    if fallos:
        return componente(ident, nombre, "error_lectura", f"{fallos} sensor(es) presentes que no se pudieron leer")
    return componente(ident, nombre, "no_disponible", vacio)


def detectar_sensores():
    temps, fallos_t = leer_hwmon("temp", 1000)
    cpu = [(i, v) for i, v in temps if i.split("/")[0] in ("coretemp", "k10temp", "zenpower", "cpu_thermal")]
    gpu = [(i, v) for i, v in temps if i.split("/")[0] in ("amdgpu", "radeon", "nouveau", "i915", "xe")]
    otros = [(i, v) for i, v in temps if (i, v) not in cpu and (i, v) not in gpu]
    salida = [
        _sensor("temp_cpu", "Temperatura de la CPU", cpu, fallos_t if not cpu else 0, "°C",
                "Sin sensor de CPU (coretemp o k10temp): normal en una máquina virtual"),
    ]
    nvidia = os.path.exists(ruta("sys", "module", "nvidia")) and shutil.which("nvidia-smi")
    if gpu:
        salida.append(_sensor("temp_gpu", "Temperatura de la GPU", gpu, 0, "°C", ""))
    elif nvidia:
        salida.append(componente("temp_gpu", "Temperatura de la GPU", "compatible",
                                 "NVIDIA con nvidia-smi: solo mientras está despierta (leerla dormida la despertaría)"))
    else:
        salida.append(componente("temp_gpu", "Temperatura de la GPU", "no_disponible", "Ninguna gráfica da su temperatura"))
    if otros:
        salida.append(_sensor("temp_otros", "Otras temperaturas", otros, 0, "°C", ""))
    ventiladores, fallos_f = leer_hwmon("fan", 1)
    salida.append(_sensor("ventiladores", "Ventiladores", ventiladores, fallos_f, "RPM",
                          "El firmware no expone los ventiladores (habitual en portátiles Acer)"))
    voltajes, fallos_v = leer_hwmon("in", 1000)
    salida.append(_sensor("voltajes", "Voltajes", voltajes, fallos_v, "V", "Sin sensores de voltaje en hwmon"))
    return salida


def detectar_retroiluminacion():
    pantallas = sorted(glob.glob(ruta("sys", "class", "backlight", "*")))
    if not pantallas:
        return componente("brillo", "Brillo de pantalla", "no_disponible", "Sin control de brillo (pantalla externa o VM)")
    actual = leer_entero(os.path.join(pantallas[0], "brightness"))
    maximo = leer_entero(os.path.join(pantallas[0], "max_brightness"))
    if actual is None or not maximo:
        return componente("brillo", "Brillo de pantalla", "error_lectura", f"{os.path.basename(pantallas[0])} no da su brillo")
    herramienta = "" if shutil.which("brightnessctl") else "; falta brightnessctl para cambiarlo"
    return componente("brillo", "Brillo de pantalla", "compatible" if not herramienta else "detectado",
                      f"{os.path.basename(pantallas[0])} al {round(100 * actual / maximo)} %{herramienta}")


def detectar_red_inalambrica():
    wifi = [n for n in sorted(glob.glob(ruta("sys", "class", "net", "*"))) if os.path.isdir(os.path.join(n, "wireless"))]
    if not wifi:
        return componente("wifi", "Wi-Fi", "no_disponible", "Sin interfaz inalámbrica")
    bloqueo = []
    for r in glob.glob(ruta("sys", "class", "rfkill", "rfkill*")):
        if leer_ruta(os.path.join(r, "type")) == "wlan" and leer_ruta(os.path.join(r, "hard")) == "1":
            bloqueo.append("bloqueada por el interruptor o la BIOS")
    nombre = os.path.basename(wifi[0])
    if bloqueo:
        return componente("wifi", "Wi-Fi", "detectado", f"{nombre} " + bloqueo[0])
    return componente("wifi", "Wi-Fi", "compatible", nombre)


def detectar_bluetooth():
    hci = sorted(glob.glob(ruta("sys", "class", "bluetooth", "hci*")))
    if not hci:
        return componente("bluetooth", "Bluetooth", "no_disponible", "Sin adaptador Bluetooth")
    return componente("bluetooth", "Bluetooth", "compatible" if shutil.which("bluetoothctl") else "detectado",
                      os.path.basename(hci[0]) + ("" if shutil.which("bluetoothctl") else "; falta bluez"))


def detectar_suspension():
    estados = leer_ruta(ruta("sys", "power", "state"))
    if estados is None:
        return componente("suspension", "Suspensión", "error_lectura", "No se pudo leer /sys/power/state")
    if "mem" not in estados.split():
        return componente("suspension", "Suspensión", "no_disponible", "El equipo no admite suspender en RAM")
    modo = next((m.strip("[]") for m in (leer_ruta(ruta("sys", "power", "mem_sleep")) or "").split() if m.startswith("[")), None)
    return componente("suspension", "Suspensión", "compatible", f"Modo {modo or 'desconocido'}")


def detectar_perfiles_energia(energia):
    """energia: perfil activo de power-profiles-daemon (lo que ve el servicio) o None."""
    if energia:
        return componente("perfiles_energia", "Perfiles de energía", "compatible", f"power-profiles-daemon: {energia}")
    if shutil.which("powerprofilesctl"):
        return componente("perfiles_energia", "Perfiles de energía", "detectado",
                          "power-profiles-daemon instalado pero sin responder (¿servicio parado?)")
    return componente("perfiles_energia", "Perfiles de energía", "no_disponible", "Sin power-profiles-daemon")


def detectar_smart(smart):
    """smart: lo que consulta el servicio a UDisks2 (lista o None)."""
    if smart is None:
        return componente("smart", "Salud del disco (SMART)", "no_disponible",
                          "UDisks2 no informa de SMART (disco virtual o sin soporte)")
    if not smart:
        return componente("smart", "Salud del disco (SMART)", "no_disponible", "Ningún disco da datos SMART")
    return componente("smart", "Salud del disco (SMART)", "compatible", f"{len(smart)} disco(s) con SMART")


def detectar_hardware(energia=None, smart=None):
    """Todos los componentes, en orden. Nunca lanza: un fallo es error_lectura de ese componente."""
    pasos = (("bateria", "Batería", lambda: [detectar_bateria()]), ("cargador", "Cargador", lambda: [detectar_cargador()]),
             ("graficas", "Gráficas", detectar_graficas), ("sensores", "Sensores", detectar_sensores),
             ("brillo", "Brillo de pantalla", lambda: [detectar_retroiluminacion()]),
             ("wifi", "Wi-Fi", lambda: [detectar_red_inalambrica()]), ("bluetooth", "Bluetooth", lambda: [detectar_bluetooth()]),
             ("suspension", "Suspensión", lambda: [detectar_suspension()]),
             ("perfiles_energia", "Perfiles de energía", lambda: [detectar_perfiles_energia(energia)]),
             ("smart", "Salud del disco (SMART)", lambda: [detectar_smart(smart)]))
    salida = []
    for ident, nombre, paso in pasos:
        try:
            salida += paso()
        except Exception as e:
            registrar(f"error al detectar {ident}: {e}")
            salida.append(componente(ident, nombre, "error_lectura", f"Fallo al leerlo: {type(e).__name__}"))
    cuenta = {e: sum(1 for c in salida if c["estado"] == e) for e in ESTADOS_HARDWARE}
    return {"ok": True, "componentes": salida, "cuenta": cuenta}
