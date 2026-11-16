# jaime0_servicio.api: protocolo del socket de control (procesar_linea, _orden_reglas): una linea
# JSON por peticion y una por respuesta. Todo el estado le llega en `ctx` (el Servicio). Depende de:
# base, privacidad y reglas (solo constantes de limites).

import functools
import json
import threading
import traceback

from .base import VERSION_DATOS, MAX_INCIDENCIAS, REGLAS_EN_CURSO, registrar
from .privacidad import MAX_HISTORIAL_PRIVACIDAD
from .reglas import MAX_EJECUCIONES

__all__ = [
    "procesar_linea", "_orden_reglas"
]


# ---------------------------------------------------------------------------
# API: una linea JSON por peticion, una linea JSON por respuesta
# ---------------------------------------------------------------------------

def procesar_linea(linea, ctx, responder=None):
    """Procesa una peticion y devuelve la respuesta como texto JSON (sin salto de linea).
    ctx ofrece rapido() -> (intervalo, hasta), estado_doc(), instante_doc(), serie(rango),
    incidencias(limite), eventos_lista(), perfiles (un MotorPerfiles) y, de privacidad,
    privacidad_doc(), ufw_reglas_doc() y priv_historial. Las ordenes lentas de privacidad
    ("privacidad", "ufw_reglas") se calculan en un hilo si hay `responder`: se devuelve None y
    responder(texto) se llama al terminar; sin `responder` se calculan en el acto."""
    try:
        peticion = json.loads(linea)
    except ValueError:
        return json.dumps({"ok": False, "error": "JSON mal formado"})
    if not isinstance(peticion, dict):
        return json.dumps({"ok": False, "error": "petición no válida"})
    try:
        orden = peticion.get("orden")
        if orden == "rapido":
            intervalo, hasta = ctx.rapido()
            return json.dumps({"ok": True, "intervalo": intervalo, "hasta": hasta})
        if orden in ("estado", "instante"):
            doc = ctx.estado_doc() if orden == "estado" else ctx.instante_doc()
            if doc is None:
                return json.dumps({"ok": False, "error": "sin datos todavía"})
            return json.dumps(doc, ensure_ascii=False)
        if orden == "serie":
            return json.dumps(ctx.serie(peticion.get("rango")), ensure_ascii=False)
        if orden == "incidencias":
            limite = peticion.get("limite", 50)
            if not isinstance(limite, int) or isinstance(limite, bool) or limite < 1:
                limite = 50
            return json.dumps({"ok": True, "v": VERSION_DATOS,
                               "incidencias": ctx.incidencias(min(limite, MAX_INCIDENCIAS))},
                              ensure_ascii=False)
        if orden == "eventos":
            return json.dumps({"ok": True, "v": VERSION_DATOS, "eventos": ctx.eventos_lista()},
                              ensure_ascii=False)
        if orden in ("perfiles", "perfil", "perfil_anterior", "personalizado"):
            # El motor de perfiles toca D-Bus y programas externos: con `responder` se usa en
            # el hilo de efectos y se contesta al terminar (el bucle no espera).
            if orden == "perfiles":
                calcular = ctx.perfiles.perfiles_doc
            elif orden == "personalizado":
                ajustes = peticion.get("ajustes")
                calcular = lambda: ctx.perfiles.guardar_personalizado(ajustes)
            else:
                origen = peticion.get("origen", "usuario")
                if origen not in ("usuario", "regla"):
                    return json.dumps({"ok": False, "error": "origen no válido"})
                if orden == "perfil_anterior":
                    calcular = lambda: ctx.perfiles.aplicar_anterior(origen)
                elif not isinstance(peticion.get("valor"), str):
                    return json.dumps({"ok": False, "error": "falta el perfil"})
                else:
                    valor = peticion["valor"]
                    calcular = lambda: ctx.perfiles.aplicar(valor, origen)
            efectos = getattr(ctx, "efectos", None)
            if responder is None or efectos is None or not efectos.activo():
                return json.dumps(calcular(), ensure_ascii=False)
            efectos.enviar(calcular, lambda doc: responder(json.dumps(doc, ensure_ascii=False)), "orden " + orden)
            return None
        if orden in ("privacidad", "ufw_reglas"):
            calcular = ctx.privacidad_doc if orden == "privacidad" else ctx.ufw_reglas_doc
            if responder is None:
                return json.dumps(calcular(), ensure_ascii=False)
            if orden == "ufw_reglas":
                # El cerrojo se toma aqui, antes del hilo (ver ufw_reglas_doc).
                if not ctx._reglas_en_curso.acquire(blocking=False):
                    return json.dumps({"ok": False, "error": REGLAS_EN_CURSO}, ensure_ascii=False)
                calcular = functools.partial(ctx.ufw_reglas_doc, reservado=True)

            def en_hilo():
                try:
                    texto = json.dumps(calcular(), ensure_ascii=False)
                except Exception:
                    registrar("error al atender una orden de privacidad:\n" + traceback.format_exc())
                    texto = json.dumps({"ok": False, "error": "error interno"})
                responder(texto)

            threading.Thread(target=en_hilo, daemon=True).start()
            return None
        if orden == "actualizaciones":
            # Sin red: jaime0-update estado --json (un subproceso corto) en el hilo de efectos.
            efectos = getattr(ctx, "efectos", None)
            if responder is None or efectos is None or not efectos.activo():
                return json.dumps(ctx.actualizaciones_doc(), ensure_ascii=False)
            efectos.enviar(ctx.actualizaciones_doc, lambda doc: responder(json.dumps(doc, ensure_ascii=False)),
                           "orden actualizaciones")
            return None
        if orden == "actualizaciones_comprobar":
            # Con red (manifiesto firmado y apt): en su propio hilo, una a la vez; contesta al acabar.
            if responder is None:
                return json.dumps({"ok": False, "error": "esta orden contesta al terminar: hace falta el socket"})
            if not ctx.comprobador.comprobar(lambda doc: ctx.al_bucle(responder, json.dumps(doc, ensure_ascii=False))):
                return json.dumps({"ok": False, "error": "ya hay una comprobación en marcha"})
            return None
        if orden == "diagnostico":
            return json.dumps(ctx.diagnosticador.documento(), ensure_ascii=False)
        if orden == "diagnostico_ejecutar":
            # Unos segundos de comprobaciones: en su propio hilo, uno a la vez; contesta al acabar.
            if responder is None:
                return json.dumps({"ok": False, "error": "esta orden contesta al terminar: hace falta el socket"})
            if not ctx.diagnosticador.ejecutar_diagnostico(
                    lambda doc: ctx.al_bucle(responder, json.dumps(doc, ensure_ascii=False))):
                return json.dumps({"ok": False, "error": "ya hay un diagnóstico en marcha"})
            return None
        if orden == "diagnostico_historial":
            efectos = getattr(ctx, "efectos", None)
            if responder is None or efectos is None or not efectos.activo():
                return json.dumps(ctx.diagnosticador.historial(), ensure_ascii=False)
            efectos.enviar(ctx.diagnosticador.historial, lambda doc: responder(json.dumps(doc, ensure_ascii=False)),
                           "orden diagnostico_historial")
            return None
        if orden == "privacidad_historial":
            limite = peticion.get("limite", 50)
            if not isinstance(limite, int) or isinstance(limite, bool) or limite < 1:
                limite = 50
            return json.dumps({"ok": True, "v": VERSION_DATOS,
                               "historial": ctx.priv_historial.ultimos(min(limite, MAX_HISTORIAL_PRIVACIDAD))},
                              ensure_ascii=False)
        if isinstance(orden, str) and (orden.startswith("regla") or orden == "evento"):
            return _orden_reglas(orden, peticion, ctx, responder)
        return json.dumps({"ok": False, "error": "orden desconocida"})
    except Exception:
        registrar("error al atender una orden:\n" + traceback.format_exc())
        return json.dumps({"ok": False, "error": "error interno"})


def _orden_reglas(orden, peticion, ctx, responder):
    """Ordenes del motor de reglas (reglas, regla_guardar, regla_activar, regla_borrar,
    regla_probar, reglas_historial, reglas_importar y evento). Respuesta en JSON de una linea;
    regla_probar espera a que acaben las acciones (hasta minutos): con `responder` se contesta
    despues y se devuelve None."""
    texto = lambda doc: json.dumps(doc, ensure_ascii=False)
    motor = ctx.reglas
    if orden in ("reglas", "regla_guardar", "reglas_importar"):
        hacer = {"reglas": motor.listar,
                 "regla_guardar": lambda: motor.guardar(peticion.get("regla")),
                 "reglas_importar": lambda: motor.importar(peticion.get("reglas"))}[orden]
        efectos = getattr(ctx, "efectos", None)
        if responder is None or efectos is None or not efectos.activo():
            return texto(hacer())
        # Lo lento (aplicaciones instaladas y eventos disponibles por D-Bus) se refresca en el
        # hilo de efectos; la operacion se hace despues en el bucle, donde vive el estado de
        # las reglas, ya con esos datos recordados.
        efectos.enviar(lambda: (motor.apps(), motor.disponibilidad()),
                       lambda _: responder(texto(hacer())), "orden " + orden)
        return None
    if orden in ("regla_activar", "regla_borrar", "regla_probar"):
        rid = peticion.get("id")
        if not isinstance(rid, str):
            return texto({"ok": False, "error": "falta el id de la regla"})
        if orden == "regla_borrar":
            return texto(motor.borrar(rid))
        if orden == "regla_activar":
            if not isinstance(peticion.get("activa"), bool):
                return texto({"ok": False, "error": "«activa» debe ser verdadero o falso"})
            return texto(motor.activar(rid, peticion["activa"]))
        caja = {"sincrono": True, "respuesta": None}

        def al_acabar(doc):
            if caja["sincrono"]:
                caja["respuesta"] = doc
            elif responder is not None:
                responder(texto(doc))

        motor.probar(rid, al_acabar)
        caja["sincrono"] = False
        if caja["respuesta"] is not None:
            return texto(caja["respuesta"])
        if responder is None:
            return texto({"ok": False, "error": "la prueba no ha terminado"})
        return None
    if orden == "reglas_historial":
        limite = peticion.get("limite", 50)
        if not isinstance(limite, int) or isinstance(limite, bool) or limite < 1:
            limite = 50
        return texto(motor.historial_doc(min(limite, MAX_EJECUCIONES)))
    if orden == "evento":
        nombre = peticion.get("nombre")
        if nombre not in ("inactivo", "activo"):
            return texto({"ok": False, "error": "evento no válido: solo «inactivo» y «activo»"})
        return texto({"ok": True, "disparadas": motor.evento("inactividad", {"estado": nombre})})
    return texto({"ok": False, "error": "orden desconocida"})
