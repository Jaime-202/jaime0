# jaime0_servicio.base: constantes comunes (intervalos, tamanos, UMBRALES por defecto,
# gravedades), rutas (raiz falsa de las pruebas, directorios de ejecucion y de estado) y utilidades
# de todo el servicio: registrar, protegido, Recordado, Trabajador (hilo de efectos) y escribir_json.
# Depende solo de la biblioteca estandar.

import functools
import json
import os
import sys
import threading
import time
import traceback

__all__ = [
    "PROGRAMA", "VERSION_DATOS", "SENAL_BARRA", "INTERVALO_NORMAL", "INTERVALO_RAPIDO",
    "DURACION_RAPIDO", "REFRESCO_LENTO", "TAMANO_ANILLO", "DURACION_ANILLO", "VOLCADO_CADA",
    "SMART_CADA", "FACTOR_HUECO", "RETENCION_MINUTOS", "MAX_PUNTOS", "MAX_EVENTOS",
    "MAX_INCIDENCIAS", "MUESTRAS_INCIDENCIA", "MUESTRAS_SIN_DATO", "MUESTRAS_PICO_CPU",
    "UMBRAL_PICO_CPU", "UMBRAL_PICO_RAM", "SALTO_TEMPERATURA", "RANGOS", "METRICAS", "UMBRALES",
    "OPCIONES_NOTIFICAR", "REGLAS_EN_CURSO", "GRAVEDADES_AVISO", "AJUSTES_UMBRALES",
    "carpeta_config", "es_root", "raiz", "modo_prueba", "ruta", "directorio_ejecucion",
    "directorio_estado", "registrar", "protegido", "Recordado", "AVISO_EFECTO_LENTO",
    "ERROR_INTERNO", "Trabajador", "escribir_json"
]


PROGRAMA = "jaime0-servicio"
VERSION_DATOS = 1
SENAL_BARRA = 11            # RTMIN+11: la barra relee el indicador
INTERVALO_NORMAL = 10       # segundos entre muestras
INTERVALO_RAPIDO = 2        # segundos mientras la interfaz esta abierta
DURACION_RAPIDO = 15        # segundos que dura cada peticion "rapido"
REFRESCO_LENTO = 60         # segundos entre consultas de unidades fallidas y cortafuegos
TAMANO_ANILLO = 3600        # muestras como maximo (una hora a 1 s; sobra a 2 s y a 10 s)
DURACION_ANILLO = 3600      # segundos que se conservan las muestras del anillo
VOLCADO_CADA = 300          # segundos entre volcados del historico a disco
SMART_CADA = 600            # segundos entre consultas SMART a udisks2
FACTOR_HUECO = 3            # hueco si entre dos muestras pasa mas de 3 x el intervalo
RETENCION_MINUTOS = 2 * 86400   # los archivos diarios (agregados de minuto) duran 2 dias
MAX_PUNTOS = 720            # puntos como maximo en una serie
MAX_EVENTOS = 200           # eventos de actividad en RAM
MAX_INCIDENCIAS = 500       # lineas de incidencias.jsonl
MUESTRAS_INCIDENCIA = 3     # muestras seguidas para abrir o cerrar una incidencia
MUESTRAS_SIN_DATO = 3       # muestras seguidas sin dato de un componente para dar por cerrada su incidencia
MUESTRAS_PICO_CPU = 2
UMBRAL_PICO_CPU = 85.0
UMBRAL_PICO_RAM = 90.0
SALTO_TEMPERATURA = 15.0    # grados entre muestras consecutivas
RANGOS = {"5m": 300, "1h": 3600, "24h": 86400}      # "historia" no tiene ventana fija
METRICAS = ("cpu", "ram", "swap", "presion", "temp", "gpu_temp", "bateria", "vatios",
            "lectura", "escritura", "disco")

# Umbrales unicos del estado global (ver evaluar). Por defecto; los de jaime0-ajustes los
# sustituyen (ver cargar_umbrales).
UMBRALES = {
    "temp_aviso": 85.0, "temp_critico": 95.0,          # cpu.temp, en grados
    "disco_aviso": 85.0, "disco_critico": 95.0,        # % ocupado
    "bateria_aviso": 15, "bateria_critico": 5,         # % y descargando
    "ram_libre_critico": 5.0,                          # % disponible por debajo
    "swap_aviso": 50.0,                                # % de swap usada por encima
    "presion_aviso": 20.0,                             # avg10 de /proc/pressure/memory
    "historial_dias": 90,                              # duracion del historico de 15 min
    "intervalo_normal": INTERVALO_NORMAL,              # s entre muestras (cc_intervalo)
    "intervalo_rapido": INTERVALO_RAPIDO,              # s con la ventana abierta (cc_intervalo_rapido)
    "notificar": "criticas",                           # avisos de incidencias (cc_notificar)
}
OPCIONES_NOTIFICAR = ("todas", "criticas", "ninguna")
REGLAS_EN_CURSO = "ya hay una consulta de reglas en curso"
# Gravedades de incidencia que avisan en el escritorio segun cc_notificar
GRAVEDADES_AVISO = {"todas": ("WARNING", "CRITICAL"), "criticas": ("CRITICAL",), "ninguna": ()}
# Ajuste de jaime0-ajustes -> clave de UMBRALES
AJUSTES_UMBRALES = {
    "umbral_temp_aviso": "temp_aviso", "umbral_temp_critico": "temp_critico",
    "umbral_disco_aviso": "disco_aviso", "umbral_disco_critico": "disco_critico",
    "umbral_bateria_aviso": "bateria_aviso", "umbral_bateria_critico": "bateria_critico",
    "historial_dias": "historial_dias",
    "cc_intervalo": "intervalo_normal", "cc_intervalo_rapido": "intervalo_rapido",
}


def carpeta_config():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "jaime0")


def es_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def raiz():
    """Raiz de /proc y /sys: la falsa de JAIME0_RAIZ solo sin privilegios."""
    return "/" if es_root() else os.environ.get("JAIME0_RAIZ", "/")


def modo_prueba():
    return raiz() != "/"


def ruta(*partes):
    return os.path.join(raiz(), *[p.lstrip("/\\") for p in partes])


def directorio_ejecucion():
    """JAIME0_RUNTIME o $XDG_RUNTIME_DIR/jaime0, creado con 0700."""
    d = os.environ.get("JAIME0_RUNTIME")
    if not d:
        base = os.environ.get("XDG_RUNTIME_DIR")
        if not base:
            raise RuntimeError("no hay XDG_RUNTIME_DIR ni JAIME0_RUNTIME")
        d = os.path.join(base, "jaime0")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def directorio_estado():
    """JAIME0_ESTADO, o $XDG_STATE_HOME/jaime0, o ~/.local/state/jaime0, creado con 0700."""
    d = os.environ.get("JAIME0_ESTADO")
    if not d:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
        d = os.path.join(base, "jaime0")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def registrar(texto):
    print(f"{PROGRAMA}: {texto}", file=sys.stderr, flush=True)


def protegido(defecto):
    """Aisla un manejador: si falla, lo registra y devuelve `defecto` (True mantiene viva
    una fuente de GLib)."""
    def deco(f):
        @functools.wraps(f)
        def envoltorio(*a, **k):
            try:
                return f(*a, **k)
            except Exception:
                registrar("error en " + f.__name__ + ":\n" + traceback.format_exc())
                return defecto
        return envoltorio
    return deco


class Recordado:
    """fn() recordada `validez` s (para consultas lentas como la disponibilidad por D-Bus).
    refrescar() la calcula de nuevo; se llama desde el hilo de efectos antes de usarla en
    el bucle, que asi solo lee el valor recordado."""

    def __init__(self, fn, validez, reloj=time.monotonic):
        self.fn, self.validez, self.reloj = fn, validez, reloj
        self._valor, self._t = None, None
        self._lock = threading.Lock()

    def refrescar(self):
        valor = self.fn()
        with self._lock:
            self._valor, self._t = valor, self.reloj()
        return valor

    def __call__(self):
        with self._lock:
            if self._t is not None and self.reloj() - self._t < self.validez:
                return self._valor
        return self.refrescar()


AVISO_EFECTO_LENTO = 10             # s: una operacion de efectos que tarda mas se anota
ERROR_INTERNO = {"ok": False, "error": "error interno"}


class Trabajador:
    """Hilo de efectos: las operaciones que pueden tardar o colgarse (D-Bus sincrono,
    programas externos como hyprctl, swaync-client o jaime0-ajustes) se hacen aqui, de una
    en una y en orden, nunca en el bucle de GLib. Asi las medidas, el socket, las reglas y
    la interfaz no esperan a nadie. Cada operacion lleva ya su propio limite de tiempo
    (llamadas D-Bus de 3 s, subprocesos con timeout); el hilo solo anota las lentas.

    enviar(fn, fin): fn se ejecuta en el hilo y fin(resultado) vuelve al bucle (al_bucle).
    esperar(fn): para otros hilos (las acciones de las reglas): encola fn y espera su
    resultado. Sin iniciar (pruebas, o antes del bucle) todo se ejecuta en el acto.
    Un fallo en fn se registra y da ERROR_INTERNO: nunca mata el hilo."""

    def __init__(self, al_bucle=None, reloj=time.monotonic):
        self.al_bucle = al_bucle or (lambda fn, *a: fn(*a))
        self.reloj = reloj
        self._cola = None
        self._hilo = None
        self.en_curso = None                # (descripcion, instante de inicio) o None

    def iniciar(self, al_bucle=None):
        import queue
        if al_bucle is not None:
            self.al_bucle = al_bucle
        if self._hilo is None:
            self._cola = queue.Queue()
            self._hilo = threading.Thread(target=self._bucle, name="jaime0-efectos", daemon=True)
            self._hilo.start()

    def activo(self):
        return self._hilo is not None

    def pendientes(self):
        return self._cola.qsize() if self._cola is not None else 0

    def estado(self):
        """{"pendientes", "en_curso", "desde"} para estado.json (diagnostico)."""
        en = self.en_curso
        return {"pendientes": self.pendientes(), "en_curso": en[0] if en else None,
                "segundos": round(self.reloj() - en[1], 1) if en else None}

    def _correr(self, fn, descripcion):
        inicio = self.reloj()
        self.en_curso = (descripcion, inicio)
        try:
            return fn()
        except Exception:
            registrar(f"error en una operación de efectos ({descripcion}):\n" + traceback.format_exc())
            return dict(ERROR_INTERNO)
        finally:
            self.en_curso = None
            dur = self.reloj() - inicio
            if dur > AVISO_EFECTO_LENTO:
                registrar(f"operación lenta ({descripcion}): {dur:.1f} s")

    def enviar(self, fn, fin=None, descripcion="efecto"):
        if self._hilo is None:
            res = self._correr(fn, descripcion)
            if fin is not None:
                fin(res)
            return
        self._cola.put((fn, fin, descripcion, None))

    def esperar(self, fn, descripcion="efecto", limite=None):
        """Resultado de fn ejecutada en el hilo de efectos (o en el acto si no hay hilo, o si
        ya se esta en el). Con limite (s) y sin respuesta, devuelve un error sin esperar mas."""
        if self._hilo is None or threading.current_thread() is self._hilo:
            return self._correr(fn, descripcion)
        hecho, caja = threading.Event(), []
        self._cola.put((fn, None, descripcion, (hecho, caja)))
        if not hecho.wait(limite):
            return {"ok": False, "error": f"sin respuesta en {limite} s ({descripcion})"}
        return caja[0]

    def _bucle(self):
        while True:
            fn, fin, descripcion, espera = self._cola.get()
            res = self._correr(fn, descripcion)
            if espera is not None:
                espera[1].append(res)
                espera[0].set()
            if fin is not None:
                try:
                    self.al_bucle(fin, res)
                except Exception:
                    registrar("no se pudo devolver un resultado al bucle:\n" + traceback.format_exc())


def escribir_json(destino, objeto):
    """Escritura atomica: temporal en el mismo directorio y os.replace."""
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(objeto, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, destino)
