# jaime0_servicio.actualizaciones: estado de las actualizaciones para UPDATES (evolucion, fase 4).
# Junta dos fuentes que ya existen y no las sustituye:
#   - jaime0-update (componentes propios de ZYRON): "estado --json" sin red y "comprobar --json"
#     con red;
#   - actualizaciones (paquetes de Debian con apt): el archivo que deja su ultima comprobacion
#     (~/.local/state/jaime0/actualizaciones.json); comprobar de nuevo lanza "actualizaciones
#     comprobar --silencioso".
# Nunca instala nada: instalar y revertir piden autorizacion en una terminal (jaime0-update).
# Depende de: base y sistema (programa_hermano).

import json
import os
import subprocess
import threading
import time

from .base import VERSION_DATOS, registrar
from .sistema import programa_hermano

__all__ = [
    "LIMITE_ESTADO_UPDATE", "LIMITE_COMPROBAR_UPDATE", "LIMITE_COMPROBAR_APT", "archivo_debian",
    "leer_debian", "ejecutar_json", "estado_actualizaciones", "Comprobador",
]

LIMITE_ESTADO_UPDATE = 20           # s: "jaime0-update estado --json" no usa la red
LIMITE_COMPROBAR_UPDATE = 300       # s: descarga y verifica el manifiesto firmado
LIMITE_COMPROBAR_APT = 300          # s: apt list --upgradable y debsecan


def archivo_debian():
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "jaime0", "actualizaciones.json")


def leer_debian():
    """{"paquetes", "seguridad": [...], "comprobado"} de la ultima comprobacion de apt, o None si
    aun no se ha hecho ninguna (no se inventa un "al dia")."""
    try:
        with open(archivo_debian(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("paquetes"), int):
        return None
    seguridad = d.get("seguridad") if isinstance(d.get("seguridad"), list) else []
    return {"paquetes": d["paquetes"], "seguridad": [str(p) for p in seguridad][:200],
            "comprobado": d.get("comprobado")}


def ejecutar_json(orden, limite, ejecutar=None):
    """(doc, error): ejecuta un programa de ZYRON con salida JSON de una linea."""
    ejecutar = ejecutar or subprocess.run
    try:
        r = ejecutar(orden, capture_output=True, text=True, timeout=limite, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return None, f"{os.path.basename(orden[0])} no respondió en {limite} s"
    except OSError as e:
        return None, f"no se pudo ejecutar {os.path.basename(orden[0])}: {e.strerror or e}"
    lineas = [l for l in (r.stdout or "").splitlines() if l.strip()]
    try:
        doc = json.loads(lineas[-1]) if lineas else None
    except ValueError:
        doc = None
    if not isinstance(doc, dict):
        err = (r.stderr or "").strip().splitlines()
        return None, (err[-1] if err else f"{os.path.basename(orden[0])} no devolvió datos (código {r.returncode})")
    return doc, None


def estado_actualizaciones(ejecutar=None, buscar=programa_hermano):
    """Documento de UPDATES, sin red. jaime0 = lo que dice jaime0-update (o el motivo de que no
    se pueda saber); debian = la ultima comprobacion de apt."""
    doc = {"ok": True, "v": VERSION_DATOS, "jaime0": None, "error_jaime0": None, "debian": leer_debian()}
    programa = buscar("jaime0-update")
    if not programa:
        doc["error_jaime0"] = ("Este sistema no tiene jaime0-update (las ISO 0.3 y 0.4 no lo traían): "
                               "ver docs/actualizaciones.md para instalarlo a mano")
        return doc
    estado, error = ejecutar_json([programa, "estado", "--json"], LIMITE_ESTADO_UPDATE, ejecutar)
    if error or not estado.get("ok", True):
        doc["error_jaime0"] = error or estado.get("error") or "jaime0-update no pudo leer su estado"
    else:
        doc["jaime0"] = estado
    return doc


class Comprobador:
    """Comprobacion con red (jaime0-update y apt), una a la vez y en su propio hilo: tarda
    (descarga, apt, debsecan) y no debe ocupar el hilo de efectos. comprobar(fin) devuelve False
    si ya hay una en marcha; fin(doc) recibe el estado nuevo (o el error) al terminar."""

    def __init__(self, ejecutar=None, buscar=programa_hermano, lanzar=None, reloj=time.time):
        self.ejecutar, self.buscar, self.reloj = ejecutar, buscar, reloj
        self.lanzar = lanzar or (lambda fn: threading.Thread(target=fn, name="jaime0-comprobar", daemon=True).start())
        self._cerrojo = threading.Lock()
        self.desde = None                   # instante de inicio de la comprobacion en curso

    def en_curso(self):
        return self.desde

    def comprobar(self, fin):
        if not self._cerrojo.acquire(blocking=False):
            return False
        self.desde = int(self.reloj())

        def trabajo():
            avisos = []
            try:
                update = self.buscar("jaime0-update")
                if update:
                    plan, error = ejecutar_json([update, "comprobar", "--json"], LIMITE_COMPROBAR_UPDATE, self.ejecutar)
                    if error or (plan and plan.get("ok") is False):
                        avisos.append("ZYRON: " + (error or plan.get("error") or "no se pudo comprobar"))
                else:
                    plan = None
                apt = self.buscar("actualizaciones")
                if apt:
                    try:
                        (self.ejecutar or subprocess.run)([apt, "comprobar", "--silencioso"], capture_output=True,
                                                          text=True, timeout=LIMITE_COMPROBAR_APT, stdin=subprocess.DEVNULL)
                    except (OSError, subprocess.TimeoutExpired) as e:
                        avisos.append(f"Debian: no se pudo comprobar ({e})")
                doc = estado_actualizaciones(self.ejecutar, self.buscar)
                doc["plan"] = plan.get("plan") if isinstance(plan, dict) else None
                doc["avisos"] = avisos
            except Exception as e:
                registrar(f"error al comprobar actualizaciones: {e}")
                doc = {"ok": False, "error": "error interno al comprobar"}
            finally:
                self.desde = None
                self._cerrojo.release()
            fin(doc)

        self.lanzar(trabajo)
        return True
