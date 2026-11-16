# jaime0_servicio.sistema: lo que habla con el resto del sistema: SMART (udisks2), umbrales de
# jaime0-ajustes, programa_hermano, D-Bus con Gio (_gi, _llamar, consultas y vigilancias), el aviso
# a la barra (avisar_barra) y la firma/socket de Hyprland. Depende de: base.

import functools
import glob
import json
import os
import shutil
import subprocess
import sys
import traceback

from .base import (
    SENAL_BARRA, UMBRALES, OPCIONES_NOTIFICAR, AJUSTES_UMBRALES, modo_prueba, registrar
)

__all__ = [
    "UDISKS", "IFACE_DRIVE", "IFACE_ATA", "IFACE_NVME", "AVISOS_NVME", "kelvin_a_celsius",
    "parsear_smart", "CARPETA_PROGRAMAS", "programa_hermano", "umbrales_desde_ajustes",
    "leer_ajustes", "cargar_umbrales", "SERVICIOS_IMPORTANTES", "parsear_show", "estado_unidades", "_gi",
    "SYSTEMD", "PPD", "_llamar", "consultar_fallidas", "consultar_unidad_activa",
    "vigilar_perfil", "consultar_smart", "vigilar_suspension", "vigilar_archivos",
    "avisar_barra", "ruta_socket2", "firma_hyprland", "entorno_hyprland"
]


# ---------------------------------------------------------------------------
# SMART (udisks2) y umbrales (jaime0-ajustes)
# ---------------------------------------------------------------------------

UDISKS = ("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2")
IFACE_DRIVE = "org.freedesktop.UDisks2.Drive"
IFACE_ATA = "org.freedesktop.UDisks2.Drive.Ata"
IFACE_NVME = "org.freedesktop.UDisks2.NVMe.Controller"
AVISOS_NVME = {"spare": "Espacio de reserva por debajo del umbral",
               "temperature": "Temperatura fuera del rango seguro",
               "degraded": "Fiabilidad del disco degradada",
               "readonly": "El disco ha pasado a solo lectura",
               "volatile_memory": "Fallo de la memoria volátil del disco"}


def kelvin_a_celsius(k):
    try:
        k = float(k)
    except (TypeError, ValueError):
        return None
    return round(k - 273.15, 1) if k > 0 else None


def parsear_smart(objetos):
    """Lista de {"disco","tipo","estado","temperatura","horas","avisos"} a partir del
    resultado de GetManagedObjects ({ruta: {interfaz: {propiedad: valor}}}). Solo propiedades
    ya publicadas por udisks2: no se llama a SmartUpdate (necesitaria permisos)."""
    discos = []
    for ifaces in (objetos or {}).values():
        drive = ifaces.get(IFACE_DRIVE)
        nvme, ata = ifaces.get(IFACE_NVME), ifaces.get(IFACE_ATA)
        if drive is None or (nvme is None and ata is None):
            continue
        # Lectores de CD/DVD: udisks2 los publica como Drive.Ata, pero no son discos.
        compat = [str(c) for c in (drive.get("MediaCompatibility") or [])]
        if drive.get("Optical") or any(c.startswith("optical") for c in compat):
            continue
        modelo = str(drive.get("Model") or "").strip() or str(drive.get("Id") or "disco")
        if nvme is not None:
            avisos = [AVISOS_NVME.get(a, str(a)) for a in (nvme.get("SmartCriticalWarning") or [])]
            leido = bool(nvme.get("SmartUpdated"))
            estado = "FALLO" if avisos else ("OK" if leido else "N/D")
            horas = nvme.get("SmartPowerOnHours")
            discos.append({"disco": modelo, "tipo": "nvme", "estado": estado,
                           "temperatura": kelvin_a_celsius(nvme.get("SmartTemperature")) if leido else None,
                           "horas": int(horas) if leido and horas is not None else None, "avisos": avisos})
        else:
            leido = bool(ata.get("SmartUpdated"))
            avisos = []
            if ata.get("SmartFailing"):
                estado = "FALLO"
                avisos.append("El disco informa de un fallo inminente (SMART)")
            elif not ata.get("SmartSupported") or not ata.get("SmartEnabled"):
                estado = "N/D"
            else:
                estado = "OK" if leido else "N/D"
            segundos = ata.get("SmartPowerOnSeconds")
            discos.append({"disco": modelo, "tipo": "ata", "estado": estado,
                           "temperatura": kelvin_a_celsius(ata.get("SmartTemperature")) if leido else None,
                           "horas": int(segundos // 3600) if leido and segundos else None, "avisos": avisos})
    return sorted(discos, key=lambda d: d["disco"])


# usr/local/bin visto desde usr/local/lib/jaime0/jaime0_servicio (antes era la carpeta del propio script)
CARPETA_PROGRAMAS = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                  "..", "..", "..", "bin"))


def programa_hermano(nombre):
    """Otro programa de Jaime0: junto al lanzador jaime0-servicio o en PATH. Este modulo vive en
    usr/local/lib/jaime0/jaime0_servicio y los programas en usr/local/bin (en el repositorio y
    en el sistema instalado)."""
    junto = os.path.join(CARPETA_PROGRAMAS, nombre)
    return junto if os.path.exists(junto) else shutil.which(nombre)


def umbrales_desde_ajustes(doc):
    """UMBRALES con los valores de 'jaime0-ajustes ver --json'. Si algun par es incoherente
    (editado a mano) se queda con los de fabrica de ese par."""
    u = dict(UMBRALES)
    if not isinstance(doc, dict):
        return u
    leidos = {}
    for a in doc.get("ajustes") or []:
        if isinstance(a, dict) and a.get("clave") in AJUSTES_UMBRALES:
            try:
                leidos[AJUSTES_UMBRALES[a["clave"]]] = int(a["valor"])
            except (KeyError, TypeError, ValueError):
                pass
    for menor, mayor in (("temp_aviso", "temp_critico"), ("disco_aviso", "disco_critico"),
                         ("bateria_critico", "bateria_aviso")):
        if menor in leidos and mayor in leidos and not leidos[menor] < leidos[mayor]:
            del leidos[menor], leidos[mayor]
    for k, v in leidos.items():
        u[k] = float(v) if k.startswith(("temp", "disco")) else v
    for a in doc.get("ajustes") or []:
        if isinstance(a, dict) and a.get("clave") == "cc_notificar" and a.get("valor") in OPCIONES_NOTIFICAR:
            u["notificar"] = a["valor"]
    return u


# Servicios que SYSTEM ensena (nombre, unidad, de usuario). Uno que no esta instalado sale como
# tal, no como fallo.
SERVICIOS_IMPORTANTES = (
    ("Red", "NetworkManager.service", False),
    ("Energía", "power-profiles-daemon.service", False),
    ("Cortafuegos", "ufw.service", False),
    ("Bluetooth", "bluetooth.service", False),
    ("Sonido", "pipewire.service", True),
)


def parsear_show(texto):
    """Bloques de 'systemctl show -p Id -p LoadState -p ActiveState u1 u2...' -> {Id: estado}."""
    estados = {}
    for bloque in (texto or "").split("\n\n"):
        d = dict(l.split("=", 1) for l in bloque.splitlines() if "=" in l)
        if not d.get("Id"):
            continue
        if d.get("LoadState") == "not-found":
            estado = "no instalado"
        elif d.get("ActiveState") == "active":
            estado = "activo"
        elif d.get("ActiveState") == "failed":
            estado = "fallido"
        elif d.get("ActiveState") in ("activating", "reloading"):
            estado = "arrancando"
        elif d.get("ActiveState"):
            estado = "inactivo"
        else:
            estado = "desconocido"
        estados[d["Id"]] = estado
    return estados


def estado_unidades(servicios=SERVICIOS_IMPORTANTES, ejecutar=None):
    """Estado de cada servicio con una llamada a systemctl por ambito (sistema y usuario).
    Lo que no se pudo consultar queda como "desconocido"."""
    ejecutar = ejecutar or subprocess.run
    estados = {}
    for usuario in (False, True):
        unidades = [u for _, u, de_usuario in servicios if de_usuario == usuario]
        if not unidades:
            continue
        orden = ["systemctl"] + (["--user"] if usuario else []) + ["show", "-p", "Id", "-p", "LoadState",
                                                                   "-p", "ActiveState"] + unidades
        try:
            r = ejecutar(orden, capture_output=True, text=True, timeout=5)
            estados.update(parsear_show(r.stdout))
        except (OSError, subprocess.TimeoutExpired):
            pass
    return [{"nombre": n, "unidad": u, "usuario": de_usuario, "estado": estados.get(u, "desconocido")}
            for n, u, de_usuario in servicios]


def leer_ajustes(ejecutar=None):
    """'jaime0-ajustes ver --json' (subproceso con timeout de 5 s), o None si falla."""
    ejecutar = ejecutar or subprocess.run
    try:
        programa = programa_hermano("jaime0-ajustes")
        if not programa:
            return None
        r = ejecutar([sys.executable, "-I", programa, "ver", "--json"],
                     capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def cargar_umbrales(ejecutar=None):
    """Umbrales de jaime0-ajustes o los de fabrica si falla."""
    return umbrales_desde_ajustes(leer_ajustes(ejecutar))


# ---------------------------------------------------------------------------
# Bus: D-Bus con Gio (python3-gi). Importacion perezosa: sin gi el resto sigue valiendo.
# ---------------------------------------------------------------------------

def _gi():
    import gi
    gi.require_version("GLib", "2.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import GLib, Gio
    return GLib, Gio


SYSTEMD = ("org.freedesktop.systemd1", "/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager")
PPD = ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles")


def _llamar(con, destino, objeto, interfaz, metodo, params, cb):
    """Llamada asincrona; cb(resultado_desempaquetado | None)."""
    GLib, Gio = _gi()

    def listo(fuente, res, _datos):
        try:
            valor = fuente.call_finish(res).unpack()
        except Exception:
            valor = None
        try:
            cb(valor)
        except Exception:
            registrar("error en una respuesta de D-Bus:\n" + traceback.format_exc())

    con.call(destino, objeto, interfaz, metodo, params, None, Gio.DBusCallFlags.NONE, 3000, None, listo, None)


def consultar_fallidas(cb):
    """Unidades en estado failed del bus de sistema y del de sesion: cb(lista | None)."""
    GLib, Gio = _gi()
    resultados = {}

    def fin(tipo, valor):
        resultados[tipo] = None if valor is None else [u[0] for u in valor[0]]
        if len(resultados) == 2:
            listas = [r for r in resultados.values() if r is not None]
            cb(sorted(set(sum(listas, []))) if listas else None)

    for tipo in (Gio.BusType.SYSTEM, Gio.BusType.SESSION):
        try:
            con = Gio.bus_get_sync(tipo, None)
        except Exception:
            fin(tipo, None)
            continue
        _llamar(con, SYSTEMD[0], SYSTEMD[1], SYSTEMD[2], "ListUnitsFiltered",
                GLib.Variant("(as)", (["failed"],)), functools.partial(fin, tipo))


def consultar_unidad_activa(unidad, cb):
    """ActiveState == 'active' de una unidad del bus de sistema: cb(True|False|None)."""
    GLib, Gio = _gi()
    try:
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception:
        cb(None)
        return

    def tiene_objeto(valor):
        if not valor:
            cb(None)
            return
        _llamar(con, SYSTEMD[0], valor[0], "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", ("org.freedesktop.systemd1.Unit", "ActiveState")),
                lambda v: cb(None if not v else v[0] == "active"))

    _llamar(con, SYSTEMD[0], SYSTEMD[1], SYSTEMD[2], "LoadUnit", GLib.Variant("(s)", (unidad,)), tiene_objeto)


def vigilar_perfil(cb):
    """Perfil activo de power-profiles-daemon: cb(valor | None) ahora y en cada cambio."""
    GLib, Gio = _gi()
    try:
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception:
        cb(None)
        return None

    def cambio(_con, _emisor, _objeto, _iface, _senal, params, _datos):
        try:
            _interfaz, cambiadas, _inval = params.unpack()
            if "ActiveProfile" in cambiadas:
                cb(cambiadas["ActiveProfile"])
        except Exception:
            registrar("error en PropertiesChanged:\n" + traceback.format_exc())

    suscripcion = con.signal_subscribe(PPD[0], "org.freedesktop.DBus.Properties", "PropertiesChanged",
                                       PPD[1], None, Gio.DBusSignalFlags.NONE, cambio, None)
    _llamar(con, PPD[0], PPD[1], "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (PPD[0], "ActiveProfile")), lambda v: cb(v[0] if v else None))
    return con, suscripcion


def consultar_smart(cb):
    """SMART de todos los discos por udisks2 (asincrono, solo lectura): cb(lista | None).
    None si udisks2 no responde."""
    GLib, Gio = _gi()
    try:
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception:
        cb(None)
        return

    def respuesta(valor):
        try:
            cb(None if valor is None else parsear_smart(valor[0]))
        except Exception:
            registrar("error al leer SMART:\n" + traceback.format_exc())
            cb(None)

    _llamar(con, UDISKS[0], UDISKS[1], "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
            None, respuesta)


def vigilar_suspension(cb):
    """PrepareForSleep de logind: cb(True) antes de suspender, cb(False) al reanudar."""
    GLib, Gio = _gi()
    try:
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except Exception:
        return None

    def senal(_con, _emisor, _objeto, _iface, _senal, params, _datos):
        try:
            cb(bool(params.unpack()[0]))
        except Exception:
            registrar("error en PrepareForSleep:\n" + traceback.format_exc())

    return con, con.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                                     "PrepareForSleep", "/org/freedesktop/login1", None,
                                     Gio.DBusSignalFlags.NONE, senal, None)


def vigilar_archivos(rutas, cb):
    """Llama a cb() cuando cambia alguno de los archivos (Gio.FileMonitor). Devuelve los
    monitores, que hay que conservar vivos."""
    GLib, Gio = _gi()
    monitores = []
    for r in rutas:
        try:
            m = Gio.File.new_for_path(r).monitor_file(Gio.FileMonitorFlags.WATCH_MOVES, None)
            m.connect("changed", lambda *_a: cb())
            monitores.append(m)
        except Exception:
            registrar(f"no se pudo vigilar {r}:\n" + traceback.format_exc())
    return monitores


def avisar_barra():
    """Pide a Waybar que relea el indicador (RTMIN+11). Solo si lleva unos segundos en
    marcha: al arrancar aun no atiende la senal y una senal RTMIN sin atender la cerraria."""
    if modo_prueba() or not shutil.which("pgrep"):
        return
    try:
        r = subprocess.run(["pgrep", "-x", "-u", str(os.getuid()), "waybar"],
                           capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return
    try:
        with open("/proc/uptime", encoding="ascii") as f:
            uptime = float(f.read().split()[0])
        for pid in r.stdout.split():
            with open(f"/proc/{pid}/stat", encoding="ascii") as f:
                inicio = int(f.read().rsplit(")", 1)[1].split()[19]) / os.sysconf("SC_CLK_TCK")
            if uptime - inicio < 3:
                return
    except (OSError, ValueError, IndexError):
        return
    if r.stdout.split():
        try:
            subprocess.run(["pkill", f"-RTMIN+{SENAL_BARRA}", "-x", "-u", str(os.getuid()), "waybar"], timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass




# Hyprland: socket de eventos y firma de la instancia viva (los usan los perfiles y las reglas)

def ruta_socket2(entorno=None, listar=glob.glob, existe=os.path.exists):
    """Socket de eventos de Hyprland: el de HYPRLAND_INSTANCE_SIGNATURE si existe; si no (Hyprland
    reiniciado: la firma del entorno es la vieja), el mas reciente de $XDG_RUNTIME_DIR/hypr/*.
    None si no hay ninguno."""
    entorno = os.environ if entorno is None else entorno
    base = entorno.get("XDG_RUNTIME_DIR")
    if not base:
        return None
    firma = entorno.get("HYPRLAND_INSTANCE_SIGNATURE")
    if firma:
        p = os.path.join(base, "hypr", firma, ".socket2.sock")
        if existe(p):
            return p
    candidatos = [p for p in listar(os.path.join(base, "hypr", "*", ".socket2.sock")) if existe(p)]
    if not candidatos:
        return None

    def mtime(p):
        try:
            return os.stat(p).st_mtime
        except OSError:
            return 0
    return max(candidatos, key=mtime)


def firma_hyprland(entorno=None, **k):
    """Firma de la instancia de Hyprland, resuelta en cada uso: la del socket vivo (ruta_socket2)
    y, si no hay ninguno, la del entorno. None si no hay Hyprland. La del entorno del arranque
    puede estar vacia (el servicio arranca a la vez que Hyprland) o ser la de una sesion anterior."""
    entorno = os.environ if entorno is None else entorno
    p = ruta_socket2(entorno, **k)
    if p:
        return os.path.basename(os.path.dirname(p))
    return entorno.get("HYPRLAND_INSTANCE_SIGNATURE") or None


def entorno_hyprland(firma):
    """Entorno para lanzar hyprctl con la firma resuelta (None = el heredado)."""
    return dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=firma) if firma else None
