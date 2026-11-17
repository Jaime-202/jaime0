#!/usr/bin/env python3
"""Pruebas de la reorganizacion del Control Center (evolucion, fase 7): lista y detalle de
procesos (PERFORMANCE), trafico de red, servicios importantes (SYSTEM) y las tres categorias
de PRIVACY & SECURITY. Con la raiz falsa de test_jaime0_servicio.

    python3 -m unittest discover -s pruebas -v
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_jaime0_servicio import Base, S  # noqa: E402


def stat(pid, nombre, ut, st, estado="S", hilos=3, rss=256):
    campos = [estado, "1", "1", "1", "0", "-1", "0", "0", "0", "0", "0", str(ut), str(st), "0", "0", "20", "0",
              str(hilos), "0", "500", "1", str(rss)]
    return f"{pid} ({nombre}) " + " ".join(campos) + "\n"


class PruebasProcesos(Base):
    def test_lista_completa_con_cpu_ram_hilos_y_estado(self):
        self.escribir("proc/10/stat", stat(10, "firefox", 100, 0, "R", 80, 51200))
        self.escribir("proc/11/stat", stat(11, "kitty", 0, 0))
        antes = S.leer_procesos()
        self.escribir("proc/10/stat", stat(10, "firefox", 150, 50, "R", 80, 51200))
        self.escribir("proc/12/stat", stat(12, "nuevo", 9, 0, "Z"))
        with mock.patch.object(S.medicion_mod, "tics_por_segundo", return_value=100), \
                mock.patch.object(S.medicion_mod, "tamano_pagina", return_value=4096):
            lista = S.lista_procesos(antes, S.leer_procesos(), 2.0)
        self.assertEqual([p["pid"] for p in lista], [10, 11, 12])
        self.assertEqual(lista[0], {"pid": 10, "nombre": "firefox", "cpu": 50.0, "ram": 200.0, "hilos": 80,
                                    "estado": "ejecutando"})
        self.assertEqual(lista[1]["cpu"], 0.0)
        self.assertIsNone(lista[2]["cpu"], "sin muestra previa no se inventa la CPU")
        self.assertEqual(lista[2]["estado"], "zombi")
        self.assertEqual(S.lista_procesos(None, {}, 1.0), [])

    def test_detalle_de_un_proceso(self):
        self.escribir("proc/uptime", "1000.0 0\n")
        self.escribir("proc/42/status", "Name:\tmpv\nState:\tS (sleeping)\nPPid:\t7\nUid:\t1000\t1000\t1000\t1000\n"
                                        "VmRSS:\t  20480 kB\nThreads:\t12\n")
        self.escribir("proc/42/cmdline", "mpv\x00--fs\x00vídeo.mkv\x00")
        self.escribir("proc/42/stat", stat(42, "mpv", 1, 1))
        with mock.patch.object(S.medicion_mod, "tics_por_segundo", return_value=100):
            d = S.detalle_proceso(42)
        self.assertEqual((d["nombre"], d["orden"], d["padre"], d["hilos"], d["ram_mib"], d["swap_mib"]),
                         ("mpv", "mpv --fs vídeo.mkv", 7, 12, 20.0, None))
        self.assertEqual(d["estado"], "S (sleeping)")
        self.assertIsInstance(d["inicio"], int)
        self.assertIsNone(S.detalle_proceso(43))

    def test_red_sin_lo_y_por_diferencias(self):
        texto = ("Inter-|   Receive |  Transmit\n face |bytes packets errs drop fifo frame compressed multicast|bytes\n"
                 "    lo: 999 1 0 0 0 0 0 0 999 1 0 0 0 0 0 0\n"
                 "  eth0: 1000 1 0 0 0 0 0 0 5000 1 0 0 0 0 0 0\n")
        antes = S.parsear_net_dev(texto)
        self.assertEqual(antes, {"eth0": (1000, 5000)})
        ahora = {"eth0": (21000, 7000), "wlan0": (5, 5)}
        self.assertEqual(S.io_red(antes, ahora, 2.0), {"rx": 10.0, "tx": 1.0})
        self.assertIsNone(S.io_red(None, ahora, 2.0))
        self.assertIsNone(S.io_red({"x": (0, 0)}, ahora, 2.0))

    def test_la_lista_completa_solo_con_la_ventana_abierta(self):
        self.escribir("proc/10/stat", stat(10, "firefox", 100, 0))
        m = S.Muestreador()
        m.base()
        m.muestrear(completa=False)
        self.assertEqual(m.lista, [])
        m.muestrear()
        self.assertEqual([p["pid"] for p in m.lista], [10])
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        sv.muestreador.base()
        sv.muestrear()
        self.assertEqual(sv.muestreador.lista, [], "sin el modo rápido (ventana cerrada) no se calcula")
        sv.rapido()
        sv.muestrear()
        self.assertEqual([p["pid"] for p in sv.muestreador.lista], [10])

    def test_ordenes_procesos_y_proceso(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        sv.muestreador.lista = [{"pid": 1, "nombre": "a", "cpu": 1.0, "ram": 1.0, "hilos": 1, "estado": "esperando"}]
        r = json.loads(S.procesar_linea(json.dumps({"orden": "procesos"}), sv))
        self.assertEqual((r["ok"], r["total"], r["procesos"][0]["nombre"]), (True, 1, "a"))
        r = json.loads(S.procesar_linea(json.dumps({"orden": "proceso", "pid": "1"}), sv))
        self.assertEqual(r, {"ok": False, "error": "falta el pid"})
        r = json.loads(S.procesar_linea(json.dumps({"orden": "proceso", "pid": 99}), sv))
        self.assertEqual(r["error"], "ese proceso ya no existe")


class PruebasServiciosImportantes(unittest.TestCase):
    SALIDA = ("Id=NetworkManager.service\nLoadState=loaded\nActiveState=active\n\n"
              "Id=power-profiles-daemon.service\nLoadState=loaded\nActiveState=failed\n\n"
              "Id=ufw.service\nLoadState=loaded\nActiveState=inactive\n\n"
              "Id=bluetooth.service\nLoadState=not-found\nActiveState=inactive\n")

    def test_estado_por_unidad_y_ambito(self):
        llamadas = []

        def ejecutar(orden, **k):
            llamadas.append(orden)
            if "--user" in orden:
                return mock.Mock(stdout="Id=pipewire.service\nLoadState=loaded\nActiveState=activating\n")
            return mock.Mock(stdout=self.SALIDA)

        r = {s["nombre"]: s["estado"] for s in S.estado_unidades(ejecutar=ejecutar)}
        self.assertEqual(r, {"Red": "activo", "Energía": "fallido", "Cortafuegos": "inactivo",
                             "Bluetooth": "no instalado", "Sonido": "arrancando"})
        self.assertEqual(len(llamadas), 2, "una llamada por ámbito")

    def test_sin_systemctl_es_desconocido(self):
        r = S.estado_unidades(ejecutar=mock.Mock(side_effect=OSError))
        self.assertEqual({s["estado"] for s in r}, {"desconocido"})


class PruebasCategoriasPrivacidad(Base):
    def doc(self, **cambios):
        d = {"cortafuegos": {"instalado": True, "activo": True, "unidad_activa": True,
                             "politicas": {"entrante": "DROP", "saliente": "ACCEPT"}},
             "puertos": [], "conexiones": [],
             "dispositivos": {"microfono": [], "camara": [], "pantalla": None},
             "flatpak": {"estado": "UNAVAILABLE", "texto": "x"},
             "privilegios": {"grupos": [{"grupo": "sudo", "texto": "sudo: ..."}]},
             "servicios": [{"nombre": "ssh", "estado": "no instalado", "texto": "x"},
                           {"nombre": "cups", "estado": "activo", "texto": "Impresión"}],
             "telemetria": [{"elemento": "ZYRON", "estado": "NINGUNA", "texto": "nada"}]}
        d.update(cambios)
        return d

    def estados(self, c):
        return {e["id"]: (cat, e["estado"]) for cat in ("activa", "permisos", "visibilidad") for e in c[cat]}

    def test_equipo_protegido_y_lo_no_comprobable_aparte(self):
        c = S.categorias_privacidad(self.doc(), apparmor=True, secure_boot="no_efi")
        e = self.estados(c)
        self.assertEqual(e["cortafuegos"], ("activa", "ACTIVE"))
        self.assertEqual(e["puertos"], ("activa", "ACTIVE"))
        self.assertEqual(e["apparmor"], ("activa", "ACTIVE"))
        self.assertEqual(e["secure_boot"], ("visibilidad", "NOT_APPLICABLE"))
        self.assertEqual(e["servicio_ssh"], ("visibilidad", "NOT_APPLICABLE"))
        self.assertEqual(e["servicio_cups"], ("activa", "ACTIVE"))
        self.assertEqual(e["flatpak"], ("visibilidad", "NOT_APPLICABLE"))
        self.assertEqual(e["carpetas"], ("visibilidad", "UNAVAILABLE"))
        self.assertEqual(e["microfono"], ("permisos", "ACTIVE"))
        self.assertEqual(e["pantalla"], ("visibilidad", "UNAVAILABLE"))
        self.assertEqual(e["reglas_ufw"], ("visibilidad", "UNAVAILABLE"))
        self.assertEqual(sum(c["cuenta"].values()), len(e))
        self.assertEqual(c["cuenta"]["WARNING"], 0)

    def test_avisos_reales(self):
        doc = self.doc(puertos=[{"protocolo": "tcp", "puerto": 22, "expuesto": True, "proceso": None}],
                       dispositivos={"microfono": [{"aplicacion": "Zoom", "pid": 9}], "camara": [], "pantalla": []},
                       servicios=[{"nombre": "ssh", "estado": "activo", "texto": "entrada remota"}],
                       privilegios={"grupos": [{"grupo": "docker", "texto": "docker: ..."}]},
                       telemetria=[{"elemento": "popularity-contest", "estado": "ACTIVO", "texto": "envía"}])
        doc["cortafuegos"]["politicas"]["entrante"] = "ACCEPT"
        e = self.estados(S.categorias_privacidad(doc, apparmor=False, secure_boot=False))
        for clave in ("cortafuegos", "puertos", "servicio_ssh", "microfono", "privilegios", "telemetria"):
            self.assertEqual(e[clave][1], "WARNING", clave)
        self.assertEqual(e["apparmor"][1], "DISABLED")
        self.assertEqual(e["secure_boot"][1], "DISABLED")
        self.assertIn("otros_usuarios", e)

    def test_cortafuegos_en_cada_situacion(self):
        sin = {"instalado": False}
        self.assertEqual(S._cortafuegos(sin)["estado"], "UNAVAILABLE")
        self.escribir("etc/ufw/ufw.conf", "ENABLED=no\n")
        self.assertEqual(S._cortafuegos({"instalado": True, "activo": False, "unidad_activa": True})["estado"], "DISABLED")
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertEqual(S._cortafuegos({"instalado": True, "activo": False, "unidad_activa": False})["estado"], "WARNING")
        self.assertEqual(S._cortafuegos({"instalado": True, "activo": False, "unidad_activa": None})["estado"], "UNAVAILABLE")

    def test_apparmor_y_secure_boot_desde_sysfs(self):
        self.assertIsNone(S.estado_apparmor())
        self.escribir("sys/module/apparmor/parameters/enabled", "Y\n")
        self.assertTrue(S.estado_apparmor())
        self.assertEqual(S.estado_secure_boot(), "no_efi")
        os.makedirs(os.path.join(self.raiz, "sys", "firmware", "efi", "efivars"))
        self.assertIsNone(S.estado_secure_boot())
        with open(os.path.join(self.raiz, "sys", "firmware", "efi", "efivars", S.EFIVAR_SECURE_BOOT), "wb") as f:
            f.write(b"\x06\x00\x00\x00\x01")
        self.assertTrue(S.estado_secure_boot())


if __name__ == "__main__":
    unittest.main()
