#!/usr/bin/env python3
"""Pruebas de jaime0-servicio y jaime0-salud con una raiz falsa (JAIME0_RAIZ) y un
directorio de ejecucion temporal (JAIME0_RUNTIME). No necesitan gi, D-Bus ni sockets.

    python3 -m unittest discover -s pruebas -v
"""
import copy
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
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


S = cargar("jaime0_servicio_pruebas", "jaime0-servicio")
H = cargar("jaime0_salud_pruebas", "jaime0-salud")


class Base(unittest.TestCase):
    """Crea una raiz falsa y un directorio de ejecucion por prueba."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-serv-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.raiz = os.path.join(self.tmp, "raiz")
        self.rt = os.path.join(self.tmp, "rt")
        os.makedirs(self.raiz)
        os.makedirs(self.rt)
        p = mock.patch.dict(os.environ, {"JAIME0_RAIZ": self.raiz, "JAIME0_RUNTIME": self.rt})
        p.start()
        self.addCleanup(p.stop)

    def escribir(self, rel, texto):
        p = os.path.join(self.raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        return p


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def instante_base(**cambios):
    inst = {"v": 1, "t": int(time.time()), "intervalo": 10,
            "cpu": {"total": 10.0, "nucleos": [10.0], "mhz": None, "temp": 50.0},
            "ram": {"usada": 4000, "total": 16000, "swap": 0, "swap_total": 8000, "presion": 0.0},
            "temp": [], "gpu": {"nvidia": None, "temp": None},
            "disco": [{"punto": "/", "usado": 100.0, "total": 500.0, "lectura": None, "escritura": None}],
            "bateria": None, "cargador": None, "uptime": 100, "procesos": None, "fallidas": None,
            "estado": "ONLINE", "alertas": 0}
    inst.update(cambios)
    return inst


class PruebasMedicion(Base):
    def test_ruta_antepone_la_raiz_falsa(self):
        self.assertEqual(S.ruta("proc", "stat"), os.path.join(self.raiz, "proc", "stat"))
        self.assertEqual(os.path.normpath(S.ruta("/proc/stat")), os.path.join(self.raiz, "proc", "stat"))

    def test_directorio_de_ejecucion_se_crea(self):
        d = os.path.join(self.tmp, "nuevo", "jaime0")
        with mock.patch.dict(os.environ, {"JAIME0_RUNTIME": d}):
            self.assertEqual(S.directorio_ejecucion(), d)
        self.assertTrue(os.path.isdir(d))

    def test_cpu_por_deltas(self):
        a = S.parsear_cpu_stat("cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 50 0 50 350 50 0 0 0 0 0\n"
                               "cpu1 50 0 50 350 50 0 0 0 0 0\nintr 5\n")
        b = S.parsear_cpu_stat("cpu  200 0 200 750 150 0 0 0 0 0\ncpu0 100 0 100 375 75 0 0 0 0 0\n"
                               "cpu1 100 0 100 375 75 0 0 0 0 0\n")
        # total: +100 user +100 sys, +50 idle +50 iowait => 200 activos de 300
        self.assertAlmostEqual(S.porcentaje_cpu(a[0], b[0]), 66.7)
        self.assertEqual(sorted(a[1]), [0, 1])
        self.assertAlmostEqual(S.porcentaje_cpu(a[1][0], b[1][0]), 66.7)
        self.assertIsNone(S.porcentaje_cpu(a[0], a[0]))

    def test_muestreador_con_raiz_falsa(self):
        self.escribir("proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
        self.escribir("sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "2600000\n")
        m = S.Muestreador()
        m.base()
        self.escribir("proc/stat", "cpu  150 0 150 900 0 0 0 0 0 0\ncpu0 150 0 150 900 0 0 0 0 0 0\n")
        med = m.muestrear()
        self.assertEqual(med["cpu"]["total"], 50.0)
        self.assertEqual(med["cpu"]["nucleos"], [50.0])
        self.assertEqual(med["cpu"]["mhz"], [2600])
        self.assertIsNone(med["cpu"]["temp"])
        self.assertIsNone(med["bateria"])
        self.assertIsNone(med["cargador"])
        self.assertIsNone(med["gpu"]["nvidia"])
        self.assertIsNone(med["gpu"]["temp"])

    def test_frecuencia_inexistente_es_null(self):
        self.escribir("proc/stat", "cpu  1 0 1 8 0 0 0 0 0 0\ncpu0 1 0 1 8 0 0 0 0 0 0\n")
        m = S.Muestreador()
        m.base()
        self.assertIsNone(m.muestrear()["cpu"]["mhz"])

    def test_ram_y_presion(self):
        self.escribir("proc/meminfo", "MemTotal: 16384000 kB\nMemFree: 1000 kB\nMemAvailable: 12288000 kB\n"
                                      "SwapTotal: 8192000 kB\nSwapFree: 7168000 kB\n")
        self.escribir("proc/pressure/memory", "some avg10=1.50 avg60=0.50 avg300=0.10 total=123\n"
                                              "full avg10=0.20 avg60=0.00 avg300=0.00 total=5\n")
        r = S.leer_ram()
        self.assertEqual(r["total"], 16000)
        self.assertEqual(r["usada"], 4000)
        self.assertEqual(r["swap"], 1000)
        self.assertEqual(r["swap_total"], 8000)
        self.assertEqual(r["presion"], 1.5)

    def test_ram_sin_presion_ni_meminfo(self):
        self.assertIsNone(S.leer_ram())
        self.escribir("proc/meminfo", "MemTotal: 1024 kB\nMemAvailable: 512 kB\n")
        self.assertIsNone(S.leer_ram()["presion"])

    def test_temperaturas_y_cpu_temp_coretemp(self):
        self.escribir("sys/class/hwmon/hwmon0/name", "coretemp\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_input", "48000\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_label", "Package id 0\n")
        self.escribir("sys/class/hwmon/hwmon0/temp2_input", "52000\n")
        self.escribir("sys/class/hwmon/hwmon0/temp2_label", "Core 0\n")
        self.escribir("sys/class/hwmon/hwmon1/name", "nvme\n")
        self.escribir("sys/class/hwmon/hwmon1/temp1_input", "36900\n")   # sin etiqueta: temp1
        t = S.leer_temperaturas()
        self.assertIn({"id": "coretemp/Package id 0", "c": 48.0}, t)
        self.assertIn({"id": "coretemp/Core 0", "c": 52.0}, t)
        self.assertIn({"id": "nvme/temp1", "c": 36.9}, t)
        self.assertEqual(S.temperatura_cpu(t), 48.0)

    def test_cpu_temp_alternativas_y_ausencia(self):
        self.assertIsNone(S.temperatura_cpu([]))
        self.assertIsNone(S.temperatura_cpu([{"id": "nvme/Composite", "c": 40.0}]))
        self.assertEqual(S.temperatura_cpu([{"id": "k10temp/Tctl", "c": 61.0}, {"id": "nvme/x", "c": 70.0}]), 61.0)
        self.assertEqual(S.temperatura_cpu([{"id": "coretemp/Core 0", "c": 50.0},
                                            {"id": "coretemp/Core 1", "c": 57.0}]), 57.0)
        self.assertEqual(S.leer_temperaturas(), [])

    def test_bateria_descargando_con_estimacion(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "status", "Discharging\n")
        self.escribir(b + "capacity", "83\n")
        self.escribir(b + "power_now", "10000000\n")        # 10 W
        self.escribir(b + "energy_now", "40000000\n")       # 40 Wh -> 240 min
        self.escribir(b + "energy_full", "45500000\n")
        self.escribir(b + "energy_full_design", "50000000\n")
        r = S.leer_bateria()
        self.assertEqual(r, {"nivel": 83, "estado": "descargando", "vatios": 10.0,
                             "minutos_estimados": 240, "salud": 91.0, "estimado": True})

    def test_bateria_con_corriente_y_tension(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "status", "Discharging\n")
        self.escribir(b + "capacity", "50\n")
        self.escribir(b + "current_now", "1000000\n")       # 1 A
        self.escribir(b + "voltage_now", "11000000\n")      # 11 V -> 11 W
        self.escribir(b + "charge_now", "2000000\n")        # 2 Ah -> 120 min
        self.escribir(b + "charge_full", "4000000\n")
        self.escribir(b + "charge_full_design", "5000000\n")
        r = S.leer_bateria()
        self.assertEqual(r["vatios"], 11.0)
        self.assertEqual(r["minutos_estimados"], 120)
        self.assertEqual(r["salud"], 80.0)

    def test_bateria_cargando_sin_estimacion(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "status", "Charging\n")
        self.escribir(b + "capacity", "40\n")
        self.escribir(b + "power_now", "20000000\n")
        self.escribir(b + "energy_now", "20000000\n")
        r = S.leer_bateria()
        self.assertEqual(r["estado"], "cargando")
        self.assertEqual(r["vatios"], 20.0)
        self.assertIsNone(r["minutos_estimados"])
        self.assertIsNone(r["salud"])

    def test_estados_de_bateria_traducidos(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "capacity", "100\n")
        for original, esperado in (("Full", "llena"), ("Not charging", "sin-cargar"), ("Unknown", "desconocido")):
            self.escribir(b + "status", original + "\n")
            self.assertEqual(S.leer_bateria()["estado"], esperado)

    def test_sin_bateria_es_null_y_cargador(self):
        self.assertIsNone(S.leer_bateria())
        self.assertIsNone(S.leer_cargador())
        self.escribir("sys/class/power_supply/AC/type", "Mains\n")
        self.escribir("sys/class/power_supply/AC/online", "0\n")
        self.assertFalse(S.leer_cargador())
        self.escribir("sys/class/power_supply/AC/online", "1\n")
        self.assertTrue(S.leer_cargador())

    def _gpu(self, runtime=None, driver=True, vendor="0x10de", clase="0x030000"):
        d = "sys/bus/pci/devices/0000-01-00.0/"
        self.escribir(d + "vendor", vendor + "\n")
        self.escribir(d + "class", clase + "\n")
        if runtime:
            self.escribir(d + "power/runtime_status", runtime + "\n")
        if driver:
            os.makedirs(os.path.join(self.raiz, "sys/bus/pci/devices/0000-01-00.0/driver"), exist_ok=True)

    def test_nvidia_suspendida_activa_sin_driver_y_ausente(self):
        self.assertIsNone(S.estado_nvidia())
        self._gpu(runtime="suspended")
        self.assertEqual(S.estado_nvidia(), "suspendida")
        self._gpu(runtime="active")
        self.assertEqual(S.estado_nvidia(), "activa")
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self._gpu(runtime="active", driver=False)
        self.assertEqual(S.estado_nvidia(), "sin-driver")

    def test_nvidia_ignora_otros_fabricantes_y_clases(self):
        self._gpu(runtime="active", vendor="0x8086")
        self.assertIsNone(S.estado_nvidia())
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self._gpu(runtime="active", clase="0x040300")     # audio de la NVIDIA, no la GPU
        self.assertIsNone(S.estado_nvidia())
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self._gpu(runtime="suspended", clase="0x030200")  # 3D controller
        self.assertEqual(S.estado_nvidia(), "suspendida")

    def test_disco_en_gib_y_diskstats(self):
        v = mock.Mock(f_blocks=1000, f_bfree=400, f_frsize=1024 ** 3 // 10)
        with mock.patch.object(S.os, "statvfs", create=True, return_value=v):
            u = S.uso_disco("/")
        self.assertEqual(u, {"punto": "/", "usado": 60.0, "total": 100.0})
        d = S.parsear_diskstats("   8       0 sda 10 0 2000 5 20 0 4000 9 0 0 0\n"
                                "   8       1 sda1 5 0 1000 2 10 0 3000 4 0 0 0\n")
        self.assertEqual(d["sda"], (2000, 4000))
        # 2000 sectores en 1 s = 1,024 MB/s
        self.assertEqual(S.io_disco((0, 0), (2000, 4000), 1.0), (1.02, 2.05))
        self.assertEqual(S.io_disco(None, (1, 1), 1.0), (None, None))

    def test_procesos_top_y_desaparecidos(self):
        def proc(pid, nombre, ut, st, rss=None):
            self.escribir(f"proc/{pid}/stat", f"{pid} ({nombre} x) S 1 1 1 0 -1 0 0 0 0 0 {ut} {st} 0 0 20 0 1 0 1 1 1\n")
            if rss:
                self.escribir(f"proc/{pid}/status", f"Name: {nombre}\nVmRSS:\t{rss} kB\n")
        proc(10, "alfa", 100, 0, 2048)
        proc(11, "beta", 0, 0)
        proc(12, "gamma", 5, 5)
        antes = S.leer_procesos()
        self.assertEqual(antes[10], (100, "alfa x"))
        proc(10, "alfa", 150, 50, 2048)    # +100 tics
        proc(11, "beta", 0, 1)
        shutil.rmtree(os.path.join(self.raiz, "proc", "12"))    # desaparece
        proc(13, "nuevo", 500, 0)                                # sin muestra previa
        self.escribir("proc/basura", "no es un pid")
        with mock.patch.object(S, "tics_por_segundo", return_value=100):
            top = S.procesos_top(antes, S.leer_procesos(), 1.0)
        self.assertEqual([p["pid"] for p in top], [10, 11])
        self.assertEqual(top[0], {"pid": 10, "nombre": "alfa x", "cpu": 100.0, "ram": 2})
        self.assertIsNone(top[1]["ram"])

    def test_uptime(self):
        self.assertIsNone(S.leer_uptime())
        self.escribir("proc/uptime", "12345.67 9999.00\n")
        self.assertEqual(S.leer_uptime(), 12345)


class PruebasEvaluar(unittest.TestCase):
    def comp(self, inst, estado, gravedad=None, componente=None):
        e, motivos = S.evaluar(inst, S.UMBRALES)
        self.assertEqual(e, estado, motivos)
        if componente:
            self.assertIn((gravedad, componente), [(m["gravedad"], m["componente"]) for m in motivos])
        return motivos

    def test_online(self):
        self.assertEqual(S.evaluar(instante_base(), S.UMBRALES), ("ONLINE", []))

    def test_datos_ausentes_no_alertan(self):
        i = instante_base(cpu={"total": None, "nucleos": None, "mhz": None, "temp": None},
                          ram=None, disco=None, bateria=None)
        self.assertEqual(S.evaluar(i), ("ONLINE", []))

    def test_temperatura(self):
        i = instante_base()
        i["cpu"]["temp"] = 85.0
        self.comp(i, "WARNING", "WARNING", "cpu")
        i["cpu"]["temp"] = 95.0
        m = self.comp(i, "CRITICAL", "CRITICAL", "cpu")
        self.assertEqual(len(m), 1)
        self.assertIn("95", m[0]["texto"])

    def test_disco(self):
        i = instante_base(disco=[{"punto": "/home", "usado": 91.0, "total": 100.0}])
        m = self.comp(i, "WARNING", "WARNING", "disco")
        self.assertEqual(m[0]["texto"], "Disco /home al 91 %")
        i["disco"][0]["usado"] = 95.0
        self.comp(i, "CRITICAL", "CRITICAL", "disco")

    def test_bateria_solo_si_descarga(self):
        bat = {"nivel": 15, "estado": "descargando", "vatios": 5.0, "minutos_estimados": 10, "salud": None,
               "estimado": True}
        self.comp(instante_base(bateria=bat), "WARNING", "WARNING", "bateria")
        self.comp(instante_base(bateria=dict(bat, nivel=5)), "CRITICAL", "CRITICAL", "bateria")
        self.comp(instante_base(bateria=dict(bat, nivel=3, estado="cargando")), "ONLINE")
        self.comp(instante_base(bateria=dict(bat, nivel=16)), "ONLINE")

    def test_ram_disponible_critica(self):
        i = instante_base(ram={"usada": 15300, "total": 16000, "swap": 0, "swap_total": 0, "presion": None})
        self.comp(i, "CRITICAL", "CRITICAL", "ram")
        i["ram"]["usada"] = 15200        # justo 5 % disponible: no es critico
        self.comp(i, "ONLINE")

    def test_swap_y_presion(self):
        i = instante_base()
        i["ram"]["swap"] = 4001
        self.comp(i, "WARNING", "WARNING", "swap")
        i["ram"]["swap"] = 4000          # no supera el 50 %
        self.comp(i, "ONLINE")
        i["ram"].update(swap=100, swap_total=0)   # sin swap, no se evalua
        self.comp(i, "ONLINE")
        i["ram"]["presion"] = 20.5
        self.comp(i, "WARNING", "WARNING", "ram")
        i["ram"]["presion"] = 20.0
        self.comp(i, "ONLINE")

    def test_unidades_fallidas(self):
        m = self.comp(instante_base(fallidas=["ufw.service"]), "WARNING", "WARNING", "systemd")
        self.assertIn("ufw.service", m[0]["texto"])
        self.comp(instante_base(fallidas=[]), "ONLINE")
        self.comp(instante_base(fallidas=None), "ONLINE")

    def test_lo_critico_domina_y_se_acumulan_motivos(self):
        i = instante_base(fallidas=["x.service"])
        i["cpu"]["temp"] = 96.0
        e, m = S.evaluar(i)
        self.assertEqual(e, "CRITICAL")
        self.assertEqual(len(m), 2)

    def test_evaluar_no_modifica_el_instante(self):
        i = instante_base(fallidas=["x"])
        copia = copy.deepcopy(i)
        S.evaluar(i)
        self.assertEqual(i, copia)

    def test_motivos_con_el_formato_pedido(self):
        i = instante_base()
        i["cpu"]["temp"] = 90.0
        for m in S.evaluar(i)[1]:
            self.assertEqual(sorted(m), ["componente", "gravedad", "texto"])


class PruebasPrivacidad(Base):
    def test_sin_ufw_conf_no_disponible(self):
        r = S.resumen_privacidad(True)
        self.assertEqual(r["estado"], "UNAVAILABLE")
        self.assertTrue(r["detalles"])

    def test_desactivado_es_warning(self):
        self.escribir("etc/ufw/ufw.conf", "# comentario\nENABLED=no\nLOGLEVEL=low\n")
        self.assertEqual(S.resumen_privacidad(True)["estado"], "WARNING")

    def test_activado_con_servicio_activo_es_secure(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.escribir("etc/default/ufw", 'DEFAULT_INPUT_POLICY="DROP"\n')
        r = S.resumen_privacidad(True)
        self.assertEqual(r["estado"], "SECURE")
        self.assertEqual(r["detalles"], ["Cortafuegos activo: entrante denegado por defecto"])

    def test_secure_sin_politica_conocida_no_la_afirma(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertEqual(S.resumen_privacidad(True)["detalles"], ["Cortafuegos activo"])

    def test_activado_pero_servicio_parado_o_desconocido_es_warning(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertEqual(S.resumen_privacidad(False)["estado"], "WARNING")
        self.assertEqual(S.resumen_privacidad(None)["estado"], "WARNING")


class PruebasInstanteYServicio(Base):
    def test_escritura_atomica_con_v1(self):
        destino = os.path.join(self.rt, "instante.json")
        S.escribir_json(destino, {"v": 1, "x": None})
        self.assertEqual(leer_json(destino), {"v": 1, "x": None})
        self.assertEqual(os.listdir(self.rt), ["instante.json"])      # sin temporales
        S.escribir_json(destino, {"v": 1, "x": 2})
        self.assertEqual(leer_json(destino)["x"], 2)

    def test_ciclo_de_muestreo_escribe_ambos_archivos(self):
        self.escribir("proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
        sv = S.Servicio(directorio=self.rt)
        sv.muestreador.base()
        self.escribir("proc/stat", "cpu  150 0 150 900 0 0 0 0 0 0\ncpu0 150 0 150 900 0 0 0 0 0 0\n")
        sv.muestrear()
        inst = leer_json(os.path.join(self.rt, "instante.json"))
        est = leer_json(os.path.join(self.rt, "estado.json"))
        self.assertEqual(inst["v"], 1)
        self.assertEqual(inst["cpu"]["total"], 50.0)
        self.assertIsNone(inst["ram"])
        self.assertIsNone(inst["bateria"])
        self.assertEqual(inst["estado"], "ONLINE")
        self.assertEqual(inst["alertas"], 0)
        self.assertEqual(est["v"], 1)
        self.assertEqual(est["estado"], "ONLINE")
        self.assertEqual(est["servicio"]["pid"], os.getpid())
        self.assertEqual(est["perfil"], {"activo": None, "fuente": "power-profiles-daemon"})
        self.assertEqual(est["privacidad"]["estado"], "UNAVAILABLE")
        self.assertEqual(est["actividad"][0]["texto"], "Servicio iniciado")
        self.assertEqual(len(sv.anillo), 1)
        self.assertEqual(set(sv.anillo[0]), {"t", "cpu", "ram", "temp"})

    def test_actividad_registra_cambios_de_estado_y_perfil(self):
        sv = S.Servicio(directorio=self.rt)
        sv.instante = instante_base()
        sv.publicar("ONLINE", [])
        sv.publicar("WARNING", [{"gravedad": "WARNING", "componente": "cpu", "texto": "x"}])
        sv.poner_perfil("performance")
        textos = [e["texto"] for e in sv.actividad]
        self.assertIn("Estado: ONLINE → WARNING", textos)
        self.assertIn("Perfil de energía: performance", textos)
        self.assertLessEqual(sv.actividad.maxlen, 20)

    def test_modo_rapido(self):
        sv = S.Servicio(directorio=self.rt)
        self.assertEqual(sv.intervalo_actual(), 10)
        intervalo, hasta = sv.rapido()
        self.assertEqual(intervalo, 2)
        self.assertGreater(hasta, time.time() + 10)
        self.assertEqual(sv.intervalo_actual(), 2)

    def test_medir_devuelve_instante_completo(self):
        self.escribir("proc/stat", "cpu  1 0 1 8 0 0 0 0 0 0\ncpu0 1 0 1 8 0 0 0 0 0 0\n")
        with mock.patch.object(S.time, "sleep"):
            inst = S.medir()
        self.assertEqual(inst["v"], 1)
        for clave in ("cpu", "ram", "temp", "gpu", "disco", "bateria", "cargador", "uptime", "procesos",
                      "estado", "alertas"):
            self.assertIn(clave, inst)
        json.dumps(inst)


class ContextoFalso:
    def __init__(self, estado=None, instante=None):
        self._e, self._i, self.llamadas = estado, instante, 0

    def rapido(self):
        self.llamadas += 1
        return 2, 1763123471

    def estado_doc(self):
        return self._e

    def instante_doc(self):
        return self._i


class PruebasApi(unittest.TestCase):
    def pedir(self, linea, ctx=None):
        return json.loads(S.procesar_linea(linea, ctx or ContextoFalso()))

    def test_rapido(self):
        ctx = ContextoFalso()
        r = self.pedir('{"orden":"rapido"}', ctx)
        self.assertEqual(r, {"ok": True, "intervalo": 2, "hasta": 1763123471})
        self.assertEqual(ctx.llamadas, 1)

    def test_estado_e_instante(self):
        ctx = ContextoFalso(estado={"v": 1, "estado": "ONLINE"}, instante={"v": 1, "t": 5})
        self.assertEqual(self.pedir('{"orden":"estado"}', ctx), {"v": 1, "estado": "ONLINE"})
        self.assertEqual(self.pedir('{"orden":"instante"}', ctx), {"v": 1, "t": 5})

    def test_sin_datos_todavia(self):
        self.assertFalse(self.pedir('{"orden":"estado"}')["ok"])

    def test_orden_desconocida(self):
        self.assertEqual(self.pedir('{"orden":"borrar"}'), {"ok": False, "error": "orden desconocida"})
        self.assertEqual(self.pedir('{}'), {"ok": False, "error": "orden desconocida"})

    def test_json_roto_y_no_objeto(self):
        self.assertFalse(self.pedir("{esto no es json")["ok"])
        self.assertFalse(self.pedir("")["ok"])
        self.assertFalse(self.pedir("[1,2]")["ok"])

    def test_fallo_interno_no_cae(self):
        class Roto(ContextoFalso):
            def rapido(self):
                raise RuntimeError("fallo")
        with mock.patch.object(S, "registrar"):
            r = self.pedir('{"orden":"rapido"}', Roto())
        self.assertFalse(r["ok"])

    def test_con_el_servicio_real(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        sv = S.Servicio(directorio=d)
        self.assertFalse(self.pedir('{"orden":"instante"}', sv)["ok"])
        self.assertTrue(self.pedir('{"orden":"rapido"}', sv)["ok"])


class PruebasSalud(Base):
    def estado_json(self, **cambios):
        e = {"v": 1, "t": int(time.time()), "estado": "ONLINE", "motivos": [],
             "perfil": {"activo": "balanced", "fuente": "power-profiles-daemon"},
             "privacidad": {"estado": "SECURE", "detalles": []}, "actividad": [],
             "servicio": {"pid": 1, "desde": 0, "intervalo": 10}}
        e.update(cambios)
        self.escribir_rt("estado.json", e)

    def escribir_rt(self, nombre, doc):
        with open(os.path.join(self.rt, nombre), "w", encoding="utf-8") as f:
            json.dump(doc, f)

    def test_barra_online(self):
        self.estado_json()
        r = H.barra()
        self.assertEqual(r["class"], "online")
        self.assertEqual(r["text"], "\U000f0f85 ")
        self.assertEqual(r["tooltip"].splitlines()[0], "Jaime0 · SYSTEM ONLINE")
        self.assertIn("Perfil: balanced", r["tooltip"])
        self.assertTrue(r["tooltip"].endswith("Clic: Control Center"))

    def test_barra_warning_con_icono_de_alerta_y_motivos_maximo_4(self):
        motivos = [{"gravedad": "WARNING", "componente": "x", "texto": f"motivo {i}"} for i in range(6)]
        self.estado_json(estado="WARNING", motivos=motivos,
                         perfil={"activo": "performance", "fuente": "power-profiles-daemon"})
        r = H.barra()
        self.assertEqual(r["class"], "warning")
        self.assertEqual(r["text"], "\U000f04c5 \U000f0026 ")
        self.assertIn("motivo 3", r["tooltip"])
        self.assertNotIn("motivo 4", r["tooltip"])

    def test_barra_critical_y_perfil_desconocido(self):
        self.estado_json(estado="CRITICAL", perfil={"activo": None, "fuente": "power-profiles-daemon"})
        r = H.barra()
        self.assertEqual(r["class"], "critical")
        self.assertTrue(r["text"].startswith("\U000f0f85"))
        self.assertIn("SYSTEM CRITICAL", r["tooltip"])

    def test_barra_power_saver(self):
        self.estado_json(perfil={"activo": "power-saver", "fuente": "power-profiles-daemon"})
        self.assertEqual(H.barra()["text"], "\U000f0f86 ")

    def test_barra_parado_con_estado_viejo(self):
        self.estado_json(t=int(time.time()) - 120)
        with mock.patch.object(H, "perfil_actual_sin_servicio", return_value="power-saver"):
            r = H.barra()
        self.assertEqual(r["class"], "parado")
        self.assertEqual(r["text"], "\U000f0f86 ")
        self.assertTrue(r["tooltip"].startswith("Servicio de Jaime0 parado"))

    def test_barra_parado_sin_estado_y_sin_powerprofilesctl(self):
        with mock.patch.object(H.subprocess, "run", side_effect=FileNotFoundError):
            r = H.barra()
        self.assertEqual(r["class"], "parado")
        self.assertEqual(r["text"], "\U000f0f85 ")
        json.dumps(r)

    def test_barra_estado_roto_cuenta_como_parado(self):
        with open(os.path.join(self.rt, "estado.json"), "w") as f:
            f.write("{no json")
        with mock.patch.object(H, "perfil_actual_sin_servicio", return_value=None):
            self.assertEqual(H.barra()["class"], "parado")

    def test_obtener_usa_archivos_frescos(self):
        self.estado_json()
        self.escribir_rt("instante.json", instante_base())
        i, e, parado = H.obtener()
        self.assertFalse(parado)
        self.assertEqual(e["estado"], "ONLINE")
        txt = H.resumen(i, e, parado)
        self.assertIn("SYSTEM ONLINE", txt)
        self.assertIn("N/D", txt)       # batería ausente
        self.assertNotIn("Servicio parado", txt)

    def test_obtener_servicio_parado_hace_medicion_puntual(self):
        self.escribir_rt("instante.json", instante_base(t=int(time.time()) - 600))
        puntual = instante_base(bateria={"nivel": 80, "estado": "descargando", "vatios": 10.0,
                                         "minutos_estimados": 125, "salud": None, "estimado": True})
        with mock.patch.object(H, "medicion_puntual", return_value=puntual):
            i, e, parado = H.obtener()
        self.assertTrue(parado)
        self.assertIsNone(e)
        txt = H.resumen(i, e, parado)
        self.assertIn("Servicio parado: medición puntual", txt)
        self.assertIn("(estimado)", txt)
        self.assertIn("2 h 5 min", txt)

    def test_salida_con_error_si_no_hay_nada(self):
        with mock.patch.object(H, "medicion_puntual", return_value=None), \
                mock.patch.object(H.sys, "stderr"):
            self.assertEqual(H.main(["ahora"]), 1)


if __name__ == "__main__":
    unittest.main()
