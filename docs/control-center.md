# Jaime0 Control Center — plan y arquitectura

Estado: **Fases 1 a 6 terminadas.** Funcionan el servicio, `jaime0-salud`, `jaime0-perfil`, `jaime0-privacidad`, `jaime0-reglas`, la ventana con SYSTEM OVERVIEW, PERFORMANCE, PROFILES, AUTOMATION, PRIVACY & SECURITY y HEALTH (gráficas, histórico, incidencias y DIAGNOSTIC MODE), el atajo y el indicador de la barra. SETTINGS dice en qué fase llegará y no muestra datos inventados.

## AUTOMATION · Jaime0 Rules (fase 6)

Reglas **CUANDO → SI → HACER**. Las ejecuta el servicio aunque el Control Center esté cerrado.

| | Disponibles |
|---|---|
| **CUANDO** (un evento) | Batería baja (umbral, se rearma 5 puntos por encima), cargador conectado/desconectado, dispositivo Bluetooth (de audio o cualquiera, por nombre), monitor conectado/desconectado, aplicación abierta (primera ventana) o cerrada (última), hora del día y días, red conectada/desconectada (o una Wi-Fi concreta), suspender/reanudar, inactividad de 5 min y vuelta, cambio del estado del sistema, servicio fallido, cambio de perfil hecho por ti |
| **SI** (opcional) | Perfil activo, cargador conectado o no, batería por debajo o por encima de un valor, entre dos horas (también de noche, pasando la medianoche), días de la semana |
| **HACER** (1 a 5, lista cerrada) | Cambiar de perfil, modo noche, no molestar, notificar, abrir una aplicación instalada, volumen, silenciar, salida de audio por nombre (p. ej. los auriculares Bluetooth), mantenimiento seguro (borrar miniaturas de más de 30 días; comprobar actualizaciones) y scripts autorizados |

**De dónde salen los eventos** (sin sondeo nuevo): batería y cargador, de las muestras que el servicio ya toma; Bluetooth (BlueZ), red (NetworkManager) y suspensión (logind), de señales de D-Bus; monitores y aplicaciones, del socket de eventos de Hyprland; la hora, de un temporizador al instante exacto; la inactividad, de hypridle (`jaime0-reglas evento inactivo|activo` a los 5 min). Un evento que el equipo no puede detectar sale apagado en el editor, con el motivo.

**Seguridad.** Ninguna acción necesita root. Los scripts solo se ejecutan si están en `~/.config/jaime0/scripts-autorizados/`, son tuyos, ejecutables y nadie más puede modificarlos (tampoco la carpeta); sin shell, sin argumentos y con 60 s como mucho. Las reglas importadas (`jaime0-reglas importar`) entran desactivadas y marcadas `REVISAR`.

**Sin bucles:** lo que hace una regla no dispara otras reglas; los disparadores son por flanco; 30 s de enfriamiento por regla (se registra como «omitida»); si una regla se ejecuta 5 veces en 5 min o hay más de 20 ejecuciones en un minuto, se desactiva sola y abre una incidencia; una regla «cambio de perfil → cambiar de perfil» se rechaza al guardarla.

**Ventana:** lista con interruptor, resumen CUANDO → SI → HACER y última ejecución (ok, fallo u omitida), botones PROBAR, EDITAR y BORRAR (pide confirmación), editor construido con el catálogo del servicio e historial de ejecuciones. **Terminal:** `jaime0-reglas lista|catalogo|historial|crear ARCHIVO|importar ARCHIVO|activar|desactivar|probar|borrar ID`.

### Resultados de la fase 6 (14-11-2026, misma VM)

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 525 correctas (149 nuevas del motor, validación, eventos, acciones, enfriamiento, topes, importación y cliente) |
| Reglas reales | Inactividad → POWER SAVER y notificación (correcto; el segundo disparo a los 3 s, «omitida» por enfriamiento); abrir kitty (evento real de Hyprland) → modo noche encendido; hora 01:03 → notificación a las 01:03:00 |
| Bucle | «Cambio de perfil → cambiar de perfil» rechazada al crearla, con el motivo |
| Ventana | Regla creada desde el editor (evento, acción y textos), PROBAR, desactivar y borrar con confirmación; historial con colores por resultado; 0 avisos de QML y 0 errores del servicio |
| No probado | Bluetooth, batería y cargador reales, red Wi-Fi y suspensión real, y la salida de audio a unos auriculares: necesitan el portátil |

Encontrado al probar: en el editor cada tecla reconstruía el formulario y el campo perdía el foco (solo se guardaba la primera letra); y las opciones largas se salían del editor (ahora pasan de línea).

## PRIVACY & SECURITY (fase 5)

Una sección más del Control Center, no una aplicación aparte. Muestra comprobaciones concretas, no una garantía: nunca dice que el equipo esté «totalmente protegido».

| Panel | Qué muestra | Cómo se obtiene (sin root salvo donde se indica) |
|---|---|---|
| PRIVACY STATUS | `SECURE` (UFW activo con entrante denegado), `WARNING` (UFW inactivo, entrante permitido o puertos abiertos a la red, con el motivo) o `UNAVAILABLE` (sin UFW) | Todo lo de abajo |
| FIREWALL · UFW | Activo o no, políticas por defecto y registro; **las reglas, solo si pulsas «VER REGLAS»**: aparece la ventana de contraseña y un ayudante de solo lectura ejecuta `ufw status verbose` | `/etc/ufw/ufw.conf`, `/etc/default/ufw`, systemd; reglas con `pkexec /usr/local/libexec/jaime0-ufw-estado` (acción de polkit `es.jaime0.ufw-estado`, contraseña de administrador recordada unos minutos) |
| OPEN PORTS | Programas que escuchan conexiones; ◆ = abierto a la red (no solo al propio equipo) | `ss -tulnp` |
| DEVICES IN USE | Micrófono, cámara y pantalla compartida, con la aplicación; el punto parpadea mientras se usan | PipeWire (`pw-dump`) y `/proc/*/fd` → `/dev/video*` |
| ACTIVE CONNECTIONS | Conexiones establecidas agrupadas por programa, con sus destinos (sin resolver nombres: no genera tráfico) | `ss -tunp` (de otros usuarios no se ve el programa) |
| APPS · PRIVILEGES · SERVICES | Flatpak (`UNAVAILABLE`: no está en Jaime0, así que no hay permisos por aplicación), tus grupos con privilegios y qué permiten, y servicios con efecto en la privacidad (SSH, avahi, CUPS, Bluetooth, NetworkManager) | `os.getgrouplist`, systemd |
| TELEMETRY · HISTORY | Jaime0 sin telemetría; popularity-contest; qué consulta debsecan; si el widget del tiempo conecta con Open-Meteo; Brave y sus opciones (P3A). Historial de cambios relevantes | `dpkg-query`, archivos de configuración |

El historial (`~/.local/state/jaime0/privacidad.jsonl`, 300 líneas como mucho) guarda cambios del cortafuegos, puertos que se abren o se cierran, el uso de micrófono, cámara o pantalla (nombre de la aplicación) y las consultas de reglas con autorización. **No guarda direcciones ni la salida de las reglas.** Cortafuegos y puertos se revisan cada minuto; los dispositivos, cada 10 s con la ventana abierta y cada minuto si no.

`jaime0-privacidad` (resumen por apartados, `--json`), `jaime0-privacidad reglas` (pide la contraseña) y `jaime0-privacidad historial -n N`.

### Resultados de la fase 5 (14-11-2026, misma VM)

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 376 correctas (90 nuevas: UFW, `ss`, `pw-dump`, cámara, flatpak, grupos, telemetría, estado, historial, API, cliente y ayudante) |
| Estado real | WARNING por el puerto 22 (SSH) abierto a la red: es el servidor SSH instalado en la VM para manejarla en las pruebas, y el motivo lo dice |
| Micrófono | Una grabación con `pw-record` se detectó mientras duraba y quedó en el historial al empezar y al terminar |
| Reglas con autorización | El botón abrió la ventana de contraseña de polkit con el mensaje de Jaime0; con la contraseña se vieron las reglas reales (22/tcp ALLOW IN, IPv4 e IPv6) y la consulta quedó en el historial |
| Ventana | Seis paneles con datos reales, 0 avisos de QML |
| No probado | Cámara real y pantalla compartida real (la VM no tiene cámara ni se compartió pantalla), y Flatpak instalado (no está en Jaime0) |

Encontrado al probar: **faltaba el paquete `pkexec`** (solo estaban `polkitd` y el agente), sin el cual el botón de reglas no podía pedir la contraseña; está añadido a la lista de paquetes. También se corrigieron dos nombres de campo entre el servicio y la ventana, la fila central que aplastaba a la de abajo y un texto de grupos duplicado.

## PROFILES (fase 4)

| Perfil | Qué cambia |
|---|---|
| BALANCED | Nada: tu configuración tal cual (predeterminado) |
| PERFORMANCE | Energía en alto rendimiento (solo si el equipo lo ofrece) |
| POWER SAVER | Energía en ahorro, sin animaciones ni desenfoque |
| FOCUS | No molestar (las notificaciones se guardan en el centro) |
| MULTIMEDIA | No molestar y sin bloqueo ni apagado de pantalla |
| CUSTOM | Lo que elijas en el editor (`✎ EDITAR CUSTOM`) o con `jaime0-perfil personalizado clave=valor` |

**Cómo se aplica.** El servicio es el único que cambia el perfil; la ventana, `jaime0-perfil` y (en la fase 6) las reglas se lo piden. Cada perfil declara todo lo que gestiona y nada más, y se aplica sin reiniciar (unas décimas de segundo):

- **Energía:** con una *retención* de power-profiles-daemon (`HoldProfile`), nunca escribiendo tu preferencia; si el servicio se para, la retención se suelta sola.
- **Animaciones y desenfoque:** una capa de sesión en `$XDG_RUNTIME_DIR/jaime0/perfil.ajustes` que `hyprland.lua` lee encima de tus ajustes (solo esas dos claves) seguida de `hyprctl reload`. Tus ajustes de `~/.config/jaime0/ajustes` no se tocan.
- **No molestar:** swaync. **Sin bloqueo:** un inhibidor de logind (hypridle lo respeta). **Modo noche:** `modo-noche encender|apagar`.
- **Volver atrás:** antes de cambiar algo se guarda su valor real y, al dejar de gestionarlo, se restaura (si tenías el no molestar puesto a mano, sigue puesto al salir de FOCUS). `↶ VOLVER A …` o `jaime0-perfil anterior` aplica el perfil anterior.
- **Persistencia:** el perfil elegido se guarda en `~/.local/state/jaime0/perfil.json` y se vuelve a aplicar al arrancar el servicio.
- **Lo que no se toca nunca:** governors, EPP, sysctl, servicios del sistema, brillo ni radios.

Un perfil que el equipo no admite sale como `UNAVAILABLE` con el motivo (en la VM, PERFORMANCE: VirtualBox no ofrece el perfil de energía de alto rendimiento) y no se puede aplicar.

`jaime0-perfil` (lista), `jaime0-perfil poner FOCUS`, `jaime0-perfil anterior`, `jaime0-perfil personalizado energia=power-saver no_molestar=si`. Claves de CUSTOM: `energia` (balanced, performance, power-saver), `animaciones`, `desenfoque`, `no_molestar`, `modo_noche` (si, no, base = como esté) e `inhibir_inactividad` (si, no).

**PERFORMANCE** (sección): cada núcleo con su uso y frecuencia, la carga de los últimos 5 minutos, RAM, swap y presión de memoria, el perfil y el estado real de la energía (y si el rendimiento está degradado) y los procesos que más consumen.

### Resultados de la fase 4 (14/15-11-2026, misma VM)

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 286 correctas (94 nuevas de perfiles y de `jaime0-perfil`) |
| Efecto real de cada perfil | POWER SAVER: power-profiles-daemon en *power-saver* por retención y capa con animaciones y desenfoque desactivados; FOCUS: no molestar; MULTIMEDIA: no molestar más inhibidor de logind; BALANCED: todo liberado. Cada cambio, unos 0,1 s |
| Vuelta atrás | El no molestar puesto a mano sigue puesto al pasar por FOCUS y volver; `anterior` restaura el perfil previo |
| CUSTOM | Modo noche, ahorro y sin animaciones aplicados y deshechos al volver a BALANCED; valores no válidos rechazados con un mensaje claro; editado y guardado desde la ventana |
| Persistencia | Tras reiniciar el servicio se reaplica el perfil guardado |
| Ventana | PROFILES y PERFORMANCE con datos reales; aplicar con un clic; 0 avisos de QML; Hyprland acepta la configuración con la capa (`--verify-config`) |
| No probado | PERFORMANCE con energía real, el efecto visual de animaciones y desenfoque (en una VM Jaime0 los apaga siempre) y que hypridle respete el inhibidor durante 10 minutos reales: necesitan el portátil o una espera larga |

Arreglos encontrados al probar: el enlace para editar CUSTOM estaba dentro de su tarjeta y el clic también aplicaba el perfil (ahora es un botón aparte); el editor no cargaba lo guardado; el botón de volver se salía de la cabecera con textos largos; la descripción de CUSTOM decía «sin definir» aunque estuviera definido; y la gráfica de PERFORMANCE no avisaba mientras recogía el primer minuto de datos.

## HEALTH (fase 3)

| Zona | Qué muestra |
|---|---|
| SYSTEM HEALTH | Estado global, CPU, RAM, temperatura y alertas activas; selector de intervalo (`REAL TIME`, `LAST 5 MIN`, `LAST HOUR`, `LAST 24 HOURS`, `HISTORY`: los que aún no tienen datos suficientes salen apagados) y `DIAGNOSTIC MODE` |
| LIVE MONITORING | Las dos gráficas grandes, CPU y RAM: valor actual, media y pico del intervalo, diferencia con la media, línea de referencia y marcas de eventos (▼) |
| HARDWARE DIAGNOSTICS | Temperaturas (CPU y GPU, con los umbrales de aviso y crítico), almacenamiento (ocupación, lectura/escritura y SMART) y batería (nivel, consumo, autonomía marcada como *estimada* y salud) |
| SYSTEM EVENTS | Incidencias: fecha, gravedad, componente, descripción y recomendación; también la recuperación |
| DIAGNOSTIC MODE | Sustituye la zona de hardware por el detalle: cada núcleo con su uso y frecuencia, todos los sensores, memoria desglosada, procesos y eventos del intervalo |

Las gráficas solo dibujan datos medidos. Al pasar el cursor muestran el valor exacto con fecha y hora (y el mínimo y máximo en los intervalos agregados); arrastrar amplía un tramo y el doble clic vuelve a la vista completa. Los tramos sin datos (suspensión, servicio parado) se rayan y se rotulan `SIN DATOS`, nunca se rellenan.

**Umbrales** (en `jaime0-ajustes`, grupo *Control Center*, también en la aplicación de ajustes): `umbral_temp_aviso`/`critico` (85/95 °C), `umbral_disco_aviso`/`critico` (85/95 %), `umbral_bateria_aviso`/`critico` (15/5 %) e `historial_dias` (90). El servicio los aplica al momento y rechaza combinaciones incoherentes (un aviso por encima del crítico).

**Incidencias:** una condición debe mantenerse 3 muestras para abrirse y otras 3 para cerrarse (evita falsas alarmas por un pico suelto); las de systemd y SMART vienen del refresco de cada minuto y se abren a la primera. Nada se repara solo: cada incidencia trae su diagnóstico y una recomendación. Un reinicio del servicio recupera las abiertas sin duplicarlas. `jaime0-salud incidencias` las lista en la terminal.

**Límite conocido:** el anillo de la última hora vive en memoria; si el servicio se reinicia, `LAST 5 MIN` y `LAST HOUR` empiezan de nuevo (lo anterior sigue en `LAST 24 HOURS` y `HISTORY`).

### Resultados de la fase 3 (14-11-2026, misma VM)

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 194 correctas (89 nuevas: histórico, huecos, reducción, disponibilidad, incidencias con histéresis, eventos, SMART, umbrales y `jaime0-salud`) |
| D-Bus real | SMART por udisks2 sin root (los discos de VirtualBox no dan SMART: `N/D`, como corresponde); vigilancia del archivo de ajustes; el perfil y las unidades fallidas siguen funcionando |
| Series | `5m` se ofrece al tener un minuto de datos, con las 11 métricas; antes, «sin datos suficientes» |
| Incidencias | Una unidad que falla a propósito abrió WARNING (systemd) y, al retirarla, quedó «Recuperado» (NORMAL) |
| Huecos | Paradas reales de 37 s y 46 s del servicio quedaron registradas con su duración exacta |
| Ventana | Lectura bajo el cursor, gráficas compactas en los paneles pequeños, DIAGNOSTIC MODE, umbrales en la aplicación de ajustes; 0 avisos de QML |
| Consumo | Con HEALTH abierto: 6,7 % de un núcleo y 152 MiB (VM, dibujo por software) |
| No probado | Temperaturas, frecuencias, batería, SMART de un NVMe real, NVIDIA y la suspensión real: necesitan el portátil |

Arreglos encontrados al probar: el lector de CD de la VM salía como disco en STORAGE (ahora se descartan las unidades ópticas); un reinicio del servicio duplicaba una incidencia ya abierta (ahora la recupera); y una parada a mitad de minuto no se registraba como hueco porque se contaba hasta el final del minuto (ahora se guarda la hora de la última muestra real).

## Uso (fase 2)

| Qué | Cómo |
|---|---|
| Abrir o cerrar el Control Center | `SUPER + I`, clic en el indicador de Jaime0 de la barra (junto a la batería) o `jaime0-control` |
| Dentro | `1`–`7` cambian de sección, `Esc` cierra |
| Estado en la terminal | `jaime0-salud` (`--json` para la salida completa) |
| El servicio | `systemctl --user status jaime0-servicio`; lo arranca la sesión de Hyprland |
| Cambiar el atajo | `atajos quitar "SUPER+I"` y `atajos añadir "TECLAS" "jaime0-control" "Control Center"` |

### Resultados de la fase 2 (14-11-2026, VM `jaime0-pruebas`, sistema instalado 0.3.0-beta.1 con los archivos nuevos copiados)

| Prueba | Resultado |
|---|---|
| Pruebas automáticas (`pruebas/`) | 105 correctas (31 nuevas del servicio y de `jaime0-salud`) |
| `validar-repo.sh` | Sin fallos salvo `luac`, que falta en la VM de compilación (GitHub Actions sí lo tiene) |
| Servicio | Arranca, publica `instante.json` y `estado.json`, lee el perfil (power-profiles-daemon) y el cortafuegos, para limpio (borra su socket) |
| API | `rapido` pasa el muestreo a 2 s y caduca sola; JSON roto y órdenes desconocidas se rechazan sin caerse |
| Estado global | Detectó un fallo real (`swaync.service` en *failed*), pasó a WARNING y volvió a ONLINE al corregirlo; los cambios quedan en la actividad |
| Ventana | Datos reales en SYSTEM OVERVIEW, 0 avisos de QML; abre y cierra con `SUPER + I`, con el clic en la barra y con `Esc`; al cerrar, el proceso termina y el servicio vuelve a 10 s |
| Consumo | Servicio: 41 MiB, 0,3 % de un núcleo en reposo y 1,8 % con la ventana abierta. Ventana: 130 MiB y 5,4 % de un núcleo (la VM dibuja por software) |
| No probado | Temperaturas, frecuencias, batería real y NVIDIA: la VM no los tiene (se ven como `N/D`) |

Arreglos encontrados al probar: `swaync` podía arrancar dos veces por D-Bus (el nombre `org.erikreider.swaync.cc` del paquete iba a la unidad de systemd) y la unidad quedaba *failed*; ahora ese nombre también lo arranca `notificaciones iniciar`. La barra de la cabecera, en bucle, gastaba un 22 % de CPU: ahora es una pasada cada 10 s.

## Qué hay hoy y qué se reutiliza

| Pieza existente | Uso en el Control Center |
|---|---|
| `jaime0-ajustes` (esquema único, `~/.config/jaime0/ajustes`, archivos generados) | Ajustes nuevos del grupo *Control Center* en el mismo esquema; los perfiles se superponen sin reescribirlo |
| Quickshell 0.3.2 (widgets y aplicación de ajustes, opcional) | Interfaz del Control Center, como configuración aparte |
| Widget *Sistema* (lee `/proc/stat` y `/proc/meminfo`) | Referencia; en el Control Center los datos los da el servicio |
| `jaime0-anclar vigilar` (socket2 de Hyprland) | Patrón para los eventos de ventanas y monitores |
| power-profiles-daemon, swaync, hypridle, hyprsunset, UFW, debsecan, `actualizaciones` | Lo que aplican los perfiles y lo que muestra PRIVACY & SECURITY |
| Módulo `power-profiles-daemon` de Waybar | Se sustituye por un indicador propio |

### Fuentes de datos comprobadas (sistema instalado 0.3.0-beta.1, VM)

| Dato | Fuente | Sin root | Nota |
|---|---|---|---|
| CPU, RAM, swap, presión | `/proc/stat`, `/proc/meminfo`, `/proc/pressure/*` | Sí | |
| Frecuencia por núcleo | `/sys/devices/system/cpu/cpu*/cpufreq` | Sí | No existe en la VM; sí en el portátil (intel_pstate) |
| Temperaturas | `/sys/class/hwmon` (coretemp, nvme, acpitz…) | Sí | La VM no tiene sensores; se probará en el portátil |
| Temperatura NVIDIA | `nvidia-smi` | Sí | **Solo si `power/runtime_status` = `active`**: leerla la despierta |
| Batería y cargador | UPower (D-Bus), con respaldo en `/sys/class/power_supply` | Sí | `upower` **no está instalado**: hay que añadirlo |
| Salud del disco | udisks2 2.11 (D-Bus, NVMe) | Sí | `smartctl` existe pero necesita root |
| Lectura/escritura de disco | `/proc/diskstats` | Sí | |
| Perfil de energía | power-profiles-daemon (D-Bus) | Sí | En la VM solo `balanced`/`power-saver` (driver *placeholder*) |
| Cortafuegos | `/etc/ufw/ufw.conf` y `systemctl is-active ufw` | Sí | Las reglas (`/etc/ufw/user.rules`, 0640) **necesitan root** |
| Conexiones | `ss -tunp` | Sí | Procesos solo del propio usuario |
| Micrófono/cámara/pantalla en uso | PipeWire (`pw-dump`) | Sí | |
| Red, Bluetooth, suspensión | NetworkManager, BlueZ, logind (D-Bus) | Sí | |
| Ventanas y monitores | socket2 de Hyprland | Sí | |
| Flatpak | — | — | **Retirado en la 0.3**: la sección lo mostrará como `UNAVAILABLE` |

`python3-gi` (Gio) está instalado: sirve para escuchar D-Bus desde Python sin dependencias nuevas.

## Arquitectura

```
                         ┌──────────────────────── sesión del usuario ─────────────────────────┐
  D-Bus (UPower, ppd,    │  jaime0-servicio  (Python + Gio, systemd --user, siempre activo)     │
  NM, BlueZ, logind,  ──►│   ├─ salud     muestreo 10 s (1–2 s si la interfaz lo pide), anillo │
  udisks2)               │   │            en RAM, agregados a disco, incidencias               │
  socket2 de Hyprland ──►│   ├─ perfiles  único dueño del perfil activo y de su vuelta atrás    │
  /proc, /sys        ──► │   ├─ reglas    CUANDO → SI → HACER por eventos, acciones en lista    │
                         │   │            blanca, historial                                    │
                         │   └─ API       socket Unix $XDG_RUNTIME_DIR/jaime0/control.sock      │
                         │                (JSON por líneas, solo el propio usuario)             │
                         │                                                                      │
                         │  $XDG_RUNTIME_DIR/jaime0/  instante.json · estado.json (tmpfs)       │
                         │  ~/.local/state/jaime0/    historial, incidencias, ejecuciones        │
                         └──────────────────────────────────────────────────────────────────────┘
        ▲ clientes                      ▲                                 ▲
  jaime0-control (Quickshell,     jaime0-perfil · jaime0-salud ·     Waybar: custom/jaime0
  ventana propia, solo mientras   jaime0-reglas · jaime0-privacidad  (por señal, sin sondeo)
  está abierta)                   (CLIs con --json)
```

### Decisiones

1. **Un único servicio, un único dueño del estado.** `jaime0-servicio` aplica los perfiles, mide y ejecuta las reglas. Las CLIs y la interfaz son clientes: piden por el socket y leen los archivos de estado. Si el servicio no corre, las CLIs de solo lectura funcionan solas y las que cambian algo lo dicen, en lugar de aplicar por su cuenta (evita carreras y dos fuentes de verdad).
2. **Separación por módulos dentro del servicio** (salud, perfiles, reglas, API), cada manejador aislado con `try/except`; `Restart=on-failure`; sin subprocesos en el bucle de muestreo. Atado a `graphical-session.target` para tener `HYPRLAND_INSTANCE_SIGNATURE`; reconecta al socket2 si Hyprland se reinicia.
3. **La interfaz no mide.** Lee `instante.json` (tmpfs, sin escrituras a disco) con `FileView` y pide al servicio subir a 1–2 s mientras está abierta. Al cerrarla, el proceso de Quickshell termina y el servicio vuelve a 10 s.
4. **Quickshell es opcional.** Sin él, el escritorio, el servicio, las reglas, los perfiles y las CLIs funcionan; solo falta la ventana. `jaime0-control` lo avisa.
5. **Sin root por defecto.** Lo único que lo necesita es leer las reglas de UFW: ayudante mínimo con una acción de polkit fija (solo esa lectura, sin argumentos libres), pedido al pulsar, con el agente `lxpolkit` de la sesión.
6. **Sin telemetría.** Nada sale del equipo; los datos viven en `$XDG_RUNTIME_DIR` y `~/.local/state/jaime0/` y se pueden borrar.

### Histórico

| Nivel | Resolución | Dónde | Duración | Sirve para |
|---|---|---|---|---|
| Instante | 1–2 s (interfaz abierta) / 10 s | RAM (anillo) + `instante.json` en tmpfs | 1 h | `REAL TIME`, `LAST 5 MIN`, `LAST HOUR` |
| Minuto | agregados de 60 s (mín/media/máx) | `~/.local/state/jaime0/salud/AAAA-MM-DD.jsonl` | 48 h | `LAST 24 HOURS` |
| Cuarto de hora | agregados de 15 min | `~/.local/state/jaime0/salud/historico.jsonl` | 90 días | `HISTORY` |

Se vuelca a disco cada 5 min, al suspender (`PrepareForSleep`) y al parar. Los huecos (suspensión, equipo apagado) se marcan y se dibujan como tales, nunca se rellenan. Un intervalo sin datos suficientes no se ofrece. Unos pocos MB en total.

### Perfiles

Un perfil es una **capa de sesión** sobre los ajustes: declara el estado completo de lo que gestiona (no cambios relativos), se aplica de forma idempotente y nunca reescribe `~/.config/jaime0/ajustes`; reiniciar la sesión vuelve a la base. Antes de aplicar se guarda una instantánea del estado real para **volver al anterior**. Se reaplica tras `configreloaded` de Hyprland.

| Se puede tocar (sin root) | No se toca |
|---|---|
| Perfil de power-profiles-daemon (que ya gestiona el EPP de intel_pstate; PERFORMANCE con `HoldProfile`, que se libera solo si el servicio muere) | Governor o EPP directos (chocan con ppd), `no_turbo`, sysctl, MSR/undervolt, ASPM, ventiladores |
| Animaciones, desenfoque y sombras de Hyprland en caliente | Gestión de energía de la NVIDIA |
| Brillo (logind), no molestar de swaync, inhibición de hypridle, modo noche | Instalar TLP u otros gestores |
| Radios con nmcli/bluetoothctl (solo si el perfil lo declara) | Servicios del sistema |

Cada perfil declara sus capacidades: lo que el equipo no admite (p. ej. `performance` en la VM) se muestra como no disponible, no se finge.

### Reglas: sin bucles

1. Todo cambio lleva origen (`usuario` o `regla`); los eventos causados por una regla no disparan reglas.
2. Disparadores por flanco con histéresis (salta al 20 %, se rearma al 25 %).
3. Enfriamiento por regla (30 s) y tope global; si se supera, la regla se desactiva y queda una incidencia.
4. Se rechaza al cargar cualquier regla «perfil cambiado → cambiar perfil».
5. Las reglas importadas entran desactivadas hasta revisarlas.

## Formatos de datos (versión 1)

Todos los archivos llevan `"v": 1`. Los valores que no existen se escriben `null` (y la interfaz los muestra como `N/D`), nunca como 0.

`$XDG_RUNTIME_DIR/jaime0/instante.json`
```json
{"v":1,"t":1763123456,"intervalo":2,
 "cpu":{"total":12.5,"nucleos":[10.1,15.0],"mhz":[2600,3100],"temp":48.0},
 "ram":{"usada":3215,"total":15873,"swap":0,"swap_total":7936,"presion":0.00},
 "temp":[{"id":"coretemp/Package id 0","c":48.0},{"id":"nvme/Composite","c":36.9}],
 "gpu":{"nvidia":"suspendida","temp":null},
 "disco":[{"punto":"/","usado":24.1,"total":476.9,"lectura":0.0,"escritura":0.1}],
 "bateria":{"nivel":83,"estado":"descargando","vatios":11.2,"minutos_estimados":231,"salud":91.0},
 "procesos":[{"pid":1234,"nombre":"brave","cpu":8.2,"ram":512}],
 "cargador":true,"uptime":4210,
 "fallidas":[],
 "estado":"ONLINE","alertas":0}
```

`fallidas` es la lista de unidades de systemd en estado *failed* (sistema y sesión, consultada cada 60 s) o `null` si no se pudo consultar. `bateria.minutos_estimados` solo existe descargando y va marcado con `"estimado": true`.

`$XDG_RUNTIME_DIR/jaime0/estado.json`: perfil activo y anterior, estado global (`ONLINE`/`WARNING`/`CRITICAL`) con sus motivos, resumen de privacidad (`SECURE`/`WARNING`/`UNAVAILABLE`) y alertas activas. Waybar lo lee al recibir su señal.

`~/.local/state/jaime0/incidencias.jsonl`: `{"v":1,"t":…,"gravedad":"WARNING","componente":"thermal","descripcion":…,"diagnostico":…,"recomendacion":…}`

`~/.config/jaime0/reglas.json`: `{"v":1,"reglas":[{"id":"ahorro-al-20","nombre":"Ahorro al 20 %","activa":true,"revisar":false,"cuando":{"evento":"bateria_baja","umbral":20},"si":[{"condicion":"cargador","conectado":false}],"hacer":[{"accion":"perfil","perfil":"power-saver"},{"accion":"notificar","titulo":"Batería","texto":"Modo ahorro"}]}]}` (cada evento, condición y acción lleva sus parámetros por nombre; `jaime0-reglas catalogo` los lista)

Órdenes del socket (una línea JSON por petición): `estado`, `instante`, `rapido` (muestreo a 2 s durante 15 s), `serie` con `rango` `5m`/`1h`/`24h`/`historia` (como mucho 720 puntos; en 24 h e historia, mínimo/media/máximo de cada agregado; con `huecos`, `eventos` y `disponible`), `incidencias` (con `limite`) y `eventos`. Los agregados de minuto llevan `u`, la hora de su última muestra real.

`~/.local/state/jaime0/ejecuciones.jsonl`: `{"v":1,"t":…,"regla":…,"evento":…,"resultado":"ok"|"fallo"|"omitida","detalle":…}`

## Plan por fases

| Fase | Contenido | Se prueba en |
|---|---|---|
| 2 · Control Center | `jaime0-servicio` (esqueleto, API, `instante.json`, `estado.json`), `jaime0-salud` básico, ventana Quickshell con navegación de las 7 secciones, identidad visual y SYSTEM OVERVIEW con datos reales; `jaime0-control`, atajo, acceso en Waybar; paquete `upower` | VM |
| 3 · HEALTH | Sensores completos, anillo e históricos, incidencias y umbrales, gráficas en Canvas interactivas, DIAGNOSTIC MODE | VM (lo que haya) y portátil |
| 4 · PROFILES | Los 6 perfiles con capacidades, capa de sesión, vuelta atrás, CUSTOM | VM y portátil (PERFORMANCE solo allí) |
| 5 · PRIVACY & SECURITY | UFW (estado y reglas con polkit), conexiones, dispositivos en uso, servicios, historial | VM |
| 6 · AUTOMATION | Motor de reglas por eventos, lista blanca de acciones, editor sencillo, historial de ejecuciones | VM (Bluetooth y batería reales, en el portátil) |
| 7 · ANIMATIONS & INTEGRATION | Animaciones OFF/SUBTLE/SMOOTH (migrando el ajuste `animaciones` de sí/no), transiciones del Control Center, Waybar, atajos | VM |
| 8 · TESTING | Todo, persistencia, reinicios, consumo, funciones no disponibles bien indicadas | VM y portátil |

## Riesgos

- **Hardware sin probar:** sensores, frecuencias, batería real, PERFORMANCE y la NVIDIA solo existen en el portátil; en la VM esas partes se verán como `N/D`.
- **Rendimiento de las gráficas:** en la VM Quickshell dibuja por software; las gráficas se diseñan para redibujar solo lo que cambia y a la frecuencia del muestreo.
- **Alcance:** el servicio (salud y reglas) es el núcleo; las partes visuales se pueden recortar sin romperlo.
- **Waybar:** el indicador nuevo debe seguir mostrando el perfil de power-profiles-daemon aunque el servicio esté parado.
