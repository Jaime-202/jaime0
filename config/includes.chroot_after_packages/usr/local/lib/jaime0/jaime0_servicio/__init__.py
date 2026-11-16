# jaime0_servicio: el servicio del Control Center (jaime0-servicio) partido en modulos por
# responsabilidad, todos en el MISMO proceso. El programa /usr/local/bin/jaime0-servicio es solo
# el lanzador: pone /usr/local/lib/jaime0 en sys.path y llama a servicio.main().
#
# Orden (cada modulo solo importa de alguno de los anteriores; no hay ciclos):
#   base, medicion, historico, incidencias, sistema, perfiles, privacidad, estado, reglas,
#   actualizaciones, diagnostico, energia, hardware, api, servicio
# La cabecera de cada modulo dice de cuales depende exactamente.
#
# Cada modulo declara en __all__ todo lo que define (tambien los nombres con guion bajo que
# usan las pruebas): el lanzador lo reexporta con "from ... import *".
