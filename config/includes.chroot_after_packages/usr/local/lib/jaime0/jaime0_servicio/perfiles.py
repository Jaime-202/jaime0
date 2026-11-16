# jaime0_servicio.perfiles: motor de perfiles (SistemaReal y MotorPerfiles). Depende de: base,
# sistema.

import json
import os
import re
import shutil
import subprocess
import traceback

from .base import VERSION_DATOS, carpeta_config, ruta, registrar, escribir_json
from .sistema import programa_hermano, _gi, PPD, firma_hyprland, entorno_hyprland

__all__ = [
    "nivel_animaciones_usuario", "AJUSTES_PERFIL", "TRI", "VALORES_AJUSTE", "CAPA_CLAVES",
    "PERFILES", "PERFIL_CUSTOM", "PERFIL_BASE", "ORIGENES", "normalizar_perfil",
    "validar_ajustes", "textos_cambios", "SistemaReal", "MotorPerfiles"
]


# ---------------------------------------------------------------------------
# Perfiles (Fase 4): capa de sesion sobre los ajustes. Un perfil declara el estado completo
# de lo que gestiona; lo que no menciona es "base" (como estaba antes de que un perfil lo
# tocara). Modulo propio: no depende de la salud ni de la API; todo lo que toca el sistema
# pasa por un objeto "sistema" (SistemaReal, o uno falso en las pruebas).
# ---------------------------------------------------------------------------

def nivel_animaciones_usuario():
    """Ajuste efectivo de animaciones SIN la capa del perfil, como lo resuelve hyprland.lua:
    el del usuario, si no el predeterminado y, si ninguno es valido, 'sutil' ('si' = 'sutil')."""
    for archivo in (os.path.join(carpeta_config(), "ajustes"),
                    ruta("usr", "share", "jaime0", "ajustes.predeterminados")):
        valor = None
        try:
            with open(archivo, encoding="utf-8") as f:
                for linea in f:
                    m = re.match(r"^\s*animaciones\s*=\s*(.*?)\s*$", linea)
                    if m:
                        valor = m.group(1)
        except OSError:
            continue
        if valor in ("si", "sutil"):
            return "sutil"
        if valor in ("no", "suave"):
            return valor
    return "sutil"


AJUSTES_PERFIL = ("energia", "animaciones", "desenfoque", "no_molestar", "inhibir_inactividad", "modo_noche")
TRI = ("si", "no", "base")
VALORES_AJUSTE = {"energia": ("balanced", "performance", "power-saver"),
                  "animaciones": TRI, "desenfoque": TRI, "no_molestar": TRI, "modo_noche": TRI,
                  "inhibir_inactividad": ("si", "no")}
CAPA_CLAVES = ("animaciones", "desenfoque")     # unicas claves que Hyprland lee de la capa
PERFILES = (
    {"id": "balanced", "nombre": "BALANCED", "ajustes": {},
     "descripcion": "Equilibrio entre rendimiento y consumo. Deja todo como lo tienes configurado."},
    {"id": "performance", "nombre": "PERFORMANCE", "ajustes": {"energia": "performance"},
     "descripcion": "Prioriza el rendimiento con el perfil de energía de alto rendimiento. "
                    "No toca servicios ni el núcleo."},
    {"id": "power-saver", "nombre": "POWER SAVER",
     "ajustes": {"energia": "power-saver", "animaciones": "no", "desenfoque": "no"},
     "descripcion": "Reduce el consumo: perfil de ahorro, sin animaciones ni desenfoque."},
    {"id": "focus", "nombre": "FOCUS", "ajustes": {"no_molestar": "si"},
     "descripcion": "Menos distracciones: no molestar activado (las notificaciones se guardan "
                    "en el centro sin aparecer)."},
    {"id": "multimedia", "nombre": "MULTIMEDIA", "ajustes": {"inhibir_inactividad": "si", "no_molestar": "si"},
     "descripcion": "Para ver vídeo o escuchar música: la pantalla no se bloquea ni se apaga y no "
                    "hay interrupciones."},
)
PERFIL_CUSTOM = {"id": "custom", "nombre": "CUSTOM",
                 "descripcion": "Tu propia combinación: eliges qué cambia (EDITAR CUSTOM en PROFILES "
                                "o jaime0-perfil personalizado)."}
PERFIL_BASE = "balanced"
ORIGENES = ("usuario", "regla", "inicio")


def normalizar_perfil(texto):
    """'POWER SAVER', 'Power_Saver' y 'power-saver' son el mismo id."""
    return re.sub(r"[\s_]+", "-", str(texto).strip().lower())


def validar_ajustes(doc):
    """(ajustes, error): estricta. Solo claves y valores conocidos; error en espanol o None."""
    if not isinstance(doc, dict):
        return {}, "los ajustes deben ser un objeto"
    limpio = {}
    for clave, valor in doc.items():
        if clave not in VALORES_AJUSTE:
            return {}, f"ajuste desconocido: {clave}"
        if not isinstance(valor, str) or valor not in VALORES_AJUSTE[clave]:
            return {}, f"valor no válido para {clave}: {valor!r} (admitidos: {', '.join(VALORES_AJUSTE[clave])})"
        limpio[clave] = valor
    return limpio, None


def textos_cambios(aj):
    """Lo que aplica un perfil, legible; lo que esta en base no aparece."""
    t = []
    if "energia" in aj:
        t.append("Energía: " + {"balanced": "equilibrado", "performance": "rendimiento",
                                "power-saver": "ahorro"}[aj["energia"]])
    for clave, etiqueta, si, no in (("animaciones", "Animaciones", "activadas", "desactivadas"),
                                    ("desenfoque", "Desenfoque", "activado", "desactivado")):
        if aj.get(clave) in ("si", "no"):
            t.append(f"{etiqueta}: {si if aj[clave] == 'si' else no}")
    if aj.get("no_molestar") in ("si", "no"):
        t.append("No molestar: " + ("activado" if aj["no_molestar"] == "si" else "desactivado"))
    if "inhibir_inactividad" in aj:
        t.append("Inactividad: se evita el bloqueo y el apagado de pantalla" if aj["inhibir_inactividad"] == "si"
                 else "Inactividad: sin inhibir")
    if aj.get("modo_noche") in ("si", "no"):
        t.append("Modo noche: " + ("activado" if aj["modo_noche"] == "si" else "desactivado"))
    return t


class SistemaReal:
    """Lo que el motor de perfiles toca de verdad: ppd y logind por D-Bus (bus de sistema,
    llamadas sincronas con timeout de 3 s), swaync-client, hyprctl y modo-noche como
    subprocesos. `ejecutar` sustituye a subprocess.run en las pruebas."""

    def __init__(self, ejecutar=None):
        self.ejecutar = ejecutar or subprocess.run

    # -- subprocesos ---------------------------------------------------------
    def _correr(self, orden, timeout, env=None):
        extra = {} if env is None else {"env": env}
        try:
            return self.ejecutar(orden, capture_output=True, text=True, timeout=timeout, **extra)
        except subprocess.TimeoutExpired:
            raise OSError(f"{os.path.basename(orden[0])} no responde")

    # -- D-Bus ---------------------------------------------------------------
    def _llamada(self, destino, objeto, interfaz, metodo, params):
        GLib, Gio = _gi()
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        return con.call_sync(destino, objeto, interfaz, metodo, params, None, Gio.DBusCallFlags.NONE, 3000, None)

    def _propiedad(self, destino, objeto, interfaz, nombre):
        GLib, _Gio = _gi()
        r = self._llamada(destino, objeto, "org.freedesktop.DBus.Properties", "Get",
                          GLib.Variant("(ss)", (interfaz, nombre)))
        return r.unpack()[0]

    # -- power-profiles-daemon -----------------------------------------------
    def ppd_perfiles(self):
        """Nombres de perfil que ofrece ppd, o None si no responde."""
        try:
            return [str(d["Profile"]) for d in self._propiedad(PPD[0], PPD[1], PPD[0], "Profiles") if "Profile" in d]
        except Exception:
            return None

    def ppd_degradado(self):
        try:
            return str(self._propiedad(PPD[0], PPD[1], PPD[0], "PerformanceDegraded") or "") or None
        except Exception:
            return None

    def ppd_retener(self, perfil):
        GLib, _Gio = _gi()
        return self._llamada(PPD[0], PPD[1], PPD[0], "HoldProfile",
                             GLib.Variant("(sss)", (perfil, "Perfil de Jaime0", "jaime0"))).unpack()[0]

    def ppd_liberar(self, cookie):
        GLib, _Gio = _gi()
        self._llamada(PPD[0], PPD[1], PPD[0], "ReleaseProfile", GLib.Variant("(u)", (int(cookie),)))

    # -- logind --------------------------------------------------------------
    def inhibir_disponible(self):
        try:
            self._propiedad("org.freedesktop.login1", "/org/freedesktop/login1",
                            "org.freedesktop.login1.Manager", "BlockInhibited")
            return True
        except Exception:
            return False

    def inhibir_abrir(self, motivo):
        """Descriptor del inhibidor 'idle'; hay que mantenerlo abierto."""
        GLib, Gio = _gi()
        con = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        r, fds = con.call_with_unix_fd_list_sync(
            "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "Inhibit",
            GLib.Variant("(ssss)", ("idle", "Jaime0", motivo, "block")), GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE, 3000, None, None)
        return fds.get(r.unpack()[0])

    def inhibir_cerrar(self, fd):
        os.close(fd)

    # -- swaync --------------------------------------------------------------
    def dnd_disponible(self):
        return shutil.which("swaync-client") is not None

    def dnd_leer(self):
        r = self._correr(["swaync-client", "--get-dnd", "--skip-wait"], 3)
        valor = (r.stdout or "").strip().lower()
        if r.returncode != 0 or valor not in ("true", "false"):
            raise OSError("swaync no responde")
        return valor == "true"

    def dnd_poner(self, activo):
        r = self._correr(["swaync-client", "--dnd-on" if activo else "--dnd-off", "--skip-wait"], 3)
        if r.returncode != 0:
            raise OSError("swaync no ha aceptado el cambio")

    # -- Hyprland ------------------------------------------------------------
    def hypr_disponible(self):
        return firma_hyprland() is not None and shutil.which("hyprctl") is not None

    def hypr_recargar(self):
        r = self._correr(["hyprctl", "reload"], 5, env=entorno_hyprland(firma_hyprland()))
        if r.returncode != 0:
            raise OSError("hyprctl reload ha fallado")

    # -- modo noche ----------------------------------------------------------
    def noche_disponible(self):
        return programa_hermano("modo-noche") is not None and shutil.which("hyprsunset") is not None

    def noche_leer(self):
        programa = programa_hermano("modo-noche")
        if not programa:
            raise OSError("modo-noche no está instalado")
        valor = (self._correr([programa, "estado"], 3).stdout or "").strip()
        if valor not in ("encendido", "apagado"):
            raise OSError("modo-noche no informa de su estado")
        return valor == "encendido"

    def noche_poner(self, activo):
        programa = programa_hermano("modo-noche")
        if not programa:
            raise OSError("modo-noche no está instalado")
        if self._correr([programa, "encender" if activo else "apagar"], 5).returncode != 0:
            raise OSError("modo-noche no ha aceptado el cambio")

    # -- capacidades ---------------------------------------------------------
    def capacidades(self):
        ppd = self.ppd_perfiles()
        return {"energia": [p for p in (ppd or []) if p in VALORES_AJUSTE["energia"]],
                "ppd": ppd is not None,
                "no_molestar": self.dnd_disponible(),
                "animaciones": self.hypr_disponible(),
                "inhibir_inactividad": self.inhibir_disponible(),
                "modo_noche": self.noche_disponible()}


class MotorPerfiles:
    """Perfil activo, instantaneas por ajuste y aplicadores. Un solo hilo: el de efectos del
    servicio (Trabajador). Desde el bucle solo se lee doc_estado."""

    def __init__(self, sistema, dir_ejecucion, dir_estado, archivo_custom, evento=None, notificar=None,
                 cambio=None, animaciones_usuario=None):
        self.sistema = sistema
        self.animaciones_usuario = animaciones_usuario or nivel_animaciones_usuario   # callable -> no|sutil|suave
        self.dir_ejecucion = dir_ejecucion      # donde vive perfil.ajustes (tmpfs)
        self.dir_estado = dir_estado            # callable -> ~/.local/state/jaime0
        self.archivo_custom = archivo_custom    # callable -> ~/.config/jaime0/perfil-personalizado.json
        self.evento = evento or (lambda *a, **k: None)
        self.notificar = notificar or (lambda: None)
        self.cambio = cambio or (lambda perfil, origen: None)     # (id, origen) al cambiar de perfil
        self.activo = self.anterior = self.origen = None
        self.fallos = []
        self.cookie = self.retencion = None
        self.inhibidor = self.inhibidor_nombre = None
        self.degradado = None
        self.capa_sin_recargar = False
        self.instantaneas = {}                  # {"no_molestar": bool, "modo_noche": bool}
        self._cargar_instantaneas()

    # -- definiciones --------------------------------------------------------
    def personalizado(self):
        """(ajustes, error) de perfil-personalizado.json; sin archivo = todo base, sin error."""
        try:
            with open(self.archivo_custom(), encoding="utf-8") as f:
                doc = json.load(f)
        except FileNotFoundError:
            return {}, None
        except (OSError, ValueError) as e:
            return {}, f"no se pudo leer el perfil personalizado: {e}"
        if not isinstance(doc, dict) or doc.get("v") != 1 or not isinstance(doc.get("ajustes"), dict):
            return {}, "el perfil personalizado no tiene el formato esperado"
        aj, error = validar_ajustes(doc["ajustes"])
        return aj, (f"el perfil personalizado no es válido: {error}" if error else None)

    def definiciones(self):
        aj, error = self.personalizado()
        d = [dict(p, error=None) for p in PERFILES]
        d.append(dict(PERFIL_CUSTOM, ajustes=aj, error=error))
        return d

    def buscar(self, texto):
        return next((d for d in self.definiciones() if d["id"] == normalizar_perfil(texto)), None)

    # -- disponibilidad ------------------------------------------------------
    @staticmethod
    def motivo_no_disponible(aj, caps):
        motivos = []
        e = aj.get("energia", "balanced")
        if e != "balanced":
            if not caps.get("ppd"):
                motivos.append("power-profiles-daemon no está disponible")
            elif e not in caps["energia"]:
                motivos.append("este equipo no ofrece el perfil de energía "
                               + ("de alto rendimiento" if e == "performance" else "de ahorro"))
        if any(aj.get(k) in ("si", "no") for k in CAPA_CLAVES) and not caps.get("animaciones"):
            motivos.append("Hyprland no está disponible (animaciones y desenfoque)")
        if aj.get("no_molestar") in ("si", "no") and not caps.get("no_molestar"):
            motivos.append("swaync no está instalado (no molestar)")
        if aj.get("inhibir_inactividad") == "si" and not caps.get("inhibir_inactividad"):
            motivos.append("logind no responde (inhibir inactividad)")
        if aj.get("modo_noche") in ("si", "no") and not caps.get("modo_noche"):
            motivos.append("no hay modo noche (falta hyprsunset)")
        return "; ".join(motivos) or None

    def perfiles_doc(self):
        caps = self.sistema.capacidades()
        perfiles = []
        for d in self.definiciones():
            motivo = self.motivo_no_disponible(d["ajustes"], caps)
            perfiles.append({"id": d["id"], "nombre": d["nombre"], "descripcion": d["descripcion"],
                             "cambios": textos_cambios(d["ajustes"]), "ajustes": dict(d["ajustes"]),
                             "disponible": motivo is None, "motivo": motivo})
        aj, error = self.personalizado()
        return {"ok": True, "v": VERSION_DATOS, "activo": self.activo, "anterior": self.anterior,
                "perfiles": perfiles,
                "capacidades": {k: caps[k] for k in ("energia", "no_molestar", "animaciones",
                                                     "inhibir_inactividad", "modo_noche")},
                "personalizado": {"ajustes": aj, "error": error}}

    # -- instantaneas (de sesion, en el directorio de ejecucion) ---------------
    def _archivo_instantaneas(self):
        return os.path.join(self.dir_ejecucion, "perfil-instantaneas.json")

    def _cargar_instantaneas(self):
        try:
            with open(self._archivo_instantaneas(), encoding="utf-8") as f:
                doc = json.load(f)
            ajustes = doc.get("ajustes") if isinstance(doc, dict) else None
            if isinstance(ajustes, dict):
                self.instantaneas = {k: v for k, v in ajustes.items()
                                     if k in ("no_molestar", "modo_noche") and isinstance(v, bool)}
        except (OSError, ValueError):
            pass

    def _guardar_instantaneas(self):
        try:
            if self.instantaneas:
                escribir_json(self._archivo_instantaneas(), {"v": VERSION_DATOS, "ajustes": self.instantaneas})
            elif os.path.exists(self._archivo_instantaneas()):
                os.remove(self._archivo_instantaneas())
        except OSError:
            registrar("no se pudieron guardar las instantáneas del perfil:\n" + traceback.format_exc())

    # -- aplicadores ---------------------------------------------------------
    def _liberar_energia(self):
        cookie, self.cookie, self.retencion = self.cookie, None, None
        if cookie is not None:
            try:
                self.sistema.ppd_liberar(cookie)
            except Exception:
                registrar("no se pudo liberar la retención de energía:\n" + traceback.format_exc())

    def retencion_obsoleta(self, activo):
        """ppd suelta las retenciones cuando alguien cambia el perfil por fuera. Si el perfil
        activo real ya no es el que retenemos, la cookie no vale: se olvida (y se intenta
        soltar, por si ppd aun la guardara) para que volver a pedirlo vuelva a retener."""
        if self.cookie is not None and activo is not None and activo != self.retencion:
            self._liberar_energia()

    def _ap_energia(self, valor):
        if valor == "balanced":
            self._liberar_energia()
        elif self.cookie is None or self.retencion != valor:
            self._liberar_energia()         # una sola retencion a la vez
            self.cookie = self.sistema.ppd_retener(valor)
            self.retencion = valor

    def _ap_capa(self, aj):
        deseado = [(k, aj[k]) for k in CAPA_CLAVES if aj.get(k) in ("si", "no")]
        if deseado and not self.sistema.hypr_disponible():
            raise OSError("Hyprland no está disponible")
        # hyprland.lua convierte la animacion "si" en "sutil" por encima del ajuste del usuario
        # (rebajaria "suave"): "si" solo escribe la clave si el usuario las tiene apagadas.
        deseado = [(k, "sutil" if (k, v) == ("animaciones", "si") else v) for k, v in deseado
                   if (k, v) != ("animaciones", "si") or self.animaciones_usuario() == "no"]
        archivo = os.path.join(self.dir_ejecucion, "perfil.ajustes")
        nuevo = "".join(f"{k} = {v}\n" for k, v in deseado) or None
        try:
            with open(archivo, encoding="utf-8") as f:
                actual = f.read()
        except OSError:
            actual = None
        if nuevo == actual and not self.capa_sin_recargar:
            return
        if nuevo is None:
            try:
                os.remove(archivo)
            except OSError:
                pass
        else:
            tmp = archivo + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(nuevo)
            os.replace(tmp, archivo)
        self.capa_sin_recargar = True
        if self.sistema.hypr_disponible():
            self.sistema.hypr_recargar()
        elif deseado:
            raise OSError("no se pudo recargar Hyprland")
        self.capa_sin_recargar = False

    def _ap_tri(self, clave, valor, leer, poner):
        """Ajuste si/no/base con instantanea del valor real previo."""
        if valor == "base":
            if clave in self.instantaneas:
                previo = self.instantaneas[clave]
                if leer() != previo:
                    poner(previo)
                del self.instantaneas[clave]        # solo si se restauro (si falla, se conserva)
                self._guardar_instantaneas()
            return
        quiero = valor == "si"
        creada = clave not in self.instantaneas
        actual = leer()
        if creada:
            self.instantaneas[clave] = actual
        try:
            if actual != quiero:
                poner(quiero)
        except Exception:
            if creada:
                del self.instantaneas[clave]        # no cambio nada: sin instantanea incoherente
            raise
        if creada:
            self._guardar_instantaneas()

    def _ap_inhibir(self, valor, nombre):
        if valor == "si":
            if self.inhibidor is not None and self.inhibidor_nombre == nombre:
                return
            nuevo = self.sistema.inhibir_abrir(f"Perfil {nombre}: sin bloqueo ni apagado de pantalla")
            self._cerrar_inhibidor()
            self.inhibidor, self.inhibidor_nombre = nuevo, nombre
        else:
            self._cerrar_inhibidor()

    def _cerrar_inhibidor(self):
        fd, self.inhibidor, self.inhibidor_nombre = self.inhibidor, None, None
        if fd is not None:
            try:
                self.sistema.inhibir_cerrar(fd)
            except Exception:
                registrar("no se pudo cerrar el inhibidor:\n" + traceback.format_exc())

    # -- aplicar -------------------------------------------------------------
    def aplicar(self, pid, origen="usuario", persistir=True):
        d = self.buscar(pid)
        if d is None:
            return {"ok": False, "error": f"perfil desconocido: {pid}"}
        aj = d["ajustes"]
        motivo = self.motivo_no_disponible(aj, self.sistema.capacidades())
        if motivo:
            return {"ok": False, "error": f"El perfil {d['nombre']} no está disponible: {motivo}"}
        fallos = [d["error"]] if d["error"] else []
        s = self.sistema
        pasos = (("Energía", lambda: self._ap_energia(aj.get("energia", "balanced"))),
                 ("Animaciones y desenfoque", lambda: self._ap_capa(aj)),
                 ("No molestar", lambda: self._ap_tri("no_molestar", aj.get("no_molestar", "base"),
                                                      s.dnd_leer, s.dnd_poner)),
                 ("Inactividad", lambda: self._ap_inhibir(aj.get("inhibir_inactividad", "no"), d["nombre"])),
                 ("Modo noche", lambda: self._ap_tri("modo_noche", aj.get("modo_noche", "base"),
                                                     s.noche_leer, s.noche_poner)))
        for etiqueta, paso in pasos:
            try:
                paso()
            except Exception as e:
                registrar(f"error al aplicar {etiqueta}:\n" + traceback.format_exc())
                fallos.append(f"{etiqueta}: {e or type(e).__name__}")
        cambia = d["id"] != self.activo
        if origen != "inicio" and cambia:
            self.anterior = self.activo
        self.activo, self.origen, self.fallos = d["id"], origen, fallos
        if persistir:
            self.guardar()
        if cambia or origen == "inicio":
            self.evento(f"Perfil: {d['nombre']}", "perfil", "INFO", None, origen)
        self.notificar()
        if cambia and origen != "inicio":
            try:
                self.cambio(d["id"], origen)
            except Exception:
                registrar("error al avisar del cambio de perfil:\n" + traceback.format_exc())
        return {"ok": True, "activo": d["id"], "nombre": d["nombre"], "fallos": list(fallos)}

    def aplicar_anterior(self, origen="usuario"):
        if not self.anterior:
            return {"ok": False, "error": "no hay un perfil anterior"}
        return self.aplicar(self.anterior, origen)

    def guardar_personalizado(self, ajustes):
        """Valida y guarda CUSTOM; si esta activo, lo vuelve a aplicar."""
        aj, error = validar_ajustes(ajustes)
        if error:
            return {"ok": False, "error": error}
        try:
            archivo = self.archivo_custom()
            os.makedirs(os.path.dirname(archivo), exist_ok=True)
            escribir_json(archivo, {"v": VERSION_DATOS, "ajustes": aj})
        except OSError as e:
            return {"ok": False, "error": f"no se pudo guardar el perfil personalizado: {e}"}
        r = {"ok": True, "ajustes": aj, "fallos": []}
        if self.activo == "custom":
            ap = self.aplicar("custom", self.origen if self.origen in ("usuario", "regla") else "usuario")
            if not ap["ok"]:
                return {"ok": False, "error": "guardado, pero no se puede aplicar: " + ap["error"]}
            r["fallos"] = ap["fallos"]
        return r

    # -- persistencia y arranque ---------------------------------------------
    def _archivo_perfil(self):
        return os.path.join(self.dir_estado(), "perfil.json")

    def guardar(self):
        try:
            escribir_json(self._archivo_perfil(), {"v": VERSION_DATOS, "activo": self.activo,
                                                   "anterior": self.anterior})
        except OSError:
            registrar("no se pudo guardar perfil.json:\n" + traceback.format_exc())

    def iniciar(self):
        """Reaplica el perfil guardado; si no se puede, balanced y se anota el motivo."""
        ids = [p["id"] for p in PERFILES] + ["custom"]
        guardado, nota = None, None
        try:
            with open(self._archivo_perfil(), encoding="utf-8") as f:
                doc = json.load(f)
            if (isinstance(doc, dict) and doc.get("v") == 1 and doc.get("activo") in ids
                    and doc.get("anterior") in ids + [None]):
                guardado = doc["activo"]
                self.anterior = doc["anterior"]
            else:
                nota = "el perfil guardado no es válido"
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            nota = "no se pudo leer el perfil guardado"
        if guardado is not None:
            r = self.aplicar(guardado, "inicio")
            if r["ok"]:
                self.refrescar_degradado()
                return r
            nota = r["error"]
        r = self.aplicar(PERFIL_BASE, "inicio", persistir=nota is None)    # con motivo: no pisa lo guardado
        if nota:
            self.fallos.insert(0, nota)
            self.evento(f"Perfil guardado no aplicado: {nota}", "perfil", "WARNING", None, "inicio")
            self.notificar()
        self.refrescar_degradado()
        return r

    def refrescar_degradado(self):
        try:
            self.degradado = self.sistema.ppd_degradado()
        except Exception:
            self.degradado = None

    def doc_estado(self, energia):
        nombre = next((d["nombre"] for d in self.definiciones() if d["id"] == self.activo), None)
        return {"activo": self.activo, "nombre": nombre, "anterior": self.anterior, "origen": self.origen,
                "energia": energia, "retencion": self.retencion, "degradado": self.degradado,
                "fallos": list(self.fallos)}
