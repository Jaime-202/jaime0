# jaime0_servicio.servicio: el Servicio (bucle de GLib que reune medicion, estado, historico,
# incidencias, bus, perfiles, privacidad, reglas y api), el cerrojo de instancia unica, medir() y
# main(). Depende de todos los demas modulos; ninguno depende de el.

import argparse
import collections
import json
import os
import subprocess
import threading
import time
import traceback

from .base import PRODUCTO
from .base import (
    PROGRAMA, VERSION_DATOS, INTERVALO_NORMAL, INTERVALO_RAPIDO, DURACION_RAPIDO,
    REFRESCO_LENTO, TAMANO_ANILLO, VOLCADO_CADA, SMART_CADA, MAX_EVENTOS, MAX_INCIDENCIAS,
    UMBRALES, REGLAS_EN_CURSO, GRAVEDADES_AVISO, carpeta_config, ruta, directorio_ejecucion,
    directorio_estado, registrar, protegido, Recordado, Trabajador, escribir_json
)
from .medicion import leer, nvidia_activa, temperatura_nvidia, Muestreador, armar_instante
from .historico import leer_jsonl, anexar_jsonl, reescribir_jsonl, Historico
from .incidencias import nuevo_evento, Detector, NOMBRES_COMPONENTE, Incidencias
from .sistema import (
    leer_ajustes, cargar_umbrales, estado_unidades, _gi, consultar_fallidas, consultar_unidad_activa, vigilar_perfil,
    consultar_smart, vigilar_suspension, vigilar_archivos, avisar_barra
)
from .perfiles import SistemaReal, MotorPerfiles, textos_cambios
from .privacidad import (
    DISPOSITIVOS_CADA_RAPIDO, leer_conf_ufw, estado_cortafuegos, consultar_ufw_reglas,
    puertos_expuestos, consultar_puertos, dispositivos_en_uso, info_flatpak,
    grupos_privilegiados, servicios_privacidad, telemetria, eventos_privacidad,
    HistorialPrivacidad, categorias_privacidad, estado_apparmor, estado_secure_boot
)
from .estado import evaluar, resumen_privacidad, anillo_agregar
from .reglas import (
    VALIDEZ_DISPONIBILIDAD, LIMITE_PERFIL, AnalizadorHyprland, AplicacionesDisponibles,
    ejecutar_grupo, MotorReglas, disponibilidad_sistema, vigilar_bluetooth, vigilar_red,
    FuenteHyprland
)
from .actualizaciones import estado_actualizaciones, Comprobador
from .diagnostico import Diagnosticador, resumen_diagnostico
from .energia import (
    detalle_bateria, graficas, cpu_energia, suspension, inactividad, tiempo_con_cargador,
    comparar_perfiles, reglas_energia
)
from .api import procesar_linea

__all__ = [
    "fcntl", "SALIDA_YA_EN_MARCHA", "ServicioYaEnMarcha", "adquirir_cerrojo", "Servicio",
    "medir", "main"
]


try:
    import fcntl            # solo Linux: en Windows (pruebas) no hay cerrojo de instancia unica
except ImportError:
    fcntl = None


# ---------------------------------------------------------------------------
# Servicio: reune medicion, estado, bus y api
# ---------------------------------------------------------------------------

SALIDA_YA_EN_MARCHA = 2     # codigo de salida cuando ya hay otra instancia del servicio


class ServicioYaEnMarcha(Exception):
    pass


def adquirir_cerrojo(directorio, modulo=None):
    """Cerrojo de instancia unica: flock exclusivo y no bloqueante sobre servicio.lock del
    directorio de ejecucion. Devuelve el archivo (hay que mantenerlo abierto mientras viva el
    servicio) o None si el sistema no tiene fcntl. Lanza ServicioYaEnMarcha si ya esta tomado."""
    modulo = fcntl if modulo is None else modulo
    if modulo is None:
        return None
    f = open(os.path.join(directorio, "servicio.lock"), "a+")
    try:
        modulo.flock(f, modulo.LOCK_EX | modulo.LOCK_NB)
    except OSError:
        f.close()
        raise ServicioYaEnMarcha(f"ya hay otra instancia de {PROGRAMA} en marcha")
    return f


class Servicio:
    def __init__(self, directorio=None, estado=None, leer_umbrales=None, reloj=time.time, sistema=None):
        """directorio: de ejecucion (tmpfs); estado: de ~/.local/state/jaime0 (se crea al
        usarlo); leer_umbrales: funcion que devuelve los umbrales (por defecto
        cargar_umbrales, que llama a jaime0-ajustes); sistema: lo que tocan los perfiles
        (por defecto SistemaReal)."""
        self.dir = directorio or directorio_ejecucion()
        self._estado = estado
        self._leer_umbrales = leer_umbrales or cargar_umbrales
        self.reloj = reloj
        self.umbrales = dict(UMBRALES)
        self.muestreador = Muestreador()
        self.anillo = collections.deque(maxlen=TAMANO_ANILLO)
        self.actividad = collections.deque(maxlen=20)
        self.eventos = collections.deque(maxlen=MAX_EVENTOS)
        self.historico = Historico(self.carpeta_salud, reloj=reloj, eventos=self.eventos)
        self.detector = Detector()
        self.incidencias_estado = Incidencias()
        try:
            self.incidencias_estado.restaurar(leer_jsonl(self.archivo_incidencias()))
        except Exception:
            registrar("no se pudieron recuperar las incidencias abiertas:\n" + traceback.format_exc())
        self.n_incidencias = None
        self.smart = None
        self.gpu_temp = None
        self.instante = None
        self.estado = None
        self.motivos = []
        self.energia = None                 # ActiveProfile de power-profiles-daemon (solo lectura)
        # Hilo de efectos (ver Trabajador): el motor de perfiles solo se usa desde el; sus
        # avisos (actividad, estado y reglas) vuelven al bucle con al_bucle.
        self.efectos = Trabajador()
        al_bucle = lambda fn: (lambda *a: self.efectos.al_bucle(fn, *a))
        self.perfiles = MotorPerfiles(sistema or SistemaReal(), self.dir, self.dir_estado,
                                      lambda: os.path.join(carpeta_config(), "perfil-personalizado.json"),
                                      evento=al_bucle(self.evento), notificar=al_bucle(self._perfil_cambiado),
                                      cambio=al_bucle(lambda perfil, origen: self.reglas.perfil_cambiado(perfil, origen)))
        # Actualizaciones (fase 4): estado sin red por el hilo de efectos; comprobar con red, en
        # su propio hilo (Comprobador). Instalar nunca pasa por el servicio.
        self.comprobador = Comprobador()
        # Diagnostics (fase 5): jaime0-diagnostico en su propio hilo; el resultado vuelve al bucle.
        self.diagnosticador = Diagnosticador(al_terminar=lambda doc: self.al_bucle(self._diagnostico_hecho, doc))
        self._problemas_vistos = None       # ids de la ultima vez (para avisar solo de los nuevos)
        self.aviso_lanzar = self._lanzar_aviso  # las pruebas lo sustituyen
        self.reglas_ejecutar = subprocess.run   # las pruebas lo sustituyen
        ejecutar_reglas = lambda *a, **k: self.reglas_ejecutar(*a, **k)
        self.reglas_ejecutar_script = ejecutar_grupo    # scripts autorizados: ver ejecutar_grupo
        self.reglas = MotorReglas(
            lambda: os.path.join(carpeta_config(), "reglas.json"),
            lambda: os.path.join(self.dir_estado(), "ejecuciones.jsonl"),
            reloj=reloj, ejecutar=ejecutar_reglas, estado=self._estado_reglas,
            ejecutar_script=lambda *a, **k: self.reglas_ejecutar_script(*a, **k),
            aplicar_perfil=lambda pid: self.efectos.esperar(lambda: self.perfiles.aplicar(pid, "regla"),
                                                            "perfil desde una regla", LIMITE_PERFIL),
            apps=AplicacionesDisponibles(ejecutar_reglas).obtener,
            disponibilidad=Recordado(disponibilidad_sistema, VALIDEZ_DISPONIBILIDAD),
            incidencia=lambda linea: self.anotar_incidencias([linea]), evento=self.evento,
            notificar=self._perfil_cambiado)
        self.fallidas = None
        self.servicios = None               # SERVICIOS_IMPORTANTES con su estado (refresco lento)
        self.privacidad = resumen_privacidad(None)
        self.priv_ejecutar = subprocess.run     # las pruebas lo sustituyen
        self.priv_historial = HistorialPrivacidad(
            lambda: os.path.join(self.dir_estado(), "privacidad.jsonl"), reloj=reloj)
        self.priv_puertos = None            # puertos en escucha (None: ss no responde)
        self.priv_conexiones = None
        self.priv_disp = None
        self._ufw_activa = None             # ActiveState de ufw.service (None: aun no se sabe)
        self._priv_snap = None
        self._priv_disp_t = 0.0
        self._priv_lock = threading.RLock()     # secciones cortas; nunca se mantiene durante un subproceso
        self._priv_ejec = threading.Lock()      # un refresco de privacidad a la vez
        self._reglas_en_curso = threading.Lock()
        self.desde = int(time.time())
        self.rapido_hasta = 0.0
        self.clave_aviso = None
        self.previo_cargador = None
        self.evento("Servicio iniciado")
        # Lo siguiente solo se usa dentro del bucle de GLib
        self._fuente = None
        self._intervalo_programado = None
        self._servidor = None
        self._bucle = None
        self._monitores = []
        self._recarga_pendiente = False
        self._recarga_reglas_pendiente = False
        self._fallidas_vistas = None        # unidades fallidas de la consulta anterior (None: ninguna aun)

    # -- estado y registro ---------------------------------------------------
    def dir_estado(self):
        if self._estado is None:
            self._estado = directorio_estado()
        os.makedirs(self._estado, mode=0o700, exist_ok=True)
        return self._estado

    def carpeta_salud(self):
        d = os.path.join(self.dir_estado(), "salud")
        os.makedirs(d, mode=0o700, exist_ok=True)
        return d

    def evento(self, texto, tipo=None, gravedad="INFO", proceso=None, origen=None, valor=None):
        """Anota en la actividad y, si lleva tipo, tambien como evento para las graficas."""
        t = int(time.time())
        act = {"t": t, "texto": texto}
        if origen:
            act["origen"] = origen
        self.actividad.append(act)
        if tipo:
            self.eventos.append(nuevo_evento(t, tipo, gravedad, texto, proceso, origen, valor))

    def recargar_umbrales(self):
        """Lee los umbrales (jaime0-ajustes: un subproceso) y los aplica, en el acto. En
        marcha se usa la version en dos pasos de _recarga_diferida."""
        self.aplicar_umbrales(self._leer_umbrales())

    def aplicar_umbrales(self, leidos):
        """Aplica unos umbrales ya leidos (rapido: va en el bucle)."""
        antes = self.intervalo_actual()
        u = dict(UMBRALES)
        u.update(leidos or {})
        self.umbrales = u
        self.historico.dias = int(u["historial_dias"])
        self.historico.intervalo = self.intervalo_normal()
        if self._fuente is not None and self.intervalo_actual() != antes:
            self._programar()               # el temporizador sigue ya el intervalo nuevo

    def al_bucle(self, fn, *a):
        """Ejecuta fn(*a) en el bucle principal (desde otro hilo)."""
        self.efectos.al_bucle(fn, *a)

    def _diagnostico_hecho(self, doc):
        """En el bucle: problemas nuevos a la actividad y estado.json al dia (SYSTEM)."""
        if not isinstance(doc, dict) or not doc.get("ok"):
            return
        actuales = {p.get("id"): p for p in doc.get("problemas") or []
                    if isinstance(p, dict) and p.get("gravedad") in ("CRITICAL", "ERROR", "WARNING")}
        if self._problemas_vistos is not None:
            for pid in sorted(set(actuales) - self._problemas_vistos):
                p = actuales[pid]
                self.evento(f"Diagnóstico: {p.get('titulo')}", "diagnostico",
                            "WARNING" if p.get("gravedad") == "WARNING" else "CRITICAL", None, "diagnostico")
        self._problemas_vistos = set(actuales)
        if self.instante is not None and self.estado is not None:
            self.publicar(self.estado, self.motivos)

    def _diagnostico_periodico(self):
        self.diagnosticador.ejecutar_diagnostico()
        return True

    def _diagnostico_inicial(self):
        self.diagnosticador.ejecutar_diagnostico()
        return False

    def actualizaciones_doc(self):
        doc = estado_actualizaciones()
        doc["comprobando_desde"] = self.comprobador.en_curso()
        return doc

    # -- energia (POWER) -----------------------------------------------------------
    def energia_instantanea(self):
        """En el bucle: copia de lo que vive en el (anillo, minutos y reglas) para energia_doc."""
        self.reglas._asegurar()
        actual = self.historico._minuto_en_curso()
        return {"ahora": self.reloj(), "anillo": list(self.anillo),
                "minutos": list(self.historico.minutos) + ([actual] if actual else []),
                "reglas": reglas_energia(self.reglas.reglas),
                "cargador": (self.instante or {}).get("cargador")}

    def energia_doc(self, foto):
        """En el hilo de efectos (lee sysfs, /proc, logind, jaime0-ajustes y, si la NVIDIA ya
        esta despierta, nvidia-smi). Solo lee: los cambios van por PROFILES y jaime0-ajustes."""
        ahora, minutos = foto["ahora"], foto["minutos"]
        perfil = self.perfiles.doc_estado(self.energia)
        perfiles = []
        for d in self.perfiles.definiciones():
            aj = d.get("ajustes") or {}
            perfiles.append({"id": d["id"], "nombre": d["nombre"], "energia": aj.get("energia"),
                             "inhibe": aj.get("inhibir_inactividad") == "si",
                             "cambios": textos_cambios(aj), "descripcion": d.get("descripcion")})
        activo = next((p for p in perfiles if p["id"] == perfil["activo"]), None)
        return {"ok": True, "v": VERSION_DATOS, "t": int(ahora), "cargador": foto["cargador"],
                "bateria": detalle_bateria(foto["anillo"]), "graficas": graficas(), "cpu": cpu_energia(),
                "suspension": suspension(), "inactividad": dict(inactividad(leer_ajustes()),
                                                                inhibida_por=activo["nombre"] if activo and activo["inhibe"] else None),
                "perfil": perfil, "perfiles": perfiles, "reglas": foto["reglas"],
                "historial": {"desde": int(minutos[0]["t"]) if minutos else None,
                              "cargador_24h": tiempo_con_cargador(minutos, ahora - 86400),
                              "perfiles": comparar_perfiles(minutos)}}

    def intervalo_normal(self):
        return max(1, int(self.umbrales.get("intervalo_normal", INTERVALO_NORMAL)))

    def intervalo_rapido(self):
        return max(1, int(self.umbrales.get("intervalo_rapido", INTERVALO_RAPIDO)))

    # -- avisos de incidencias en el escritorio ----------------------------------
    def _lanzar_aviso(self, orden):
        """Lanza notify-send fuera del bucle de muestreo (hilo; no espera el bucle)."""
        def trabajo():
            try:
                subprocess.run(orden, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass

        threading.Thread(target=trabajo, daemon=True).start()

    def avisar_incidencias(self, lineas):
        """Una notificacion por incidencia nueva o escalada, segun cc_notificar. Las
        recuperaciones (NORMAL) no avisan. Solo lleva texto de la incidencia."""
        permitidas = GRAVEDADES_AVISO.get(self.umbrales.get("notificar"), ())
        for d in lineas:
            if d.get("gravedad") not in permitidas:
                continue
            nombre = NOMBRES_COMPONENTE.get(d.get("componente"), d.get("componente") or "").upper()
            cuerpo = ". ".join(t.rstrip(".") for t in (d.get("descripcion"), d.get("recomendacion")) if t)
            self.aviso_lanzar(["notify-send", f"--app-name={PRODUCTO}",
                               "--urgency=" + ("critical" if d["gravedad"] == "CRITICAL" else "normal"),
                               "--", f"{nombre} · {d['gravedad']}", cuerpo])

    # -- incidencias (archivo) -------------------------------------------------
    def archivo_incidencias(self):
        return os.path.join(self.dir_estado(), "incidencias.jsonl")

    def anotar_incidencias(self, lineas):
        """Anexa las lineas a incidencias.jsonl y lo recorta a MAX_INCIDENCIAS."""
        if not lineas:
            return
        archivo = self.archivo_incidencias()
        anexar_jsonl(archivo, lineas)
        if self.n_incidencias is None:
            self.n_incidencias = len(leer_jsonl(archivo))
        else:
            self.n_incidencias += len(lineas)
        if self.n_incidencias > MAX_INCIDENCIAS:
            docs = leer_jsonl(archivo)[-MAX_INCIDENCIAS:]
            reescribir_jsonl(archivo, docs)
            self.n_incidencias = len(docs)

    # -- consultas de la API ---------------------------------------------------
    def serie(self, rango):
        return self.historico.serie(rango, self.anillo, self.reloj())

    def incidencias(self, limite):
        docs = [d for d in leer_jsonl(self.archivo_incidencias()) if "componente" in d]
        return docs[-limite:][::-1]

    def eventos_lista(self):
        return list(self.eventos)[::-1]

    def intervalo_actual(self):
        return self.intervalo_rapido() if time.time() < self.rapido_hasta else self.intervalo_normal()

    def rapido(self):
        self.rapido_hasta = time.time() + DURACION_RAPIDO
        if self._fuente is not None and self._intervalo_programado != self.intervalo_rapido():
            self._programar()
        return self.intervalo_rapido(), int(self.rapido_hasta)

    def instante_doc(self):
        return self.instante

    def estado_doc(self):
        if self.estado is None:
            return None
        return {"v": VERSION_DATOS, "t": int(time.time()), "estado": self.estado, "motivos": self.motivos,
                "perfil": self.perfiles.doc_estado(self.energia),
                "privacidad": self.privacidad, "actividad": list(self.actividad),
                "incidencias_abiertas": self.incidencias_estado.abiertas(),
                "disponible": self.historico.disponibilidad(self.anillo, self.reloj()),
                "diagnostico": resumen_diagnostico(self.diagnosticador.ultimo),
                "servicios": self.servicios,
                "servicio": {"pid": os.getpid(), "desde": self.desde, "intervalo": self.intervalo_actual(),
                             "efectos": self.efectos.estado()}}

    # -- ciclo de medicion ---------------------------------------------------
    def muestrear(self):
        # La lista de todos los procesos solo hace falta con la ventana abierta (modo rapido).
        med = self.muestreador.muestrear(completa=time.time() < self.rapido_hasta)
        if med["gpu"]["nvidia"] != "activa":
            self.gpu_temp = None            # suspendida o sin GPU: sin temperatura, jamas se despierta
        med["gpu"]["temp"] = self.gpu_temp
        inst = armar_instante(med, time.time(), self.intervalo_actual(), self.fallidas, self.smart)
        estado, motivos = evaluar(inst, self.umbrales)
        inst["estado"], inst["alertas"] = estado, len(motivos)
        self.instante = inst
        muestra = anillo_agregar(self.anillo, inst)
        escribir_json(os.path.join(self.dir, "instante.json"), inst)
        self.publicar(estado, motivos)
        for ev in self.detector.procesar(inst):
            self.eventos.append(ev)
        self.historico.anadir(muestra, inst["intervalo"])
        nuevas = self.incidencias_estado.observar(inst, self.umbrales, inst["t"])
        try:
            self.anotar_incidencias(nuevas)
        except OSError:
            registrar("no se pudo escribir incidencias.jsonl:\n" + traceback.format_exc())
        self.avisar_incidencias(nuevas)
        self._reglas_muestra(inst)

    def publicar(self, estado, motivos):
        """Anota los cambios, reescribe estado.json y avisa a Waybar si algo visible cambio."""
        cambio_estado = self.estado is not None and estado != self.estado
        if cambio_estado:
            self.evento(f"Estado: {self.estado} → {estado}", "estado",
                        "INFO" if estado == "ONLINE" else estado)
        self.estado, self.motivos = estado, motivos
        if cambio_estado:
            self._reglas_evento("estado_sistema", {"estado": estado})
        cargador = (self.instante or {}).get("cargador")
        if self.previo_cargador is not None and cargador is not None and cargador != self.previo_cargador:
            self.evento("Cargador conectado" if cargador else "Cargador desconectado", "cargador")
        if cargador is not None:
            self.previo_cargador = cargador
        escribir_json(os.path.join(self.dir, "estado.json"), self.estado_doc())
        clave = (estado, self.perfiles.activo, self.energia, self.perfiles.retencion, len(motivos),
                 self.privacidad["estado"])
        if clave != self.clave_aviso:
            self.clave_aviso = clave
            # pgrep y pkill: en el hilo de efectos (un fallo alli se registra y no sube).
            self.efectos.enviar(lambda: avisar_barra(), descripcion="aviso a Waybar")

    # -- bus -----------------------------------------------------------------
    def poner_energia(self, valor):
        """Cambio del perfil de ppd (el que sea: el del usuario o una retencion nuestra)."""
        if valor == self.energia:
            return
        if self.energia is not None or valor is not None:
            self.evento(f"Perfil de energía: {valor or 'N/D'}", "perfil", valor=valor)
        self.energia = valor
        self.efectos.enviar(lambda: self.perfiles.retencion_obsoleta(valor), descripcion="retención de energía")
        self._perfil_cambiado()

    def _perfil_cambiado(self):
        """Perfil de ZYRON o de energia distintos: reescribe estado.json y avisa a Waybar."""
        if self.instante is not None:
            self.publicar(self.estado, self.motivos)

    # -- reglas (modulo propio) -----------------------------------------------------
    def _estado_reglas(self):
        """Estado actual para las condiciones SI."""
        inst = self.instante or {}
        return {"perfil": self.perfiles.activo, "cargador": inst.get("cargador"),
                "bateria": (inst.get("bateria") or {}).get("nivel")}

    @protegido(None)
    def _reglas_evento(self, nombre, datos):
        self.reglas.evento(nombre, datos)

    @protegido(None)
    def _reglas_muestra(self, inst):
        self.reglas.muestra(inst)

    @protegido(None)
    def _reglas_bluetooth(self, estado, nombre, audio):
        self.reglas.evento("bluetooth", {"estado": estado, "nombre": nombre, "audio": audio})

    @protegido(None)
    def _reglas_red(self, estado, wifi):
        self.reglas.evento("red", {"estado": estado, "wifi": wifi})

    @protegido(None)
    def _reglas_hyprland(self, evento, datos):
        self.reglas.evento(evento, datos)

    @protegido(False)
    def _recarga_reglas_diferida(self):
        self._recarga_reglas_pendiente = False
        self.reglas.cargar()
        return False

    def pedir_recarga_reglas(self):
        """reglas.json ha cambiado: se relee 0,3 s despues (agrupa los eventos de una escritura)."""
        if self._recarga_reglas_pendiente:
            return
        GLib, _Gio = _gi()
        self._recarga_reglas_pendiente = True
        GLib.timeout_add(300, self._recarga_reglas_diferida)

    @protegido(None)
    def iniciar_perfiles(self):
        self.efectos.enviar(self.perfiles.iniciar, descripcion="perfil guardado")

    def refrescar_lento(self):
        """Unidades fallidas y cortafuegos: cada 60 s, no en cada muestra."""
        def con_fallidas(lista):
            if lista is not None:
                nuevas = sorted(set(lista) - set(self._fallidas_vistas or []))
                if nuevas and self._fallidas_vistas is not None:
                    self._reglas_evento("servicio_fallido", {"unidad": ", ".join(nuevas)})
                self._fallidas_vistas = list(lista)
            self.fallidas = lista

        def con_ufw(activa):
            self._ufw_activa = activa
            self.priv_recalcular()

        self.efectos.enviar(self.perfiles.refrescar_degradado, descripcion="perfil degradado")
        self.efectos.enviar(estado_unidades, lambda r: setattr(self, "servicios", r), "servicios importantes")
        consultar_fallidas(con_fallidas)
        if leer("etc", "ufw", "ufw.conf") is not None:
            consultar_unidad_activa("ufw.service", con_ufw)
        else:
            self._ufw_activa = None
            self.priv_recalcular()
        self.priv_lanzar(True, True)
        # Temperatura de la NVIDIA: solo con la GPU activa, en un hilo (nvidia-smi tarda).
        if nvidia_activa():
            threading.Thread(target=self._leer_gpu, daemon=True).start()
        else:
            self.gpu_temp = None

    # -- privacidad (modulo propio) ------------------------------------------------
    def priv_recalcular(self):
        """Resumen de privacidad (estado.json) e instantanea para el historial, con lo ultimo
        que se sabe del cortafuegos y de los puertos."""
        with self._priv_lock:
            self.privacidad = resumen_privacidad(self._ufw_activa, self.priv_puertos)
            nuevos = {}
            fw = estado_cortafuegos(self._ufw_activa)
            if not fw["instalado"] or fw["unidad_activa"] is not None:
                nuevos["fw"] = {"activo": fw["activo"], "politicas": fw["politicas"]}
            if self.priv_puertos is not None:
                nuevos["puertos"] = puertos_expuestos(self.priv_puertos)
            self._priv_instantanea(nuevos)

    def _priv_instantanea(self, nuevos):
        """Fusiona `nuevos` en la instantanea y anota en el historial lo que cambio."""
        with self._priv_lock:
            antes = self._priv_snap
            ahora = dict(antes or {})
            ahora.update({k: v for k, v in nuevos.items() if v is not None})
            if antes is not None:
                for tipo, texto in eventos_privacidad(antes, ahora):
                    try:
                        self.priv_historial.anotar(tipo, texto)
                    except OSError:
                        registrar("no se pudo escribir privacidad.jsonl:\n" + traceback.format_exc())
            self._priv_snap = ahora

    def priv_refrescar(self, puertos=True, dispositivos=True):
        """Consulta puertos y/o dispositivos (subprocesos: no llamar desde el bucle de GLib)."""
        if puertos:
            escucha, conexiones = consultar_puertos(self.priv_ejecutar)
            with self._priv_lock:
                self.priv_puertos, self.priv_conexiones = escucha, conexiones
            self.priv_recalcular()
        if dispositivos:
            disp = dispositivos_en_uso(self.priv_ejecutar)
            with self._priv_lock:
                self.priv_disp = disp
                self._priv_disp_t = time.monotonic()
                self._priv_instantanea({k: ({d["aplicacion"] for d in v} if v is not None else None)
                                        for k, v in disp.items()})

    def priv_lanzar(self, puertos=True, dispositivos=True):
        """priv_refrescar en un hilo; si ya hay un refresco en curso no hace nada."""
        if not self._priv_ejec.acquire(blocking=False):
            return False

        def trabajo():
            try:
                self.priv_refrescar(puertos, dispositivos)
            except Exception:
                registrar("error al refrescar la privacidad:\n" + traceback.format_exc())
            finally:
                self._priv_ejec.release()

        threading.Thread(target=trabajo, daemon=True).start()
        return True

    @protegido(True)
    def _priv_periodico(self):
        """Cada 10 s: dispositivos en uso, pero solo mientras la ventana esta abierta (peticion
        "rapido" vigente); sin ella se miran cada 60 s con el refresco lento."""
        if time.time() < self.rapido_hasta and time.monotonic() - self._priv_disp_t >= DISPOSITIVOS_CADA_RAPIDO - 1:
            self.priv_lanzar(False, True)
        return True

    def privacidad_doc(self):
        """Detalle completo de privacidad, calculado ahora (bloquea: se llama desde un hilo)."""
        with self._priv_ejec:
            self.priv_refrescar(True, True)
        ejecutar = self.priv_ejecutar
        with self._priv_lock:
            fw = estado_cortafuegos(self._ufw_activa)
            doc = {"ok": True, "v": VERSION_DATOS, "estado": self.privacidad, "cortafuegos": fw,
                   "puertos": self.priv_puertos, "conexiones": self.priv_conexiones,
                   "dispositivos": self.priv_disp}
        doc.update({"flatpak": info_flatpak(ejecutar),
                    "privilegios": {"grupos": grupos_privilegiados()},
                    "servicios": servicios_privacidad(ejecutar),
                    "telemetria": telemetria(ejecutar),
                    "historial": self.priv_historial.ultimos(20)})
        doc["categorias"] = categorias_privacidad(doc, estado_apparmor(), estado_secure_boot())
        return doc

    def ufw_reglas_doc(self, reservado=False):
        """Reglas de UFW con autorizacion (pkexec). Bloquea hasta que el usuario responde: se
        llama desde un hilo. Anota el resultado en el historial; la salida no se guarda.
        Con reservado=True el cerrojo ya lo tomo quien lanzo el hilo (procesar_linea, en el
        bucle): asi una segunda peticion seguida no puede colarse antes de que el hilo
        arranque y abrir otra ventana de contraseña. Aqui solo se suelta."""
        if not reservado and not self._reglas_en_curso.acquire(blocking=False):
            return {"ok": False, "error": REGLAS_EN_CURSO}
        try:
            if leer_conf_ufw() is None:
                return {"ok": False, "error": "El cortafuegos (UFW) no está instalado"}
            doc = consultar_ufw_reglas(self.priv_ejecutar)
        finally:
            self._reglas_en_curso.release()
        try:
            self.priv_historial.anotar(
                "reglas", "Reglas del cortafuegos consultadas (con autorización)" if doc.get("ok")
                else f"Consulta de las reglas del cortafuegos: {doc.get('error')}")
        except OSError:
            registrar("no se pudo escribir privacidad.jsonl:\n" + traceback.format_exc())
        return doc

    def _leer_gpu(self):
        try:
            self.gpu_temp = temperatura_nvidia()
        except Exception:
            registrar("error al leer la temperatura de la GPU:\n" + traceback.format_exc())

    def refrescar_smart(self):
        def con_smart(lista):
            self.smart = lista

        consultar_smart(con_smart)

    # -- historico, suspension y ajustes -----------------------------------------
    @protegido(None)
    def al_suspender(self, suspendiendo):
        """PrepareForSleep: al suspender se vuelca todo; al reanudar se cierra el hueco."""
        self._reglas_suspension(suspendiendo)
        if suspendiendo:
            self.historico.volcar(cerrar_parcial=True)
        else:
            self.historico.cerrar_hueco(int(self.reloj()))

    @protegido(None)
    def _reglas_suspension(self, suspendiendo):
        self.reglas.evento("suspension", {"estado": "suspender" if suspendiendo else "reanudar"})
        if not suspendiendo:
            self.reglas.tras_reanudar()     # el temporizador de la hora no cuenta la suspension

    @protegido(True)
    def _volcado_periodico(self):
        self.historico.volcar()
        return True

    @protegido(True)
    def _smart_periodico(self):
        self.refrescar_smart()
        return True

    @protegido(False)
    def _recarga_diferida(self):
        self._recarga_pendiente = False
        # Leer los ajustes lanza jaime0-ajustes (hasta 5 s): en el hilo de efectos; aplicarlos,
        # en el bucle.
        self.efectos.enviar(self._leer_umbrales, protegido(None)(self.aplicar_umbrales), "leer umbrales")
        return False

    def pedir_recarga(self):
        """Cambio en los ajustes: recarga los umbrales medio segundo despues (agrupa los
        varios eventos que produce una escritura)."""
        if self._recarga_pendiente:
            return
        GLib, _Gio = _gi()
        self._recarga_pendiente = True
        GLib.timeout_add(500, self._recarga_diferida)

    # -- bucle ---------------------------------------------------------------
    def _programar(self):
        GLib, _Gio = _gi()
        if self._fuente is not None:
            GLib.source_remove(self._fuente)
        self._intervalo_programado = self.intervalo_actual()
        self._fuente = GLib.timeout_add(self._intervalo_programado * 1000, self._tick)

    def _tick(self):
        self._fuente = None
        try:
            self.muestrear()
        except Exception:
            registrar("error al medir:\n" + traceback.format_exc())
        finally:
            self._programar()
        return False

    @protegido(True)
    def _lento(self):
        self.refrescar_lento()
        return True

    def _iniciar_api(self, GLib):
        import socket
        destino = os.path.join(self.dir, "control.sock")
        try:
            os.unlink(destino)
        except OSError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        anterior = os.umask(0o177)
        try:
            s.bind(destino)
        finally:
            os.umask(anterior)
        os.chmod(destino, 0o600)
        s.listen(8)
        s.setblocking(False)
        self._servidor = s
        GLib.io_add_watch(s.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, self._aceptar)

    @protegido(True)
    def _aceptar(self, _fd, _cond):
        GLib, _Gio = _gi()
        try:
            con, _ = self._servidor.accept()
        except (BlockingIOError, InterruptedError):
            return True
        con.setblocking(False)
        buf = bytearray()
        pendientes = [0]            # respuestas de hilos aun por entregar
        por_cerrar = [False]        # el cliente ya cerro su lado
        fuente = [None]             # id del watch de lectura de esta conexion

        def cerrar():
            """Cierra la conexion quitando antes su watch: un watch sobre un descriptor ya
            cerrado (o reutilizado por otra conexion) vigilaria el descriptor equivocado."""
            if fuente[0] is not None:
                id_watch, fuente[0] = fuente[0], None
                try:
                    GLib.source_remove(id_watch)
                except Exception:
                    registrar("no se pudo quitar el watch de la conexión:\n" + traceback.format_exc())
            con.close()

        def enviar(texto):
            try:
                con.settimeout(5.0)     # respuestas grandes (series): sendall espera al cliente
                con.sendall(texto.encode("utf-8") + b"\n")
                con.setblocking(False)
                return True
            except OSError:
                cerrar()
                return False

        @protegido(False)
        def entregar(texto):
            """Respuesta de un hilo, ya en el bucle de GLib."""
            pendientes[0] -= 1
            if enviar(texto) and por_cerrar[0] and not pendientes[0]:
                cerrar()
            return False

        def responder_desde_hilo(texto):
            GLib.idle_add(entregar, texto)

        @protegido(False)
        def leer_cliente(_fd2, _cond2):
            try:
                datos = con.recv(65536)
            except (BlockingIOError, InterruptedError):
                return True
            except OSError:
                datos = b""
            if datos:
                buf.extend(datos)
            if len(buf) > 262144:
                cerrar()
                return False
            final = not datos
            while True:
                if b"\n" in buf:
                    linea, _, resto = bytes(buf).partition(b"\n")
                    buf[:] = resto
                elif final and buf.strip():
                    linea = bytes(buf)
                    buf.clear()
                else:
                    break
                pendientes[0] += 1
                respuesta = procesar_linea(linea.decode("utf-8", "replace"), self, responder_desde_hilo)
                if respuesta is None:       # la contestara un hilo
                    continue
                pendientes[0] -= 1
                if not enviar(respuesta):
                    return False
            if final:
                por_cerrar[0] = True
                fuente[0] = None        # este watch acaba al devolver False: no hay que quitarlo
                if not pendientes[0]:
                    cerrar()
                return False
            return True

        fuente[0] = GLib.io_add_watch(con.fileno(), GLib.PRIORITY_DEFAULT,
                                      GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, leer_cliente)
        return True

    @protegido(None)
    def iniciar_reglas(self):
        """Carga reglas.json, lo vigila y abre las fuentes de eventos (todas por senales: sin sondeo)."""
        self.reglas.conectar_glib()
        self.reglas.cargar()
        self._monitores += vigilar_archivos([os.path.join(carpeta_config(), "reglas.json")], self.pedir_recarga_reglas)
        self._reglas_bluetooth_bus = vigilar_bluetooth(self._reglas_bluetooth)
        self._reglas_red_bus = vigilar_red(self._reglas_red)
        self._reglas_hyprland_fuente = FuenteHyprland(AnalizadorHyprland(), self._reglas_hyprland)
        self._reglas_hyprland_fuente.iniciar()

    def ejecutar(self):
        import signal
        # Antes del try/finally: si ya hay otra instancia, limpiar() no debe borrar SU control.sock.
        self._cerrojo = adquirir_cerrojo(self.dir)
        GLib, _Gio = _gi()
        self._bucle = GLib.MainLoop()
        try:
            # Hilo de efectos: sus resultados vuelven al bucle con idle_add (seguro entre hilos).
            def al_bucle(fn, *a):
                GLib.idle_add(lambda: (protegido(None)(fn)(*a), False)[1])
            self.efectos.iniciar(al_bucle)
            self._iniciar_api(GLib)
            self.muestreador.base()
            self._perfil_bus = vigilar_perfil(self.poner_energia)
            # Umbrales y perfil guardado: en el hilo de efectos; hasta que lleguen se mide con
            # los umbrales de fabrica.
            self.efectos.enviar(self._leer_umbrales, protegido(None)(self.aplicar_umbrales), "leer umbrales")
            self.iniciar_perfiles()
            try:
                self.historico.cargar()
            except Exception:
                registrar("no se pudo leer el historico:\n" + traceback.format_exc())
            self._monitores = vigilar_archivos(
                [os.path.join(carpeta_config(), "ajustes"), ruta("usr", "share", "jaime0", "ajustes.predeterminados")],
                self.pedir_recarga)
            self._suspension = vigilar_suspension(self.al_suspender)
            self.iniciar_reglas()
            self.refrescar_lento()
            self.refrescar_smart()
            GLib.timeout_add_seconds(REFRESCO_LENTO, self._lento)
            GLib.timeout_add_seconds(DISPOSITIVOS_CADA_RAPIDO, self._priv_periodico)
            GLib.timeout_add_seconds(SMART_CADA, self._smart_periodico)
            GLib.timeout_add_seconds(VOLCADO_CADA, self._volcado_periodico)
            # Diagnostico: a los 2 min de arrancar (con la sesion ya en marcha) y cada 6 h.
            GLib.timeout_add_seconds(120, self._diagnostico_inicial)
            GLib.timeout_add_seconds(6 * 3600, self._diagnostico_periodico)
            self._fuente = GLib.timeout_add(1000, self._tick)   # primera muestra con 1 s de deltas
            self._intervalo_programado = 1
            salir = lambda *_: (self._bucle.quit(), GLib.SOURCE_REMOVE)[1]
            # GLibUnix en PyGObject reciente; GLib.unix_signal_add en versiones anteriores.
            try:
                from gi.repository import GLibUnix
                anadir_senal = lambda s: GLibUnix.signal_add(GLib.PRIORITY_HIGH, s, salir)
            except ImportError:
                anadir_senal = lambda s: GLib.unix_signal_add(GLib.PRIORITY_HIGH, s, salir)
            anadir_senal(signal.SIGTERM)
            anadir_senal(signal.SIGINT)
            self._bucle.run()
        finally:
            self.limpiar()

    def limpiar(self):
        try:
            self.historico.volcar(cerrar_parcial=True)      # al parar (SIGTERM): no se pierde nada
        except Exception:
            registrar("no se pudo volcar el historico al parar:\n" + traceback.format_exc())
        try:
            if self._servidor is not None:
                self._servidor.close()
        except OSError:
            pass
        # Al parar, fuera tambien los datos publicados: si se quedaran, la barra, jaime0-salud
        # y la ventana mostrarian el ultimo estado como si fuera actual.
        for nombre in ("control.sock", "instante.json", "estado.json"):
            try:
                os.unlink(os.path.join(self.dir, nombre))
            except OSError:
                pass
        avisar_barra()      # la barra no se refresca sola: que pase a "parado" ya


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------

def medir():
    """Una medicion inmediata: dos lecturas separadas 0,5 s."""
    m = Muestreador()
    m.base()
    time.sleep(0.5)
    inst = armar_instante(m.muestrear(), time.time(), INTERVALO_NORMAL, None)
    inst["estado"], motivos = evaluar(inst, UMBRALES)
    inst["alertas"] = len(motivos)
    return inst


def main(argv=None):
    ap = argparse.ArgumentParser(prog=PROGRAMA, description=f"Servicio de salud del sistema de {PRODUCTO}.")
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("ejecutar", help="ejecuta el servicio (bucle de GLib)")
    pm = sub.add_parser("medir", help="una medicion inmediata en JSON")
    pm.add_argument("--json", action="store_true", help="imprime JSON (es lo unico que hace)")
    args = ap.parse_args(argv)
    if args.orden == "medir":
        print(json.dumps(medir(), ensure_ascii=False))
        return 0
    try:
        Servicio().ejecutar()
    except ServicioYaEnMarcha as e:
        registrar(f"{e}: no se inicia otra (cerrojo servicio.lock)")
        return SALIDA_YA_EN_MARCHA
    except KeyboardInterrupt:
        pass
    except Exception:
        registrar("error fatal:\n" + traceback.format_exc())
        return 1
    return 0
