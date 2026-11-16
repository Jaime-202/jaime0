# jaime0_servicio.diagnostico: DIAGNOSTICS (evolucion, fase 5). El diagnostico lo hace
# jaime0-diagnostico ("comprobar --json": interpreta problemas reales con su causa probable y
# su solucion); aqui solo se lanza, se recuerda el ultimo resultado y se resume para SYSTEM.
# Va en su propio hilo (lspci, journalctl, dkms... tardan unos segundos) y nunca repara nada:
# las reparaciones piden confirmacion en una terminal ("jaime0-diagnostico reparar ID").
# Depende de: base, sistema (programa_hermano) y actualizaciones (ejecutar_json).

import threading
import time

from .base import registrar
from .sistema import programa_hermano
from .actualizaciones import ejecutar_json

__all__ = [
    "LIMITE_DIAGNOSTICO", "LIMITE_HISTORIAL_DIAGNOSTICO", "GRAVEDADES_ALERTA", "ORDEN_GRAVEDAD", "resumen_diagnostico",
    "Diagnosticador",
]

LIMITE_DIAGNOSTICO = 120            # s: todas las comprobaciones (cada una lleva su propio limite)
LIMITE_HISTORIAL_DIAGNOSTICO = 20   # s: leer el historial no usa la red ni el sistema
GRAVEDADES_ALERTA = ("CRITICAL", "ERROR", "WARNING")
ORDEN_GRAVEDAD = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}


def resumen_diagnostico(doc):
    """Lo que necesita SYSTEM (en estado.json): cuando, cuantos de cada gravedad y los tres
    problemas mas graves. None si aun no hay ningun diagnostico."""
    if not isinstance(doc, dict) or not doc.get("ok"):
        return None
    problemas = [p for p in doc.get("problemas") or [] if isinstance(p, dict) and p.get("gravedad") in GRAVEDADES_ALERTA]
    problemas.sort(key=lambda p: ORDEN_GRAVEDAD.get(p.get("gravedad"), 9))
    return {"t": doc.get("t"), "resumen": doc.get("resumen") or {},
            "principales": [{"id": p.get("id"), "titulo": p.get("titulo"), "gravedad": p.get("gravedad")}
                            for p in problemas[:3]],
            "total": len(problemas)}


class Diagnosticador:
    """Un diagnostico a la vez, en su propio hilo. ejecutar(fin) devuelve False si ya hay uno en
    marcha; fin(doc) recibe el resultado (o el error). ultimo y desde son de solo lectura."""

    def __init__(self, ejecutar=None, buscar=programa_hermano, lanzar=None, reloj=time.time, al_terminar=None):
        self.ejecutar, self.buscar, self.reloj = ejecutar, buscar, reloj
        self.lanzar = lanzar or (lambda fn: threading.Thread(target=fn, name="jaime0-diagnostico", daemon=True).start())
        self.al_terminar = al_terminar or (lambda doc: None)
        self._cerrojo = threading.Lock()
        self.ultimo = None                  # ultimo resultado correcto
        self.error = None                   # error de la ultima ejecucion, si fallo
        self.desde = None                   # instante de inicio de la ejecucion en curso

    def ejecutar_diagnostico(self, fin=None):
        if not self._cerrojo.acquire(blocking=False):
            return False
        self.desde = int(self.reloj())

        def trabajo():
            try:
                programa = self.buscar("jaime0-diagnostico")
                if not programa:
                    doc, error = None, "falta jaime0-diagnostico"
                else:
                    doc, error = ejecutar_json([programa, "comprobar", "--json"], LIMITE_DIAGNOSTICO, self.ejecutar)
                if error or not doc or doc.get("ok") is False:
                    self.error = error or (doc or {}).get("error") or "el diagnóstico no devolvió datos"
                    doc = {"ok": False, "error": self.error}
                else:
                    self.ultimo, self.error = doc, None
            except Exception as e:
                registrar(f"error al diagnosticar: {e}")
                self.error = "error interno al diagnosticar"
                doc = {"ok": False, "error": self.error}
            finally:
                self.desde = None
                self._cerrojo.release()
            try:
                self.al_terminar(doc)
            finally:
                if fin is not None:
                    fin(doc)

        self.lanzar(trabajo)
        return True

    def historial(self):
        programa = self.buscar("jaime0-diagnostico")
        if not programa:
            return {"ok": False, "error": "falta jaime0-diagnostico"}
        doc, error = ejecutar_json([programa, "historial", "--json"], LIMITE_HISTORIAL_DIAGNOSTICO, self.ejecutar)
        return doc if doc and not error else {"ok": False, "error": error or "sin historial"}

    def documento(self):
        """Lo que pide la ventana: el ultimo diagnostico (sin volver a ejecutarlo)."""
        return {"ok": True, "ultimo": self.ultimo, "error": self.error, "ejecutando_desde": self.desde}
