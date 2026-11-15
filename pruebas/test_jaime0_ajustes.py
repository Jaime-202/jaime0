#!/usr/bin/env python3
"""Pruebas de jaime0-ajustes sobre un sistema de mentira (JAIME0_RAIZ) y una carpeta
personal temporal. No necesitan sesion grafica: en modo de prueba no se recarga nada.

    python3 -m unittest discover -s pruebas -v
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
INCLUDES = REPO / "config/includes.chroot_after_packages"
PROGRAMA = INCLUDES / "usr/local/bin/jaime0-ajustes"
PREDETERMINADOS = INCLUDES / "usr/share/jaime0/ajustes.predeterminados"


class Escenario:
    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-ajustes-"))
        self.raiz = self.tmp / "raiz"
        self.casa = self.tmp / "casa"
        destino = self.raiz / "usr/share/jaime0/ajustes.predeterminados"
        destino.parent.mkdir(parents=True)
        # El fondo predeterminado apunta a la raiz falsa, para que exista.
        self.fondos = self.raiz / "usr/share/backgrounds/jaime0"
        self.fondos.mkdir(parents=True)
        (self.fondos / "jaime0.png").write_bytes(b"png")
        texto = PREDETERMINADOS.read_text(encoding="utf-8").replace(
            "/usr/share/backgrounds/jaime0/jaime0.png", (self.fondos / "jaime0.png").as_posix())
        destino.write_text(texto, encoding="utf-8")
        self.casa.mkdir()
        self.config = self.casa / ".config"

    @property
    def archivo(self):
        return self.config / "jaime0" / "ajustes"

    def generado(self, nombre):
        return (self.config / "jaime0" / "generado" / nombre).read_text(encoding="utf-8")

    def ejecutar(self, *args):
        env = dict(os.environ, JAIME0_RAIZ=str(self.raiz), HOME=str(self.casa),
                   XDG_CONFIG_HOME=str(self.config), XDG_DATA_HOME=str(self.casa / ".local/share"),
                   PYTHONIOENCODING="utf-8")
        env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        r = subprocess.run([sys.executable, str(PROGRAMA), *args], env=env,
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout, r.stderr

    def ver(self):
        rc, out, err = self.ejecutar("ver", "--json")
        assert rc == 0, err
        d = json.loads(out)
        return {a["clave"]: a for a in d["ajustes"]}, d

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PruebasAjustes(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.addCleanup(self.e.limpiar)

    def test_predeterminados_sin_archivo_de_usuario(self):
        ajustes, d = self.e.ver()
        self.assertEqual(ajustes["borde"]["valor"], "2")
        self.assertEqual(ajustes["esquinas"]["valor"], "8")
        self.assertEqual(ajustes["acento"]["valor"], "verde")
        self.assertEqual(ajustes["acento"]["color"], "#54e58a")
        self.assertEqual(ajustes["barra_altura"]["valor"], "26")
        self.assertFalse(any(a["propio"] for a in ajustes.values()))
        self.assertEqual(d["temas"]["cian"], "#55cde0")
        self.assertIn((self.e.fondos / "jaime0.png").as_posix(), [pathlib.Path(f).as_posix() for f in d["fondos"]])
        self.assertFalse(self.e.archivo.exists(), "ver no debe crear el archivo del usuario")

    def test_poner_guarda_solo_lo_cambiado_y_genera(self):
        rc, out, err = self.e.ejecutar("poner", "acento", "cian", "barra_altura", "30")
        self.assertEqual(rc, 0, err)
        texto = self.e.archivo.read_text(encoding="utf-8")
        claves = [l.split("=")[0].strip() for l in texto.splitlines() if l and not l.startswith("#")]
        self.assertEqual(sorted(claves), ["acento", "barra_altura"])
        self.assertIn("@define-color acento #55cde0;", self.e.generado("waybar.css"))
        self.assertIn("acento: #55cde0;", self.e.generado("rofi.rasi"))
        self.assertEqual(json.loads(self.e.generado("waybar.json")), {"height": 30, "position": "top"})
        ajustes, _ = self.e.ver()
        self.assertTrue(ajustes["acento"]["propio"])
        self.assertFalse(ajustes["borde"]["propio"])

    def test_acento_en_bloqueo_notificaciones_y_osd(self):
        propio = self.e.casa / "fondo.png"
        propio.write_bytes(b"png")
        self.assertEqual(self.e.ejecutar("poner", "acento", "ambar", "fondo", str(propio))[0], 0)
        hyprlock = self.e.generado("hyprlock.conf")
        self.assertIn("$acento = rgb(e0b050)", hyprlock)
        imagen = [l for l in hyprlock.splitlines() if l.startswith("$imagen = ")]
        self.assertEqual(len(imagen), 1)
        self.assertTrue(imagen[0].endswith("fondo.png"))
        self.assertIn("@define-color acento #e0b050;", self.e.generado("swaync.css"))
        wob = self.e.generado("wob.ini")
        self.assertIn("bar_color = e0b050ff", wob)
        self.assertNotIn("[", wob, "wob: las claves por defecto van sin cabecera de seccion")

    def test_widgets(self):
        # Por defecto, ninguno: el escritorio empieza vacio.
        self.e.ejecutar("generar")
        self.assertEqual(json.loads(self.e.generado("widgets.json"))["widgets"], {})
        self.assertEqual(self.e.ejecutar("poner", "widget_reloj", "arriba-izquierda", "widget_musica",
                                         "abajo-derecha", "reloj_formato", "12h", "widgets_tarjetas", "no",
                                         "tiempo_ciudad", "  San  Sebastián de los Reyes, España ")[0], 0)
        w = json.loads(self.e.generado("widgets.json"))
        self.assertEqual(w["widgets"], {"reloj": "arriba-izquierda", "musica": "abajo-derecha"})
        self.assertEqual((w["reloj_formato"], w["tarjetas"], w["acento"]), ("12h", False, "#54e58a"))
        self.assertEqual(w["ciudad"], "San Sebastián de los Reyes, España")
        for args in (("widget_reloj", "izquierda"), ("tiempo_ciudad", "Madrid; rm -rf /"),
                     ("tiempo_ciudad", "x" * 61), ("tiempo_ciudad", "123"), ("reloj_formato", "48h")):
            self.assertEqual(self.e.ejecutar("poner", *args)[0], 1, args)
        self.assertEqual(self.e.ejecutar("poner", "tiempo_ciudad", "")[0], 0)  # vacia: permitido

    def test_valores_invalidos_no_cambian_nada(self):
        self.e.ejecutar("poner", "borde", "1")
        antes = self.e.archivo.read_text(encoding="utf-8")
        for args in (("borde", "99"), ("esquinas", "abc"), ("acento", "rojizo"), ("acento", "#12345"),
                     ("barra_posicion", "izquierda"), ("desenfoque", "quizas"), ("no_existe", "1"),
                     ("opacidad_inactiva", "0.2"), ("fondo", "/no/existe.png"),
                     ("esquinas", "6", "borde", "50")):  # todo o nada
            rc, _, err = self.e.ejecutar("poner", *args)
            self.assertEqual(rc, 1, args)
            self.assertTrue(err.strip(), args)
            self.assertEqual(self.e.archivo.read_text(encoding="utf-8"), antes, args)

    def test_normaliza_valores(self):
        self.assertEqual(self.e.ejecutar("poner", "opacidad_inactiva", "0,85")[0], 0)
        self.assertEqual(self.e.ejecutar("poner", "desenfoque", "NO")[0], 0)
        self.assertEqual(self.e.ejecutar("poner", "acento", "#ABCDEF")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertEqual(ajustes["opacidad_inactiva"]["valor"], "0.85")
        self.assertEqual(ajustes["desenfoque"]["valor"], "no")
        self.assertEqual(ajustes["acento"]["color"], "#abcdef")
        self.assertIn("#abcdef", self.e.generado("waybar.css"))

    def test_conserva_comentarios_y_quita_duplicados(self):
        self.e.archivo.parent.mkdir(parents=True)
        self.e.archivo.write_text("# mis notas\nborde = 1\n# otra\nborde = 3\nesquinas = 4\n", encoding="utf-8")
        self.assertEqual(self.e.ejecutar("poner", "borde", "4")[0], 0)
        self.assertEqual(self.e.archivo.read_text(encoding="utf-8"),
                         "# mis notas\nborde = 4\n# otra\nesquinas = 4\n")

    def test_poner_el_predeterminado_no_lo_guarda(self):
        self.e.ejecutar("poner", "barra_altura", "30")
        self.assertEqual(self.e.ejecutar("poner", "barra_altura", "26")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertFalse(ajustes["barra_altura"]["propio"])
        self.assertNotIn("barra_altura", self.e.archivo.read_text(encoding="utf-8"))

    def test_restablecer(self):
        self.e.ejecutar("poner", "borde", "1", "esquinas", "4", "acento", "ambar")
        self.assertEqual(self.e.ejecutar("restablecer", "borde")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertEqual(ajustes["borde"]["valor"], "2")
        self.assertFalse(ajustes["borde"]["propio"])
        self.assertEqual(ajustes["esquinas"]["valor"], "4")
        self.assertEqual(self.e.ejecutar("restablecer", "--todo")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertFalse(any(a["propio"] for a in ajustes.values()))
        self.assertIn("#54e58a", self.e.generado("waybar.css"))
        self.assertTrue(self.e.archivo.read_text(encoding="utf-8").startswith("#"), "la cabecera se conserva")
        self.assertEqual(self.e.ejecutar("restablecer", "inventado")[0], 1)

    def test_edicion_a_mano_invalida_se_ignora(self):
        self.e.archivo.parent.mkdir(parents=True)
        self.e.archivo.write_text("borde = muchos\nesquinas = 3\nbasura sin igual\nclave_rara = 1\n", encoding="utf-8")
        rc, _, err = self.e.ejecutar("aplicar")
        self.assertEqual(rc, 0)
        self.assertIn("borde", err)
        self.assertIn("clave_rara", err)
        ajustes, d = self.e.ver()
        self.assertEqual(ajustes["borde"]["valor"], "2")
        self.assertEqual(ajustes["esquinas"]["valor"], "3")
        self.assertEqual(len(d["avisos"]), 2)

    def test_fondo_y_barra_abajo(self):
        propio = self.e.casa / "mi fondo.jpg"
        propio.write_bytes(b"jpg")
        self.assertEqual(self.e.ejecutar("poner", "fondo", str(propio), "barra_posicion", "abajo")[0], 0)
        self.assertEqual(pathlib.Path(self.e.generado("fondo").strip()), propio.resolve())
        self.assertEqual(json.loads(self.e.generado("waybar.json"))["position"], "bottom")
        self.assertEqual(self.e.ejecutar("poner", "fondo", str(self.e.casa / "texto.txt"))[0], 1)

    def test_generar_es_idempotente(self):
        self.assertEqual(self.e.ejecutar("generar")[0], 0)
        css = self.e.config / "jaime0/generado/waybar.css"
        os.utime(css, (1, 1))
        self.assertEqual(self.e.ejecutar("generar")[0], 0)
        self.assertEqual(css.stat().st_mtime, 1, "no debe reescribir lo que no cambia")

    def test_cada_ajuste_tiene_predeterminado_valido(self):
        # El archivo real del repositorio: todas las claves del esquema, con valores validos.
        claves = {l.split("=")[0].strip() for l in PREDETERMINADOS.read_text(encoding="utf-8").splitlines()
                  if "=" in l and not l.lstrip().startswith("#") and not l.startswith("tema.")}
        ajustes, d = self.e.ver()
        self.assertEqual(claves, set(ajustes))
        self.assertEqual(d["avisos"], [])
        for a in ajustes.values():
            self.assertEqual(a["valor"], a["predeterminado"])

    def test_umbrales_predeterminados_y_limites(self):
        ajustes, _ = self.e.ver()
        esperado = {"umbral_temp_aviso": ("85", 60, 100), "umbral_temp_critico": ("95", 70, 105),
                    "umbral_disco_aviso": ("85", 50, 99), "umbral_disco_critico": ("95", 60, 100),
                    "umbral_bateria_aviso": ("15", 5, 50), "umbral_bateria_critico": ("5", 2, 30),
                    "historial_dias": ("90", 7, 365)}
        for clave, (valor, minimo, maximo) in esperado.items():
            a = ajustes[clave]
            self.assertEqual((a["valor"], a["tipo"], a["min"], a["max"], a["grupo"]),
                             (valor, "entero", minimo, maximo, "Control Center"), clave)
            self.assertEqual(self.e.ejecutar("poner", clave, str(minimo - 1))[0], 1, clave)
            self.assertEqual(self.e.ejecutar("poner", clave, str(maximo + 1))[0], 1, clave)

    def test_umbrales_validos_se_guardan(self):
        rc, _, err = self.e.ejecutar("poner", "umbral_temp_aviso", "80", "umbral_temp_critico", "90",
                                     "historial_dias", "30")
        self.assertEqual(rc, 0, err)
        ajustes, _ = self.e.ver()
        self.assertEqual(ajustes["umbral_temp_aviso"]["valor"], "80")
        self.assertEqual(ajustes["historial_dias"]["valor"], "30")
        self.assertTrue(ajustes["historial_dias"]["propio"])

    def test_validacion_cruzada_de_umbrales(self):
        casos = (("umbral_temp_aviso", "96"),                           # aviso >= critico (95)
                 ("umbral_temp_critico", "80"),                         # critico <= aviso (85)
                 ("umbral_temp_aviso", "90", "umbral_temp_critico", "90"),
                 ("umbral_disco_aviso", "95"), ("umbral_disco_critico", "85"),
                 ("umbral_bateria_critico", "15"),                      # critico >= aviso (15)
                 ("umbral_bateria_aviso", "5"))
        for args in casos:
            rc, _, err = self.e.ejecutar("poner", *args)
            self.assertEqual(rc, 1, args)
            self.assertIn("debe ser menor", err, args)
        self.assertFalse(self.e.archivo.exists(), "rechazado: no se guarda nada")
        # En la misma orden se comprueba el conjunto: subir los dos a la vez si vale.
        self.assertEqual(self.e.ejecutar("poner", "umbral_temp_aviso", "97", "umbral_temp_critico", "100")[0], 0)
        # En la bateria el critico es el mas bajo.
        self.assertEqual(self.e.ejecutar("poner", "umbral_bateria_aviso", "20", "umbral_bateria_critico", "10")[0], 0)

    def test_restablecer_no_deja_umbrales_incoherentes(self):
        self.assertEqual(self.e.ejecutar("poner", "umbral_temp_aviso", "98", "umbral_temp_critico", "100")[0], 0)
        rc, _, err = self.e.ejecutar("restablecer", "umbral_temp_critico")    # 95 < 98
        self.assertEqual(rc, 1)
        self.assertIn("debe ser menor", err)
        self.assertEqual(self.e.ejecutar("restablecer", "--todo")[0], 0)

    def test_orden_desconocida(self):
        self.assertEqual(self.e.ejecutar("inventada")[0], 2)
        self.assertEqual(self.e.ejecutar("--help")[0], 0)

    # -- Fase 7: animaciones en tres niveles y ajustes del Control Center ----------
    def usuario(self, texto):
        self.e.archivo.parent.mkdir(parents=True, exist_ok=True)
        self.e.archivo.write_text(texto, encoding="utf-8")

    def test_animaciones_tres_niveles_en_el_esquema(self):
        a = self.e.ver()[0]["animaciones"]
        self.assertEqual((a["tipo"], a["opciones"], a["grupo"], a["valor"], a["predeterminado"]),
                         ("opcion", ["no", "sutil", "suave"], "Efectos", "sutil", "sutil"))
        self.assertEqual(a["etiqueta"], "Animaciones (no, sutil, suave)")

    def test_animaciones_migra_si_y_no_antiguos_del_usuario_sin_reescribir(self):
        for antiguo, nuevo in (("si", "sutil"), ("sí", "sutil"), ("yes", "sutil"), ("1", "sutil"),
                               ("on", "sutil"), ("true", "sutil"), ("s", "sutil"),
                               ("no", "no"), ("n", "no"), ("off", "no"), ("0", "no"), ("false", "no")):
            texto = f"# mio\nanimaciones = {antiguo}\n"
            self.usuario(texto)
            a = self.e.ver()[0]["animaciones"]
            self.assertEqual(a["valor"], nuevo, antiguo)
            self.assertEqual(self.e.archivo.read_text(encoding="utf-8"), texto, "no se reescribe")

    def test_animaciones_migra_si_y_no_antiguos_de_los_predeterminados(self):
        destino = self.e.raiz / "usr/share/jaime0/ajustes.predeterminados"
        base = destino.read_text(encoding="utf-8")
        for antiguo, nuevo in (("si", "sutil"), ("no", "no")):
            destino.write_text(base.replace("animaciones = sutil", f"animaciones = {antiguo}"), encoding="utf-8")
            a = self.e.ver()[0]["animaciones"]
            self.assertEqual((a["valor"], a["predeterminado"]), (nuevo, nuevo))

    def test_poner_animaciones_si_guarda_sutil_y_valida(self):
        self.assertEqual(self.e.ejecutar("poner", "animaciones", "suave")[0], 0)
        self.assertEqual(self.e.ver()[0]["animaciones"]["valor"], "suave")
        rc, out, _ = self.e.ejecutar("poner", "animaciones", "si")
        self.assertEqual(rc, 0)
        self.assertIn("animaciones = sutil", out)
        self.assertNotIn("animaciones", self.e.archivo.read_text(encoding="utf-8"), "sutil = predeterminado")
        self.assertEqual(self.e.ejecutar("poner", "animaciones", "no")[0], 0)
        self.assertIn("animaciones = no", self.e.archivo.read_text(encoding="utf-8"))
        antes = self.e.archivo.read_text(encoding="utf-8")
        for malo in ("mucho", "", "2", "sutiles"):
            self.assertEqual(self.e.ejecutar("poner", "animaciones", malo)[0], 1, malo)
        self.assertEqual(self.e.archivo.read_text(encoding="utf-8"), antes)

    def test_animaciones_invalida_en_el_archivo_del_usuario_se_ignora(self):
        self.usuario("animaciones = mucho\n")
        ajustes, d = self.e.ver()
        self.assertEqual(ajustes["animaciones"]["valor"], "sutil")
        self.assertTrue(any("animaciones" in a for a in d["avisos"]))

    def test_ajustes_del_control_center_en_el_esquema(self):
        ajustes, _ = self.e.ver()
        esperado = {"cc_intervalo": (["5", "10", "30"], "10"), "cc_intervalo_rapido": (["1", "2", "5"], "2"),
                    "cc_notificar": (["todas", "criticas", "ninguna"], "criticas")}
        for clave, (opciones, valor) in esperado.items():
            a = ajustes[clave]
            self.assertEqual((a["tipo"], a["opciones"], a["grupo"], a["valor"]),
                             ("opcion", opciones, "Control Center", valor), clave)
        a = ajustes["control_atajo"]
        self.assertEqual((a["tipo"], a["grupo"], a["valor"], a["etiqueta"]),
                         ("atajo", "Control Center", "SUPER+I", "Atajo del Control Center"))
        self.assertEqual(ajustes["cc_intervalo"]["etiqueta"], "Frecuencia de medición en segundo plano (s)")

    def test_opciones_del_control_center(self):
        for clave, valor in (("cc_intervalo", "30"), ("cc_intervalo_rapido", "5"), ("cc_notificar", "ninguna")):
            self.assertEqual(self.e.ejecutar("poner", clave, valor)[0], 0, clave)
            self.assertEqual(self.e.ver()[0][clave]["valor"], valor)
        for clave, valor in (("cc_intervalo", "7"), ("cc_intervalo", "0"), ("cc_intervalo_rapido", "10"),
                             ("cc_notificar", "siempre")):
            self.assertEqual(self.e.ejecutar("poner", clave, valor)[0], 1, (clave, valor))

    def test_atajos_validos_se_normalizan(self):
        for escrito, normal in (("SUPER+I", "SUPER+I"), ("super + i", "SUPER+I"), ("ctrl+alt+f5", "CTRL+ALT+F5"),
                                ("Super+Shift+7", "SUPER+SHIFT+7"), ("alt+escape", "ALT+Escape"),
                                ("super+SPACE", "SUPER+space"), ("ctrl+backspace", "CTRL+BackSpace"),
                                ("super+prior", "SUPER+Prior"), ("shift+f12", "SHIFT+F12")):
            self.assertEqual(self.e.ejecutar("poner", "control_atajo", escrito)[0], 0, escrito)
            self.assertEqual(self.e.ver()[0]["control_atajo"]["valor"], normal, escrito)
        self.assertEqual(json.loads(self.e.generado("control.json"))["atajo"], "SHIFT+F12")

    def test_atajos_invalidos_se_rechazan_con_mensaje_claro(self):
        self.e.ejecutar("poner", "control_atajo", "ALT+X")
        antes = self.e.archivo.read_text(encoding="utf-8")
        for malo in ("I", "SUPER", "SUPER+", "+I", "SUPER++I", "WIN+I", "SUPER+AB", "SUPER+F13", "SUPER+F0",
                     "SUPER+Intro", "SUPER+I+SHIFT", "SUPER+ñ", "SUPER+-", "", "SUPER I"):
            rc, _, err = self.e.ejecutar("poner", "control_atajo", malo)
            self.assertEqual(rc, 1, malo)
            self.assertIn("control_atajo: escribe modificadores y una tecla", err, malo)
        rc, _, err = self.e.ejecutar("poner", "control_atajo", "SUPER+SUPER+I")
        self.assertEqual(rc, 1)
        self.assertIn("modificador repetido", err)
        self.assertEqual(self.e.archivo.read_text(encoding="utf-8"), antes)

    def test_atajo_invalido_en_el_archivo_usa_el_predeterminado(self):
        self.usuario("control_atajo = I\n")
        ajustes, d = self.e.ver()
        self.assertEqual(ajustes["control_atajo"]["valor"], "SUPER+I")
        self.assertTrue(any("control_atajo" in a for a in d["avisos"]))

    def test_generar_animaciones_en_widgets_swaync_y_control(self):
        self.e.ejecutar("generar")
        self.assertEqual(json.loads(self.e.generado("widgets.json"))["animaciones"], "sutil")
        css = self.e.generado("swaync.css")
        self.assertIn("@define-color acento #54e58a;", css)
        self.assertNotIn("transition:", css)
        self.assertNotIn("transition-duration", css)
        self.assertIn("Animaciones: sutil", css)
        self.assertEqual(json.loads(self.e.generado("control.json")),
                         {"atajo": "SUPER+I", "animaciones": "sutil", "intervalo": 10,
                          "intervalo_rapido": 2, "notificar": "criticas"})
        self.assertEqual(self.e.ejecutar("poner", "animaciones", "no")[0], 0)
        css = self.e.generado("swaync.css")
        self.assertIn("* { transition: none; animation: none; }", css)
        self.assertTrue(css.index("@define-color acento") < css.index("transition: none"))
        self.assertEqual(json.loads(self.e.generado("widgets.json"))["animaciones"], "no")
        self.assertEqual(json.loads(self.e.generado("control.json"))["animaciones"], "no")
        self.assertEqual(self.e.ejecutar("poner", "animaciones", "suave")[0], 0)
        css = self.e.generado("swaync.css")
        self.assertIn(".notification-row, .notification, .control-center { transition-duration: 280ms; }", css)
        self.assertNotIn("transition: none", css)
        self.assertEqual(json.loads(self.e.generado("widgets.json"))["animaciones"], "suave")

    def test_generar_control_json_con_los_ajustes_del_usuario(self):
        self.assertEqual(self.e.ejecutar("poner", "control_atajo", "ctrl+alt+c", "cc_intervalo", "30",
                                         "cc_intervalo_rapido", "1", "cc_notificar", "todas")[0], 0)
        self.assertEqual(json.loads(self.e.generado("control.json")),
                         {"atajo": "CTRL+ALT+C", "animaciones": "sutil", "intervalo": 30,
                          "intervalo_rapido": 1, "notificar": "todas"})

    def test_animaciones_antiguas_tambien_generan_bien(self):
        self.usuario("animaciones = no\n")
        self.e.ejecutar("generar")
        self.assertEqual(json.loads(self.e.generado("control.json"))["animaciones"], "no")
        self.assertIn("transition: none", self.e.generado("swaync.css"))


if __name__ == "__main__":
    unittest.main()
