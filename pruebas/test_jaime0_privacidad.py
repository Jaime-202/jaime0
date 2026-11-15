#!/usr/bin/env python3
"""Pruebas de PRIVACY & SECURITY (Fase 5): el modulo de privacidad de jaime0-servicio, el
cliente jaime0-privacidad y el ayudante de UFW. Las salidas de ufw, ss, pw-dump, systemctl y
pkexec son cadenas simuladas inyectadas con una funcion `ejecutar` falsa: no se ejecuta nada real.

    python3 -m unittest discover -s pruebas -v
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.dom.minidom
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
INCLUDES = REPO / "config/includes.chroot_after_packages"
BIN = INCLUDES / "usr/local/bin"
AYUDANTE = INCLUDES / "usr/local/libexec/jaime0-ufw-estado"
POLITICA = INCLUDES / "usr/share/polkit-1/actions/es.jaime0.ufw-estado.policy"


def cargar(nombre, programa):
    cargador = importlib.machinery.SourceFileLoader(nombre, str(BIN / programa))
    spec = importlib.util.spec_from_loader(cargador.name, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


S = cargar("jaime0_servicio_privacidad", "jaime0-servicio")
C = cargar("jaime0_privacidad_pruebas", "jaime0-privacidad")

UFW_ACTIVO = """Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
80,443/tcp                 ALLOW IN    192.168.1.0/24             # web de casa
8000:8010/tcp              LIMIT IN    Anywhere
23/tcp                     DENY IN     Anywhere
25/tcp                     REJECT IN   Anywhere                   # sin correo
Anywhere                   DENY IN     10.0.0.5
53                         ALLOW OUT   Anywhere                   (out)
22/tcp (v6)                ALLOW IN    Anywhere (v6)
23/tcp (v6)                DENY IN     Anywhere (v6)
"""

UFW_INACTIVO = "Status: inactive\n"

SS_ESCUCHA = """udp   UNCONN 0      0            0.0.0.0:68         0.0.0.0:*    users:(("dhclient",pid=500,fd=6))
udp   UNCONN 0      0      127.0.0.53%lo:53         0.0.0.0:*
tcp   LISTEN 0      128          0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=1,fd=3))
tcp   LISTEN 0      4096       127.0.0.1:631        0.0.0.0:*    users:(("cupsd",pid=700,fd=7))
tcp   LISTEN 0      4096           [::1]:631           [::]:*
tcp   LISTEN 0      128             [::]:80           [::]:*
udp   UNCONN 0      0       [fe80::1]%eth0:546        [::]:*
tcp   LISTEN 0      5                  *:8080            *:*    users:(("Web Content",pid=42,fd=9))
"""

SS_ESTABLECIDAS = """tcp   ESTAB 0      0      192.168.1.20:44332  93.184.216.34:443   users:(("brave",pid=900,fd=30))
tcp   ESTAB 0      0      192.168.1.20:44334  93.184.216.34:443   users:(("brave",pid=900,fd=31))
tcp   ESTAB 0      0      192.168.1.20:50000  151.101.1.69:443    users:(("brave",pid=900,fd=32))
tcp   ESTAB 0      0      192.168.1.20:22     192.168.1.50:51000
udp   ESTAB 0      0      192.168.1.20:5353   224.0.0.251:5353    users:(("avahi-daemon",pid=300,fd=12))
"""


def pw_nodo(estado, clase, **props):
    p = {"media.class": clase}
    p.update(props)
    return {"id": 1, "type": "PipeWire:Interface:Node", "info": {"state": estado, "props": p}}


PW_MICROFONO = json.dumps([
    {"id": 0, "type": "PipeWire:Interface:Core", "info": {}},
    pw_nodo("running", "Stream/Input/Audio", **{"application.name": "Firefox", "application.process.id": 1234}),
    pw_nodo("idle", "Stream/Input/Audio", **{"application.name": "Discord", "application.process.id": 777}),
    pw_nodo("running", "Audio/Sink", **{"node.name": "alsa_output"}),
])
PW_PANTALLA = json.dumps([
    pw_nodo("running", "Video/Source", **{"node.name": "xdph-streaming-Virtual-1"}),
    pw_nodo("running", "Stream/Input/Video", **{"application.name": "OBS", "media.role": "Screen"}),
    pw_nodo("running", "Video/Source", **{"node.name": "v4l2_input.pci-0000", "application.name": "Camara web"}),
    pw_nodo("idle", "Video/Source", **{"node.name": "xdg-desktop-portal-hyprland"}),
])


def leer_archivo(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read().strip()


def resultado(salida="", codigo=0, error=""):
    return SimpleNamespace(returncode=codigo, stdout=salida, stderr=error)


class Ejecutor:
    """`ejecutar` falso: responde segun el primer argumento y anota las llamadas."""

    def __init__(self, **respuestas):
        self.respuestas = respuestas
        self.llamadas = []

    def __call__(self, cmd, **kw):
        self.llamadas.append((list(cmd), kw))
        r = self.respuestas.get(cmd[0], resultado("", 1))
        if isinstance(r, BaseException):
            raise r
        if callable(r):
            return r(cmd)
        return r


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-priv-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.raiz = os.path.join(self.tmp, "raiz")
        self.rt = os.path.join(self.tmp, "rt")
        self.estado = os.path.join(self.tmp, "estado")
        os.makedirs(self.raiz)
        os.makedirs(self.rt)
        p = mock.patch.dict(os.environ, {"JAIME0_RAIZ": self.raiz, "JAIME0_RUNTIME": self.rt,
                                         "JAIME0_ESTADO": self.estado})
        p.start()
        self.addCleanup(p.stop)

    def escribir(self, rel, texto):
        p = os.path.join(self.raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        return p

    def servicio(self, **respuestas):
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        sv.priv_ejecutar = Ejecutor(**respuestas)
        return sv

    def historial(self, sv):
        return [d["texto"] for d in sv.priv_historial.ultimos(1000)][::-1]


class PruebasUfwSinRoot(Base):
    def test_sin_ufw_conf_no_instalado(self):
        fw = S.estado_cortafuegos(True)
        self.assertFalse(fw["instalado"])
        self.assertFalse(fw["activo"])
        self.assertEqual(fw["politicas"], {"entrante": None, "saliente": None, "enrutado": None})

    def test_politicas_y_registro_de_los_archivos(self):
        self.escribir("etc/ufw/ufw.conf", "# c\nENABLED=yes\nLOGLEVEL=medium\n")
        self.escribir("etc/default/ufw", '# c\nDEFAULT_INPUT_POLICY="DROP"\nDEFAULT_OUTPUT_POLICY="ACCEPT"\n'
                                         'DEFAULT_FORWARD_POLICY="REJECT"\nIPV6=yes\n')
        fw = S.estado_cortafuegos(True)
        self.assertEqual(fw, {"instalado": True, "activo": True, "unidad_activa": True, "registro": "medium",
                              "politicas": {"entrante": "DROP", "saliente": "ACCEPT", "enrutado": "REJECT"}})

    def test_activo_exige_enabled_y_unidad(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertFalse(S.estado_cortafuegos(False)["activo"])
        self.assertFalse(S.estado_cortafuegos(None)["activo"])
        self.escribir("etc/ufw/ufw.conf", "ENABLED=no\n")
        self.assertFalse(S.estado_cortafuegos(True)["activo"])

    def test_sin_default_ufw_politicas_nulas(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertEqual(S.estado_cortafuegos(True)["politicas"],
                         {"entrante": None, "saliente": None, "enrutado": None})


class PruebasReglasUfw(unittest.TestCase):
    def test_activo_con_reglas_ipv4_e_ipv6(self):
        r = S.parsear_ufw_estado(UFW_ACTIVO)
        self.assertTrue(r["ok"])
        self.assertTrue(r["activo"])
        self.assertEqual(r["registro"], "on (low)")
        self.assertEqual(r["politicas"], {"entrante": "DROP", "saliente": "ACCEPT", "enrutado": "DISABLED"})
        self.assertEqual(len(r["reglas"]), 9)
        self.assertEqual(r["reglas"][0], {"destino": "22/tcp", "accion": "ALLOW IN", "origen": "Anywhere",
                                          "ipv6": False, "comentario": ""})
        v6 = r["reglas"][7]
        self.assertEqual((v6["destino"], v6["origen"], v6["ipv6"]), ("22/tcp", "Anywhere", True))
        self.assertTrue(r["reglas"][8]["ipv6"])

    def test_comentarios_y_origen_con_red(self):
        r = S.parsear_ufw_estado(UFW_ACTIVO)["reglas"]
        self.assertEqual(r[1]["origen"], "192.168.1.0/24")
        self.assertEqual(r[1]["comentario"], "web de casa")
        self.assertEqual(r[4]["comentario"], "sin correo")
        self.assertEqual(r[4]["accion"], "REJECT IN")

    def test_regla_de_salida_no_cuenta_como_puerto_de_entrada(self):
        r = S.parsear_ufw_estado(UFW_ACTIVO)
        salida = r["reglas"][6]
        self.assertEqual((salida["destino"], salida["accion"], salida["origen"]), ("53", "ALLOW OUT", "Anywhere"))
        self.assertNotIn("53", r["puertos_permitidos"])

    def test_puertos_permitidos_y_bloqueados(self):
        r = S.parsear_ufw_estado(UFW_ACTIVO)
        self.assertEqual(r["puertos_permitidos"], ["22/tcp", "80,443/tcp", "8000:8010/tcp"])    # ALLOW y LIMIT
        self.assertEqual(r["puertos_bloqueados"], ["23/tcp", "25/tcp"])                         # DENY y REJECT

    def test_inactivo(self):
        r = S.parsear_ufw_estado(UFW_INACTIVO)
        self.assertTrue(r["ok"])
        self.assertFalse(r["activo"])
        self.assertEqual(r["reglas"], [])
        self.assertEqual(r["politicas"], {"entrante": None, "saliente": None, "enrutado": None})


class PruebasPkexec(unittest.TestCase):
    def consulta(self, **kw):
        return S.consultar_ufw_reglas(Ejecutor(pkexec=resultado(**kw)) if kw else Ejecutor())

    def test_exito_ejecuta_solo_el_ayudante_con_timeout(self):
        ej = Ejecutor(pkexec=resultado(UFW_ACTIVO))
        r = S.consultar_ufw_reglas(ej)
        self.assertTrue(r["ok"] and r["activo"])
        cmd, kw = ej.llamadas[0]
        self.assertEqual(cmd, ["pkexec", "/usr/local/libexec/jaime0-ufw-estado"])
        self.assertEqual(kw["timeout"], 120)

    def test_126_es_cancelado(self):
        self.assertEqual(self.consulta(codigo=126), {"ok": False, "error": "autorización cancelada"})

    def test_127_es_sin_agente(self):
        self.assertEqual(self.consulta(codigo=127),
                         {"ok": False, "error": "no hay agente de autorización (polkit)"})

    def test_otro_codigo_y_salida_rara(self):
        self.assertFalse(self.consulta(codigo=1)["ok"])
        self.assertIn("código 1", self.consulta(codigo=1)["error"])
        self.assertFalse(self.consulta(salida="otra cosa")["ok"])

    def test_pkexec_ausente_y_timeout(self):
        r = S.consultar_ufw_reglas(Ejecutor(pkexec=FileNotFoundError()))
        self.assertFalse(r["ok"])
        self.assertIn("polkit", r["error"])
        r = S.consultar_ufw_reglas(Ejecutor(pkexec=subprocess.TimeoutExpired("pkexec", 120)))
        self.assertFalse(r["ok"])
        self.assertIn("tiempo", r["error"])


class PruebasSs(unittest.TestCase):
    def setUp(self):
        self.e = S.parsear_ss(SS_ESCUCHA)

    def por(self, proto, puerto, direccion=None):
        return [x for x in self.e if x["protocolo"] == proto and x["puerto"] == puerto
                and (direccion is None or x["direccion"] == direccion)]

    def test_todas_las_lineas(self):
        self.assertEqual(len(self.e), 8)

    def test_0000_expuesto_con_proceso(self):
        x = self.por("tcp", 22)[0]
        self.assertEqual((x["direccion"], x["proceso"], x["pid"], x["expuesto"]), ("0.0.0.0", "sshd", 1, True))
        self.assertEqual(x["estado"], "LISTEN")
        self.assertEqual(x["remoto"], "0.0.0.0:*")

    def test_bucle_ipv4_no_expuesto(self):
        self.assertFalse(self.por("tcp", 631, "127.0.0.1")[0]["expuesto"])
        self.assertFalse(self.por("udp", 53)[0]["expuesto"])          # 127.0.0.53%lo
        self.assertEqual(self.por("udp", 53)[0]["direccion"], "127.0.0.53")

    def test_bucle_ipv6_no_expuesto_y_sin_proceso(self):
        x = self.por("tcp", 631, "::1")[0]
        self.assertFalse(x["expuesto"])
        self.assertIsNone(x["proceso"])
        self.assertIsNone(x["pid"])

    def test_ipv6_sin_especificar_expuesto(self):
        x = self.por("tcp", 80)[0]
        self.assertEqual(x["direccion"], "::")
        self.assertTrue(x["expuesto"])
        self.assertIsNone(x["proceso"])

    def test_enlace_local_no_expuesto(self):
        x = self.por("udp", 546)[0]
        self.assertEqual(x["direccion"], "fe80::1")
        self.assertFalse(x["expuesto"])

    def test_asterisco_y_nombre_con_espacios(self):
        x = self.por("tcp", 8080)[0]
        self.assertTrue(x["expuesto"])
        self.assertEqual((x["proceso"], x["pid"]), ("Web Content", 42))

    def test_direccion_expuesta_casos(self):
        for d in ("0.0.0.0", "::", "*", "192.168.1.5", "2001:db8::1", "10.0.0.1"):
            self.assertTrue(S.direccion_expuesta(d), d)
        for d in ("127.0.0.1", "127.5.5.5", "::1", "fe80::abcd", "febf::1", "::ffff:127.0.0.1"):
            self.assertFalse(S.direccion_expuesta(d), d)

    def test_puertos_expuestos_deduplica_por_puerto_y_protocolo(self):
        exp = S.puertos_expuestos(self.e)
        self.assertEqual(exp, {(68, "udp"): "dhclient", (22, "tcp"): "sshd", (80, "tcp"): None,
                               (8080, "tcp"): "Web Content"})

    def test_establecidas_agrupadas_por_proceso(self):
        g = S.agrupar_conexiones(S.parsear_ss(SS_ESTABLECIDAS))
        brave = g[0]
        self.assertEqual((brave["proceso"], brave["pid"], brave["conexiones"]), ("brave", 900, 3))
        self.assertEqual(brave["destinos"], ["93.184.216.34:443", "151.101.1.69:443"])    # sin repetir
        sin_proceso = [x for x in g if x["proceso"] is None][0]
        self.assertEqual(sin_proceso["conexiones"], 1)
        self.assertEqual(sin_proceso["destinos"], ["192.168.1.50:51000"])
        self.assertEqual(sorted(x["proceso"] or "" for x in g), ["", "avahi-daemon", "brave"])

    def test_consultar_puertos_usa_las_dos_ordenes_con_timeout(self):
        ej = Ejecutor(ss=lambda cmd: resultado(SS_ESCUCHA if cmd[1] == "-tulnpH" else SS_ESTABLECIDAS))
        escucha, conexiones = S.consultar_puertos(ej)
        self.assertEqual([c for c, _ in ej.llamadas], [["ss", "-tulnpH"], ["ss", "-tunpH"]])
        self.assertTrue(all(kw["timeout"] == 3 for _, kw in ej.llamadas))
        self.assertEqual(len(escucha), 8)
        self.assertEqual(conexiones[0]["proceso"], "brave")

    def test_sin_ss_o_con_error_devuelve_none(self):
        self.assertEqual(S.consultar_puertos(Ejecutor(ss=FileNotFoundError())), (None, None))
        self.assertEqual(S.consultar_puertos(Ejecutor(ss=subprocess.TimeoutExpired("ss", 3))), (None, None))
        self.assertEqual(S.consultar_puertos(Ejecutor(ss=resultado("", 1))), (None, None))


class PruebasPwDump(Base):
    def test_microfono_en_uso_y_parado(self):
        r = S.parsear_pw_dump(PW_MICROFONO)
        self.assertEqual(r["microfono"], [{"aplicacion": "Firefox", "pid": 1234}])      # Discord esta parado
        self.assertEqual(r["pantalla"], [])

    def test_captura_de_pantalla(self):
        r = S.parsear_pw_dump(PW_PANTALLA)
        apps = sorted(x["aplicacion"] for x in r["pantalla"])
        self.assertEqual(apps, ["OBS", "xdph-streaming-Virtual-1"])     # la camara web y el nodo parado no
        self.assertEqual(r["microfono"], [])

    def test_sin_nodos(self):
        self.assertEqual(S.parsear_pw_dump("[]"), {"microfono": [], "pantalla": []})

    def test_json_roto_o_no_lista(self):
        self.assertIsNone(S.parsear_pw_dump("no es json"))
        self.assertIsNone(S.parsear_pw_dump('{"a": 1}'))

    def test_aplicacion_por_binario_y_pid_texto(self):
        doc = json.dumps([pw_nodo("running", "Stream/Input/Audio",
                                  **{"application.process.binary": "zoom", "application.process.id": "55"})])
        self.assertEqual(S.parsear_pw_dump(doc)["microfono"], [{"aplicacion": "zoom", "pid": 55}])

    def test_camara_por_proc_simulado(self):
        self.escribir("proc/123/fd/3", "/dev/video0")
        self.escribir("proc/123/fd/4", "/dev/null")
        self.escribir("proc/123/comm", "cheese\n")
        self.escribir("proc/456/fd/7", "socket:[99]")
        self.escribir("proc/789/comm", "sinfd\n")
        leer_enlace = leer_archivo
        self.assertEqual(S.camaras_en_uso(leer_enlace),
                         [{"aplicacion": "cheese", "pid": 123, "dispositivo": "/dev/video0"}])

    def test_camara_tolera_permisos(self):
        self.escribir("proc/321/fd/3", "x")

        def sin_permiso(_p):
            raise PermissionError("no")

        self.assertEqual(S.camaras_en_uso(sin_permiso), [])

    def test_dispositivos_sin_pw_dump(self):
        self.escribir("proc/123/fd/3", "/dev/video2")
        leer_enlace = leer_archivo
        d = S.dispositivos_en_uso(Ejecutor(**{"pw-dump": FileNotFoundError()}), leer_enlace)
        self.assertIsNone(d["microfono"])
        self.assertIsNone(d["pantalla"])
        self.assertEqual(d["camara"][0]["dispositivo"], "/dev/video2")

    def test_dispositivos_con_pw_dump_timeout_5(self):
        ej = Ejecutor(**{"pw-dump": resultado(PW_MICROFONO)})
        d = S.dispositivos_en_uso(ej, lambda p: "")
        self.assertEqual(ej.llamadas[0][0], ["pw-dump"])
        self.assertEqual(ej.llamadas[0][1]["timeout"], 5)
        self.assertEqual(d["microfono"], [{"aplicacion": "Firefox", "pid": 1234}])
        self.assertEqual(d["pantalla"], [])
        self.assertEqual(d["camara"], [])


class PruebasAplicaciones(Base):
    def test_flatpak_ausente(self):
        r = S.info_flatpak(Ejecutor())
        self.assertEqual(r, {"estado": "UNAVAILABLE",
                             "texto": "Flatpak no está instalado en Jaime0: no hay permisos por aplicación. "
                                      "Los programas de Debian se ejecutan con el acceso de tu usuario "
                                      "(tus carpetas, tus dispositivos)."})

    def test_flatpak_presente_lista_y_permisos(self):
        self.escribir("usr/bin/flatpak", "")
        ej = Ejecutor(flatpak=lambda cmd: resultado("org.a.App\norg.b.App\n") if cmd[1] == "list"
                      else resultado("[Context]\nshared=network;\n"))
        r = S.info_flatpak(ej)
        self.assertEqual(r["estado"], "AVAILABLE")
        self.assertEqual([a["aplicacion"] for a in r["aplicaciones"]], ["org.a.App", "org.b.App"])
        self.assertEqual(r["aplicaciones"][0]["permisos"], ["[Context]", "shared=network;"])
        self.assertEqual(ej.llamadas[0][0], ["flatpak", "list", "--app", "--columns=application"])
        self.assertEqual(ej.llamadas[1][0], ["flatpak", "info", "--show-permissions", "org.a.App"])
        self.assertTrue(all(kw["timeout"] for _, kw in ej.llamadas))

    def test_grupos_con_poder_y_explicacion(self):
        g = S.grupos_privilegiados(["jaime", "video", "sudo", "otro", "docker"])
        self.assertEqual([x["grupo"] for x in g], ["sudo", "docker", "video"])
        self.assertEqual(g[0]["texto"], "sudo: puede ejecutar órdenes como administrador con su contraseña")
        self.assertEqual(S.grupos_privilegiados(["jaime"]), [])

    def test_todos_los_grupos_pedidos_tienen_explicacion(self):
        pedidos = ["sudo", "adm", "lpadmin", "docker", "libvirt", "kvm", "plugdev", "netdev",
                   "bluetooth", "video", "audio", "render", "input"]
        self.assertEqual([x["grupo"] for x in S.grupos_privilegiados(pedidos)], pedidos)

    def test_servicios_activo_inactivo_no_instalado(self):
        def systemctl(cmd):
            unidad = cmd[-1]
            if unidad == "ssh.service":
                return resultado("LoadState=loaded\nActiveState=active\n")
            if unidad == "cups.service":
                return resultado("LoadState=not-found\nActiveState=inactive\n")
            return resultado("LoadState=loaded\nActiveState=inactive\n")

        r = {s["nombre"]: s for s in S.servicios_privacidad(Ejecutor(systemctl=systemctl))}
        self.assertEqual(list(r), ["ssh", "avahi-daemon", "cups", "bluetooth", "NetworkManager"])
        self.assertEqual(r["ssh"]["estado"], "activo")
        self.assertIn("entrada remota", r["ssh"]["texto"])
        self.assertEqual(r["cups"]["estado"], "no instalado")
        self.assertEqual(r["bluetooth"]["estado"], "inactivo")

    def test_servicios_sin_systemctl(self):
        r = S.servicios_privacidad(Ejecutor(systemctl=FileNotFoundError()))
        self.assertTrue(all(s["estado"] == "desconocido" for s in r))


class PruebasTelemetria(Base):
    def por(self, lista):
        return {t["elemento"]: t for t in lista}

    def test_siempre_jaime0_sin_telemetria(self):
        t = self.por(S.telemetria(Ejecutor(), ciudad=""))
        self.assertEqual(t["Jaime0"]["texto"], "Sin telemetría: nada sale del equipo")

    def test_popularity_contest_ausente(self):
        t = self.por(S.telemetria(Ejecutor(**{"dpkg-query": resultado("", 1)}), ciudad=""))
        self.assertEqual(t["popularity-contest"]["estado"], "NO INSTALADO")

    def test_popularity_contest_presente_participando_o_no(self):
        ej = Ejecutor(**{"dpkg-query": resultado("install ok installed")})
        self.escribir("etc/popularity-contest.conf", '# c\nPARTICIPATE="yes"\n')
        self.assertEqual(self.por(S.telemetria(ej, ciudad=""))["popularity-contest"]["estado"], "ACTIVO")
        self.escribir("etc/popularity-contest.conf", 'PARTICIPATE="no"\n')
        self.assertEqual(self.por(S.telemetria(ej, ciudad=""))["popularity-contest"]["estado"], "INACTIVO")
        shutil.rmtree(os.path.join(self.raiz, "etc"))
        self.assertEqual(self.por(S.telemetria(ej, ciudad=""))["popularity-contest"]["estado"], "INACTIVO")

    def test_tiempo_con_y_sin_ciudad(self):
        con = self.por(S.telemetria(Ejecutor(), ciudad="Madrid"))["Widget del tiempo"]
        self.assertEqual((con["estado"], con["texto"]),
                         ("ACTIVO", "Conecta con Open-Meteo con la ciudad que escribiste"))
        sin = self.por(S.telemetria(Ejecutor(), ciudad=""))["Widget del tiempo"]
        self.assertEqual(sin["estado"], "INACTIVO")
        self.assertEqual(self.por(S.telemetria(Ejecutor(), ciudad=None))["Widget del tiempo"]["estado"],
                         "DESCONOCIDO")

    def test_ciudad_leida_de_jaime0_ajustes(self):
        doc = json.dumps({"ajustes": [{"clave": "reloj_formato", "valor": "24h"},
                                      {"clave": "tiempo_ciudad", "valor": "Sevilla"}]})
        ej = Ejecutor(**{sys.executable: resultado(doc)})
        self.assertEqual(S.ciudad_del_tiempo(ej), "Sevilla")
        self.assertEqual(ej.llamadas[0][0][1:2], ["-I"])
        self.assertEqual(ej.llamadas[0][0][-2:], ["ver", "--json"])
        self.assertIsNone(S.ciudad_del_tiempo(Ejecutor(**{sys.executable: resultado("", 1)})))

    def test_debsecan_y_brave(self):
        t = self.por(S.telemetria(Ejecutor(), ciudad=""))
        self.assertEqual(t["debsecan"]["estado"], "NO INSTALADO")
        self.assertEqual(t["Brave"]["estado"], "NO INSTALADO")
        self.escribir("usr/bin/debsecan", "")
        self.escribir("usr/bin/brave-browser", "")
        t = self.por(S.telemetria(Ejecutor(), ciudad=""))
        self.assertIn("security-tracker.debian.org", t["debsecan"]["texto"])
        self.assertIn("no envía datos del equipo", t["debsecan"]["texto"])
        self.assertIn("brave://settings/privacy", t["Brave"]["texto"])
        self.assertIn("P3A", t["Brave"]["texto"])


class PruebasEstado(Base):
    def activo(self, politica='DEFAULT_INPUT_POLICY="DROP"\n'):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        if politica:
            self.escribir("etc/default/ufw", politica)

    def test_unavailable_sin_ufw(self):
        r = S.resumen_privacidad(True, [])
        self.assertEqual(r["estado"], "UNAVAILABLE")
        self.assertEqual(r["detalles"], ["El cortafuegos (UFW) no está instalado"])
        self.assertEqual(r["motivos"], ["El cortafuegos (UFW) no está instalado"])

    def test_secure_con_textos_exactos(self):
        self.activo()
        r = S.resumen_privacidad(True, S.parsear_ss(SS_ESCUCHA.split("\n")[3] + "\n"))   # solo 127.0.0.1
        self.assertEqual(r["estado"], "SECURE")
        self.assertEqual(r["detalles"], ["Cortafuegos activo: entrante denegado por defecto",
                                         "Ningún puerto abierto a la red"])
        self.assertEqual(r["motivos"], [])

    def test_secure_con_reject(self):
        self.activo('DEFAULT_INPUT_POLICY="REJECT"\n')
        self.assertEqual(S.resumen_privacidad(True, [])["estado"], "SECURE")

    def test_secure_sin_mirar_puertos_no_dice_nada_de_ellos(self):
        self.activo()
        r = S.resumen_privacidad(True, None)
        self.assertEqual(r["estado"], "SECURE")
        self.assertEqual(r["detalles"], ["Cortafuegos activo: entrante denegado por defecto"])

    def test_warning_inactivo(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=no\n")
        r = S.resumen_privacidad(False, [])
        self.assertEqual(r["estado"], "WARNING")
        self.assertEqual(r["motivos"], ["El cortafuegos (UFW) está desactivado"])

    def test_warning_servicio_parado(self):
        self.activo()
        r = S.resumen_privacidad(False, [])
        self.assertEqual(r["estado"], "WARNING")
        self.assertIn("servicio no está activo", r["motivos"][0])

    def test_warning_entrante_accept(self):
        self.activo('DEFAULT_INPUT_POLICY="ACCEPT"\n')
        r = S.resumen_privacidad(True, [])
        self.assertEqual(r["estado"], "WARNING")
        self.assertEqual(r["motivos"], ["Cortafuegos activo: entrante permitido por defecto"])

    def test_warning_puerto_expuesto_dice_puerto_proceso_y_aclara_ufw(self):
        self.activo()
        r = S.resumen_privacidad(True, S.parsear_ss(SS_ESCUCHA))
        self.assertEqual(r["estado"], "WARNING")
        self.assertIn("4 puerto(s) abierto(s) a la red", r["detalles"])
        sshd = [m for m in r["motivos"] if "22/tcp" in m]
        self.assertEqual(len(sshd), 1)
        self.assertIn("sshd", sshd[0])
        self.assertIn("UFW bloquea la entrada salvo que una regla lo permita", sshd[0])
        self.assertTrue(any("80/tcp" in m and "proceso no identificado" in m for m in r["motivos"]))

    def test_puerto_expuesto_sin_ufw_activo_no_afirma_bloqueo(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=no\n")
        r = S.resumen_privacidad(False, S.parsear_ss(SS_ESCUCHA))
        self.assertTrue(all("UFW bloquea" not in m for m in r["motivos"]))

    def test_nunca_afirma_sistema_protegido(self):
        self.activo()
        for r in (S.resumen_privacidad(True, []), S.resumen_privacidad(True, S.parsear_ss(SS_ESCUCHA))):
            for texto in r["detalles"] + r["motivos"]:
                self.assertNotIn("protegido", texto.lower())

    def test_estado_global_no_cambia_por_la_privacidad(self):
        sv = self.servicio()
        inst = {"v": 1, "t": 1, "intervalo": 10, "cpu": {"total": 1.0, "temp": 40.0}, "ram": None,
                "disco": None, "bateria": None, "fallidas": None}
        antes = S.evaluar(inst)
        self.activo()
        sv.priv_puertos = S.parsear_ss(SS_ESCUCHA)
        sv.priv_recalcular()
        self.assertEqual(sv.privacidad["estado"], "WARNING")
        self.assertEqual(S.evaluar(inst), antes)
        self.assertEqual(antes[0], "ONLINE")


class PruebasHistorial(Base):
    def instalar_ufw(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.escribir("etc/default/ufw", 'DEFAULT_INPUT_POLICY="DROP"\n')

    def test_primera_lectura_no_genera_eventos(self):
        self.instalar_ufw()
        sv = self.servicio(ss=resultado(SS_ESCUCHA), **{"pw-dump": resultado(PW_MICROFONO)})
        sv._ufw_activa = True
        sv.priv_recalcular()
        sv.priv_refrescar()
        self.assertEqual(self.historial(sv), [])

    def test_aparicion_y_desaparicion_de_puerto(self):
        self.instalar_ufw()
        sv = self.servicio(ss=resultado("tcp LISTEN 0 4096 127.0.0.1:631 0.0.0.0:*\n"),
                           **{"pw-dump": FileNotFoundError()})
        sv._ufw_activa = True
        sv.priv_refrescar(True, False)
        sv.priv_ejecutar.respuestas["ss"] = resultado(
            'tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1,fd=3))\n')
        sv.priv_refrescar(True, False)
        self.assertEqual(self.historial(sv), ["Puerto expuesto: 22/tcp (sshd)"])
        sv.priv_ejecutar.respuestas["ss"] = resultado("tcp LISTEN 0 4096 127.0.0.1:631 0.0.0.0:*\n")
        sv.priv_refrescar(True, False)
        self.assertEqual(self.historial(sv), ["Puerto expuesto: 22/tcp (sshd)",
                                              "Puerto ya no expuesto: 22/tcp (sshd)"])

    def test_inicio_y_fin_de_uso_del_microfono(self):
        sv = self.servicio(ss=resultado(""), **{"pw-dump": resultado("[]")})
        sv.priv_refrescar()
        sv.priv_ejecutar.respuestas["pw-dump"] = resultado(PW_MICROFONO)
        sv.priv_refrescar(False, True)
        sv.priv_ejecutar.respuestas["pw-dump"] = resultado("[]")
        sv.priv_refrescar(False, True)
        self.assertEqual(self.historial(sv), ["Micrófono: Firefox empieza a usarlo",
                                              "Micrófono: Firefox deja de usarlo"])
        doc = sv.priv_historial.ultimos(1)[0]
        self.assertEqual(sorted(doc), ["t", "texto", "tipo", "v"])
        self.assertEqual((doc["v"], doc["tipo"]), (1, "microfono"))

    def test_pantalla_y_camara(self):
        sv = self.servicio(ss=resultado(""), **{"pw-dump": resultado("[]")})
        sv.priv_refrescar(False, True)
        sv.priv_ejecutar.respuestas["pw-dump"] = resultado(PW_PANTALLA)
        sv.priv_refrescar(False, True)
        self.assertIn("Captura de pantalla: OBS empieza a capturar", self.historial(sv))

    def test_cambios_del_cortafuegos(self):
        self.instalar_ufw()
        sv = self.servicio()
        sv._ufw_activa = True
        sv.priv_recalcular()
        self.escribir("etc/default/ufw", 'DEFAULT_INPUT_POLICY="ACCEPT"\n')
        sv.priv_recalcular()
        self.escribir("etc/ufw/ufw.conf", "ENABLED=no\n")
        sv.priv_recalcular()
        self.assertEqual(self.historial(sv), ["Política entrante del cortafuegos: DROP → ACCEPT",
                                              "Cortafuegos desactivado"])

    def test_sin_herramientas_no_inventa_cambios(self):
        sv = self.servicio(ss=resultado(SS_ESCUCHA), **{"pw-dump": resultado(PW_MICROFONO)})
        sv.priv_refrescar()
        sv.priv_ejecutar.respuestas["ss"] = FileNotFoundError()
        sv.priv_ejecutar.respuestas["pw-dump"] = FileNotFoundError()
        sv.priv_refrescar()
        self.assertEqual(self.historial(sv), [])

    def test_recorte_a_300_lineas(self):
        sv = self.servicio()
        for i in range(310):
            sv.priv_historial.anotar("puerto", f"evento {i}")
        with open(os.path.join(self.estado, "privacidad.jsonl"), encoding="utf-8") as f:
            lineas = f.read().splitlines()
        self.assertEqual(len(lineas), 300)
        self.assertEqual(json.loads(lineas[0])["texto"], "evento 10")
        self.assertEqual(json.loads(lineas[-1])["texto"], "evento 309")
        self.assertEqual(sv.priv_historial.ultimos(1)[0]["texto"], "evento 309")

    def test_sin_direcciones_remotas_ni_conexiones_en_disco(self):
        self.instalar_ufw()
        sv = self.servicio(ss=lambda cmd: resultado(SS_ESCUCHA if cmd[1] == "-tulnpH" else SS_ESTABLECIDAS),
                           **{"pw-dump": resultado("[]")})
        sv._ufw_activa = True
        sv.priv_refrescar()
        sv.priv_ejecutar.respuestas["ss"] = lambda cmd: resultado(
            "" if cmd[1] == "-tulnpH" else SS_ESTABLECIDAS)
        sv.priv_refrescar()
        sv.priv_historial.anotar("reglas", "x")
        sv.priv_refrescar()
        escrito = ""
        for base, _d, archivos in os.walk(self.tmp):
            if os.path.abspath(base).startswith(self.raiz):
                continue
            for a in archivos:
                with open(os.path.join(base, a), encoding="utf-8", errors="replace") as f:
                    escrito += f.read()
        for remoto in ("93.184.216.34", "151.101.1.69", "192.168.1.50"):
            self.assertNotIn(remoto, escrito)
        self.assertEqual(sv.priv_conexiones[0]["proceso"], "brave")      # en memoria si, en disco no

    def test_eventos_privacidad_es_puro(self):
        antes = {"puertos": {(22, "tcp"): "sshd"}, "microfono": {"a"}}
        copia = {"puertos": dict(antes["puertos"]), "microfono": set(antes["microfono"])}
        eventos_privacidad = S.eventos_privacidad(antes, {"puertos": {}, "microfono": {"a", "b"}})
        self.assertEqual(eventos_privacidad, [("puerto", "Puerto ya no expuesto: 22/tcp (sshd)"),
                                              ("microfono", "Micrófono: b empieza a usarlo")])
        self.assertEqual(antes, copia)


class PruebasApi(Base):
    def instalar_ufw(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\nLOGLEVEL=low\n")
        self.escribir("etc/default/ufw", 'DEFAULT_INPUT_POLICY="DROP"\n')

    def sv_completo(self, **extra):
        resp = {"ss": lambda cmd: resultado(SS_ESCUCHA if cmd[1] == "-tulnpH" else SS_ESTABLECIDAS),
                "pw-dump": resultado(PW_MICROFONO),
                "systemctl": resultado("LoadState=loaded\nActiveState=active\n"),
                "dpkg-query": resultado("", 1), sys.executable: resultado(
                    json.dumps({"ajustes": [{"clave": "tiempo_ciudad", "valor": ""}]}))}
        resp.update(extra)
        sv = self.servicio(**resp)
        sv._ufw_activa = True
        return sv

    def test_orden_privacidad_con_todas_las_claves(self):
        self.instalar_ufw()
        sv = self.sv_completo()
        with mock.patch.object(S, "nombres_de_grupos", return_value=["sudo", "audio"]):
            r = json.loads(S.procesar_linea(json.dumps({"orden": "privacidad"}), sv))
        self.assertEqual(sorted(r), ["conexiones", "cortafuegos", "dispositivos", "estado", "flatpak",
                                     "historial", "ok", "privilegios", "puertos", "servicios", "telemetria", "v"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["v"], 1)
        self.assertEqual(r["estado"]["estado"], "WARNING")
        self.assertEqual(r["cortafuegos"]["politicas"]["entrante"], "DROP")
        self.assertNotIn("reglas", r["cortafuegos"])
        self.assertEqual(len(r["puertos"]), 8)
        self.assertEqual(r["conexiones"][0]["proceso"], "brave")
        self.assertEqual(r["dispositivos"]["microfono"], [{"aplicacion": "Firefox", "pid": 1234}])
        self.assertEqual(r["flatpak"]["estado"], "UNAVAILABLE")
        self.assertEqual([g["grupo"] for g in r["privilegios"]["grupos"]], ["sudo", "audio"])
        self.assertEqual(len(r["servicios"]), 5)
        self.assertEqual(r["telemetria"][0]["elemento"], "Jaime0")
        self.assertIsInstance(r["historial"], list)

    def test_privacidad_en_hilo_con_responder(self):
        self.instalar_ufw()
        sv = self.sv_completo()
        hecho, textos = threading.Event(), []
        respuesta = S.procesar_linea('{"orden":"privacidad"}', sv, lambda t: (textos.append(t), hecho.set()))
        self.assertIsNone(respuesta)
        self.assertTrue(hecho.wait(10))
        self.assertTrue(json.loads(textos[0])["ok"])

    def test_ufw_reglas_ok_y_registro(self):
        self.instalar_ufw()
        sv = self.sv_completo(pkexec=resultado(UFW_ACTIVO))
        r = json.loads(S.procesar_linea('{"orden":"ufw_reglas"}', sv))
        self.assertTrue(r["ok"] and r["activo"])
        self.assertEqual(r["puertos_bloqueados"], ["23/tcp", "25/tcp"])
        self.assertEqual(self.historial(sv), ["Reglas del cortafuegos consultadas (con autorización)"])
        for base, _d, archivos in os.walk(self.tmp):       # la salida de ufw no se guarda
            for a in archivos:
                with open(os.path.join(base, a), encoding="utf-8", errors="replace") as f:
                    self.assertNotIn("80,443/tcp", f.read())

    def test_ufw_reglas_cancelado_y_sin_agente(self):
        self.instalar_ufw()
        sv = self.sv_completo(pkexec=resultado("", 126))
        self.assertEqual(json.loads(S.procesar_linea('{"orden":"ufw_reglas"}', sv)),
                         {"ok": False, "error": "autorización cancelada"})
        sv.priv_ejecutar.respuestas["pkexec"] = resultado("", 127)
        self.assertEqual(json.loads(S.procesar_linea('{"orden":"ufw_reglas"}', sv)),
                         {"ok": False, "error": "no hay agente de autorización (polkit)"})
        self.assertEqual(self.historial(sv), [
            "Consulta de las reglas del cortafuegos: autorización cancelada",
            "Consulta de las reglas del cortafuegos: no hay agente de autorización (polkit)"])

    def test_ufw_reglas_sin_ufw_no_pide_autorizacion(self):
        sv = self.sv_completo(pkexec=resultado(UFW_ACTIVO))
        r = json.loads(S.procesar_linea('{"orden":"ufw_reglas"}', sv))
        self.assertFalse(r["ok"])
        self.assertEqual(sv.priv_ejecutar.llamadas, [])

    def test_ufw_reglas_en_hilo_no_bloquea(self):
        self.instalar_ufw()
        suelta, hecho, textos = threading.Event(), threading.Event(), []

        def pkexec(_cmd):
            suelta.wait(10)
            return resultado(UFW_ACTIVO)

        sv = self.sv_completo(pkexec=pkexec)
        respuesta = S.procesar_linea('{"orden":"ufw_reglas"}', sv, lambda t: (textos.append(t), hecho.set()))
        self.assertIsNone(respuesta)             # vuelve enseguida: el bucle no espera a la contraseña
        self.assertFalse(textos)
        segunda = json.loads(S.procesar_linea('{"orden":"ufw_reglas"}', sv))
        self.assertEqual(segunda, {"ok": False, "error": "ya hay una consulta de reglas en curso"})
        suelta.set()
        self.assertTrue(hecho.wait(10))
        self.assertTrue(json.loads(textos[0])["ok"])

    def test_privacidad_historial_con_limite(self):
        sv = self.servicio()
        for i in range(30):
            sv.priv_historial.anotar("puerto", f"e{i}")
        r = json.loads(S.procesar_linea('{"orden":"privacidad_historial","limite":5}', sv))
        self.assertTrue(r["ok"])
        self.assertEqual([h["texto"] for h in r["historial"]], ["e29", "e28", "e27", "e26", "e25"])
        r = json.loads(S.procesar_linea('{"orden":"privacidad_historial","limite":"mucho"}', sv))
        self.assertEqual(len(r["historial"]), 30)

    def test_estado_json_lleva_la_privacidad_ampliada(self):
        self.instalar_ufw()
        sv = self.servicio()
        sv._ufw_activa = True
        sv.priv_recalcular()
        sv.instante = {"cargador": None}
        sv.publicar("ONLINE", [])
        with open(os.path.join(self.rt, "estado.json"), encoding="utf-8") as f:
            priv = json.load(f)["privacidad"]
        self.assertEqual(sorted(priv), ["detalles", "estado", "motivos"])
        self.assertEqual(priv["estado"], "SECURE")

    def test_dispositivos_solo_cada_10_s_con_ventana_abierta(self):
        sv = self.servicio()
        llamadas = []
        sv.priv_lanzar = lambda p=True, d=True: llamadas.append((p, d))
        sv._priv_disp_t = -1000.0
        sv.rapido_hasta = 0.0
        self.assertTrue(sv._priv_periodico())
        self.assertEqual(llamadas, [])                   # sin cliente "rapido": solo el refresco de 60 s
        sv.rapido_hasta = 2 ** 40
        sv._priv_periodico()
        self.assertEqual(llamadas, [(False, True)])


class PruebasAyudante(unittest.TestCase):
    def setUp(self):
        self.texto = AYUDANTE.read_text(encoding="utf-8")
        self.lineas = [l for l in self.texto.splitlines() if l.strip() and not l.lstrip().startswith("#")]

    def test_es_sh_posix_de_solo_lectura(self):
        self.assertTrue(self.texto.startswith("#!/bin/sh\n"))
        self.assertIn("SOLO LECTURA", self.texto)
        self.assertIn("set -eu", self.lineas)

    def test_rechaza_argumentos_con_codigo_2(self):
        self.assertIn('if [ "$#" -ne 0 ]; then', self.lineas)
        i = self.lineas.index('if [ "$#" -ne 0 ]; then')
        self.assertEqual(self.lineas[i + 2].strip(), "exit 2")

    def test_path_fijo(self):
        self.assertIn("PATH=/usr/sbin:/usr/bin:/sbin:/bin", self.lineas)
        self.assertIn("export PATH", self.lineas)

    def test_solo_ejecuta_ufw_status_verbose(self):
        ejecuciones = [l for l in self.lineas if "ufw" in l and not l.strip().startswith("echo")]
        self.assertEqual(ejecuciones, ["exec ufw status verbose"])
        for peligro in ("$1", "$@", "$*", "eval", "sudo", "|", "`", "$("):
            self.assertNotIn(peligro, "\n".join(self.lineas), peligro)

    @unittest.skipUnless(shutil.which("sh"), "no hay sh")
    def test_con_argumentos_sale_con_2_sin_ejecutar_ufw(self):
        r = subprocess.run(["sh", AYUDANTE.as_posix(), "reset"], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no admite argumentos", r.stderr)


class PruebasPolitica(unittest.TestCase):
    def test_accion_polkit(self):
        doc = xml.dom.minidom.parse(str(POLITICA))
        acciones = doc.getElementsByTagName("action")
        self.assertEqual(len(acciones), 1)
        a = acciones[0]
        texto = lambda etiqueta: a.getElementsByTagName(etiqueta)[0].firstChild.data
        self.assertEqual(a.getAttribute("id"), "es.jaime0.ufw-estado")
        self.assertEqual(texto("description"), "Ver las reglas del cortafuegos")
        self.assertEqual(texto("message"), "Para ver las reglas del cortafuegos hace falta tu contraseña. "
                                           "Solo se leen; no se cambia nada.")
        self.assertEqual((texto("allow_any"), texto("allow_inactive"), texto("allow_active")),
                         ("no", "no", "auth_admin_keep"))
        anota = a.getElementsByTagName("annotate")[0]
        self.assertEqual(anota.getAttribute("key"), "org.freedesktop.policykit.exec.path")
        self.assertEqual(anota.firstChild.data, "/usr/local/libexec/jaime0-ufw-estado")
        self.assertEqual(anota.firstChild.data, S.AYUDANTE_UFW)


class PruebasCliente(unittest.TestCase):
    DOC = {"ok": True, "v": 1,
           "estado": {"estado": "WARNING", "detalles": ["Cortafuegos activo: entrante denegado por defecto"],
                      "motivos": ["Puerto 22/tcp abierto a la red (sshd): UFW bloquea la entrada salvo que una regla lo permita"]},
           "cortafuegos": {"instalado": True, "activo": True, "unidad_activa": True, "registro": "low",
                           "politicas": {"entrante": "DROP", "saliente": "ACCEPT", "enrutado": "DROP"}},
           "puertos": [{"protocolo": "tcp", "estado": "LISTEN", "direccion": "0.0.0.0", "puerto": 22,
                        "remoto": "0.0.0.0:*", "proceso": "sshd", "pid": 1, "expuesto": True}],
           "conexiones": [{"proceso": "brave", "pid": 9, "conexiones": 2, "destinos": ["1.2.3.4:443"]}],
           "dispositivos": {"microfono": [{"aplicacion": "Firefox", "pid": 5}], "camara": [], "pantalla": None},
           "flatpak": {"estado": "UNAVAILABLE", "texto": "Flatpak no está instalado en Jaime0"},
           "privilegios": {"grupos": [{"grupo": "sudo", "texto": "sudo: puede ejecutar órdenes"}]},
           "servicios": [{"nombre": "ssh", "estado": "activo", "texto": "Servidor SSH"}],
           "telemetria": [{"elemento": "Jaime0", "estado": "NINGUNA", "texto": "Sin telemetría: nada sale del equipo"}],
           "historial": [{"v": 1, "t": 1763123456, "tipo": "puerto", "texto": "Puerto expuesto: 22/tcp (sshd)"}]}

    def ejecutar(self, argv, respuesta, **kw):
        peticiones = []

        def enviar(p, timeout=None):
            peticiones.append((p, timeout))
            if isinstance(respuesta, BaseException):
                raise respuesta
            return respuesta

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            codigo = C.main(argv, enviar)
        return codigo, out.getvalue(), err.getvalue(), peticiones

    def test_resumen_legible_por_apartados(self):
        codigo, out, err, pet = self.ejecutar([], self.DOC)
        self.assertEqual(codigo, 0)
        self.assertEqual(pet[0][0], {"orden": "privacidad"})
        for apartado in ("PRIVACY & SECURITY: WARNING", "CORTAFUEGOS", "PUERTOS EN ESCUCHA", "CONEXIONES POR PROGRAMA",
                         "DISPOSITIVOS EN USO", "APLICACIONES", "PRIVILEGIOS DEL USUARIO", "SERVICIOS",
                         "TELEMETRÍA", "HISTORIAL RECIENTE"):
            self.assertIn(apartado, out)
        self.assertIn("EXPUESTO", out)
        self.assertIn("Micrófono: Firefox (pid 5)", out)
        self.assertIn("Cámara: nadie lo usa", out)
        self.assertIn("Captura de pantalla: N/D", out)
        self.assertIn("Sin telemetría: nada sale del equipo", out)

    def test_json(self):
        codigo, out, _e, _p = self.ejecutar(["--json"], self.DOC)
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(out), self.DOC)

    def test_sin_servicio_error_claro_y_codigo_1(self):
        for argv in ([], ["--json"], ["reglas"], ["historial"]):
            codigo, out, err, _p = self.ejecutar(argv, FileNotFoundError("sin socket"))
            self.assertEqual(codigo, 1, argv)
            self.assertEqual(out, "")
            self.assertIn("el servicio de Jaime0 no está en marcha", err)

    def test_reglas_avisa_y_pide_ufw_reglas(self):
        doc = {"ok": True, "activo": True, "registro": "on (low)",
               "politicas": {"entrante": "DROP", "saliente": "ACCEPT", "enrutado": "DISABLED"},
               "reglas": [{"destino": "22/tcp", "accion": "ALLOW IN", "origen": "Anywhere", "ipv6": True,
                           "comentario": "ssh"}],
               "puertos_permitidos": ["22/tcp"], "puertos_bloqueados": []}
        codigo, out, err, pet = self.ejecutar(["reglas"], doc)
        self.assertEqual(codigo, 0)
        self.assertEqual(pet[0][0], {"orden": "ufw_reglas"})
        self.assertGreaterEqual(pet[0][1], 120)             # tiempo para escribir la contraseña
        self.assertIn("Se pedirá tu contraseña para leer las reglas (solo lectura)", err)
        self.assertIn("22/tcp", out)
        self.assertIn("(IPv6)", out)
        self.assertIn("# ssh", out)

    def test_reglas_error_de_autorizacion(self):
        codigo, out, err, _p = self.ejecutar(["reglas"], {"ok": False, "error": "autorización cancelada"})
        self.assertEqual(codigo, 1)
        self.assertIn("autorización cancelada", err)

    def test_historial_con_n(self):
        codigo, out, _e, pet = self.ejecutar(["historial", "-n", "5"], {"ok": True, "historial": self.DOC["historial"]})
        self.assertEqual(codigo, 0)
        self.assertEqual(pet[0][0], {"orden": "privacidad_historial", "limite": 5})
        self.assertIn("Puerto expuesto: 22/tcp (sshd)", out)

    def test_historial_por_defecto_20_y_n_invalido(self):
        _c, _o, _e, pet = self.ejecutar(["historial"], {"ok": True, "historial": []})
        self.assertEqual(pet[0][0]["limite"], 20)
        codigo, _o, err, pet = self.ejecutar(["historial", "-n", "cero"], {"ok": True, "historial": []})
        self.assertEqual(codigo, 1)
        self.assertEqual(pet, [])

    def test_orden_desconocida(self):
        codigo, _o, err, _p = self.ejecutar(["borrar"], self.DOC)
        self.assertEqual(codigo, 1)
        self.assertIn("orden desconocida", err)


if __name__ == "__main__":
    unittest.main()
