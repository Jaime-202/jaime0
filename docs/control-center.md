# Jaime0 Control Center — plan y arquitectura

Estado: **Fases 1 y 2 terminadas.** Funcionan el servicio, `jaime0-salud`, la ventana con SYSTEM OVERVIEW, el atajo y el indicador de la barra. Las demás secciones dicen en qué fase llegarán y no muestran datos inventados.

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

`~/.config/jaime0/reglas.json`: `{"v":1,"reglas":[{"id":…,"nombre":…,"activa":true,"cuando":{"evento":"bateria","debajo":20,"rearme":25},"si":[…],"hacer":[{"accion":"perfil","valor":"power-saver"}]}]}`

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
