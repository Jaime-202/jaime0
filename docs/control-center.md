# Jaime0 Control Center — plan y arquitectura

Estado: **Fases 1 a 8 del Control Center terminadas y evolución del sistema (fases 1 a 10) terminada.** Funcionan el servicio, `jaime0-salud`, `jaime0-perfil`, `jaime0-privacidad`, `jaime0-reglas`, `jaime0-update`, `jaime0-diagnostico` y la ventana con sus 10 secciones (SYSTEM, PERFORMANCE, PROFILES, AUTOMATION, PRIVACY & SECURITY, HEALTH, SETTINGS, UPDATES, DIAGNOSTICS y POWER), los tres niveles de animación, el atajo configurable, los avisos de incidencias y el indicador de la barra. Lo que solo existe en el portátil (NVIDIA, batería y sensores reales) queda por probar allí. El resumen de la evolución está en [evolucion.md](evolucion.md).

Después (evolución del sistema) se añadieron **UPDATES** (sección 08, ver [actualizaciones.md](actualizaciones.md)) y **DIAGNOSTICS** (sección 09, ver [diagnostico.md](diagnostico.md)) y **POWER** (sección 10, tecla `0`, ver [energia.md](energia.md)); las teclas van de `1` a `9` y `0`.

## Una responsabilidad por sección (evolución, fase 7)

| Sección | Responde a | No repite |
|---|---|---|
| SYSTEM | ¿Cómo está el sistema ahora? Estado global, perfil, CPU, memoria, temperatura, disco, batería, privacidad, servicios importantes (red, energía, cortafuegos, Bluetooth, sonido), actualizaciones pendientes, alertas (con la de DIAGNOSTICS) y actividad reciente | Procesos (antes «TOP PROCESSES»: ahora en PERFORMANCE) |
| PERFORMANCE | ¿Qué está pasando ahora? Núcleos y frecuencias, carga de 5 min y carga media 1/5/15, memoria, disco, red, GPU, picos recientes y la tabla de procesos: ordenar por CPU, RAM, nombre o PID, buscar, ver el detalle (orden completa, usuario, padre, hilos, memoria, inicio) y en ámbar los que gastan mucho | El perfil de energía (está en PROFILES y POWER) y el histórico (HEALTH). No hay acciones sobre procesos: es solo lectura |
| HEALTH | ¿Cómo evoluciona y qué problemas presenta? Gráficas por rango, temperaturas, almacenamiento, batería, incidencias y SENSORS & TRENDS (mínimo, media y pico de cada métrica en el rango, la detección de hardware con sus sensores, y los eventos) | Núcleos y procesos (la antigua vista detallada los repetía) |
| PRIVACY & SECURITY | ACTIVE SECURITY, APPLICATION PERMISSIONS y SYSTEM VISIBILITY, con los estados `ACTIVE`, `WARNING`, `DISABLED`, `UNAVAILABLE` y `NOT APPLICABLE` | Lo no comprobable o lo que el equipo no tiene va siempre a SYSTEM VISIBILITY: ni es un problema ni cuenta como protección |
| AUTOMATION | Reglas activas y desactivadas, últimas y próximas ejecuciones, errores, conflictos e historial (fase 3) | |
| SETTINGS | Preferencias del Control Center: animaciones, frecuencia, umbrales, avisos y atajo | Inactividad y suspensión (POWER), actualizaciones (UPDATES), diagnósticos (DIAGNOSTICS) |

Nuevo en el servicio: órdenes `procesos` (todos los de la última muestra) y `proceso` (detalle de uno, solo lectura de `/proc`); `red` (KB/s recibidos y enviados, sin `lo`) y `cpu.carga` (`/proc/loadavg`) en el instante; `servicios` en `estado.json` (una llamada a `systemctl show` por ámbito cada 60 s); y `categorias` en la orden `privacidad`, con AppArmor (`/sys/module/apparmor`) y Secure Boot (variable EFI, legible sin root) además de lo que ya se comprobaba.

## Accesibilidad (evolución, fase 9)

| Aspecto | Cómo |
|---|---|
| Teclado | `1`–`9` y `0` van a cada sección; `Ctrl+Tab` / `Ctrl+AvPág` a la siguiente y `Ctrl+Mayús+Tab` / `Ctrl+RePág` a la anterior; `Tab` y `Mayús+Tab` recorren los botones y filas en orden (primero la barra lateral, luego la sección); `Intro` o `Espacio` los pulsan; `Esc` cierra. Al cambiar de sección el foco vuelve a la ventana. Todo lo pulsable usa `Pulsar.qml`: no queda nada que solo funcione con el ratón |
| Foco | Marco blanco de 2 px alrededor del elemento, distinto de los colores de estado |
| Contraste | Todo color de texto supera 4,5:1 sobre los fondos (principal 14:1, secundario 6:1, atenuado 4,7:1, estados de 5 a 12:1). Los colores de líneas (`rejilla`, `borde`) no se usan para texto. Lo comprueba `pruebas/test_accesibilidad.py` |
| Tamaño | Ningún texto por debajo de 10 px. `cc_escala` (90–130 %) amplía o reduce toda la ventana; si no cabe el diseño mínimo (1100 × 680 puntos), se reduce lo justo, nunca por debajo del 75 %. La escala de Hyprland del monitor se aplica además, como en cualquier ventana |
| No solo color | Los estados llevan texto (`ACTIVE`, `WARNING`, `COMPATIBLE`…); las gráficas con varias series llevan leyenda con el nombre; los procesos que gastan mucho llevan `▲` además del ámbar |
| Movimiento | Tres niveles (`no`, `sutil`, `suave`). Con `sutil` nada se repite en bucle; el latido de un estado en alerta y el barrido de la cabecera solo con `suave`. Se respeta la preferencia del escritorio de no animar |

Probado en la VM (1280 × 800, ventana de 1100 × 688): Tab recorre la barra lateral y llega al botón de DIAGNOSTICS con el marco visible, Intro lo ejecuta, Ctrl+Tab pasa a POWER, escala 90 % reduce la ventana entera y 130 % se limita a lo que cabe.

## Detección de hardware (evolución, fase 8)

La orden `hardware` del servicio (módulo `hardware`, solo lee sysfs) dice, para cada componente, si ZYRON puede usarlo en ese equipo. La muestra HEALTH › SENSORS & TRENDS (panel HARDWARE · SENSORS).

| Estado | Significa |
|---|---|
| COMPATIBLE | Está y ZYRON lo lee o lo usa |
| DETECTADO | Está, pero falta algo para usarlo: controlador, módulo o herramienta (p. ej. NVIDIA sin su módulo, Wi-Fi bloqueada por el interruptor) |
| NO DISPONIBLE | Este equipo no lo tiene (sin batería, solo gráfica integrada, VM sin sensores) |
| ERROR DE LECTURA | Está, pero leerlo ha fallado |

Componentes: batería (y qué datos da), cargador, gráfica integrada (o virtual) y dedicada por separado (nunca se supone NVIDIA), temperatura de CPU y de GPU, otras temperaturas, ventiladores, voltajes, brillo de pantalla, Wi-Fi, Bluetooth, suspensión, perfiles de energía y SMART. Nunca despierta la NVIDIA ni ejecuta programas; un fallo inesperado en un componente da ERROR DE LECTURA solo en ese componente.

## DIAGNOSTICS (evolución, fase 5)

| Zona | Contenido |
|---|---|
| X0 | Último diagnóstico: problemas por gravedad, cuándo y cuánto tardó, y `EJECUTAR DIAGNÓSTICO` |
| X1 · PROBLEMS | Problemas detectados, de más a menos grave |
| X2 · detalle | Lo detectado, causas posibles (marcadas como no confirmadas), consecuencias, qué hacer y, si hay reparación, sus órdenes y el botón `REPARAR` (abre una terminal que pide confirmación y guarda copia) |
| X3 · CHECKS | Todas las comprobaciones por área, con su estado (incluidas `NO DISPONIBLE` y `NO APLICA`) |
| X4 · HISTORY | Problemas activos y resueltos, con cuántas veces han aparecido |

El servicio lanza `jaime0-diagnostico comprobar --json` en su propio hilo (a los 2 minutos de arrancar y cada 6 horas, o al pulsar el botón) y nunca repara nada. SYSTEM OVERVIEW enseña una línea con el problema más grave (`△ DIAGNOSTICS … (tecla 9)`); HEALTH sigue siendo para métricas e incidencias, sin repetir los diagnósticos.

## Pruebas de conjunto (fase 8)

**Cómo:** ISO nueva compilada con las fases 2 a 7 (15-11-2026), arrancada en vivo e instalada con el instalador gráfico (UEFI, ext4, disco entero) en una VM nueva (`jaime0-fase8`: 4 GiB, 4 CPU). Los arreglos de esta fase se copiaron encima del sistema instalado (la ISO se compiló antes). Además, revisión del código de las fases 2 a 7 por un revisor independiente.

**Revisión del código:** sin fallos de seguridad (el ayudante de polkit no acepta argumentos y solo vale en la sesión activa; las órdenes externas van sin shell; socket 0600 en una carpeta 0700; nada sale del equipo). Corregidos 9 fallos:

| Fallo | Arreglo |
|---|---|
| El tope global de reglas (20 por minuto) desactivaba para siempre reglas sin culpa | Se omiten esas ejecuciones con el motivo; desactivar queda para el tope por regla |
| Una incidencia de un sensor que deja de dar datos (p. ej. la GPU al suspenderse) quedaba abierta para siempre | Tras 3 muestras sin dato se cierra («Sin datos del sensor») |
| Si el perfil de energía se cambiaba fuera, power-profiles-daemon soltaba la retención y ZYRON no lo veía | Se olvida la retención y se vuelve a pedir |
| El servicio podía arrancar antes de exportar el entorno de Hyprland (POWER SAVER salía como no disponible) | Se arranca después, en la misma orden, y busca la firma de Hyprland en cada uso |
| Un `reglas.json` roto a mano se sobrescribía | Antes se guarda una copia `reglas.json.roto` |
| Una conexión cerrada por error dejaba su vigilancia de GLib activa | Se quita antes de cerrar |
| Un script autorizado que dejaba un proceso en segundo plano daba un falso «superó el tiempo» | Grupo de procesos propio; al agotar el tiempo se mata el grupo |
| CUSTOM con animaciones «SÍ» bajaba «suave» a «sutil» | Solo escribe el nivel si el usuario las tiene apagadas |
| Se podían lanzar dos servicios a la vez | Cerrojo (`flock`); la segunda instancia sale con código 2 y systemd no la reintenta |

**Fallos encontrados en el sistema instalado y corregidos:**

- Con el servicio parado, la barra, `jaime0-salud` y la ventana seguían mostrando el último estado como actual (la ventana, con el PID y la hora de la última muestra). Ahora el servicio borra lo que publica al parar y avisa a la barra; la ventana pasa a SERVICE OFFLINE con todo en N/D; `jaime0-salud` hace una medición puntual y lo dice.
- El límite fijo de 30 s para dar los datos por frescos no servía con `cc_intervalo = 30` (fase 7): ahora es el mayor de 30 s y tres muestras.
- Sin datos, la ventana afirmaba «SIN BATERÍA» y «sin swap en uso»: ahora no afirma nada.
- Dos peticiones seguidas de las reglas del cortafuegos podían abrir dos ventanas de contraseña: la marca de «consulta en curso» se ponía dentro del hilo. Ahora se pone antes de lanzarlo (salió como una prueba que fallaba 2 de cada 20 veces en Linux; tras el arreglo, 0 de 300).

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 580 correctas en Windows y en Linux (la del cerrojo real solo en Linux) |
| ISO | Compila; en vivo, el servicio arranca, el ayudante de polkit es `root:root 755`, `pkexec` y `upower` presentes |
| Instalación | Instalador gráfico completo; primer arranque en 24 s hasta tuigreet, sin unidades fallidas |
| Secciones | Las 7, abiertas con el atajo real (SUPER+I) y las teclas 1–7, con datos reales; 0 avisos de QML |
| No disponible bien indicado | Temperatura N/D, PERFORMANCE «UNAVAILABLE» con el motivo, Flatpak no instalado, rangos del historial sin datos desactivados, consumo y autonomía de la batería N/D |
| Terminal | `jaime0-salud`, `barra`, `jaime0-perfil`, `jaime0-privacidad`, `jaime0-reglas` correctos; con el servicio parado, `jaime0-perfil` y `jaime0-reglas` lo dicen con la orden para arrancarlo |
| Regla real | «Servicio fallido → notificar» se ejecuta con una unidad fallida de verdad y queda en el historial |
| Fallos | Servicio parado (ver arriba); `reglas.json` roto (copia `.roto` y se reescribe); sin Quickshell, `jaime0-control` explica que el estado se ve con `jaime0-salud`; segunda instancia rechazada |
| Reinicio | Tras reiniciar el sistema siguen los ajustes, el perfil (FOCUS se vuelve a aplicar), las reglas y el historial; la incidencia abierta antes se cierra una sola vez al ver que las unidades ya no fallan; 0 errores del servicio |
| Consumo | Servicio en reposo (cada 10 s, ventana cerrada): 0,10 % de CPU y 55 MiB, estable en 20 min (de 55,05 a 55,20 MiB en 15 min, mientras se llena el anillo). Ventana abierta en HEALTH: 2,5 % de CPU y 134 MiB; el servicio, midiendo cada 2 s, 0,6 %. Sistema entero con la sesión abierta: 613 MiB |
| No probado | Lo que solo existe en el portátil (sensores, NVIDIA, batería real, PERFORMANCE, Bluetooth, Wi-Fi, suspensión), el efecto visual de las animaciones de Hyprland (en una VM están apagadas) y el histórico de 24 h con un hueco por reinicio (necesita una hora de datos) |

**Pendiente (no corregido):** el servicio atiende algunas órdenes de perfil dentro de su bucle principal; si un programa externo se cuelga (p. ej. swaync), el muestreo, el socket y las reglas se detienen unos segundos (como mucho el límite de cada orden, 3–5 s). Arreglarlo exige pasar la aplicación de perfiles a un hilo; queda para más adelante.

## SETTINGS, animaciones e integración (fase 7)

**Animaciones** (ajuste `animaciones`): `no`, `sutil` (predeterminado) y `suave`. El valor antiguo `si` se lee como `sutil` y `no` sigue siendo `no`; el archivo del usuario no se reescribe.

| Dónde | no | sutil | suave |
|---|---|---|---|
| Hyprland (ventanas, capas, escritorios) | Desactivadas | Velocidades de siempre; capas con fundido, escritorios con desplazamiento | Más lentas y con la curva `fluida`; capas deslizándose, escritorios con `slidefade 20%` |
| swaync (`generado/swaync.css`) | `transition: none; animation: none` | Las del tema | Transiciones de 280 ms |
| Widgets del escritorio | Aparecen sin más | Fundido y 8 px de subida en 220 ms | Lo mismo en 420 ms |
| Control Center | Sin entrada, sin barrido de la cabecera ni luces que laten | Entrada y cambios de sección de 140–220 ms | 220–340 ms |

En una máquina virtual Hyprland apaga las animaciones siempre, sea cual sea el nivel.

**Ajustes nuevos** (`jaime0-ajustes`; ver [ajustes.md](ajustes.md)): `cc_intervalo` (5, 10 o 30 s, medición en segundo plano), `cc_intervalo_rapido` (1, 2 o 5 s, con la ventana abierta), `cc_notificar` (`todas`, `criticas` o `ninguna`) y `control_atajo` (p. ej. `SUPER+I`, `SUPER+SHIFT+C`, `ALT+F5`; se rechazan modificadores repetidos y teclas desconocidas). `jaime0-ajustes aplicar` escribe además `generado/control.json` (lo lee la ventana) y el nivel en `widgets.json` y `swaync.css`. Hyprland lee el atajo y el nivel de los ajustes al recargar, que `jaime0-ajustes` hace solo.

**Servicio:** usa los intervalos elegidos (un cambio reprograma el temporizador al momento) y avisa en el escritorio de cada incidencia nueva o que empeora, según `cc_notificar`: `notify-send` con el componente, la gravedad, la descripción y la recomendación, lanzado en un hilo con 5 s de límite para no frenar las medidas. Las recuperaciones no avisan.

**Barra:** el indicador añade el número de motivos después del icono de alerta (`󰀦 2`) cuando el sistema no está en ONLINE.

**SETTINGS** (sección 07): animaciones, frecuencias, umbrales de alerta, días de historial, avisos y atajo. Las opciones se eligen con chips, los números con −5/−1/+1/+5 (sin salirse del rango) y el atajo se escribe y se confirma con APLICAR. Todo pasa por `jaime0-ajustes poner`, con la misma validación que la terminal; si algo no vale, sale el motivo. Cada ajuste cambiado muestra ↺ con el valor de fábrica para restablecerlo.

### Resultados de la fase 7 (14-11-2026, misma VM)

La VM tiene la 0.3.0-beta.1 instalada y `sudo` pide contraseña, así que la versión nueva se probó para el usuario `prueba`: los tres programas en `~/.local/bin`, el servicio con un `ExecStart` de usuario (`~/.config/systemd/user/jaime0-servicio.service.d/fase7.conf`) y la ventana lanzada desde `~/fase7`.

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 548 correctas (23 nuevas: migración de `animaciones`, atajos válidos y no válidos, `control.json`, CSS por nivel, intervalos, avisos por gravedad y número de la barra) |
| Niveles | `no`, `sutil` y `suave` aceptados por Hyprland sin errores de configuración (`hyprctl configerrors` vacío); `swaync.css`, `widgets.json` y `control.json` cambian con cada nivel; la ventana se abre con el nivel elegido |
| Atajo | SUPER+I → SUPER+SHIFT+C → ALT+F5 → SUPER+I en `hyprctl binds`, desde la terminal y escribiéndolo en SETTINGS; `SUPER+SUPER+C` y `SUPER+ñ` rechazados con el motivo |
| SETTINGS | Cambiar el nivel, un umbral, la frecuencia rápida y el atajo desde la ventana se guarda en `~/.config/jaime0/ajustes` y se aplica; un umbral incoherente (aviso = crítico = 95) se rechaza con el motivo; restablecer deja el archivo vacío |
| Frecuencia | Frecuencia rápida 5 s → el servicio publica `intervalo: 5` en unos segundos, sin reiniciarlo |
| Avisos | Unidad de usuario fallida a propósito: con `todas`, aviso «UNIDADES DE SYSTEMD · WARNING» a los 33 s; con `criticas`, ninguno; la barra muestra `󰀦 1` |
| Consumo | Ventana con SETTINGS abierta: 4,4 % de CPU y 158 MiB; servicio midiendo cada 2 s: 2,0 % y 55 MiB |
| No probado | El efecto visual de las animaciones de Hyprland (en la VM están siempre apagadas) y la entrada animada de los widgets: necesitan el portátil |

Encontrado al probar: el mensaje de error se salía de la tarjeta de SETTINGS (ahora salta de línea), y al recargar la ventana en caliente con las animaciones activas se quedaba en blanco (la opacidad inicial dependía de un enlace; ahora la pone la animación).

## AUTOMATION · ZYRON Rules (fase 6)

Reglas **CUANDO → SI → HACER**. Las ejecuta el servicio aunque el Control Center esté cerrado.

| | Disponibles |
|---|---|
| **CUANDO** (un evento) | Batería baja (umbral, se rearma 5 puntos por encima), cargador conectado/desconectado, dispositivo Bluetooth (de audio o cualquiera, por nombre), monitor conectado/desconectado, aplicación abierta (primera ventana) o cerrada (última), hora del día y días, red conectada/desconectada (o una Wi-Fi concreta), suspender/reanudar, inactividad de 5 min y vuelta, cambio del estado del sistema, servicio fallido, cambio de perfil hecho por ti |
| **SI** (opcional) | Perfil activo, cargador conectado o no, batería por debajo o por encima de un valor, entre dos horas (también de noche, pasando la medianoche), días de la semana |
| **HACER** (1 a 5, lista cerrada) | Cambiar de perfil, modo noche, no molestar, notificar, abrir una aplicación instalada, volumen, silenciar, salida de audio por nombre (p. ej. los auriculares Bluetooth), mantenimiento seguro (borrar miniaturas de más de 30 días; comprobar actualizaciones) y scripts autorizados |

**De dónde salen los eventos** (sin sondeo nuevo): batería y cargador, de las muestras que el servicio ya toma; Bluetooth (BlueZ), red (NetworkManager) y suspensión (logind), de señales de D-Bus; monitores y aplicaciones, del socket de eventos de Hyprland; la hora, de un temporizador al instante exacto; la inactividad, de hypridle (`jaime0-reglas evento inactivo|activo` a los 5 min). Un evento que el equipo no puede detectar sale apagado en el editor, con el motivo.

**Seguridad.** Ninguna acción necesita root. Los scripts solo se ejecutan si están en `~/.config/jaime0/scripts-autorizados/`, son tuyos, ejecutables y nadie más puede modificarlos (tampoco la carpeta); sin shell, sin argumentos y con 60 s como mucho. Las reglas importadas (`jaime0-reglas importar`) entran desactivadas y marcadas `REVISAR`.

**Sin bucles:** lo que hace una regla no dispara otras reglas; los disparadores son por flanco; 30 s de enfriamiento por regla (se registra como «omitida»); si una regla se ejecuta 5 veces en 5 min se desactiva sola y abre una incidencia; si hay más de 20 ejecuciones en un minuto en total, las de sobra se omiten (sin desactivar ninguna regla) y queda una incidencia; una regla «cambio de perfil → cambiar de perfil» se rechaza al guardarla.

**Conflictos y duplicadas (evolución, fase 3):** si un mismo evento dispara a la vez reglas que piden valores distintos para lo mismo (perfil, volumen, silencio, salida de audio, no molestar o modo noche), gana la de **prioridad** más alta (`alta`, `normal` —por defecto— o `baja`) y, a igual prioridad, la que va antes en la lista. A la otra solo se le omite la acción en conflicto, con el motivo en el historial; el conflicto queda en la actividad y en la lista de conflictos recientes (los 20 últimos, en memoria). Pedir el mismo valor no es conflicto, y una regla en enfriamiento no le quita el recurso a otra. Al listar, cada regla avisa de con cuáles puede chocar (mismo CUANDO y valores distintos). No se guarda ni se importa una regla que haga exactamente lo mismo que otra. AUTOMATION y `jaime0-reglas lista` muestran el resumen (activas, desactivadas, por revisar, con fallo, conflictos), la prioridad, la próxima ejecución de las reglas de hora y los conflictos recientes; el editor tiene el selector de prioridad.

Resultados (16-11-2026, VM con la ISO 0.4.0-beta.1 en vivo y el servicio nuevo): dos reglas de inactividad con perfiles distintos, una de prioridad alta: gana la alta (FOCUS y volumen al 20 %) y a la otra se le omite el perfil con el motivo; la regla duplicada se rechaza; «Noche» muestra la próxima ejecución; la prioridad se cambia y se guarda desde el editor; 0 avisos de QML.

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
| APPS · PRIVILEGES · SERVICES | Flatpak (`UNAVAILABLE`: no está en ZYRON, así que no hay permisos por aplicación), tus grupos con privilegios y qué permiten, y servicios con efecto en la privacidad (SSH, avahi, CUPS, Bluetooth, NetworkManager) | `os.getgrouplist`, systemd |
| TELEMETRY · HISTORY | ZYRON sin telemetría; popularity-contest; qué consulta debsecan; si el widget del tiempo conecta con Open-Meteo; Brave y sus opciones (P3A). Historial de cambios relevantes | `dpkg-query`, archivos de configuración |

El historial (`~/.local/state/jaime0/privacidad.jsonl`, 300 líneas como mucho) guarda cambios del cortafuegos, puertos que se abren o se cierran, el uso de micrófono, cámara o pantalla (nombre de la aplicación) y las consultas de reglas con autorización. **No guarda direcciones ni la salida de las reglas.** Cortafuegos y puertos se revisan cada minuto; los dispositivos, cada 10 s con la ventana abierta y cada minuto si no.

`jaime0-privacidad` (resumen por apartados, `--json`), `jaime0-privacidad reglas` (pide la contraseña) y `jaime0-privacidad historial -n N`.

### Resultados de la fase 5 (14-11-2026, misma VM)

| Prueba | Resultado |
|---|---|
| Pruebas automáticas | 376 correctas (90 nuevas: UFW, `ss`, `pw-dump`, cámara, flatpak, grupos, telemetría, estado, historial, API, cliente y ayudante) |
| Estado real | WARNING por el puerto 22 (SSH) abierto a la red: es el servidor SSH instalado en la VM para manejarla en las pruebas, y el motivo lo dice |
| Micrófono | Una grabación con `pw-record` se detectó mientras duraba y quedó en el historial al empezar y al terminar |
| Reglas con autorización | El botón abrió la ventana de contraseña de polkit con el mensaje de ZYRON; con la contraseña se vieron las reglas reales (22/tcp ALLOW IN, IPv4 e IPv6) y la consulta quedó en el historial |
| Ventana | Seis paneles con datos reales, 0 avisos de QML |
| No probado | Cámara real y pantalla compartida real (la VM no tiene cámara ni se compartió pantalla), y Flatpak instalado (no está en ZYRON) |

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
| No probado | PERFORMANCE con energía real, el efecto visual de animaciones y desenfoque (en una VM ZYRON los apaga siempre) y que hypridle respete el inhibidor durante 10 minutos reales: necesitan el portátil o una espera larga |

Arreglos encontrados al probar: el enlace para editar CUSTOM estaba dentro de su tarjeta y el clic también aplicaba el perfil (ahora es un botón aparte); el editor no cargaba lo guardado; el botón de volver se salía de la cabecera con textos largos; la descripción de CUSTOM decía «sin definir» aunque estuviera definido; y la gráfica de PERFORMANCE no avisaba mientras recogía el primer minuto de datos.

## HEALTH (fase 3)

| Zona | Qué muestra |
|---|---|
| SYSTEM HEALTH | Estado global, CPU, RAM, temperatura y alertas activas; selector de intervalo (`REAL TIME`, `LAST 5 MIN`, `LAST HOUR`, `LAST 24 HOURS`, `HISTORY`: los que aún no tienen datos suficientes salen apagados) y `DETAILED VIEW` (antes `DIAGNOSTIC MODE`; el diagnóstico de problemas está en DIAGNOSTICS) |
| LIVE MONITORING | Las dos gráficas grandes, CPU y RAM: valor actual, media y pico del intervalo, diferencia con la media, línea de referencia y marcas de eventos (▼) |
| HARDWARE DIAGNOSTICS | Temperaturas (CPU y GPU, con los umbrales de aviso y crítico), almacenamiento (ocupación, lectura/escritura y SMART) y batería (nivel, consumo, autonomía marcada como *estimada* y salud) |
| SYSTEM EVENTS | Incidencias: fecha, gravedad, componente, descripción y recomendación; también la recuperación |
| DETAILED VIEW | Sustituye la zona de hardware por el detalle: cada núcleo con su uso y frecuencia, todos los sensores, memoria desglosada, procesos y eventos del intervalo |

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
| Abrir o cerrar el Control Center | `SUPER + I`, clic en el indicador de ZYRON de la barra (junto a la batería) o `jaime0-control` |
| Dentro | `1`–`7` cambian de sección, `Esc` cierra |
| Estado en la terminal | `jaime0-salud` (`--json` para la salida completa) |
| El servicio | `systemctl --user status jaime0-servicio`; lo arranca la sesión de Hyprland |
| Cambiar el atajo | SETTINGS → SHORTCUT, o `jaime0-ajustes poner control_atajo SUPER+SHIFT+C` (fase 7) |

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
2. **Separación por módulos dentro del servicio**, cada manejador aislado con `try/except`; `Restart=on-failure`; sin subprocesos en el bucle de muestreo. Desde la evolución de noviembre (fase 2), el código está en el paquete `jaime0_servicio` (`/usr/local/lib/jaime0/`, ver abajo) y lo que puede tardar o colgarse va por el hilo de efectos. Atado a `graphical-session.target` para tener `HYPRLAND_INSTANCE_SIGNATURE`; reconecta al socket2 si Hyprland se reinicia.
3. **La interfaz no mide.** Lee `instante.json` (tmpfs, sin escrituras a disco) con `FileView` y pide al servicio subir a 1–2 s mientras está abierta. Al cerrarla, el proceso de Quickshell termina y el servicio vuelve a 10 s.
4. **Quickshell es opcional.** Sin él, el escritorio, el servicio, las reglas, los perfiles y las CLIs funcionan; solo falta la ventana. `jaime0-control` lo avisa.
5. **Sin root por defecto.** Lo único que lo necesita es leer las reglas de UFW: ayudante mínimo con una acción de polkit fija (solo esa lectura, sin argumentos libres), pedido al pulsar, con el agente `lxpolkit` de la sesión.
6. **Sin telemetría.** Nada sale del equipo; los datos viven en `$XDG_RUNTIME_DIR` y `~/.local/state/jaime0/` y se pueden borrar.

### Módulos y concurrencia (evolución, fase 2)

`/usr/local/bin/jaime0-servicio` es un lanzador; el código está en `/usr/local/lib/jaime0/jaime0_servicio/`, un módulo por responsabilidad y **un solo proceso** (ningún demonio nuevo). Cada módulo solo importa de los anteriores (lo vigila una prueba):

| Módulo | Responsabilidad |
|---|---|
| `base` | Rutas, registro, `protegido`, `Recordado` (caché con caducidad) y `Trabajador` (hilo de efectos) |
| `medicion` · `historico` · `incidencias` | Lectura de `/proc` y `/sys`; anillo, agregados y huecos; detector e incidencias |
| `sistema` | SMART, umbrales, D-Bus, aviso a Waybar, firma de Hyprland |
| `perfiles` · `privacidad` · `estado` | Motor de perfiles; PRIVACY & SECURITY; estado global |
| `reglas` | Catálogo, validación, acciones y motor de ZYRON Rules |
| `actualizaciones` · `diagnostico` | UPDATES (`jaime0-update` y apt, comprobación en su hilo) y DIAGNOSTICS (`jaime0-diagnostico` en su hilo) |
| `energia` · `hardware` | POWER (batería, gráficas, CPU, suspensión, historial por perfil) y la detección de hardware |
| `api` · `servicio` | Órdenes del socket; el servicio, el cerrojo de instancia única y `main` |

**Tres hilos y nada más:** el bucle de GLib (medidas, socket, reglas, estado), los trabajos de privacidad y de acciones de reglas, que ya existían, y el **hilo de efectos** (`jaime0-efectos`). Este ejecuta en orden, una a una, las operaciones que pueden tardar o colgarse: aplicar perfiles (venga de la ventana, de `jaime0-perfil` o de una regla), leer los umbrales (`jaime0-ajustes`), las consultas de energía a D-Bus, la lista de aplicaciones y de eventos para las reglas, y el aviso a Waybar. El motor de perfiles solo se usa desde ese hilo; sus avisos (actividad, `estado.json`, eventos de reglas) vuelven al bucle con `idle_add`. Las órdenes del socket que pasan por él contestan al terminar (`perfiles`, `perfil`, `perfil_anterior`, `personalizado`, `reglas`, `regla_guardar`, `reglas_importar`), sin hacer esperar a las demás. Cada operación conserva su propio límite (D-Bus 3 s, subprocesos con `timeout`); un fallo se registra y no detiene el hilo; las que pasan de 10 s se anotan. `estado.json` lleva `servicio.efectos` (pendientes, operación en curso y desde cuándo).

Medido en una VM con la ISO 0.4.0-beta.1 y un `swaync-client` que no responde, al aplicar FOCUS: el socket tardaba **3,05 s** en contestar con el servicio anterior y **0,00 s** con este (12 peticiones, una por segundo); las medidas siguen su ritmo. En reposo: 0,12 % de CPU y 37 MiB (el anterior, 38 MiB de pico en la misma VM).

Para probar a mano en un sistema instalado hay que copiar las dos partes: `/usr/local/bin/jaime0-servicio` y `/usr/local/lib/jaime0/jaime0_servicio/`.

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
3. Enfriamiento por regla (30 s); tope por regla (la regla se desactiva y queda una incidencia) y tope global (se omiten ejecuciones sin desactivar ninguna regla).
6. Conflictos entre reglas del mismo evento resueltos por prioridad y orden, y anotados (fase 3).
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
| 7 · ANIMATIONS & INTEGRATION | Animaciones OFF/SUBTLE/SMOOTH (migrando el ajuste `animaciones` de sí/no), transiciones del Control Center, Waybar, atajos, SETTINGS — **hecha** | VM |
| 8 · TESTING | Todo, persistencia, reinicios, consumo, funciones no disponibles bien indicadas — **hecha en VM; falta el portátil** | VM y portátil |

## Riesgos

- **Hardware sin probar:** sensores, frecuencias, batería real, PERFORMANCE y la NVIDIA solo existen en el portátil; en la VM esas partes se verán como `N/D`.
- **Rendimiento de las gráficas:** en la VM Quickshell dibuja por software; las gráficas se diseñan para redibujar solo lo que cambia y a la frecuencia del muestreo.
- **Alcance:** el servicio (salud y reglas) es el núcleo; las partes visuales se pueden recortar sin romperlo.
- **Waybar:** el indicador nuevo debe seguir mostrando el perfil de power-profiles-daemon aunque el servicio esté parado.
