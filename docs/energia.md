# Energía (POWER)

La sección **POWER** del Control Center (tecla `0`) enseña cómo gasta energía el equipo y reúne lo que se puede ajustar sin ser root. Los datos los da `jaime0-servicio` (orden `energia`); la sección no cambia nada por su cuenta.

## Qué muestra

| Bloque | Contenido |
|---|---|
| P0 | Nivel, estado de carga, cargador, autonomía o tiempo hasta llena, y el perfil activo con su perfil de energía |
| P1 · BATTERY | Nivel, capacidad de diseño y actual (en Wh o mAh, según el firmware), salud, ciclos, consumo, velocidad de descarga, autonomía, tensión, límite de carga, modelo y temperaturas |
| P2 · GRAPHICS | Cada gráfica (integrada, dedicada o virtual), su controlador y si está despierta o dormida; con NVIDIA, el modo PRIME, el módulo, su consumo y qué programas la usan. Y la CPU: controlador, preferencia de energía (EPP), turbo y perfil de plataforma |
| P3 · ENERGY SETTINGS | Perfil de energía, tiempos de inactividad, suspensión y tapa, y las reglas de AUTOMATION que reaccionan a la energía |
| P4 · POWER HISTORY | Gráficas de batería (con el tiempo conectado al cargador), consumo y temperaturas en 1 h, 24 h o todo el histórico |
| P5 · BY ENERGY PROFILE | Horas con cargador en las últimas 24 h y, por perfil de energía, consumo medio y descarga en batería |

Cada dato lleva su origen:

- **MEDIDO**: lo da el hardware (sysfs, nvidia-smi).
- **CALCULADO**: sale de datos medidos (salud = capacidad actual / diseño; consumo = corriente × tensión si el firmware no da la potencia).
- **ESTIMADO**: supone que el consumo sigue igual (autonomía, tiempo hasta llena, %/h).
- **N/D**: el equipo no lo da. Se dice por qué cuando se sabe (sin sensor, el firmware no lo expone, faltan 10 min en batería…).

Algunos firmwares dan 0 ciclos porque no los cuentan: se muestra el 0 con esa nota.

## Gráficas y NVIDIA

ZYRON usa **PRIME render offload**: el escritorio va en la gráfica integrada y la NVIDIA duerme hasta que abres algo con `prime-run PROGRAMA`. POWER:

- Nunca despierta la NVIDIA: con ella dormida no ejecuta `nvidia-smi` (su consumo sale «sin medir»).
- Lista los programas que tienen abierta `/dev/nvidiaN`: mientras sigan abiertos la gráfica no puede dormir. Sin root solo se ven los tuyos, y lo dice.
- No apaga, no cambia el modo PRIME ni toca la configuración gráfica: eso podría dejarte sin escritorio. Para el estado del módulo y Secure Boot está `jaime0-nvidia`; los problemas los explica DIAGNOSTICS.

## Quién manda en cada ajuste

Cada ajuste tiene un único dueño, para que POWER, PROFILES y las reglas no se peleen:

| Ajuste | Dueño | Desde POWER |
|---|---|---|
| Perfil de energía (power-profiles-daemon) | El perfil de ZYRON activo (PROFILES) | Botones BALANCED, PERFORMANCE, POWER SAVER y CUSTOM: aplican ese perfil de ZYRON |
| CPU (EPP, turbo, perfil de plataforma) | power-profiles-daemon, según el perfil de energía | Solo se muestra |
| Bloquear, apagar pantalla y suspender por inactividad | `jaime0-ajustes` (`inactividad_*`, `suspender_con_cargador`) | `−` y `+`, y SÍ/NO para suspender con cargador |
| Evitar el bloqueo un rato | El perfil MULTIMEDIA (o CUSTOM) con un inhibidor | Se avisa cuando está activo |
| Qué pasa al conectar o desconectar el cargador, con batería baja o al suspender | Reglas de AUTOMATION | Se listan; se crean en AUTOMATION |
| Tapa y botón de encendido | logind (`/etc/systemd/logind.conf`, pide root) | Solo se muestra |
| Límite de carga de la batería | El firmware (`charge_control_end_threshold`, pide root) | Solo se muestra, si existe |

Las reglas solo pueden cambiar de **perfil**, nunca el perfil de energía directamente: así un cambio de energía siempre pasa por un perfil y se ve en PROFILES. Una regla que reacciona a un cambio de perfil no puede cambiar de perfil (no hay bucles).

Los eventos de energía para las reglas ya existen: batería baja, cargador conectado o desconectado, suspender o reanudar y cambio de perfil.

## Inactividad

Se aplican con hypridle. `jaime0-ajustes` escribe `~/.config/jaime0/generado/hypridle.conf` y lo reinicia al guardar:

```bash
jaime0-ajustes poner inactividad_bloqueo 10       # min hasta bloquear (0 = nunca, hasta 120)
jaime0-ajustes poner inactividad_pantalla 11      # min hasta apagar la pantalla (0-120)
jaime0-ajustes poner inactividad_suspender 30     # min hasta suspender (0-240)
jaime0-ajustes poner suspender_con_cargador no    # con el cargador conectado no se suspende
```

Los valores de fábrica son los de siempre (10, 11 y 30 min). A los 5 min de inactividad se avisa siempre al motor de reglas (evento «inactivo»).

Si has editado tu `~/.config/hypr/hypridle.conf` (ya no es igual al de `/etc/skel`), manda el tuyo: `inactividad` lo usa y POWER avisa de que estos ajustes no se aplican. Para volver a los de ZYRON, borra o restaura ese archivo.

## Histórico

Sale del mismo histórico que HEALTH (`jaime0-servicio`): batería, consumo y temperaturas por minuto (48 h) y por cuarto de hora (los días de `historial_dias`), y desde esta versión también si el cargador estaba conectado. Nada se rellena: los huecos se ven como huecos.

La comparación por perfil de energía usa solo los minutos enteros en batería de las últimas 48 h con un perfil conocido (los cambios de perfil de energía se guardan con su valor). Un perfil necesita al menos 10 minutos para dar su consumo medio. Los datos de antes de esta versión no tienen el cargador, así que la comparación empieza a llenarse a partir de ahora.

## Limitaciones

- Lo probado en máquina virtual no tiene batería real, NVIDIA ni sensores: la batería de VirtualBox siempre está llena y con cargador. Consumo real, descarga, comparación por perfil, NVIDIA y suspensión hay que verlos en el portátil.
- La velocidad de descarga necesita 10 min seguidos sin cargador y que el nivel haya bajado al menos un punto.
- La temperatura de la NVIDIA solo existe con la gráfica despierta.
