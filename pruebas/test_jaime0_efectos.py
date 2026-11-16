#!/usr/bin/env python3
"""Pruebas de la Fase 2 (desacoplar el servicio): el hilo de efectos (Trabajador) y que el
servicio no se bloquee aunque power-profiles-daemon, swaync, hyprctl o jaime0-ajustes
tarden o se cuelguen. Usan el sistema falso de las pruebas de perfiles."""

import json
import os
import subprocess
import threading
import time
import unittest
from unittest import mock

from test_jaime0_perfil import S, Base, SistemaFalso


def instante(**cambios):
    i = {"v": 1, "t": int(time.time()), "intervalo": 10}
    i.update(cambios)
    return i


def esperar_hasta(cond, segundos=5.0):
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


class PruebasTrabajador(unittest.TestCase):
    def iniciado(self):
        t = S.Trabajador()
        vuelta = []                                 # lo que pasa por al_bucle, en orden
        t.iniciar(al_bucle=lambda fn, *a: (vuelta.append(a), fn(*a)))
        return t, vuelta

    def test_sin_iniciar_ejecuta_en_el_acto(self):
        t, res = S.Trabajador(), []
        t.enviar(lambda: 7, res.append)
        self.assertEqual(res, [7])
        self.assertFalse(t.activo())
        self.assertEqual(t.esperar(lambda: 8), 8)

    def test_ejecuta_en_orden_en_su_hilo_y_devuelve_por_al_bucle(self):
        t, vuelta = self.iniciado()
        hilos, res = [], []
        for i in range(5):
            t.enviar(lambda i=i: (hilos.append(threading.current_thread().name), i)[1], res.append)
        self.assertTrue(esperar_hasta(lambda: len(res) == 5))
        self.assertEqual(res, [0, 1, 2, 3, 4])
        self.assertEqual(set(hilos), {"jaime0-efectos"})
        self.assertEqual(vuelta, [(0,), (1,), (2,), (3,), (4,)])

    def test_un_error_no_mata_el_hilo(self):
        t, _ = self.iniciado()
        res = []
        registrar = mock.patch.object(S.base_mod, "registrar")
        registrar.start()
        self.addCleanup(registrar.stop)
        t.enviar(lambda: 1 / 0, res.append, "división")
        t.enviar(lambda: "sigue", res.append)
        self.assertTrue(esperar_hasta(lambda: len(res) == 2))
        self.assertEqual(res, [S.ERROR_INTERNO, "sigue"])

    def test_esperar_desde_otro_hilo_y_con_limite(self):
        t, _ = self.iniciado()
        self.assertEqual(t.esperar(lambda: "hecho"), "hecho")
        suelta = threading.Event()
        t.enviar(lambda: suelta.wait(5))            # el hilo queda ocupado
        inicio = time.monotonic()
        r = t.esperar(lambda: "tarde", "prueba", limite=0.2)
        self.assertLess(time.monotonic() - inicio, 2)
        self.assertFalse(r["ok"])
        self.assertIn("sin respuesta en 0.2 s", r["error"])
        suelta.set()

    def test_esperar_dentro_del_propio_hilo_no_se_bloquea(self):
        t, _ = self.iniciado()
        res = []
        t.enviar(lambda: t.esperar(lambda: 5), res.append)
        self.assertTrue(esperar_hasta(lambda: res == [5], 2))

    def test_estado_dice_que_hace_y_cuanto_lleva(self):
        t, _ = self.iniciado()
        suelta = threading.Event()
        t.enviar(lambda: suelta.wait(5), descripcion="algo lento")
        t.enviar(lambda: None)
        self.assertTrue(esperar_hasta(lambda: t.en_curso is not None))
        e = t.estado()
        self.assertEqual(e["en_curso"], "algo lento")
        self.assertEqual(e["pendientes"], 1)
        self.assertGreaterEqual(e["segundos"], 0)
        suelta.set()
        self.assertTrue(esperar_hasta(lambda: t.estado() == {"pendientes": 0, "en_curso": None, "segundos": None}))


class PruebasRecordado(unittest.TestCase):
    def test_recuerda_y_caduca(self):
        reloj, llamadas = [0.0], []
        r = S.Recordado(lambda: llamadas.append(1) or len(llamadas), 60, reloj=lambda: reloj[0])
        self.assertEqual((r(), r()), (1, 1))
        reloj[0] = 61
        self.assertEqual(r(), 2)
        self.assertEqual(r.refrescar(), 3)


class SistemaLento(SistemaFalso):
    """swaync que no contesta hasta que se suelte (como un swaync-client colgado)."""

    def __init__(self, **k):
        super().__init__(**k)
        self.suelta = threading.Event()
        self.hilos = []

    def dnd_poner(self, activo):
        self.hilos.append(threading.current_thread().name)
        self.suelta.wait(5)
        super().dnd_poner(activo)


class PruebasSinBloqueo(Base):
    def setUp(self):
        super().setUp()
        self.sis = SistemaLento()
        self.sv = self.servicio()
        self.sv.instante = instante()
        self.sv.publicar("ONLINE", [])
        self.sv.efectos.iniciar(al_bucle=lambda fn, *a: fn(*a))
        self.addCleanup(self.sis.suelta.set)

    def test_cambiar_de_perfil_no_bloquea_el_socket(self):
        respuestas = []
        inicio = time.monotonic()
        r = S.procesar_linea('{"orden":"perfil","valor":"focus"}', self.sv, respuestas.append)
        self.assertIsNone(r, "se contesta al terminar, no ahora")
        # Mientras swaync no contesta, el socket sigue atendiendo:
        estado = json.loads(S.procesar_linea('{"orden":"estado"}', self.sv))
        self.assertEqual(estado["estado"], "ONLINE")
        self.assertLess(time.monotonic() - inicio, 1.0)
        self.assertTrue(esperar_hasta(lambda: self.sv.efectos.estado()["en_curso"] == "orden perfil"))
        self.assertEqual(respuestas, [])
        self.sis.suelta.set()
        self.assertTrue(esperar_hasta(lambda: len(respuestas) == 1))
        doc = json.loads(respuestas[0])
        self.assertEqual((doc["ok"], doc["activo"]), (True, "focus"))
        self.assertEqual(self.sis.hilos, ["jaime0-efectos"])

    def test_las_medidas_siguen_mientras_se_aplica_un_perfil(self):
        S.procesar_linea('{"orden":"perfil","valor":"focus"}', self.sv, lambda t: None)
        self.assertTrue(esperar_hasta(lambda: self.sis.hilos))
        inicio = time.monotonic()
        self.sv.instante = instante(t=int(time.time()) + 1)
        self.sv.publicar("WARNING", [{"gravedad": "WARNING", "componente": "cpu", "texto": "x"}])
        self.assertLess(time.monotonic() - inicio, 1.0)
        with open(os.path.join(self.rt, "estado.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["estado"], "WARNING")

    def test_una_regla_aplica_el_perfil_en_el_hilo_de_efectos(self):
        self.sis.suelta.set()
        res = []
        hilo = threading.Thread(target=lambda: res.append(self.sv.reglas.acciones.aplicar_perfil("focus")),
                                name="regla")
        hilo.start()
        hilo.join(5)
        self.assertEqual(res[0]["activo"], "focus")
        self.assertEqual(self.sis.hilos, ["jaime0-efectos"])

    def test_listar_reglas_no_espera_a_jaime0_anclar(self):
        suelta = threading.Event()
        self.addCleanup(suelta.set)
        self.sv.reglas.apps = lambda: (suelta.wait(5), {"kitty": "Kitty"})[1]
        respuestas = []
        inicio = time.monotonic()
        self.assertIsNone(S.procesar_linea('{"orden":"reglas"}', self.sv, respuestas.append))
        self.assertLess(time.monotonic() - inicio, 1.0)
        suelta.set()
        self.assertTrue(esperar_hasta(lambda: respuestas))
        doc = json.loads(respuestas[0])
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["aplicaciones"], [{"id": "kitty", "nombre": "Kitty"}])

    def test_los_umbrales_se_leen_en_el_hilo_de_efectos(self):
        hilos = []
        self.sv._leer_umbrales = lambda: (hilos.append(threading.current_thread().name),
                                          {"historial_dias": 30})[1]
        self.sv._recarga_diferida()
        self.assertTrue(esperar_hasta(lambda: self.sv.historico.dias == 30))
        self.assertEqual(hilos, ["jaime0-efectos"])

    def test_estado_json_dice_que_hace_el_hilo_de_efectos(self):
        doc = self.sv.estado_doc()
        self.assertEqual(doc["servicio"]["efectos"], {"pendientes": 0, "en_curso": None, "segundos": None})


class PruebasAvisoBarra(unittest.TestCase):
    def test_un_pgrep_colgado_no_hace_saltar_nada(self):
        with mock.patch.object(S.sistema_mod, "modo_prueba", return_value=False), \
                mock.patch.object(S.os, "getuid", create=True, return_value=1000), \
                mock.patch.object(S.shutil, "which", return_value="/usr/bin/pgrep"), \
                mock.patch.object(S.subprocess, "run", side_effect=subprocess.TimeoutExpired("pgrep", 3)):
            S.avisar_barra()


def doc_diagnostico(*problemas, t=1000):
    return {"ok": True, "v": 1, "t": t, "duracion": 2.0,
            "resumen": {"CRITICAL": 0, "ERROR": 0, "WARNING": 0, "INFO": 0, "NO_DISPONIBLE": 0, "NO_APLICA": 0},
            "areas": [], "problemas": [{"id": i, "titulo": i.upper(), "gravedad": g} for i, g in problemas]}


class Proceso:
    def __init__(self, salida="", rc=0, err=""):
        self.stdout, self.returncode, self.stderr = salida, rc, err


class PruebasDiagnosticoServicio(Base):
    """Fase 5: el servicio lanza jaime0-diagnostico en su hilo, recuerda el resultado y lo
    resume para SYSTEM. Nunca repara nada."""

    def test_resumen_para_system(self):
        d = doc_diagnostico(("a", "INFO"), ("b", "WARNING"), ("c", "CRITICAL"), ("d", "ERROR"), ("e", "WARNING"))
        r = S.resumen_diagnostico(d)
        self.assertEqual([p["id"] for p in r["principales"]], ["c", "d", "b"])
        self.assertEqual(r["total"], 4)                      # el INFO no es una alerta
        self.assertIsNone(S.resumen_diagnostico({"ok": False, "error": "x"}))
        self.assertIsNone(S.resumen_diagnostico(None))

    def test_un_diagnostico_a_la_vez_y_resultado(self):
        pendiente, hechos = [], []
        salida = json.dumps(doc_diagnostico(("nvidia", "WARNING")))
        dg = S.Diagnosticador(ejecutar=lambda *a, **k: Proceso(salida), buscar=lambda n: "/bin/" + n,
                              lanzar=pendiente.append, al_terminar=hechos.append)
        self.assertTrue(dg.ejecutar_diagnostico())
        self.assertIsNotNone(dg.desde)
        self.assertFalse(dg.ejecutar_diagnostico(), "ya hay uno en marcha")
        pendiente.pop()()
        self.assertIsNone(dg.desde)
        self.assertEqual(dg.ultimo["problemas"][0]["id"], "nvidia")
        self.assertEqual(hechos[0]["ok"], True)
        self.assertTrue(dg.ejecutar_diagnostico(), "terminado: se puede volver a lanzar")

    def test_error_y_programa_ausente(self):
        dg = S.Diagnosticador(ejecutar=lambda *a, **k: Proceso("", 1, "fallo al leer"), buscar=lambda n: "/bin/" + n,
                              lanzar=lambda fn: fn())
        res = []
        dg.ejecutar_diagnostico(res.append)
        self.assertEqual(res[0], {"ok": False, "error": "fallo al leer"})
        self.assertIsNone(dg.ultimo)
        sin = S.Diagnosticador(buscar=lambda n: None, lanzar=lambda fn: fn())
        sin.ejecutar_diagnostico(res.append)
        self.assertEqual(res[1]["error"], "falta jaime0-diagnostico")

    def test_solo_avisa_de_problemas_nuevos_y_lo_resume_en_estado(self):
        sv = self.servicio()
        sv.instante = instante()
        sv.publicar("ONLINE", [])
        eventos = []
        sv.evento = lambda texto, *a, **k: eventos.append(texto)
        sv.diagnosticador.ultimo = doc_diagnostico(("nvidia", "WARNING"))
        sv._diagnostico_hecho(sv.diagnosticador.ultimo)          # primera vez: sin avisos
        sv.diagnosticador.ultimo = doc_diagnostico(("nvidia", "WARNING"), ("disco", "CRITICAL"))
        sv._diagnostico_hecho(sv.diagnosticador.ultimo)
        self.assertEqual(eventos, ["Diagnóstico: DISCO"])
        with open(os.path.join(self.rt, "estado.json"), encoding="utf-8") as f:
            d = json.load(f)["diagnostico"]
        self.assertEqual((d["total"], d["principales"][0]["id"]), (2, "disco"))

    def test_ordenes_del_socket(self):
        sv = self.servicio()
        self.assertEqual(json.loads(S.procesar_linea('{"orden":"diagnostico"}', sv))["ultimo"], None)
        self.assertFalse(json.loads(S.procesar_linea('{"orden":"diagnostico_ejecutar"}', sv))["ok"])
        sv.diagnosticador.lanzar = lambda fn: None            # se queda "en marcha"
        self.assertIsNone(S.procesar_linea('{"orden":"diagnostico_ejecutar"}', sv, lambda t: None))
        r = json.loads(S.procesar_linea('{"orden":"diagnostico_ejecutar"}', sv, lambda t: None))
        self.assertEqual(r, {"ok": False, "error": "ya hay un diagnóstico en marcha"})


if __name__ == "__main__":
    unittest.main()
