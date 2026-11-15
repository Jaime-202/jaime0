#!/usr/bin/env python3
"""Pruebas del motor de reglas (Fase 6) de jaime0-servicio y del cliente jaime0-reglas. Reloj,
subprocesos, hilos, temporizadores y fuentes de eventos se inyectan: no hay D-Bus, sockets ni
procesos reales.

    python3 -m unittest discover -s pruebas -v
"""
import contextlib
import datetime
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
BIN = REPO / "config/includes.chroot_after_packages/usr/local/bin"


def cargar(nombre, programa):
    cargador = importlib.machinery.SourceFileLoader(nombre, str(BIN / programa))
    spec = importlib.util.spec_from_loader(cargador.name, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


S = cargar("jaime0_servicio_reglas", "jaime0-servicio")
R = cargar("jaime0_reglas_pruebas", "jaime0-reglas")

APPS = {"org.gnome.Calculator": "Calculadora", "firefox": "Firefox"}


def proc(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


class Reloj:
    def __init__(self, dt=datetime.datetime(2026, 11, 16, 10, 0, 0)):     # lunes
        self.t = time.mktime(dt.timetuple())

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s

    def dt(self):
        return datetime.datetime.fromtimestamp(self.t)


class Ejecutor:
    """Imita subprocess.run: anota las llamadas y responde segun el nombre del programa."""

    def __init__(self):
        self.llamadas, self.resp = [], {}

    def __call__(self, orden, **k):
        self.llamadas.append((list(orden), k))
        r = self.resp.get(os.path.basename(orden[0]), proc())
        if isinstance(r, Exception):
            raise r
        return r(orden) if callable(r) else r

    @property
    def ordenes(self):
        return [o for o, _k in self.llamadas]


def regla(nombre="Prueba", cuando=None, hacer=None, **extra):
    d = {"nombre": nombre, "cuando": {"evento": "cargador", "estado": "conectado"} if cuando is None else cuando,
         "hacer": [{"accion": "notificar", "titulo": "Hola", "texto": "Mundo"}] if hacer is None else hacer}
    d.update(extra)
    return d


def stat_falso(mode, uid=1000):
    return types.SimpleNamespace(st_mode=mode, st_uid=uid)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-reglas-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.archivo = os.path.join(self.tmp, "config", "reglas.json")
        self.ejecuciones = os.path.join(self.tmp, "estado", "ejecuciones.jsonl")
        os.makedirs(os.path.dirname(self.ejecuciones))
        self.reloj, self.ejec = Reloj(), Ejecutor()
        self.est, self.apps = {"perfil": "balanced", "cargador": True, "bateria": 80}, dict(APPS)
        self.incs, self.actividad, self.avisos, self.dormidos, self.perfiles = [], [], [], [], []
        self.thumbs = os.path.join(self.tmp, "miniaturas")
        self.scripts = os.path.join(self.tmp, "scripts")
        self.disp = {"eventos": {}, "acciones": {}}
        self.motor = self.crear_motor()

    def crear_motor(self, **k):
        def aplicar_perfil(pid):
            self.perfiles.append(pid)
            return {"ok": True, "nombre": pid.upper(), "fallos": []}

        args = dict(reloj=self.reloj, ejecutar=self.ejec, estado=lambda: self.est, aplicar_perfil=aplicar_perfil,
                    apps=lambda: self.apps, disponibilidad=lambda: self.disp, incidencia=self.incs.append,
                    evento=lambda *a, **kw: self.actividad.append(a), notificar=lambda: self.avisos.append(1),
                    dormir=self.dormidos.append, dir_miniaturas=lambda: self.thumbs, dir_scripts=lambda: self.scripts,
                    uid=1000)
        args.update(k)
        return S.MotorReglas(lambda: self.archivo, lambda: self.ejecuciones, **args)

    def guardar(self, nombre="Prueba", **k):
        r = self.motor.guardar(regla(nombre, **k))
        self.assertTrue(r["ok"], r)
        return r["regla"]

    def historial(self):
        return S.leer_jsonl(self.ejecuciones)

    def leer_reglas(self):
        with open(self.archivo, encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Validacion
# ---------------------------------------------------------------------------

EVENTOS_VALIDOS = [
    {"evento": "bateria_baja"}, {"evento": "bateria_baja", "umbral": 5}, {"evento": "bateria_baja", "umbral": 95},
    {"evento": "cargador", "estado": "conectado"}, {"evento": "cargador", "estado": "desconectado"},
    {"evento": "bluetooth", "estado": "conectado"},
    {"evento": "bluetooth", "estado": "desconectado", "tipo": "audio", "nombre": "WH-1000"},
    {"evento": "monitor", "estado": "conectado"}, {"evento": "monitor", "estado": "desconectado"},
    {"evento": "aplicacion", "estado": "abierta", "clase": "firefox"},
    {"evento": "aplicacion", "estado": "cerrada", "clase": "Org.Gnome.Calculator"},
    {"evento": "hora", "hora": "08:30"}, {"evento": "hora", "hora": "23:59", "dias": [0, 1, 6]},
    {"evento": "hora", "hora": "00:00", "dias": []},
    {"evento": "red", "estado": "conectada"}, {"evento": "red", "estado": "desconectada", "wifi": "Mi Casa"},
    {"evento": "suspension", "estado": "suspender"}, {"evento": "suspension", "estado": "reanudar"},
    {"evento": "inactividad", "estado": "inactivo"}, {"evento": "inactividad", "estado": "activo"},
    {"evento": "estado_sistema", "estado": "WARNING"}, {"evento": "estado_sistema", "estado": "CRITICAL"},
    {"evento": "estado_sistema", "estado": "ONLINE"},
    {"evento": "servicio_fallido"}, {"evento": "perfil", "perfil": "focus"},
    {"evento": "perfil", "perfil": "POWER SAVER"},
]

EVENTOS_INVALIDOS = [
    {"evento": "nada"}, {"estado": "conectado"}, {"evento": "bateria_baja", "umbral": 4},
    {"evento": "bateria_baja", "umbral": 96}, {"evento": "bateria_baja", "umbral": "20"},
    {"evento": "bateria_baja", "umbral": True}, {"evento": "bateria_baja", "umbral": 20.5},
    {"evento": "cargador"}, {"evento": "cargador", "estado": "enchufado"},
    {"evento": "bluetooth", "estado": "conectado", "tipo": "teclado"},
    {"evento": "bluetooth", "estado": "conectado", "nombre": "x" * 61},
    {"evento": "bluetooth", "estado": "conectado", "nombre": ""},
    {"evento": "monitor", "estado": "abierta"},
    {"evento": "aplicacion", "estado": "abierta"}, {"evento": "aplicacion", "estado": "abierta", "clase": ""},
    {"evento": "aplicacion", "estado": "abierta", "clase": "x" * 81},
    {"evento": "aplicacion", "estado": "abierta", "clase": "a\nb"},
    {"evento": "hora"}, {"evento": "hora", "hora": "24:00"}, {"evento": "hora", "hora": "9:00"},
    {"evento": "hora", "hora": "12:60"}, {"evento": "hora", "hora": 900},
    {"evento": "hora", "hora": "08:00", "dias": [7]}, {"evento": "hora", "hora": "08:00", "dias": [-1]},
    {"evento": "hora", "hora": "08:00", "dias": ["1"]}, {"evento": "hora", "hora": "08:00", "dias": [True]},
    {"evento": "hora", "hora": "08:00", "dias": 3},
    {"evento": "red", "estado": "conectada", "wifi": "x" * 65},
    {"evento": "red", "estado": "online"}, {"evento": "suspension", "estado": "dormir"},
    {"evento": "inactividad", "estado": "idle"}, {"evento": "estado_sistema", "estado": "warning"},
    {"evento": "servicio_fallido", "estado": "x"}, {"evento": "perfil", "perfil": "turbo"},
    {"evento": "perfil"}, {"evento": "cargador", "estado": "conectado", "extra": 1},
]

CONDICIONES_VALIDAS = [
    {"condicion": "perfil_es", "perfil": "focus"}, {"condicion": "cargador", "conectado": True},
    {"condicion": "cargador", "conectado": False}, {"condicion": "bateria_menor", "valor": 1},
    {"condicion": "bateria_menor", "valor": 100}, {"condicion": "bateria_mayor", "valor": 0},
    {"condicion": "bateria_mayor", "valor": 99}, {"condicion": "entre_horas", "desde": "22:00", "hasta": "07:00"},
    {"condicion": "dias", "dias": [0, 4]},
]

CONDICIONES_INVALIDAS = [
    {"condicion": "nada"}, {"condicion": "perfil_es", "perfil": "turbo"}, {"condicion": "cargador", "conectado": "si"},
    {"condicion": "cargador"}, {"condicion": "bateria_menor", "valor": 0}, {"condicion": "bateria_menor", "valor": 101},
    {"condicion": "bateria_mayor", "valor": -1}, {"condicion": "bateria_mayor", "valor": 100},
    {"condicion": "bateria_mayor", "valor": "50"}, {"condicion": "entre_horas", "desde": "22:00"},
    {"condicion": "entre_horas", "desde": "22:00", "hasta": "22:00"},
    {"condicion": "entre_horas", "desde": "25:00", "hasta": "07:00"},
    {"condicion": "dias", "dias": []}, {"condicion": "dias", "dias": [8]}, {"condicion": "dias"},
    "perfil_es", {"perfil": "focus"},
]

ACCIONES_VALIDAS = [
    {"accion": "perfil", "perfil": "power-saver"}, {"accion": "modo_noche", "estado": "encender"},
    {"accion": "modo_noche", "estado": "apagar"}, {"accion": "no_molestar", "estado": "activar"},
    {"accion": "no_molestar", "estado": "desactivar"}, {"accion": "notificar", "titulo": "T", "texto": "X"},
    {"accion": "notificar", "titulo": "t" * 80, "texto": "x" * 300},
    {"accion": "abrir_aplicacion", "id": "firefox"}, {"accion": "abrir_aplicacion", "id": "org.gnome.Calculator"},
    {"accion": "volumen", "nivel": 0}, {"accion": "volumen", "nivel": 100},
    {"accion": "silenciar", "estado": "si"}, {"accion": "silenciar", "estado": "no"},
    {"accion": "salida_audio", "nombre": "WH-1000"},
    {"accion": "mantenimiento", "tarea": "limpiar_miniaturas"},
    {"accion": "mantenimiento", "tarea": "comprobar_actualizaciones"},
    {"accion": "script", "nombre": "copia.sh"},
]

ACCIONES_INVALIDAS = [
    {"accion": "apagar"}, {"accion": "sudo", "orden": "ls"}, {"accion": "perfil", "perfil": "turbo"},
    {"accion": "modo_noche", "estado": "alternar"}, {"accion": "no_molestar", "estado": "si"},
    {"accion": "notificar", "titulo": "t" * 81, "texto": "x"}, {"accion": "notificar", "titulo": "t", "texto": "x" * 301},
    {"accion": "notificar", "titulo": "t", "texto": "linea1\nlinea2"}, {"accion": "notificar", "titulo": "a\x1b[31m", "texto": "x"},
    {"accion": "notificar", "titulo": "", "texto": "x"}, {"accion": "notificar", "titulo": "t"},
    {"accion": "abrir_aplicacion", "id": "no.existe"}, {"accion": "abrir_aplicacion", "id": "../firefox"},
    {"accion": "abrir_aplicacion", "id": "1"}, {"accion": "abrir_aplicacion", "id": "firefox; rm -rf ~"},
    {"accion": "abrir_aplicacion"}, {"accion": "volumen", "nivel": -1}, {"accion": "volumen", "nivel": 101},
    {"accion": "volumen", "nivel": True}, {"accion": "volumen", "nivel": "50"}, {"accion": "silenciar", "estado": "mute"},
    {"accion": "salida_audio", "nombre": ""}, {"accion": "salida_audio", "nombre": "x" * 81},
    {"accion": "mantenimiento", "tarea": "borrar_todo"}, {"accion": "script", "nombre": "../x.sh"},
    {"accion": "script", "nombre": "sub/x.sh"}, {"accion": "script", "nombre": "sub\\x.sh"},
    {"accion": "script", "nombre": ".."}, {"accion": "script", "nombre": "a..b"}, {"accion": "script", "nombre": ""},
    {"accion": "script", "nombre": "x.sh", "args": ["-c"]},
]


class PruebasValidacion(Base):
    def validar(self, **k):
        return S.validar_regla(regla(**k), {"apps": APPS, "estricto": True})

    def test_cada_evento_valido(self):
        for ev in EVENTOS_VALIDOS:
            with self.subTest(ev=ev):
                r, error = self.validar(cuando=ev)
                self.assertIsNone(error, error)
                self.assertEqual(r["cuando"]["evento"], ev["evento"])

    def test_cada_evento_invalido(self):
        for ev in EVENTOS_INVALIDOS:
            with self.subTest(ev=ev):
                self.assertIsNotNone(self.validar(cuando=ev)[1])

    def test_valores_por_defecto_del_evento(self):
        self.assertEqual(self.validar(cuando={"evento": "bateria_baja"})[0]["cuando"], {"evento": "bateria_baja", "umbral": 20})
        self.assertEqual(self.validar(cuando={"evento": "bluetooth", "estado": "conectado"})[0]["cuando"],
                         {"evento": "bluetooth", "estado": "conectado", "tipo": "cualquiera"})
        self.assertEqual(self.validar(cuando={"evento": "hora", "hora": "08:00", "dias": [3, 1, 1]})[0]["cuando"]["dias"], [1, 3])
        self.assertEqual(self.validar(cuando={"evento": "hora", "hora": "08:00"})[0]["cuando"]["dias"], [])
        self.assertEqual(self.validar(cuando={"evento": "perfil", "perfil": "POWER SAVER"})[0]["cuando"]["perfil"], "power-saver")

    def test_cada_condicion_valida_e_invalida(self):
        for c in CONDICIONES_VALIDAS:
            with self.subTest(c=c):
                self.assertIsNone(self.validar(si=[c])[1])
        for c in CONDICIONES_INVALIDAS:
            with self.subTest(c=c):
                self.assertIsNotNone(self.validar(si=[c])[1])

    def test_cada_accion_valida_e_invalida(self):
        for a in ACCIONES_VALIDAS:
            with self.subTest(a=a):
                self.assertIsNone(self.validar(hacer=[a])[1])
        for a in ACCIONES_INVALIDAS:
            with self.subTest(a=a):
                self.assertIsNotNone(self.validar(hacer=[a])[1])

    def test_ids_de_aplicacion_inexistentes(self):
        _r, error = self.validar(hacer=[{"accion": "abrir_aplicacion", "id": "no.existe"}])
        self.assertIn("no está en la lista de aplicaciones disponibles", error)

    def test_sin_lista_de_aplicaciones_se_rechaza_al_guardar_pero_no_al_cargar(self):
        a = [{"accion": "abrir_aplicacion", "id": "firefox"}]
        self.assertIsNotNone(S.validar_regla(regla(hacer=a), {"apps": None, "estricto": True})[1])
        self.assertIsNone(S.validar_regla(regla(hacer=a), {"apps": None, "estricto": False})[1])
        self.assertIsNone(S.validar_regla(regla(hacer=a), {"apps": lambda: None, "estricto": False})[1])

    def test_limites_de_acciones_y_condiciones(self):
        a = {"accion": "volumen", "nivel": 10}
        self.assertIsNone(self.validar(hacer=[a] * 5)[1])
        self.assertIsNotNone(self.validar(hacer=[a] * 6)[1])
        self.assertIsNotNone(self.validar(hacer=[])[1])
        self.assertIsNotNone(self.validar(hacer="volumen")[1])
        c = {"condicion": "cargador", "conectado": True}
        self.assertIsNone(self.validar(si=[c] * 10)[1])
        self.assertIsNotNone(self.validar(si=[c] * 11)[1])

    def test_campos_de_la_regla(self):
        self.assertIsNone(self.validar(nombre="x" * 60)[1])
        for malo in ("", "   ", "x" * 61, "a\nb", 5, None):
            with self.subTest(nombre=malo):
                self.assertIsNotNone(self.validar(nombre=malo)[1])
        self.assertIsNotNone(self.validar(activa="si")[1])
        self.assertIsNotNone(self.validar(revisar=1)[1])
        self.assertIsNotNone(self.validar(extra=1)[1])
        self.assertIsNotNone(self.validar(id="Mayusculas")[1])
        self.assertIsNotNone(self.validar(id="../x")[1])
        self.assertIsNone(self.validar(ultima={"t": 1})[1])             # lo anade el listado
        self.assertIsNotNone(S.validar_regla([1], {"apps": APPS})[1])

    def test_regla_perfil_a_perfil_rechazada(self):
        r = regla(cuando={"evento": "perfil", "perfil": "focus"}, hacer=[{"accion": "perfil", "perfil": "balanced"}])
        _r, error = S.validar_regla(r, {"apps": APPS})
        self.assertIn("bucle", error)
        r["hacer"] = [{"accion": "notificar", "titulo": "a", "texto": "b"}, {"accion": "perfil", "perfil": "focus"}]
        self.assertIn("bucle", S.validar_regla(r, {"apps": APPS})[1])
        r["hacer"] = [{"accion": "notificar", "titulo": "a", "texto": "b"}]
        self.assertIsNone(S.validar_regla(r, {"apps": APPS})[1])

    def test_perfil_a_perfil_rechazado_al_guardar_y_al_cargar(self):
        malo = regla(cuando={"evento": "perfil", "perfil": "focus"}, hacer=[{"accion": "perfil", "perfil": "balanced"}])
        self.assertFalse(self.motor.guardar(malo)["ok"])
        self.assertEqual(self.motor.reglas, [])
        bueno = dict(regla("Buena"), id="buena", activa=True, revisar=False)
        bueno = S.validar_regla(bueno, {"apps": APPS})[0]
        os.makedirs(os.path.dirname(self.archivo))
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "reglas": [dict(malo, id="bucle", activa=True), bueno]}, f)
        self.motor.cargar()
        self.assertEqual([r["id"] for r in self.motor.reglas], ["buena"])
        self.assertEqual(len(self.motor.errores), 1)
        self.assertEqual(self.motor.errores[0]["id"], "bucle")
        self.assertIn("bucle", self.motor.errores[0]["error"])

    def test_acciones_privilegiadas_se_rechazan(self):
        with mock.patch.object(S, "ACCIONES_PRIVILEGIADAS", ("volumen",)):
            _r, error = self.validar(hacer=[{"accion": "volumen", "nivel": 10}])
            self.assertIn("Esta acción necesita autorización de administrador: no se puede automatizar", error)
            self.assertEqual(S.Acciones(self.ejec, lambda: APPS, None, None, None, None).ejecutar_accion(
                {"accion": "volumen", "nivel": 10}), (False, S.MENSAJE_PRIVILEGIADA))
            self.assertEqual(self.ejec.llamadas, [])
        self.assertEqual(S.ACCIONES_PRIVILEGIADAS, ())
        self.assertIsNone(self.validar(hacer=[{"accion": "volumen", "nivel": 10}])[1])

    def test_ninguna_accion_del_catalogo_es_privilegiada(self):
        self.assertEqual(S.ACCIONES_PRIVILEGIADAS, ())
        self.assertEqual(sorted(a["id"] for a in S.ACCIONES),
                         ["abrir_aplicacion", "mantenimiento", "modo_noche", "no_molestar", "notificar", "perfil",
                          "salida_audio", "script", "silenciar", "volumen"])

    def test_slug_unico(self):
        self.assertEqual(S.slug_regla("Batería baja → ahorro"), "bateria-baja-ahorro")
        self.assertEqual(S.slug_regla("¡¡¡"), "regla")
        self.assertEqual(S.id_unico("x", {"x", "x-2"}), "x-3")
        self.assertEqual(S.id_unico("x", set()), "x")


# ---------------------------------------------------------------------------
# Eventos: bateria, cargador, socket2, bluez, red
# ---------------------------------------------------------------------------

class PruebasBateria(Base):
    def test_flanco_con_histeresis(self):
        armados, saltos = {}, []
        for nivel in (30, 25, 21, 20, 19, 18, 10, 19, 24, 22, 25, 30, 20, 19, 15):
            saltos.append((nivel, S.estado_bateria_baja(armados, nivel, True, False, [20])))
        saltan = [n for n, s in saltos if s]
        # baja de 20 a 19 (salta), no vuelve a saltar por debajo, solo se rearma al llegar a 25
        self.assertEqual(saltan, [19, 19])
        self.assertEqual([n for n, s in saltos].index(19), 4)

    def test_no_salta_si_ya_estaba_por_debajo_al_empezar(self):
        armados = {}
        self.assertEqual(S.estado_bateria_baja(armados, 12, True, False, [20]), [])
        self.assertEqual(S.estado_bateria_baja(armados, 11, True, False, [20]), [])
        self.assertEqual(S.estado_bateria_baja(armados, 26, True, False, [20]), [])
        self.assertEqual(S.estado_bateria_baja(armados, 19, True, False, [20]), [20])

    def test_cargando_no_cuenta_y_el_cargador_rearma(self):
        armados = {}
        S.estado_bateria_baja(armados, 30, True, False, [20])
        self.assertEqual(S.estado_bateria_baja(armados, 19, True, False, [20]), [20])
        self.assertEqual(S.estado_bateria_baja(armados, 18, False, True, [20]), [])     # cargando
        self.assertEqual(armados[20], True)                                             # rearmado por el cargador
        self.assertEqual(S.estado_bateria_baja(armados, 18, True, False, [20]), [20])   # desenchufa por debajo

    def test_varios_umbrales_independientes(self):
        armados = {}
        S.estado_bateria_baja(armados, 60, True, False, [10, 20, 50])
        self.assertEqual(S.estado_bateria_baja(armados, 49, True, False, [10, 20, 50]), [50])
        self.assertEqual(S.estado_bateria_baja(armados, 19, True, False, [10, 20, 50]), [20])
        self.assertEqual(S.estado_bateria_baja(armados, 9, True, False, [10, 20, 50]), [10])

    def muestra(self, nivel, estado="descargando", cargador=False):
        self.motor.muestra({"bateria": {"nivel": nivel, "estado": estado}, "cargador": cargador})
        self.reloj.avanzar(40)          # fuera del enfriamiento

    def test_regla_de_bateria_baja_por_muestras(self):
        self.guardar(cuando={"evento": "bateria_baja", "umbral": 20})
        for nivel in (30, 22, 20, 19, 18, 17, 24, 19):
            self.muestra(nivel)
        self.assertEqual(len(self.historial()), 1)                  # 24 no rearma (hace falta 25)
        self.muestra(25)
        self.muestra(19)
        self.assertEqual(len(self.historial()), 2)
        self.assertEqual(self.historial()[0]["evento"], "Batería baja (19 %)")

    def test_sin_bateria_no_hay_evento(self):
        self.guardar(cuando={"evento": "bateria_baja"})
        self.motor.muestra({"bateria": None, "cargador": None})
        self.assertEqual(self.historial(), [])

    def test_evento_cargador_por_cambio_de_muestras(self):
        self.guardar(cuando={"evento": "cargador", "estado": "desconectado"})
        for c in (True, True, False, False, True, False):
            self.motor.muestra({"bateria": None, "cargador": c})
            self.reloj.avanzar(40)
        self.assertEqual(len(self.historial()), 2)                  # no cuenta la primera muestra
        self.assertEqual(self.historial()[0]["evento"], "Cargador desconectado")

    def test_cargador_none_no_genera_evento(self):
        self.guardar(cuando={"evento": "cargador", "estado": "conectado"})
        for c in (False, None, None, False):
            self.motor.muestra({"bateria": None, "cargador": c})
        self.assertEqual(self.historial(), [])


class PruebasSocket2(unittest.TestCase):
    def setUp(self):
        self.t = [100.0]
        self.a = S.AnalizadorHyprland(reloj=lambda: self.t[0])

    def test_monitoradded_y_v2_cuentan_una_vez(self):
        self.assertEqual(self.a.procesar("monitoradded>>HDMI-A-1"),
                         [("monitor", {"estado": "conectado", "nombre": "HDMI-A-1"})])
        self.assertEqual(self.a.procesar("monitoraddedv2>>1,HDMI-A-1,Dell Inc. U2720Q"), [])
        self.t[0] += 5
        self.assertEqual(self.a.procesar("monitoraddedv2>>2,DP-2,Marca X"),
                         [("monitor", {"estado": "conectado", "nombre": "DP-2"})])

    def test_solo_v2(self):
        self.assertEqual(self.a.procesar("monitoraddedv2>>1,eDP-1,Panel, con coma"),
                         [("monitor", {"estado": "conectado", "nombre": "eDP-1"})])

    def test_monitorremoved(self):
        self.assertEqual(self.a.procesar("monitorremoved>>DP-1"),
                         [("monitor", {"estado": "desconectado", "nombre": "DP-1"})])
        self.assertEqual(self.a.procesar("monitorremovedv2>>1,DP-1,X"), [])
        self.assertEqual(self.a.procesar("monitorremovedv2>>1"), [])

    def test_abierta_solo_con_la_primera_y_cerrada_con_la_ultima(self):
        a = self.a
        self.assertEqual(a.procesar("openwindow>>5f3a,1,Firefox,Mozilla, Firefox"),
                         [("aplicacion", {"estado": "abierta", "clase": "Firefox"})])
        self.assertEqual(a.procesar("openwindow>>7b10,1,firefox,Otra ventana"), [])      # misma clase
        self.assertEqual(a.procesar("openwindow>>9c00,2,kitty,~"),
                         [("aplicacion", {"estado": "abierta", "clase": "kitty"})])
        self.assertEqual(a.procesar("closewindow>>5f3a"), [])                            # queda una
        self.assertEqual(a.procesar("closewindow>>7b10"),
                         [("aplicacion", {"estado": "cerrada", "clase": "firefox"})])
        self.assertEqual(a.procesar("closewindow>>7b10"), [])                            # ya cerrada
        self.assertEqual(a.procesar("closewindow>>desconocida"), [])
        self.assertEqual(a.procesar("openwindow>>5f3a,1,Firefox,x"),
                         [("aplicacion", {"estado": "abierta", "clase": "Firefox"})])   # vuelve a abrirse

    def test_lineas_ajenas_y_rotas(self):
        for linea in ("activewindow>>kitty,~", "workspace>>2", "openwindow>>5f3a,1", "openwindow>>5f3a,1,,sin clase",
                      "", "basura", "closewindow>>"):
            self.assertEqual(self.a.procesar(linea), [], linea)

    def test_sembrar_ventanas_existentes(self):
        self.a.sembrar([("0xaa", "Firefox"), ("0xbb", "firefox"), ("0xcc", "")])
        self.assertEqual(self.a.procesar("openwindow>>dd,1,Firefox,x"), [])             # ya habia firefox
        self.assertEqual(self.a.procesar("closewindow>>aa"), [])
        self.assertEqual(self.a.procesar("closewindow>>bb"), [])
        self.assertEqual(self.a.procesar("closewindow>>dd"),
                         [("aplicacion", {"estado": "cerrada", "clase": "firefox"})])

    def test_reiniciar_olvida_las_ventanas(self):
        self.a.procesar("openwindow>>aa,1,Firefox,x")
        self.a.reiniciar()
        self.assertEqual(self.a.procesar("closewindow>>aa"), [])

    def test_ruta_socket2(self):
        env = {"XDG_RUNTIME_DIR": "/run/user/1000", "HYPRLAND_INSTANCE_SIGNATURE": "abc"}
        propia = os.path.join("/run/user/1000", "hypr", "abc", ".socket2.sock")
        self.assertEqual(S.ruta_socket2(env, listar=lambda p: [], existe=lambda p: p == propia), propia)
        otra = os.path.join("/run/user/1000", "hypr", "nueva", ".socket2.sock")
        self.assertEqual(S.ruta_socket2(env, listar=lambda p: [otra], existe=lambda p: p == otra), otra)
        self.assertIsNone(S.ruta_socket2(env, listar=lambda p: [], existe=lambda p: False))
        self.assertIsNone(S.ruta_socket2({}, listar=lambda p: [], existe=lambda p: True))


class PruebasEventosAplicacion(Base):
    def test_regla_de_aplicacion_abierta_y_cerrada(self):
        self.guardar("Abre", cuando={"evento": "aplicacion", "estado": "abierta", "clase": "FIREFOX"})
        self.guardar("Cierra", cuando={"evento": "aplicacion", "estado": "cerrada", "clase": "firefox"})
        a = S.AnalizadorHyprland()
        for linea in ("openwindow>>1,1,firefox,a", "openwindow>>2,1,firefox,b", "closewindow>>1", "closewindow>>2"):
            for ev, datos in a.procesar(linea):
                self.motor.evento(ev, datos)
        self.assertEqual([(h["nombre"], h["evento"]) for h in self.historial()],
                         [("Abre", "Aplicación abierta: firefox"), ("Cierra", "Aplicación cerrada: firefox")])

    def test_la_clase_no_coincide(self):
        self.guardar(cuando={"evento": "aplicacion", "estado": "abierta", "clase": "firefox"})
        self.assertEqual(self.motor.evento("aplicacion", {"estado": "abierta", "clase": "kitty"}), 0)
        self.assertEqual(self.motor.evento("aplicacion", {"estado": "cerrada", "clase": "firefox"}), 0)


class PruebasBluezYRed(Base):
    def test_info_bluez(self):
        self.assertEqual(S.info_bluez({"Alias": "WH-1000XM4", "Icon": "audio-headset"}), ("WH-1000XM4", True))
        self.assertEqual(S.info_bluez({"Name": "Altavoz", "UUIDs": ["0000110b-0000-1000-8000-00805f9b34fb"]}), ("Altavoz", True))
        self.assertEqual(S.info_bluez({"Alias": "Manos libres", "UUIDs": ["0000111E-0000-1000-8000-00805F9B34FB"]})[1], True)
        self.assertEqual(S.info_bluez({"Alias": "Teclado", "Icon": "input-keyboard",
                                       "UUIDs": ["00001124-0000-1000-8000-00805f9b34fb"]}), ("Teclado", False))
        self.assertEqual(S.info_bluez({}), ("", False))

    def test_cambio_bluez_solo_con_cambios_reales(self):
        previos = {}
        self.assertIsNone(S.cambio_bluez("/d1", {"RSSI": -50}, previos))
        self.assertIsNone(S.cambio_bluez("/d1", {"Connected": False}, previos))          # primera vez, desconectado
        self.assertEqual(S.cambio_bluez("/d1", {"Connected": True}, previos), "conectado")
        self.assertIsNone(S.cambio_bluez("/d1", {"Connected": True}, previos))
        self.assertEqual(S.cambio_bluez("/d1", {"Connected": False}, previos), "desconectado")
        self.assertEqual(S.cambio_bluez("/d2", {"Connected": True}, previos), "conectado")

    def test_regla_bluetooth_por_tipo_y_nombre(self):
        self.guardar("Cualquiera", cuando={"evento": "bluetooth", "estado": "conectado"})
        self.guardar("Audio", cuando={"evento": "bluetooth", "estado": "conectado", "tipo": "audio"})
        self.guardar("Nombre", cuando={"evento": "bluetooth", "estado": "conectado", "nombre": "wh-1000"})
        self.motor.evento("bluetooth", {"estado": "conectado", "nombre": "Ratón MX", "audio": False})
        self.assertEqual([h["nombre"] for h in self.historial()], ["Cualquiera"])
        self.reloj.avanzar(40)
        self.motor.evento("bluetooth", {"estado": "conectado", "nombre": "WH-1000XM4", "audio": True})
        self.assertEqual(sorted(h["nombre"] for h in self.historial()[1:]), ["Audio", "Cualquiera", "Nombre"])
        self.assertEqual(self.historial()[-1]["evento"], "Bluetooth conectado: WH-1000XM4")

    def test_estado_red(self):
        self.assertEqual(S.estado_red(70, None), "conectada")
        self.assertIsNone(S.estado_red(70, "conectada"))
        for v in (30, 40, 50, 60):
            self.assertIsNone(S.estado_red(v, "conectada"), v)
        self.assertEqual(S.estado_red(20, "conectada"), "desconectada")
        self.assertEqual(S.estado_red(10, None), "desconectada")
        self.assertIsNone(S.estado_red("70", None))

    def test_regla_de_red_con_wifi_exacta(self):
        self.guardar("Casa", cuando={"evento": "red", "estado": "conectada", "wifi": "Mi Casa"})
        self.assertEqual(self.motor.evento("red", {"estado": "conectada", "wifi": "Mi Casa 2"}), 0)
        self.assertEqual(self.motor.evento("red", {"estado": "conectada", "wifi": "mi casa"}), 0)
        self.assertEqual(self.motor.evento("red", {"estado": "conectada", "wifi": None}), 0)
        self.assertEqual(self.motor.evento("red", {"estado": "desconectada", "wifi": None}), 0)
        self.assertEqual(self.motor.evento("red", {"estado": "conectada", "wifi": "Mi Casa"}), 1)
        self.assertEqual(self.historial()[0]["evento"], "Red conectada: Mi Casa")

    def test_eventos_simples(self):
        for ev, cuando, datos in (
                ("suspension", {"evento": "suspension", "estado": "reanudar"}, {"estado": "reanudar"}),
                ("estado_sistema", {"evento": "estado_sistema", "estado": "CRITICAL"}, {"estado": "CRITICAL"}),
                ("servicio_fallido", {"evento": "servicio_fallido"}, {"unidad": "x.service"}),
                ("monitor", {"evento": "monitor", "estado": "desconectado"}, {"estado": "desconectado", "nombre": "DP-1"}),
                ("inactividad", {"evento": "inactividad", "estado": "inactivo"}, {"estado": "inactivo"})):
            with self.subTest(ev=ev):
                self.motor.reglas.clear()
                self.guardar(ev, cuando=cuando)
                self.reloj.avanzar(40)
                n = len(self.historial())
                self.assertEqual(self.motor.evento(ev, datos), 1)
                self.assertEqual(len(self.historial()), n + 1)
                contrario = dict(datos, estado="otro") if "estado" in datos else None
                if contrario:
                    self.assertEqual(self.motor.evento(ev, contrario), 0)


# ---------------------------------------------------------------------------
# Hora
# ---------------------------------------------------------------------------

class PruebasHora(Base):
    def r(self, hora, dias=None):
        return S.validar_regla(regla(cuando={"evento": "hora", "hora": hora, "dias": dias or []}),
                               {"apps": APPS})[0]

    def test_proxima_hora_basica(self):
        ahora = datetime.datetime(2026, 11, 16, 10, 0, 30)                  # lunes
        self.assertEqual(S.proxima_hora([self.r("10:05")], ahora), datetime.datetime(2026, 11, 16, 10, 5))
        self.assertEqual(S.proxima_hora([self.r("09:00")], ahora), datetime.datetime(2026, 11, 17, 9, 0))
        self.assertEqual(S.proxima_hora([self.r("10:00")], ahora), datetime.datetime(2026, 11, 17, 10, 0))   # ya paso
        self.assertEqual(S.proxima_hora([self.r("10:05"), self.r("10:01")], ahora), datetime.datetime(2026, 11, 16, 10, 1))
        self.assertIsNone(S.proxima_hora([], ahora))

    def test_proxima_hora_con_dias(self):
        lunes = datetime.datetime(2026, 11, 16, 10, 0)
        self.assertEqual(lunes.weekday(), 0)
        self.assertEqual(S.proxima_hora([self.r("08:00", [2])], lunes), datetime.datetime(2026, 11, 18, 8, 0))
        self.assertEqual(S.proxima_hora([self.r("11:00", [0])], lunes), datetime.datetime(2026, 11, 16, 11, 0))
        self.assertEqual(S.proxima_hora([self.r("09:00", [0])], lunes), datetime.datetime(2026, 11, 23, 9, 0))
        self.assertEqual(S.proxima_hora([self.r("08:00", [6, 5])], lunes), datetime.datetime(2026, 11, 21, 8, 0))

    def test_proxima_hora_ignora_inactivas_y_por_revisar(self):
        ahora = datetime.datetime(2026, 11, 16, 10, 0)
        inactiva = dict(self.r("11:00"), activa=False)
        revisar = dict(self.r("11:00"), revisar=True)
        otra = S.validar_regla(regla(), {"apps": APPS})[0]
        self.assertIsNone(S.proxima_hora([inactiva, revisar, otra], ahora))

    def motor_con_temporizador(self):
        self.timers, self.cancelados = [], []

        def temporizador(segundos, fn):
            self.timers.append((segundos, fn))
            return len(self.timers)

        self.motor = self.crear_motor(temporizador=temporizador, cancelar=self.cancelados.append)

    def test_el_temporizador_va_al_proximo_instante_sin_sondeo(self):
        self.motor_con_temporizador()
        self.guardar(cuando={"evento": "hora", "hora": "10:30", "dias": [0]})
        self.assertEqual(len(self.timers), 1)
        self.assertAlmostEqual(self.timers[0][0], 1800, delta=1)
        self.reloj.avanzar(1800)
        self.assertFalse(self.timers[0][1]())                    # GLib: no repetir
        self.assertEqual([h["evento"] for h in self.historial()], ["Hora: 10:30"])
        self.assertEqual(len(self.timers), 2)                    # recalculado para el lunes siguiente
        self.assertAlmostEqual(self.timers[1][0], 7 * 86400, delta=1)

    def test_si_el_temporizador_se_adelanta_no_dispara(self):
        self.motor_con_temporizador()
        self.guardar(cuando={"evento": "hora", "hora": "10:30"})
        self.reloj.avanzar(1700)
        self.timers[0][1]()
        self.assertEqual(self.historial(), [])
        self.assertEqual(len(self.timers), 2)
        self.assertAlmostEqual(self.timers[1][0], 100, delta=1)

    def test_no_dispara_dos_veces_si_llega_un_poco_antes(self):
        self.motor_con_temporizador()
        self.guardar(cuando={"evento": "hora", "hora": "10:30"})
        self.reloj.avanzar(1799.5)
        self.timers[0][1]()
        self.assertEqual(len(self.historial()), 1)
        self.assertAlmostEqual(self.timers[1][0], 86400, delta=2)

    def test_se_recalcula_al_reanudar_y_al_cambiar_reglas(self):
        self.motor_con_temporizador()
        r = self.guardar(cuando={"evento": "hora", "hora": "10:30"})
        self.assertEqual(self.cancelados, [])
        self.reloj.avanzar(3600 * 2)             # durmio dos horas
        self.motor.tras_reanudar()
        self.assertEqual(self.cancelados, [1])                   # cancela el temporizador anterior
        self.assertAlmostEqual(self.timers[-1][0], 22.5 * 3600, delta=2)
        n = len(self.timers)
        self.motor.activar(r["id"], False)                       # sin reglas de hora ejecutables: sin temporizador
        self.assertEqual(self.cancelados, [1, 2])
        self.assertEqual(len(self.timers), n)
        self.motor.tras_reanudar()
        self.assertEqual(len(self.timers), n)

    def test_regla_de_hora_se_ejecuta_solo_el_dia_y_la_hora(self):
        self.guardar(cuando={"evento": "hora", "hora": "10:30", "dias": [1]})
        self.assertEqual(self.motor.evento("hora", {"hora": "10:30", "dia": 0}), 0)
        self.assertEqual(self.motor.evento("hora", {"hora": "10:31", "dia": 1}), 0)
        self.assertEqual(self.motor.evento("hora", {"hora": "10:30", "dia": 1}), 1)

    def test_sin_dias_es_todos(self):
        self.guardar(cuando={"evento": "hora", "hora": "10:30"})
        self.assertEqual(self.motor.evento("hora", {"hora": "10:30", "dia": 6}), 1)


# ---------------------------------------------------------------------------
# Condiciones
# ---------------------------------------------------------------------------

class PruebasCondiciones(unittest.TestCase):
    def cond(self, c, **est):
        est.setdefault("ahora", datetime.datetime(2026, 11, 16, 10, 0))
        return S.evaluar_condicion(c, est)

    def test_perfil_cargador_bateria(self):
        self.assertTrue(self.cond({"condicion": "perfil_es", "perfil": "focus"}, perfil="focus"))
        self.assertFalse(self.cond({"condicion": "perfil_es", "perfil": "focus"}, perfil="balanced"))
        self.assertTrue(self.cond({"condicion": "cargador", "conectado": True}, cargador=True))
        self.assertFalse(self.cond({"condicion": "cargador", "conectado": True}, cargador=False))
        self.assertTrue(self.cond({"condicion": "cargador", "conectado": False}, cargador=False))
        self.assertFalse(self.cond({"condicion": "cargador", "conectado": False}, cargador=None))
        self.assertTrue(self.cond({"condicion": "bateria_menor", "valor": 50}, bateria=49))
        self.assertFalse(self.cond({"condicion": "bateria_menor", "valor": 50}, bateria=50))
        self.assertTrue(self.cond({"condicion": "bateria_mayor", "valor": 50}, bateria=51))
        self.assertFalse(self.cond({"condicion": "bateria_mayor", "valor": 50}, bateria=50))
        self.assertFalse(self.cond({"condicion": "bateria_menor", "valor": 50}, bateria=None))
        self.assertFalse(self.cond({"condicion": "bateria_mayor", "valor": 0}))

    def test_entre_horas_sin_pasar_medianoche(self):
        c = {"condicion": "entre_horas", "desde": "09:00", "hasta": "17:30"}
        for hh, mm, esperado in ((8, 59, False), (9, 0, True), (12, 0, True), (17, 29, True), (17, 30, False), (23, 0, False)):
            self.assertEqual(self.cond(c, ahora=datetime.datetime(2026, 11, 16, hh, mm)), esperado, (hh, mm))

    def test_entre_horas_pasando_medianoche(self):
        c = {"condicion": "entre_horas", "desde": "22:00", "hasta": "07:00"}
        for hh, mm, esperado in ((21, 59, False), (22, 0, True), (23, 59, True), (0, 0, True), (6, 59, True),
                                 (7, 0, False), (12, 0, False)):
            self.assertEqual(self.cond(c, ahora=datetime.datetime(2026, 11, 16, hh, mm)), esperado, (hh, mm))

    def test_dias(self):
        lunes = datetime.datetime(2026, 11, 16, 10, 0)
        self.assertTrue(self.cond({"condicion": "dias", "dias": [0, 2]}, ahora=lunes))
        self.assertFalse(self.cond({"condicion": "dias", "dias": [1, 2]}, ahora=lunes))
        self.assertTrue(self.cond({"condicion": "dias", "dias": [6]}, ahora=datetime.datetime(2026, 11, 22, 10, 0)))


class PruebasCondicionesEnElMotor(Base):
    def test_todas_deben_cumplirse_y_si_no_cumplen_no_se_registra(self):
        self.guardar(si=[{"condicion": "perfil_es", "perfil": "focus"}, {"condicion": "bateria_menor", "valor": 50}])
        self.est.update(perfil="focus", bateria=60)
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 0)
        self.assertEqual(self.historial(), [])                   # "omitida" por condiciones: sin ruido
        self.assertEqual(self.ejec.llamadas, [])
        self.est.update(bateria=40)
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 1)
        self.assertEqual(len(self.historial()), 1)
        self.est.update(perfil="balanced")
        self.reloj.avanzar(40)
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 0)
        self.assertEqual(len(self.historial()), 1)

    def test_se_evaluan_con_la_hora_del_reloj(self):
        self.guardar(si=[{"condicion": "entre_horas", "desde": "22:00", "hasta": "07:00"}])
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 0)       # 10:00
        self.reloj.avanzar(13 * 3600)                                                      # 23:00
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 1)


# ---------------------------------------------------------------------------
# Proteccion contra bucles y abuso
# ---------------------------------------------------------------------------

class PruebasProteccion(Base):
    def disparar(self):
        return self.motor.evento("cargador", {"estado": "conectado"})

    def test_enfriamiento_registra_omitida(self):
        self.guardar()
        self.disparar()
        self.reloj.avanzar(29)
        self.disparar()
        h = self.historial()
        self.assertEqual([x["resultado"] for x in h], ["ok", "omitida"])
        self.assertTrue(h[1]["detalle"].startswith("omitida (enfriamiento)"))
        self.assertEqual(len(self.ejec.llamadas), 1)
        self.reloj.avanzar(2)                                    # 31 s desde el primero
        self.disparar()
        self.assertEqual([x["resultado"] for x in self.historial()], ["ok", "omitida", "ok"])
        self.assertEqual(len(self.ejec.llamadas), 2)

    def test_el_enfriamiento_es_por_regla(self):
        self.guardar("A")
        self.guardar("B")
        self.disparar()
        self.assertEqual(sorted(x["nombre"] for x in self.historial()), ["A", "B"])

    def test_tope_por_regla_desactiva_guarda_e_incide(self):
        r = self.guardar()
        for _ in range(4):
            self.disparar()
            self.reloj.avanzar(31)
        self.assertEqual([x["resultado"] for x in self.historial()], ["ok"] * 4)
        self.disparar()                                          # la quinta en menos de 5 min
        ultimo = self.historial()[-1]
        self.assertEqual(ultimo["resultado"], "omitida")
        self.assertIn("regla desactivada", ultimo["detalle"])
        self.assertEqual(len(self.ejec.llamadas), 4)
        self.assertFalse(self.motor._buscar(r["id"])["activa"])
        self.assertFalse(self.leer_reglas()["reglas"][0]["activa"])
        self.assertEqual(len(self.incs), 1)
        inc = self.incs[0]
        self.assertEqual((inc["componente"], inc["gravedad"]), ("reglas", "WARNING"))
        self.assertIn("Prueba", inc["descripcion"])
        self.assertTrue(inc["diagnostico"] and inc["recomendacion"])
        self.assertTrue(any("desactivada" in a[0] for a in self.actividad))
        self.reloj.avanzar(31)
        self.disparar()                                          # desactivada: ya no se ejecuta
        self.assertEqual(len(self.ejec.llamadas), 4)

    def test_tope_por_regla_se_recupera_pasados_5_minutos(self):
        self.guardar()
        for _ in range(4):
            self.disparar()
            self.reloj.avanzar(31)
        self.reloj.avanzar(300)
        self.disparar()
        self.assertEqual(self.historial()[-1]["resultado"], "ok")
        self.assertEqual(self.incs, [])

    def test_reactivar_limpia_el_tope_de_la_regla(self):
        r = self.guardar()
        for _ in range(5):
            self.disparar()
            self.reloj.avanzar(31)
        self.assertFalse(self.motor._buscar(r["id"])["activa"])
        self.motor.activar(r["id"], True)
        self.reloj.avanzar(31)
        self.disparar()
        self.assertEqual(self.historial()[-1]["resultado"], "ok")

    def test_tope_global_mas_de_20_en_60_segundos(self):
        for i in range(21):
            self.guardar(f"Regla {i}")
        self.disparar()
        h = self.historial()
        self.assertEqual([x["resultado"] for x in h].count("ok"), 20)
        self.assertEqual(h[-1]["resultado"], "omitida")
        self.assertIn("20 ejecuciones en 60 s", h[-1]["detalle"])
        self.assertEqual(len(self.ejec.llamadas), 20)
        desactivadas = [r for r in self.motor.reglas if not r["activa"]]
        self.assertEqual(len(desactivadas), 1)
        self.assertEqual(desactivadas[0]["nombre"], h[-1]["nombre"])
        self.assertEqual([r["activa"] for r in self.leer_reglas()["reglas"]].count(False), 1)
        self.assertEqual(len(self.incs), 1)

    def test_el_tope_global_se_libera_con_el_tiempo(self):
        for i in range(20):
            self.guardar(f"Regla {i}")
        self.disparar()
        self.reloj.avanzar(61)
        self.assertEqual(self.disparar(), 20)
        self.assertEqual(self.incs, [])

    def test_origen_regla_no_dispara_reglas_de_perfil(self):
        self.guardar("Reacciona", cuando={"evento": "perfil", "perfil": "focus"})
        self.motor.perfil_cambiado("focus", "regla")
        self.motor.perfil_cambiado("focus", "inicio")
        self.assertEqual(self.historial(), [])
        self.motor.perfil_cambiado("focus", "usuario")
        self.assertEqual(len(self.historial()), 1)
        self.assertEqual(self.historial()[0]["evento"], "Perfil cambiado a focus")

    def test_lo_que_abre_una_regla_no_dispara_reglas_de_aplicacion(self):
        self.guardar("Abre", hacer=[{"accion": "abrir_aplicacion", "id": "firefox"}])
        self.guardar("Reacciona", cuando={"evento": "aplicacion", "estado": "abierta", "clase": "firefox"})
        self.disparar()
        self.assertEqual(self.motor.evento("aplicacion", {"estado": "abierta", "clase": "firefox"}), 0)
        self.assertEqual(self.motor.evento("aplicacion", {"estado": "cerrada", "clase": "firefox"}), 0)  # no es de las de abrir
        self.reloj.avanzar(S.SILENCIO_APLICACION + 1)
        self.assertEqual(self.motor.evento("aplicacion", {"estado": "abierta", "clase": "firefox"}), 1)

    def test_una_regla_ya_en_curso_no_se_solapa(self):
        pendiente = []
        self.motor = self.crear_motor(lanzador=lambda trabajo, fin: pendiente.append((trabajo, fin)))
        self.guardar()
        self.disparar()
        self.reloj.avanzar(31)
        self.disparar()
        self.assertEqual(len(pendiente), 1)
        self.assertEqual(self.historial()[0]["resultado"], "omitida")
        self.assertIn("ya se está ejecutando", self.historial()[0]["detalle"])
        trabajo, fin = pendiente[0]
        fin(trabajo())
        self.assertEqual(self.historial()[-1]["resultado"], "ok")
        self.reloj.avanzar(31)
        self.disparar()
        self.assertEqual(len(pendiente), 2)


class PruebasPerfilesConElServicio(unittest.TestCase):
    """origen 'regla' de punta a punta: el motor de perfiles real avisa al motor de reglas."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-reglas-sv-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        p = mock.patch.dict(os.environ, {"JAIME0_RUNTIME": os.path.join(self.tmp, "rt"),
                                         "JAIME0_ESTADO": os.path.join(self.tmp, "estado"),
                                         "XDG_CONFIG_HOME": os.path.join(self.tmp, "config")})
        p.start()
        self.addCleanup(p.stop)
        os.makedirs(os.environ["JAIME0_RUNTIME"])

        class Sistema:
            dnd = False

            def capacidades(self):
                return {"energia": ["balanced"], "ppd": True, "no_molestar": True, "animaciones": True,
                        "inhibir_inactividad": True, "modo_noche": True}

            def dnd_leer(self):
                return self.dnd

            def dnd_poner(self, activo):
                self.dnd = activo

            def hypr_disponible(self):
                return True

            def hypr_recargar(self):
                pass

            def inhibir_abrir(self, motivo):
                return 5

            def inhibir_cerrar(self, fd):
                pass

            def ppd_degradado(self):
                return None

            def noche_leer(self):
                return False

            def noche_poner(self, activo):
                pass

        self.ejec = Ejecutor()
        self.sv = S.Servicio(directorio=os.environ["JAIME0_RUNTIME"], estado=os.environ["JAIME0_ESTADO"],
                             sistema=Sistema(), leer_umbrales=lambda: {})
        self.sv.reglas_ejecutar = self.ejec
        self.sv.reglas.apps = lambda: APPS

    def historial(self):
        return S.leer_jsonl(os.path.join(os.environ["JAIME0_ESTADO"], "ejecuciones.jsonl"))

    def test_perfil_aplicado_por_una_regla_no_dispara_otras_reglas(self):
        m = self.sv.reglas
        self.assertTrue(m.guardar(regla("Pone focus", cuando={"evento": "cargador", "estado": "conectado"},
                                        hacer=[{"accion": "perfil", "perfil": "focus"}]))["ok"])
        self.assertTrue(m.guardar(regla("Reacciona", cuando={"evento": "perfil", "perfil": "focus"}))["ok"])
        m.evento("cargador", {"estado": "conectado"})
        self.assertEqual(self.sv.perfiles.activo, "focus")
        self.assertEqual(self.sv.perfiles.origen, "regla")
        self.assertEqual([h["nombre"] for h in self.historial()], ["Pone focus"])
        self.sv.perfiles.aplicar("balanced", "usuario")
        self.sv.perfiles.aplicar("focus", "usuario")
        self.assertEqual([h["nombre"] for h in self.historial()], ["Pone focus", "Reacciona"])
        self.sv.perfiles.aplicar("focus", "usuario")            # sin cambio: sin evento
        self.assertEqual(len(self.historial()), 2)

    def test_el_arranque_no_dispara_reglas_de_perfil(self):
        self.sv.reglas.guardar(regla("Reacciona", cuando={"evento": "perfil", "perfil": "balanced"}))
        self.sv.perfiles.iniciar()
        self.assertEqual(self.historial(), [])

    def test_accion_perfil_no_disponible_falla_con_el_motivo(self):
        m = self.sv.reglas
        m.guardar(regla("Pone perf", hacer=[{"accion": "perfil", "perfil": "performance"}]))
        m.evento("cargador", {"estado": "conectado"})
        h = self.historial()[0]
        self.assertEqual(h["resultado"], "fallo")
        self.assertIn("no está disponible", h["acciones"][0]["detalle"])
        self.assertIn("alto rendimiento", h["acciones"][0]["detalle"])

    def test_estado_sistema_suspension_y_actividad(self):
        m = self.sv.reglas
        m.guardar(regla("Estado", cuando={"evento": "estado_sistema", "estado": "WARNING"}))
        m.guardar(regla("Reanuda", cuando={"evento": "suspension", "estado": "reanudar"}))
        with mock.patch.object(S, "avisar_barra"):
            self.sv.publicar("ONLINE", [])                      # primera vez: sin cambio
            self.assertEqual(self.historial(), [])
            self.sv.publicar("WARNING", [{"gravedad": "WARNING", "componente": "x", "texto": "t"}])
        self.assertEqual([h["nombre"] for h in self.historial()], ["Estado"])
        self.sv.al_suspender(True)
        self.assertEqual(len(self.historial()), 1)
        self.sv.al_suspender(False)
        self.assertEqual([h["nombre"] for h in self.historial()], ["Estado", "Reanuda"])
        textos = [a["texto"] for a in self.sv.actividad]
        self.assertIn("Regla «Estado»: ok", textos)
        self.assertEqual([a for a in self.sv.actividad if a["texto"] == "Regla «Estado»: ok"][0]["origen"], "regla")

    def test_incidencia_de_tope_en_el_servicio(self):
        m = self.sv.reglas
        m.reloj = Reloj()
        m.guardar(regla("Insistente"))
        for _ in range(5):
            m.evento("cargador", {"estado": "conectado"})
            m.reloj.avanzar(31)
        incs = self.sv.incidencias(10)
        self.assertEqual([i["componente"] for i in incs], ["reglas"])
        self.assertEqual(self.sv.incidencias_estado.abiertas(), [])     # no deja una incidencia abierta para siempre

    def test_las_incidencias_de_reglas_no_se_restauran_como_abiertas(self):
        i = S.Incidencias()
        i.restaurar([{"componente": "reglas", "gravedad": "WARNING"}, {"componente": "disco", "gravedad": "WARNING"}])
        self.assertEqual(i.abiertas(), [{"componente": "disco", "gravedad": "WARNING"}])


# ---------------------------------------------------------------------------
# Archivo, importacion, activar, borrar, probar, historial
# ---------------------------------------------------------------------------

class PruebasArchivo(Base):
    def test_guardar_crea_con_slug_unico_y_escritura_atomica(self):
        a = self.guardar("Batería baja")
        b = self.guardar("Batería baja")
        self.assertEqual((a["id"], b["id"]), ("bateria-baja", "bateria-baja-2"))
        doc = self.leer_reglas()
        self.assertEqual(doc["v"], 1)
        self.assertEqual([r["id"] for r in doc["reglas"]], ["bateria-baja", "bateria-baja-2"])
        self.assertFalse(os.path.exists(self.archivo + ".tmp"))
        self.assertEqual(sorted(doc["reglas"][0]), ["activa", "cuando", "hacer", "id", "nombre", "revisar", "si"])

    def test_guardar_actualiza_si_el_id_existe_y_crea_si_no(self):
        a = self.guardar("Uno")
        r = self.motor.guardar(dict(regla("Uno editado"), id=a["id"]))
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.motor.reglas), 1)
        self.assertEqual(self.motor.reglas[0]["nombre"], "Uno editado")
        r = self.motor.guardar(dict(regla("Otro"), id="mi-id"))
        self.assertEqual(r["regla"]["id"], "mi-id")
        self.assertEqual(len(self.motor.reglas), 2)

    def test_guardar_invalida_no_cambia_nada(self):
        r = self.motor.guardar(regla(hacer=[{"accion": "volumen", "nivel": 500}]))
        self.assertFalse(r["ok"])
        self.assertIn("nivel", r["error"])
        self.assertFalse(os.path.exists(self.archivo))

    def test_una_regla_invalida_no_se_carga_se_informa_y_se_conserva_al_guardar(self):
        buena = S.validar_regla(dict(regla("Buena"), id="buena"), {"apps": APPS})[0]
        rota = {"id": "rota", "nombre": "Rota", "activa": True, "cuando": {"evento": "marte"}, "hacer": []}
        sin_id = {"nombre": 5}
        os.makedirs(os.path.dirname(self.archivo))
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "reglas": [buena, rota, sin_id, dict(buena)]}, f)
        self.motor.cargar()
        self.assertEqual([r["id"] for r in self.motor.reglas], ["buena"])
        self.assertEqual(len(self.motor.errores), 3)
        self.assertEqual(self.motor.errores[0]["id"], "rota")
        self.assertEqual(self.motor.errores[1]["indice"], 2)
        self.assertEqual(self.motor.errores[2]["id"], "buena")
        self.assertIn("repetido", self.motor.errores[2]["error"])
        self.guardar("Nueva")
        guardadas = [r.get("id") for r in self.leer_reglas()["reglas"]]
        self.assertIn("rota", guardadas)                         # la invalida no se pierde al reescribir
        self.assertEqual(len(guardadas), 5)                      # buena + 3 invalidas + la nueva
        self.assertEqual(self.motor.borrar("rota"), {"ok": True})
        self.assertNotIn("rota", [r.get("id") for r in self.leer_reglas()["reglas"]])

    def test_archivo_roto_conserva_las_reglas_cargadas(self):
        self.guardar()
        with open(self.archivo, "w", encoding="utf-8") as f:
            f.write("{esto no es json")
        self.motor.cargar()
        self.assertEqual(len(self.motor.reglas), 1)
        self.assertIn("reglas.json", self.motor.errores[0]["error"])
        with open(self.archivo, "w", encoding="utf-8") as f:
            f.write('{"v": 2, "reglas": []}')
        self.motor.cargar()
        self.assertEqual(len(self.motor.reglas), 1)
        self.assertIn("formato", self.motor.errores[0]["error"])

    def test_recarga_tras_editar_el_archivo(self):
        self.guardar("Una")
        doc = self.leer_reglas()
        doc["reglas"][0]["activa"] = False
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        self.motor.cargar()
        self.assertFalse(self.motor.reglas[0]["activa"])
        os.remove(self.archivo)
        self.motor.cargar()
        self.assertEqual((self.motor.reglas, self.motor.errores), ([], []))

    def test_fallo_al_escribir_deja_el_estado_como_estaba(self):
        self.guardar("Una")
        with mock.patch.object(self.motor, "_guardar", side_effect=OSError(13, "Permiso denegado")):
            self.assertFalse(self.motor.guardar(regla("Dos"))["ok"])
            self.assertFalse(self.motor.activar(self.motor.reglas[0]["id"], False)["ok"])
            self.assertFalse(self.motor.borrar(self.motor.reglas[0]["id"])["ok"])
        self.assertEqual(len(self.motor.reglas), 1)
        self.assertTrue(self.motor.reglas[0]["activa"])

    def test_activar_desactivar_borrar(self):
        r = self.guardar()
        self.assertFalse(self.motor.activar(r["id"], False)["regla"]["activa"])
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 0)     # desactivada
        self.assertTrue(self.motor.activar(r["id"], True)["regla"]["activa"])
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 1)
        self.assertFalse(self.motor.activar("no-existe", True)["ok"])
        self.assertEqual(self.motor.borrar(r["id"]), {"ok": True})
        self.assertEqual(self.leer_reglas()["reglas"], [])
        self.assertFalse(self.motor.borrar(r["id"])["ok"])

    def test_limite_de_reglas(self):
        for i in range(S.MAX_REGLAS):
            self.guardar(f"R{i}")
        self.assertFalse(self.motor.guardar(regla("Una mas"))["ok"])


class PruebasImportar(Base):
    def test_entran_desactivadas_y_por_revisar_y_no_se_ejecutan(self):
        r = self.motor.importar([regla("Importada", activa=True), dict(regla("Importada"), id="viejo", revisar=False)])
        self.assertEqual((r["ok"], r["importadas"], r["errores"]), (True, 2, []))
        for x in self.motor.reglas:
            self.assertEqual((x["activa"], x["revisar"]), (False, True))
        self.assertEqual(sorted(x["id"] for x in self.motor.reglas), ["importada", "viejo"])
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 0)
        self.assertEqual(self.ejec.llamadas, [])
        guardadas = self.leer_reglas()["reglas"]
        self.assertEqual([(g["activa"], g["revisar"]) for g in guardadas], [(False, True)] * 2)

    def test_activar_quita_revisar_y_la_ejecuta(self):
        self.motor.importar([regla("Importada")])
        self.assertTrue(self.motor.activar("importada", True)["ok"])
        self.assertEqual((self.motor.reglas[0]["activa"], self.motor.reglas[0]["revisar"]), (True, False))
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 1)

    def test_desactivar_no_quita_revisar(self):
        self.motor.importar([regla("Importada")])
        self.motor.activar("importada", False)
        self.assertTrue(self.motor.reglas[0]["revisar"])

    def test_guardar_una_importada_sin_activarla_mantiene_revisar(self):
        self.motor.importar([regla("Importada")])
        r = self.motor.guardar(dict(regla("Importada editada", activa=False), id="importada"))
        self.assertTrue(r["regla"]["revisar"])
        r = self.motor.guardar(dict(regla("Importada editada", activa=True), id="importada"))
        self.assertFalse(r["regla"]["revisar"])

    def test_importar_informa_de_errores_y_cuenta(self):
        r = self.motor.importar([regla("Buena"), regla(hacer=[{"accion": "apagar"}]), "no soy una regla"])
        self.assertEqual(r["importadas"], 1)
        self.assertEqual([e["indice"] for e in r["errores"]], [1, 2])
        self.assertFalse(self.motor.importar("x")["ok"])
        self.assertFalse(self.motor.importar([{}] * (S.MAX_REGLAS + 1))["ok"])

    def test_una_regla_a_mano_con_activa_y_revisar_no_se_ejecuta(self):
        dato = S.validar_regla(dict(regla("Mixta"), id="mixta", activa=True, revisar=True), {"apps": APPS})[0]
        os.makedirs(os.path.dirname(self.archivo))
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "reglas": [dato]}, f)
        self.motor.cargar()
        self.assertEqual(self.motor.evento("cargador", {"estado": "conectado"}), 0)

    def test_importar_rechaza_perfil_a_perfil(self):
        r = self.motor.importar([regla(cuando={"evento": "perfil", "perfil": "focus"},
                                       hacer=[{"accion": "perfil", "perfil": "balanced"}])])
        self.assertEqual(r["importadas"], 0)
        self.assertIn("bucle", r["errores"][0]["error"])


class PruebasProbarEHistorial(Base):
    def probar(self, rid):
        caja = []
        self.motor.probar(rid, caja.append)
        self.assertEqual(len(caja), 1)
        return caja[0]

    def test_probar_ejecuta_ahora_sin_evento_ni_condiciones_ni_estar_activa(self):
        r = self.guardar(cuando={"evento": "perfil", "perfil": "focus"}, si=[{"condicion": "perfil_es", "perfil": "focus"}],
                         activa=False)
        res = self.probar(r["id"])
        self.assertTrue(res["ok"])
        e = res["ejecucion"]
        self.assertEqual((e["evento"], e["resultado"]), ("prueba manual", "ok"))
        self.assertEqual(self.historial()[0]["evento"], "prueba manual")
        self.assertEqual(len(self.ejec.llamadas), 1)

    def test_probar_respeta_enfriamiento_y_tope(self):
        r = self.guardar()
        self.assertTrue(self.probar(r["id"])["ok"])
        res = self.probar(r["id"])
        self.assertFalse(res["ok"])
        self.assertIn("enfriamiento", res["error"])
        self.assertEqual(self.historial()[-1]["resultado"], "omitida")
        self.assertEqual(len(self.ejec.llamadas), 1)
        for _ in range(3):
            self.reloj.avanzar(31)
            self.assertTrue(self.probar(r["id"])["ok"])
        self.reloj.avanzar(31)
        res = self.probar(r["id"])
        self.assertFalse(res["ok"])
        self.assertIn("desactivada", res["error"])
        self.assertFalse(self.motor._buscar(r["id"])["activa"])
        self.assertEqual(len(self.incs), 1)

    def test_probar_cuenta_para_el_enfriamiento_de_los_eventos(self):
        r = self.guardar()
        self.probar(r["id"])
        self.motor.evento("cargador", {"estado": "conectado"})
        self.assertEqual(self.historial()[-1]["resultado"], "omitida")

    def test_probar_regla_inexistente_o_por_revisar(self):
        self.assertFalse(self.probar("no-existe")["ok"])
        self.motor.importar([regla("Importada")])
        res = self.probar("importada")
        self.assertFalse(res["ok"])
        self.assertIn("revisión", res["error"])
        self.assertEqual(self.ejec.llamadas, [])

    def test_resultado_fallo_y_detalle_por_accion(self):
        self.ejec.resp["notify-send"] = proc(1, err="no hay servidor")
        r = self.guardar(hacer=[{"accion": "notificar", "titulo": "a", "texto": "b"}, {"accion": "volumen", "nivel": 30}])
        e = self.probar(r["id"])["ejecucion"]
        self.assertEqual(e["resultado"], "fallo")
        self.assertEqual([(a["accion"], a["resultado"]) for a in e["acciones"]], [("notificar", "fallo"), ("volumen", "ok")])
        self.assertIn("no hay servidor", e["acciones"][0]["detalle"])
        self.assertTrue(e["detalle"].startswith("1 de 2"))
        self.assertEqual(len(self.ejec.llamadas), 2)            # una accion que falla no impide las demas

    def test_formato_del_historial(self):
        r = self.guardar("Mi regla")
        self.probar(r["id"])
        h = self.historial()[0]
        self.assertEqual(sorted(h), ["acciones", "detalle", "evento", "nombre", "regla", "resultado", "t", "v"])
        self.assertEqual((h["v"], h["regla"], h["nombre"]), (1, r["id"], "Mi regla"))
        self.assertEqual(h["t"], int(self.reloj()))
        self.assertEqual(sorted(h["acciones"][0]), ["accion", "detalle", "resultado"])

    def test_actividad_y_aviso_por_cada_ejecucion(self):
        self.ejec.resp["notify-send"] = proc(1, err="x")
        r = self.guardar("Mi regla")
        self.probar(r["id"])
        self.assertEqual(self.actividad[-1], ("Regla «Mi regla»: fallo", None, "WARNING", None, "regla"))
        self.assertTrue(self.avisos)
        self.reloj.avanzar(40)
        self.ejec.resp["notify-send"] = proc()
        self.probar(r["id"])
        self.assertEqual(self.actividad[-1], ("Regla «Mi regla»: ok", None, "INFO", None, "regla"))

    def test_listado_con_ultima_ejecucion(self):
        a, b = self.guardar("A"), self.guardar("B")
        self.probar(a["id"])
        doc = self.motor.listar()
        por_id = {x["id"]: x for x in doc["reglas"]}
        self.assertEqual(por_id[a["id"]]["ultima"]["evento"], "prueba manual")
        self.assertIsNone(por_id[b["id"]]["ultima"])

    def test_historial_mas_reciente_primero_y_limite(self):
        r = self.guardar()
        for _ in range(3):
            self.probar(r["id"])
            self.reloj.avanzar(31)
        doc = self.motor.historial_doc(2)
        self.assertEqual(len(doc["ejecuciones"]), 2)
        self.assertGreater(doc["ejecuciones"][0]["t"], doc["ejecuciones"][1]["t"])

    def test_recorte_a_1000_lineas(self):
        h = S.HistorialEjecuciones(lambda: self.ejecuciones)
        self.assertEqual(S.MAX_EJECUCIONES, 1000)
        for i in range(1005):
            h.anotar({"v": 1, "t": i, "regla": "x", "nombre": "x", "evento": "e", "resultado": "ok", "detalle": "", "acciones": []})
        docs = S.leer_jsonl(self.ejecuciones)
        self.assertEqual(len(docs), 1000)
        self.assertEqual((docs[0]["t"], docs[-1]["t"]), (5, 1004))
        self.assertEqual(h.ultimos(1)[0]["t"], 1004)


# ---------------------------------------------------------------------------
# Catalogo y disponibilidad
# ---------------------------------------------------------------------------

class PruebasCatalogo(Base):
    def test_forma_del_catalogo(self):
        cat = self.motor.catalogo()
        self.assertEqual(sorted(cat), ["acciones", "condiciones", "eventos"])
        self.assertEqual([e["id"] for e in cat["eventos"]],
                         ["bateria_baja", "cargador", "bluetooth", "monitor", "aplicacion", "hora", "red", "suspension",
                          "inactividad", "estado_sistema", "servicio_fallido", "perfil"])
        self.assertEqual([c["id"] for c in cat["condiciones"]],
                         ["perfil_es", "cargador", "bateria_menor", "bateria_mayor", "entre_horas", "dias"])
        for seccion in cat.values():
            for e in seccion:
                self.assertEqual(sorted(e), ["descripcion", "disponible", "id", "motivo", "nombre", "parametros"])
                for p in e["parametros"]:
                    self.assertTrue({"clave", "tipo", "defecto", "texto"} <= set(p), p)
        bateria = cat["eventos"][0]["parametros"][0]
        self.assertEqual((bateria["clave"], bateria["tipo"], bateria["min"], bateria["max"], bateria["defecto"]),
                         ("umbral", "entero", 5, 95, 20))
        estado = cat["eventos"][1]["parametros"][0]
        self.assertEqual(estado["opciones"], ["conectado", "desconectado"])

    def test_disponibilidad_inyectada(self):
        self.disp = {"eventos": {"bluetooth": (False, "BlueZ no está"), "monitor": (False, "No hay Hyprland")},
                     "acciones": {"volumen": (False, "Falta wpctl")}}
        cat = self.motor.catalogo()
        ev = {e["id"]: e for e in cat["eventos"]}
        self.assertEqual((ev["bluetooth"]["disponible"], ev["bluetooth"]["motivo"]), (False, "BlueZ no está"))
        self.assertEqual((ev["monitor"]["disponible"], ev["monitor"]["motivo"]), (False, "No hay Hyprland"))
        self.assertEqual((ev["red"]["disponible"], ev["red"]["motivo"]), (True, None))
        ac = {a["id"]: a for a in cat["acciones"]}
        self.assertFalse(ac["volumen"]["disponible"])
        self.assertTrue(ac["silenciar"]["disponible"])

    def disponibilidad(self, bluez=True, nm=True, logind=True, entorno=None, bateria=None, cargador=None, programas=()):
        def en_bus(n):
            return {"org.bluez": bluez, "org.freedesktop.NetworkManager": nm, "org.freedesktop.login1": logind}[n]

        return S.disponibilidad_sistema(
            en_bus=en_bus, entorno=entorno if entorno is not None else {}, cual=lambda p: ("/usr/bin/" + p) if p in programas else None,
            bateria=lambda: bateria, cargador=lambda: cargador, hermano=lambda p: ("/x/" + p) if p in programas else None)

    def test_sin_bluez(self):
        d = self.disponibilidad(bluez=False)["eventos"]
        self.assertFalse(d["bluetooth"][0])
        self.assertIn("BlueZ", d["bluetooth"][1])
        self.assertTrue(self.disponibilidad(bluez=True)["eventos"]["bluetooth"][0])
        d = self.disponibilidad(bluez=None)["eventos"]
        self.assertFalse(d["bluetooth"][0])
        self.assertIn("bus del sistema", d["bluetooth"][1])

    def test_sin_hyprland(self):
        d = self.disponibilidad(entorno={})["eventos"]
        for ident in ("monitor", "aplicacion"):
            self.assertFalse(d[ident][0])
            self.assertIn("Hyprland", d[ident][1])
        d = self.disponibilidad(entorno={"HYPRLAND_INSTANCE_SIGNATURE": "abc"})["eventos"]
        self.assertTrue(d["monitor"][0] and d["aplicacion"][0])

    def test_resto_de_disponibilidades(self):
        d = self.disponibilidad(nm=False, logind=False, bateria=None, cargador=None)["eventos"]
        self.assertFalse(d["bateria_baja"][0])
        self.assertFalse(d["cargador"][0])
        self.assertFalse(d["red"][0])
        self.assertFalse(d["suspension"][0])
        self.assertFalse(d["inactividad"][0])
        for ident in ("hora", "estado_sistema", "servicio_fallido", "perfil"):
            self.assertTrue(d[ident][0])
        d = self.disponibilidad(bateria={"nivel": 50}, cargador=True, programas=("hypridle",))["eventos"]
        self.assertTrue(d["bateria_baja"][0] and d["cargador"][0] and d["inactividad"][0])

    def test_disponibilidad_de_acciones(self):
        a = self.disponibilidad()["acciones"]
        for ident in ("modo_noche", "no_molestar", "notificar", "abrir_aplicacion", "volumen", "silenciar", "salida_audio"):
            self.assertFalse(a[ident][0], ident)
        for ident in ("perfil", "mantenimiento", "script"):
            self.assertTrue(a[ident][0], ident)
        a = self.disponibilidad(programas=("wpctl", "swaync-client", "notify-send", "modo-noche", "hyprsunset",
                                           "jaime0-anclar"))["acciones"]
        self.assertTrue(all(v[0] for v in a.values()))


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------

WPCTL_STATUS = """PipeWire 'pipewire-0' [1.0.5, usuario@equipo, cookie:1234]
 └─ Clients:
        33. WirePlumber                         [1.0.5, usuario@equipo, pid:900]
        51. Brave                               [1.0.5, usuario@equipo, pid:2000]

Audio
 ├─ Devices:
 │      47. Audio interno                       [alsa]
 │      60. WH-1000XM4                          [bluez5]
 │
 ├─ Sinks:
 │  *   51. Audio interno Estéreo analógico     [vol: 0.40]
 │      88. WH-1000XM4                          [vol: 0.50 MUTED]
 │      89. Altavoz [A2DP]                      [vol: 1.00]
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │  *   52. Micrófono interno                   [vol: 1.00]
 │
 └─ Streams:
        77. Brave
             101. output_FL > Audio interno:playback_FL

Video
 ├─ Devices:
 │      70. Cámara                              [v4l2]
 │
 ├─ Sinks:
 │
 └─ Sources:

Settings
 └─ Default Configured Devices:
         0. Audio/Sink    alsa_output.pci
"""


class PruebasAcciones(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(S, "programa_hermano", lambda n: "/usr/local/bin/" + n)
        p.start()
        self.addCleanup(p.stop)
        self.A = self.motor.acciones

    def run_accion(self, **a):
        return self.A.ejecutar_accion(a)

    def test_ordenes_exactas(self):
        casos = [
            ({"accion": "modo_noche", "estado": "encender"}, ["/usr/local/bin/modo-noche", "encender"]),
            ({"accion": "modo_noche", "estado": "apagar"}, ["/usr/local/bin/modo-noche", "apagar"]),
            ({"accion": "no_molestar", "estado": "activar"}, ["swaync-client", "--dnd-on", "--skip-wait"]),
            ({"accion": "no_molestar", "estado": "desactivar"}, ["swaync-client", "--dnd-off", "--skip-wait"]),
            ({"accion": "notificar", "titulo": "-t", "texto": "Texto"},
             ["notify-send", "--app-name=Jaime0", "--", "-t", "Texto"]),
            ({"accion": "volumen", "nivel": 35}, ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "35%"]),
            ({"accion": "silenciar", "estado": "si"}, ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"]),
            ({"accion": "silenciar", "estado": "no"}, ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"]),
            ({"accion": "abrir_aplicacion", "id": "firefox"}, ["/usr/local/bin/jaime0-anclar", "abrir", "firefox"]),
            ({"accion": "mantenimiento", "tarea": "comprobar_actualizaciones"},
             ["/usr/local/bin/actualizaciones", "comprobar", "--notificar", "--silencioso"]),
        ]
        for accion, orden in casos:
            with self.subTest(accion=accion):
                self.ejec.llamadas.clear()
                ok, detalle = self.A.ejecutar_accion(accion)
                self.assertTrue(ok, detalle)
                self.assertEqual(self.ejec.ordenes, [orden])
                k = self.ejec.llamadas[0][1]
                self.assertTrue(k["timeout"] > 0)
                self.assertNotIn("shell", k)

    def test_programa_ausente_timeout_y_codigo(self):
        self.ejec.resp["wpctl"] = FileNotFoundError()
        ok, d = self.run_accion(accion="volumen", nivel=10)
        self.assertEqual((ok, d), (False, "wpctl no está instalado"))
        self.ejec.resp["wpctl"] = subprocess.TimeoutExpired("wpctl", 5)
        ok, d = self.run_accion(accion="volumen", nivel=10)
        self.assertFalse(ok)
        self.assertIn("tiempo máximo", d)
        self.ejec.resp["wpctl"] = proc(2, err="Error: sink\nsegunda")
        ok, d = self.run_accion(accion="volumen", nivel=10)
        self.assertFalse(ok)
        self.assertIn("código 2", d)
        self.assertIn("Error: sink", d)

    def test_abrir_aplicacion_solo_ids_de_disponibles(self):
        ok, d = self.run_accion(accion="abrir_aplicacion", id="no.existe")
        self.assertFalse(ok)
        self.assertIn("ya no está en la lista", d)
        self.assertEqual(self.ejec.llamadas, [])
        self.apps = None
        self.A.apps = lambda: None
        ok, d = self.run_accion(accion="abrir_aplicacion", id="firefox")
        self.assertFalse(ok)
        self.assertEqual(self.ejec.llamadas, [])

    def test_perfil_via_en_bucle_con_origen_regla(self):
        llamadas = []
        self.A.en_bucle = lambda fn: (llamadas.append("bucle"), fn())[1]
        ok, d = self.run_accion(accion="perfil", perfil="focus")
        self.assertTrue(ok)
        self.assertEqual((llamadas, self.perfiles), (["bucle"], ["focus"]))
        self.A.aplicar_perfil = lambda pid: {"ok": False, "error": "El perfil X no está disponible: sin ppd"}
        self.assertEqual(self.run_accion(accion="perfil", perfil="focus"), (False, "El perfil X no está disponible: sin ppd"))
        self.A.aplicar_perfil = lambda pid: {"ok": True, "nombre": "FOCUS", "fallos": ["No molestar: roto"]}
        ok, d = self.run_accion(accion="perfil", perfil="focus")
        self.assertFalse(ok)
        self.assertIn("No molestar: roto", d)

    def test_parseo_de_sinks_de_wpctl(self):
        sinks = S.parsear_sinks_wpctl(WPCTL_STATUS)
        self.assertEqual(sinks, [{"id": 51, "nombre": "Audio interno Estéreo analógico", "defecto": True},
                                 {"id": 88, "nombre": "WH-1000XM4", "defecto": False},
                                 {"id": 89, "nombre": "Altavoz [A2DP]", "defecto": False}])
        self.assertEqual(S.parsear_sinks_wpctl(""), [])
        self.assertEqual(S.parsear_sinks_wpctl("Audio\n ├─ Sources:\n │  *   52. Micro  [vol: 1.00]\n"), [])

    def test_salida_audio_elige_por_nombre_sin_distinguir_mayusculas(self):
        self.ejec.resp["wpctl"] = lambda o: proc(0, WPCTL_STATUS) if o[1] == "status" else proc()
        ok, d = self.run_accion(accion="salida_audio", nombre="wh-1000")
        self.assertTrue(ok, d)
        self.assertEqual(self.ejec.ordenes, [["wpctl", "status"], ["wpctl", "set-default", "88"]])
        self.assertIn("WH-1000XM4", d)
        self.ejec.llamadas.clear()
        self.assertTrue(self.run_accion(accion="salida_audio", nombre="interno")[0])
        self.assertEqual(self.ejec.ordenes[-1], ["wpctl", "set-default", "51"])

    def test_salida_audio_sin_coincidencia_reintenta_y_falla_con_claridad(self):
        self.ejec.resp["wpctl"] = lambda o: proc(0, WPCTL_STATUS)
        ok, d = self.run_accion(accion="salida_audio", nombre="Auriculares Z")
        self.assertFalse(ok)
        self.assertIn("«Auriculares Z»", d)
        self.assertEqual(len(self.dormidos), S.REINTENTOS_SINK)
        self.assertEqual(all(o == ["wpctl", "status"] for o in self.ejec.ordenes), True)

    def test_salida_audio_espera_a_que_aparezca_el_sink(self):
        estados = [proc(0, WPCTL_STATUS.replace("WH-1000XM4", "Otro")), proc(0, WPCTL_STATUS)]
        self.ejec.resp["wpctl"] = lambda o: estados.pop(0) if o[1] == "status" and estados else proc(0, WPCTL_STATUS)
        ok, d = self.run_accion(accion="salida_audio", nombre="WH-1000")
        self.assertTrue(ok, d)
        self.assertEqual(self.dormidos, [1.0])

    def test_limpiar_miniaturas_solo_antiguas_sin_seguir_enlaces(self):
        ahora = self.reloj()
        os.makedirs(os.path.join(self.thumbs, "normal"))
        os.makedirs(os.path.join(self.thumbs, "large", "sub"))
        fuera = os.path.join(self.tmp, "fuera")
        os.makedirs(fuera)

        def archivo(ruta, dias, contenido="x" * 1000):
            with open(ruta, "w") as f:
                f.write(contenido)
            t = ahora - dias * 86400
            os.utime(ruta, (t, t))
            return ruta

        viejo1 = archivo(os.path.join(self.thumbs, "normal", "a.png"), 45)
        viejo2 = archivo(os.path.join(self.thumbs, "large", "sub", "b.png"), 31, "y" * 500)
        justo = archivo(os.path.join(self.thumbs, "normal", "c.png"), 29)
        nuevo = archivo(os.path.join(self.thumbs, "d.png"), 0)
        ajeno = archivo(os.path.join(fuera, "e.png"), 400)
        enlaces = []
        try:
            os.symlink(fuera, os.path.join(self.thumbs, "enlace-carpeta"), target_is_directory=True)
            os.symlink(ajeno, os.path.join(self.thumbs, "enlace-archivo.png"))
            enlaces = ["enlace-carpeta", "enlace-archivo.png"]
        except (OSError, NotImplementedError):
            pass
        ok, d = self.run_accion(accion="mantenimiento", tarea="limpiar_miniaturas")
        self.assertTrue(ok, d)
        self.assertFalse(os.path.exists(viejo1) or os.path.exists(viejo2))
        self.assertTrue(os.path.exists(justo) and os.path.exists(nuevo))
        self.assertTrue(os.path.exists(ajeno))                                  # fuera de la carpeta: intacto
        self.assertTrue(os.path.isdir(os.path.join(self.thumbs, "large", "sub")))     # no borra carpetas
        self.assertIn("2 archivo(s)", d)
        self.assertEqual(self.ejec.llamadas, [])
        for e in enlaces:
            self.assertTrue(os.path.lexists(os.path.join(self.thumbs, e)), e)

    def test_limpiar_miniaturas_no_borra_un_enlace_simulado(self):
        ahora = self.reloj()
        os.makedirs(self.thumbs)
        ruta_enlace = os.path.join(self.thumbs, "parece-enlace.png")
        with open(ruta_enlace, "w") as f:
            f.write("x")
        t = ahora - 90 * 86400
        os.utime(ruta_enlace, (t, t))
        real = os.lstat

        def lstat(p, *a, **k):
            st = real(p, *a, **k)
            if p == ruta_enlace:
                return os.stat_result((stat.S_IFLNK | 0o777,) + tuple(st)[1:])
            return st

        with mock.patch.object(S.os, "lstat", lstat):
            self.assertEqual(S.limpiar_miniaturas(self.thumbs, ahora), (0, 0, None))
        self.assertTrue(os.path.exists(ruta_enlace))
        self.assertEqual(S.limpiar_miniaturas(self.thumbs, ahora)[0], 1)

    def test_limpiar_miniaturas_carpeta_enlace_o_ausente(self):
        self.assertEqual(S.limpiar_miniaturas(os.path.join(self.tmp, "no-existe"), 0), (0, 0, None))
        with mock.patch.object(S.os.path, "islink", return_value=True):
            n, tam, error = S.limpiar_miniaturas(self.tmp, 0)
        self.assertEqual((n, tam), (0, 0))
        self.assertIn("enlace", error)
        self.assertEqual(self.run_accion(accion="mantenimiento", tarea="limpiar_miniaturas")[0], True)   # no existe: nada que hacer


class PruebasScripts(Base):
    CARPETA = "/home/u/.config/jaime0/scripts-autorizados"
    OK = stat.S_IFREG | 0o755

    def comprobar(self, nombre, st=None, carpeta_st=None, uid=1000, lstat=None):
        st = st or stat_falso(self.OK)
        carpeta_st = carpeta_st or stat_falso(stat.S_IFDIR | 0o755)
        return S.comprobar_script(nombre, self.CARPETA, uid, lstat=lstat or (lambda p: st), estatus=lambda p: carpeta_st)

    def test_script_correcto(self):
        ruta, error = self.comprobar("copia.sh")
        self.assertIsNone(error)
        self.assertEqual(ruta, os.path.join(self.CARPETA, "copia.sh"))
        self.assertIsNone(self.comprobar("copia.sh", stat_falso(stat.S_IFREG | 0o700))[1])
        self.assertIsNone(self.comprobar("copia.sh", stat_falso(stat.S_IFREG | 0o750))[1])

    def test_nombres_peligrosos(self):
        for n in ("../x", "a/b", "/etc/passwd", "a\\b", "..", ".", "", "x..y", "a\x00b", None, 5):
            with self.subTest(n=n):
                ruta, error = self.comprobar(n)
                self.assertIsNone(ruta)
                self.assertIn("nombre de script no válido", error)

    def test_escribible_por_grupo_u_otros(self):
        for modo in (0o775, 0o757, 0o777, 0o722, 0o720):
            ruta, error = self.comprobar("x", stat_falso(stat.S_IFREG | modo))
            self.assertIsNone(ruta, oct(modo))
            self.assertIn("escritura", error)

    def test_no_ejecutable(self):
        for modo in (0o644, 0o600, 0o455):
            ruta, error = self.comprobar("x", stat_falso(stat.S_IFREG | modo))
            self.assertIsNone(ruta, oct(modo))
            self.assertIn("no es ejecutable", error)

    def test_de_otro_dueno(self):
        ruta, error = self.comprobar("x", stat_falso(self.OK, uid=0))
        self.assertIsNone(ruta)
        self.assertIn("no es del usuario", error)

    def test_no_regular(self):
        for tipo in (stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO, stat.S_IFSOCK):
            ruta, error = self.comprobar("x", stat_falso(tipo | 0o755))
            self.assertIsNone(ruta)
            self.assertIn("no es un archivo regular", error)

    def test_no_existe_y_carpeta_insegura(self):
        def sin_archivo(p):
            raise FileNotFoundError()

        self.assertIn("no existe", self.comprobar("x", lstat=sin_archivo)[1])
        self.assertIn("carpeta", self.comprobar("x", carpeta_st=stat_falso(stat.S_IFDIR | 0o777))[1])
        self.assertIn("carpeta", self.comprobar("x", carpeta_st=stat_falso(stat.S_IFDIR | 0o755, uid=0))[1])
        self.assertIn("carpeta", self.comprobar("x", carpeta_st=stat_falso(stat.S_IFREG | 0o755))[1])

        def sin_carpeta(p):
            raise FileNotFoundError()

        self.assertIn("scripts-autorizados", S.comprobar_script("x", self.CARPETA, 1000, estatus=sin_carpeta)[1])

    def accion(self, nombre="copia.sh"):
        a = self.motor.acciones
        a.estatus_script = {"lstat": lambda p: stat_falso(self.OK), "estatus": lambda p: stat_falso(stat.S_IFDIR | 0o755)}
        return a.ejecutar_accion({"accion": "script", "nombre": nombre})

    def test_se_ejecuta_sin_shell_ni_argumentos_con_timeout_de_60(self):
        ok, d = self.accion()
        self.assertTrue(ok, d)
        orden, k = self.ejec.llamadas[0]
        self.assertEqual(orden, [os.path.join(self.scripts, "copia.sh")])
        self.assertEqual(k["timeout"], 60)
        self.assertNotIn("shell", k)
        self.assertEqual(k["stdin"], subprocess.DEVNULL)
        self.assertIn("código de salida 0", d)

    def test_registra_codigo_de_salida_y_primeras_lineas_de_error(self):
        self.ejec.resp["copia.sh"] = proc(3, err="uno\n\ndos\ntres\ncuatro\n")
        ok, d = self.accion()
        self.assertFalse(ok)
        self.assertIn("código de salida 3", d)
        self.assertIn("uno | dos | tres", d)
        self.assertNotIn("cuatro", d)

    def test_timeout_del_script(self):
        self.ejec.resp["copia.sh"] = subprocess.TimeoutExpired("copia.sh", 60)
        ok, d = self.accion()
        self.assertFalse(ok)
        self.assertIn("60 s", d)

    def test_un_script_inseguro_no_se_ejecuta(self):
        a = self.motor.acciones
        a.estatus_script = {"lstat": lambda p: stat_falso(stat.S_IFREG | 0o777),
                            "estatus": lambda p: stat_falso(stat.S_IFDIR | 0o755)}
        ok, d = a.ejecutar_accion({"accion": "script", "nombre": "x.sh"})
        self.assertFalse(ok)
        self.assertIn("escritura", d)
        ok, d = a.ejecutar_accion({"accion": "script", "nombre": "../x.sh"})
        self.assertFalse(ok)
        self.assertEqual(self.ejec.llamadas, [])


# ---------------------------------------------------------------------------
# API (procesar_linea) con el servicio real
# ---------------------------------------------------------------------------

class PruebasApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-reglas-api-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        p = mock.patch.dict(os.environ, {"JAIME0_RUNTIME": os.path.join(self.tmp, "rt"),
                                         "JAIME0_ESTADO": os.path.join(self.tmp, "estado"),
                                         "XDG_CONFIG_HOME": os.path.join(self.tmp, "config")})
        p.start()
        self.addCleanup(p.stop)
        os.makedirs(os.environ["JAIME0_RUNTIME"])
        self.ejec = Ejecutor()
        self.ejec.resp["jaime0-anclar"] = lambda o: proc(0, json.dumps(
            [{"id": i, "nombre": n, "anclada": False} for i, n in APPS.items()]))
        self.sv = S.Servicio(directorio=os.environ["JAIME0_RUNTIME"], estado=os.environ["JAIME0_ESTADO"],
                             leer_umbrales=lambda: {})
        self.sv.reglas_ejecutar = self.ejec

    def pedir(self, peticion, responder=None):
        texto = S.procesar_linea(json.dumps(peticion), self.sv, responder)
        return None if texto is None else json.loads(texto)

    def test_reglas_vacio_con_catalogo_y_aplicaciones(self):
        r = self.pedir({"orden": "reglas"})
        self.assertTrue(r["ok"])
        self.assertEqual((r["reglas"], r["errores"]), ([], []))
        self.assertEqual(sorted(r["catalogo"]), ["acciones", "condiciones", "eventos"])
        self.assertEqual(r["aplicaciones"], [{"id": "org.gnome.Calculator", "nombre": "Calculadora"},
                                             {"id": "firefox", "nombre": "Firefox"}])
        self.assertTrue(all("disponible" in e and "motivo" in e for e in r["catalogo"]["eventos"]))

    def test_guardar_activar_listar_borrar(self):
        r = self.pedir({"orden": "regla_guardar", "regla": regla("Mi regla")})
        self.assertTrue(r["ok"], r)
        rid = r["regla"]["id"]
        self.assertEqual(rid, "mi-regla")
        listado = self.pedir({"orden": "reglas"})
        self.assertEqual([x["id"] for x in listado["reglas"]], [rid])
        self.assertIsNone(listado["reglas"][0]["ultima"])
        self.assertFalse(self.pedir({"orden": "regla_activar", "id": rid, "activa": False})["regla"]["activa"])
        self.assertFalse(self.pedir({"orden": "regla_activar", "id": rid, "activa": "no"})["ok"])
        self.assertFalse(self.pedir({"orden": "regla_activar", "activa": True})["ok"])
        self.assertTrue(self.pedir({"orden": "regla_borrar", "id": rid})["ok"])
        self.assertFalse(self.pedir({"orden": "regla_borrar", "id": rid})["ok"])

    def test_guardar_con_error_de_validacion_en_espanol(self):
        r = self.pedir({"orden": "regla_guardar", "regla": regla(hacer=[{"accion": "volumen", "nivel": 200}])})
        self.assertFalse(r["ok"])
        self.assertIn("«nivel» debe ser un número entero entre 0 y 100", r["error"])
        r = self.pedir({"orden": "regla_guardar", "regla": regla(hacer=[{"accion": "abrir_aplicacion", "id": "no.existe"}])})
        self.assertIn("lista de aplicaciones disponibles", r["error"])
        self.assertFalse(self.pedir({"orden": "regla_guardar", "regla": "x"})["ok"])
        self.assertFalse(self.pedir({"orden": "regla_guardar"})["ok"])

    def test_probar_e_historial(self):
        rid = self.pedir({"orden": "regla_guardar", "regla": regla("Prueba")})["regla"]["id"]
        r = self.pedir({"orden": "regla_probar", "id": rid})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["ejecucion"]["evento"], "prueba manual")
        h = self.pedir({"orden": "reglas_historial", "limite": 5})
        self.assertEqual([e["regla"] for e in h["ejecuciones"]], [rid])
        self.assertEqual(self.pedir({"orden": "reglas_historial", "limite": "x"})["ok"], True)
        self.assertFalse(self.pedir({"orden": "regla_probar", "id": "no-existe"})["ok"])
        self.assertFalse(self.pedir({"orden": "regla_probar"})["ok"])
        self.assertEqual(self.pedir({"orden": "reglas"})["reglas"][0]["ultima"]["resultado"], "ok")

    def test_probar_asincrono_contesta_despues_por_el_responder(self):
        pendientes = []
        self.sv.reglas.lanzador = lambda trabajo, fin: pendientes.append((trabajo, fin))
        rid = self.pedir({"orden": "regla_guardar", "regla": regla("Lenta")})["regla"]["id"]
        respuestas = []
        r = self.pedir({"orden": "regla_probar", "id": rid}, responder=respuestas.append)
        self.assertIsNone(r)
        self.assertEqual(respuestas, [])
        trabajo, fin = pendientes[0]
        fin(trabajo())
        self.assertEqual(len(respuestas), 1)
        self.assertTrue(json.loads(respuestas[0])["ok"])
        # sin responder y sin terminar: respuesta de error clara, sin colgarse
        self.sv.reglas.reloj = lambda: time.time() + 100
        self.assertFalse(self.pedir({"orden": "regla_probar", "id": rid})["ok"])

    def test_probar_en_cooldown_responde_error_sin_esperar(self):
        rid = self.pedir({"orden": "regla_guardar", "regla": regla("Rapida")})["regla"]["id"]
        self.pedir({"orden": "regla_probar", "id": rid})
        r = self.pedir({"orden": "regla_probar", "id": rid}, responder=lambda t: self.fail("no debe usarse"))
        self.assertFalse(r["ok"])
        self.assertIn("enfriamiento", r["error"])

    def test_evento_solo_inactivo_y_activo(self):
        self.pedir({"orden": "regla_guardar", "regla": regla("Inactivo", cuando={"evento": "inactividad", "estado": "inactivo"})})
        self.pedir({"orden": "regla_guardar", "regla": regla("Activo", cuando={"evento": "inactividad", "estado": "activo"})})
        self.assertEqual(self.pedir({"orden": "evento", "nombre": "inactivo"}), {"ok": True, "disparadas": 1})
        self.assertEqual(self.pedir({"orden": "evento", "nombre": "activo"}), {"ok": True, "disparadas": 1})
        for malo in ("bateria_baja", "hora", "", None, 5, "Inactivo"):
            with self.subTest(nombre=malo):
                self.assertFalse(self.pedir({"orden": "evento", "nombre": malo})["ok"])
        self.assertFalse(self.pedir({"orden": "evento"})["ok"])
        self.assertEqual([h["evento"] for h in S.leer_jsonl(self.sv.reglas.historial.archivo())][::-1],
                         ["Sesión activa de nuevo", "Sesión inactiva"])

    def test_importar_por_la_api(self):
        r = self.pedir({"orden": "reglas_importar", "reglas": [regla("Una"), regla(hacer=[])]})
        self.assertEqual((r["ok"], r["importadas"], len(r["errores"])), (True, 1, 1))
        listado = self.pedir({"orden": "reglas"})["reglas"][0]
        self.assertEqual((listado["activa"], listado["revisar"]), (False, True))
        self.assertFalse(self.pedir({"orden": "reglas_importar", "reglas": "x"})["ok"])
        self.assertFalse(self.pedir({"orden": "reglas_importar"})["ok"])

    def test_ordenes_de_reglas_desconocidas(self):
        self.assertEqual(self.pedir({"orden": "regla_inventada"}), {"ok": False, "error": "orden desconocida"})

    def test_los_errores_de_carga_salen_en_el_listado(self):
        archivo = os.path.join(os.environ["XDG_CONFIG_HOME"], "jaime0", "reglas.json")
        os.makedirs(os.path.dirname(archivo))
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "reglas": [{"id": "rota", "nombre": "x"}, {"nombre": 3}]}, f)
        r = self.pedir({"orden": "reglas"})
        self.assertEqual(r["reglas"], [])
        self.assertEqual([e.get("id") or e.get("indice") for e in r["errores"]], ["rota", 1])


# ---------------------------------------------------------------------------
# Cliente jaime0-reglas
# ---------------------------------------------------------------------------

class Salida:
    """Captura stdout y stderr de main()."""

    def __init__(self, f, *a, **k):
        self.f, self.a, self.k = f, a, k

    def __enter__(self):
        self.o, self.e = io.StringIO(), io.StringIO()
        self.c1, self.c2 = contextlib.redirect_stdout(self.o), contextlib.redirect_stderr(self.e)
        self.c1.__enter__()
        self.c2.__enter__()
        self.codigo = self.f(*self.a, **self.k)
        return self

    def __exit__(self, *x):
        self.c2.__exit__(*x)
        self.c1.__exit__(*x)


def cliente(argv, enviar, preguntar=None):
    with Salida(R.main, argv, enviar=enviar, preguntar=preguntar) as s:
        pass
    return s.codigo, s.o.getvalue(), s.e.getvalue()


class Servidor:
    """enviar() falso: anota las peticiones y responde con lo programado."""

    def __init__(self, respuestas=None):
        self.peticiones, self.respuestas = [], respuestas or {}

    def __call__(self, peticion, **k):
        self.peticiones.append((peticion, k))
        r = self.respuestas.get(peticion["orden"], {"ok": True})
        return r(peticion) if callable(r) else r


def sin_servicio(peticion, **k):
    raise ConnectionRefusedError("no hay socket")


CAT = {"eventos": [{"id": "bateria_baja", "nombre": "Batería baja", "descripcion": "d", "disponible": True, "motivo": None,
                    "parametros": [{"clave": "umbral", "tipo": "entero", "min": 5, "max": 95, "defecto": 20,
                                    "texto": "Porcentaje", "requerido": False}]},
                   {"id": "bluetooth", "nombre": "Bluetooth", "descripcion": "d2", "disponible": False,
                    "motivo": "BlueZ no está", "parametros": [
                        {"clave": "estado", "tipo": "opcion", "opciones": ["conectado", "desconectado"], "defecto": None,
                         "texto": "Estado", "requerido": True}]}],
       "condiciones": [{"id": "perfil_es", "nombre": "El perfil es", "descripcion": "d3", "disponible": True, "motivo": None,
                        "parametros": [{"clave": "perfil", "tipo": "perfil", "opciones": ["focus"], "defecto": None,
                                        "texto": "Perfil", "requerido": True}]}],
       "acciones": [{"id": "volumen", "nombre": "Volumen", "descripcion": "d4", "disponible": True, "motivo": None,
                     "parametros": [{"clave": "nivel", "tipo": "entero", "min": 0, "max": 100, "defecto": None,
                                     "texto": "Nivel", "requerido": True}]}]}
LISTADO = {"ok": True, "v": 1, "catalogo": CAT, "aplicaciones": [], "errores": [{"id": "rota", "error": "malo"}],
           "reglas": [{"id": "bat", "nombre": "Ahorro", "activa": True, "revisar": False,
                       "cuando": {"evento": "bateria_baja", "umbral": 20}, "si": [{"condicion": "perfil_es", "perfil": "focus"}],
                       "hacer": [{"accion": "volumen", "nivel": 30}],
                       "ultima": {"t": 1763123456, "resultado": "ok", "evento": "Batería baja (19 %)"}},
                      {"id": "imp", "nombre": "Importada", "activa": False, "revisar": True,
                       "cuando": {"evento": "bateria_baja", "umbral": 10}, "si": [], "hacer": [{"accion": "volumen", "nivel": 5}],
                       "ultima": None}]}


class PruebasCliente(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-reglas-cli-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def archivo(self, doc, nombre="x.json"):
        ruta = os.path.join(self.tmp, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return ruta

    def test_lista_en_texto_y_json(self):
        sv = Servidor({"reglas": LISTADO})
        codigo, out, err = cliente(["lista"], sv)
        self.assertEqual(codigo, 0, err)
        self.assertIn("bat  [activa]  Ahorro", out)
        self.assertIn("imp  [POR REVISAR]  Importada", out)
        self.assertIn("CUANDO: Batería baja (umbral=20)", out)
        self.assertIn("SI:     El perfil es (perfil=focus)", out)
        self.assertIn("HACER:  Volumen (nivel=30)", out)
        self.assertIn("Batería baja (19 %)", out)
        self.assertIn("Última: nunca", out)
        self.assertIn("No válida (regla rota): malo", out)
        self.assertEqual(sv.peticiones[0][0], {"orden": "reglas"})
        codigo, out, _ = cliente(["lista", "--json"], sv)
        doc = json.loads(out)
        self.assertEqual([r["id"] for r in doc["reglas"]], ["bat", "imp"])
        self.assertNotIn("catalogo", doc)

    def test_lista_vacia(self):
        codigo, out, _ = cliente(["lista"], Servidor({"reglas": {"ok": True, "reglas": [], "errores": [], "catalogo": CAT}}))
        self.assertEqual((codigo, out.strip()), (0, "No hay reglas."))

    def test_sin_servicio_error_claro_y_codigo_1(self):
        for argv in (["lista"], ["historial"], ["activar", "x"], ["desactivar", "x"], ["borrar", "x", "--si"],
                     ["probar", "x"], ["catalogo"], ["importar", self.archivo([], "l.json")], ["crear", self.archivo({}, "o.json")]):
            with self.subTest(argv=argv):
                codigo, out, err = cliente(argv, sin_servicio)
                self.assertEqual(codigo, 1)
                self.assertIn("el servicio de Jaime0 no está en marcha", err)
                self.assertEqual(out, "")

    def test_evento_sin_servicio_sale_en_silencio_con_0(self):
        for nombre in ("inactivo", "activo"):
            codigo, out, err = cliente(["evento", nombre], sin_servicio)
            self.assertEqual((codigo, out, err), (0, "", ""))
        for fallo in (OSError("x"), ValueError("rota")):
            def enviar(p, **k):
                raise fallo
            self.assertEqual(cliente(["evento", "activo"], enviar), (0, "", ""))

    def test_evento_envia_el_nombre_y_valida(self):
        sv = Servidor({"evento": {"ok": True, "disparadas": 0}})
        self.assertEqual(cliente(["evento", "inactivo"], sv), (0, "", ""))
        self.assertEqual(sv.peticiones[0][0], {"orden": "evento", "nombre": "inactivo"})
        for argv in (["evento"], ["evento", "bateria"], ["evento", "activo", "x"]):
            codigo, _o, err = cliente(argv, sv)
            self.assertEqual(codigo, 1)
            self.assertIn("uso:", err)
        self.assertEqual(len(sv.peticiones), 1)
        codigo, _o, err = cliente(["evento", "activo"], Servidor({"evento": {"ok": False, "error": "no"}}))
        self.assertEqual((codigo, err.strip()), (1, "jaime0-reglas: no"))

    def test_activar_y_desactivar(self):
        sv = Servidor({"regla_activar": {"ok": True}})
        self.assertEqual(cliente(["activar", "bat"], sv)[:2], (0, "Regla activada: bat\n"))
        self.assertEqual(cliente(["desactivar", "bat"], sv)[:2], (0, "Regla desactivada: bat\n"))
        self.assertEqual([p[0] for p in sv.peticiones],
                         [{"orden": "regla_activar", "id": "bat", "activa": True},
                          {"orden": "regla_activar", "id": "bat", "activa": False}])
        codigo, _o, err = cliente(["activar", "x"], Servidor({"regla_activar": {"ok": False, "error": "no existe esa regla"}}))
        self.assertEqual((codigo, err.strip()), (1, "jaime0-reglas: no existe esa regla"))
        self.assertEqual(cliente(["activar"], sv)[0], 1)

    def test_borrar_pide_confirmacion(self):
        sv = Servidor({"regla_borrar": {"ok": True}})
        preguntas = []

        def no(p):
            preguntas.append(p)
            return "n"

        codigo, _o, err = cliente(["borrar", "bat"], sv, no)
        self.assertEqual(codigo, 1)
        self.assertIn("cancelado", err)
        self.assertEqual(sv.peticiones, [])
        self.assertIn("«bat»", preguntas[0])
        self.assertEqual(cliente(["borrar", "bat"], sv, lambda p: "")[0], 1)

        def eof(p):
            raise EOFError()

        self.assertEqual(cliente(["borrar", "bat"], sv, eof)[0], 1)
        self.assertEqual(sv.peticiones, [])
        self.assertEqual(cliente(["borrar", "bat"], sv, lambda p: "s")[:2], (0, "Regla borrada: bat\n"))
        self.assertEqual(sv.peticiones[0][0], {"orden": "regla_borrar", "id": "bat"})
        self.assertEqual(cliente(["borrar", "--si", "bat"], sv, lambda p: self.fail("no debe preguntar"))[0], 0)
        self.assertEqual(len(sv.peticiones), 2)

    def test_probar(self):
        ej = {"resultado": "ok", "detalle": "1 acción(es) correcta(s)",
              "acciones": [{"accion": "volumen", "resultado": "ok", "detalle": "Volumen al 30 %"}]}
        sv = Servidor({"regla_probar": {"ok": True, "ejecucion": ej}})
        codigo, out, _ = cliente(["probar", "bat"], sv)
        self.assertEqual(codigo, 0)
        self.assertIn("Resultado: ok", out)
        self.assertIn("- volumen: ok (Volumen al 30 %)", out)
        self.assertGreaterEqual(sv.peticiones[0][1]["timeout"], 300)
        ej["resultado"] = "fallo"
        self.assertEqual(cliente(["probar", "bat"], sv)[0], 1)
        codigo, _o, err = cliente(["probar", "bat"], Servidor({"regla_probar": {"ok": False, "error": "enfriamiento: espera 20 s"}}))
        self.assertEqual((codigo, err.strip()), (1, "jaime0-reglas: enfriamiento: espera 20 s"))

    def test_historial(self):
        doc = {"ok": True, "ejecuciones": [{"t": 1763123456, "regla": "bat", "nombre": "Ahorro", "evento": "Batería baja (19 %)",
                                            "resultado": "fallo", "detalle": "0 de 1", "acciones": [
                                                {"accion": "volumen", "resultado": "fallo", "detalle": "wpctl no está instalado"}]}]}
        sv = Servidor({"reglas_historial": doc})
        codigo, out, _ = cliente(["historial", "-n", "5"], sv)
        self.assertEqual(codigo, 0)
        self.assertIn("fallo", out)
        self.assertIn("Ahorro", out)
        self.assertIn("- volumen: fallo (wpctl no está instalado)", out)
        self.assertEqual(sv.peticiones[0][0], {"orden": "reglas_historial", "limite": 5})
        self.assertEqual(json.loads(cliente(["historial", "--json"], sv)[1]), doc)
        self.assertEqual(sv.peticiones[1][0]["limite"], 20)
        for malo in (["-n"], ["-n", "x"], ["-n", "0"]):
            self.assertEqual(cliente(["historial"] + malo, sv)[0], 1)
        self.assertIn("Todavía no", cliente(["historial"], Servidor({"reglas_historial": {"ok": True, "ejecuciones": []}}))[1])

    def test_importar(self):
        sv = Servidor({"reglas_importar": {"ok": True, "importadas": 2, "errores": [{"indice": 1, "error": "mal"}]}})
        lista = [regla("a"), regla("b"), regla("c")]
        codigo, out, err = cliente(["importar", self.archivo(lista)], sv)
        self.assertEqual(codigo, 0)
        self.assertIn("importadas: 2", out)
        self.assertIn("desactivadas", out)
        self.assertIn("entrada 2): mal", err)
        self.assertEqual(sv.peticiones[0][0], {"orden": "reglas_importar", "reglas": lista})
        cliente(["importar", self.archivo({"v": 1, "reglas": lista}, "y.json")], sv)
        self.assertEqual(sv.peticiones[1][0]["reglas"], lista)
        todas_mal = Servidor({"reglas_importar": {"ok": True, "importadas": 0, "errores": [{"indice": 0, "error": "x"}]}})
        self.assertEqual(cliente(["importar", self.archivo(lista, "z.json")], todas_mal)[0], 1)

    def test_importar_y_crear_con_archivos_malos(self):
        sv = Servidor()
        for argv in (["importar", os.path.join(self.tmp, "no-existe.json")], ["importar", self.archivo("{roto", "r.json")],
                     ["importar", self.archivo({"x": 1}, "o.json")], ["importar"], ["crear"],
                     ["crear", self.archivo([1, 2], "l.json")], ["crear", self.archivo({"reglas": []}, "m.json")],
                     ["crear", os.path.join(self.tmp, "no-existe.json")]):
            with self.subTest(argv=argv):
                codigo, _o, err = cliente(argv, sv)
                self.assertEqual(codigo, 1)
                self.assertTrue(err.startswith("jaime0-reglas: "))
        self.assertEqual(sv.peticiones, [])

    def test_crear(self):
        r = regla("Nueva")
        sv = Servidor({"regla_guardar": {"ok": True, "regla": dict(r, id="nueva")}})
        self.assertEqual(cliente(["crear", self.archivo(r)], sv)[:2], (0, "Regla guardada: nueva\n"))
        self.assertEqual(sv.peticiones[0][0], {"orden": "regla_guardar", "regla": r})
        codigo, _o, err = cliente(["crear", self.archivo(r)], Servidor({"regla_guardar": {"ok": False, "error": "falta «clase»"}}))
        self.assertEqual((codigo, err.strip()), (1, "jaime0-reglas: falta «clase»"))

    def test_catalogo(self):
        sv = Servidor({"reglas": LISTADO})
        codigo, out, _ = cliente(["catalogo"], sv)
        self.assertEqual(codigo, 0)
        for trozo in ("CUANDO (eventos)", "SI (condiciones, opcionales)", "HACER (acciones)", "bateria_baja  Batería baja",
                      "umbral: Porcentaje (entero 5–95; opcional, por defecto 20)", "Bluetooth  [NO DISPONIBLE]",
                      "Motivo: BlueZ no está", "uno de: conectado, desconectado", "nivel: Nivel (entero 0–100)"):
            self.assertIn(trozo, out)
        self.assertEqual(json.loads(cliente(["catalogo", "--json"], sv)[1]), CAT)

    def test_ayuda_y_orden_desconocida(self):
        self.assertEqual(cliente([], Servidor())[0], 0)
        self.assertIn("Uso:", cliente(["--help"], Servidor())[1])
        codigo, _o, err = cliente(["inventada"], Servidor())
        self.assertEqual(codigo, 1)
        self.assertIn("orden desconocida", err)

    def test_pedir_socket_sin_runtime_es_oserror(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OSError):
                R.pedir_socket({"orden": "reglas"})


class PruebasHypridle(unittest.TestCase):
    def test_hypridle_llama_a_los_eventos_que_existen(self):
        conf = (REPO / "config/includes.chroot_after_packages/etc/skel/.config/hypr/hypridle.conf").read_text(encoding="utf-8")
        self.assertIn("on-timeout = jaime0-reglas evento inactivo", conf)
        self.assertIn("on-resume = jaime0-reglas evento activo", conf)


if __name__ == "__main__":
    unittest.main()
