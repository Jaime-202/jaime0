# Pruebas de Jaime0

Qué se prueba, cómo y con qué resultado. Cada prueba indica si se ha **probado** de verdad, si se ha **simulado**, o si está **pendiente** (de hardware real o de una ISO 0.2 compilada). Una función no se da por buena hasta que pasa aquí.

## 1. Pruebas automáticas (sin ISO ni VM)

```bash
scripts/validar-repo.sh
```

Lo ejecuta GitHub Actions en cada `push` y solicitud de integración ([.github/workflows/validar.yml](../.github/workflows/validar.yml)). No compila la ISO ni publica nada.

| Comprobación | Qué detecta |
|---|---|
| Permisos en git | Programas, hooks, `auto/` o scripts sin permiso de ejecución |
| CRLF y secretos | Finales de línea de Windows; claves privadas dentro de `config/` |
| shellcheck | Lo que va en la ISO: ni un aviso. Scripts de prueba: sin errores (los avisos se muestran) |
| Python | Sintaxis de todos los programas Python y las pruebas de `pruebas/` |
| Configuraciones | JSON/JSONC (Waybar, swaync, fastfetch), TOML de `publicaciones/`, Lua (`hyprland.lua`, Neovim) y listas de paquetes |
| QML | Que cada componente cargado por nombre exista |
| Imprescindibles | Archivos y programas sin los que la ISO no funciona |

Se ha comprobado que la validación falla de verdad: con un error provocado de cada tipo (permiso, shell, Python, JSON, Lua, lista de paquetes y QML), detecta los 7.

Pruebas de `pruebas/` (`python3 -m unittest discover -s pruebas -v`):

| Archivo | Cubre |
|---|---|
| `test_jaime0_ajustes.py` | Ajustes: validación, archivo del usuario, generados para Waybar/rofi/swaync/hyprlock/wob/widgets |
| `test_jaime0_anclar.py` | Ancladas: nombres, máximo, orden, estado de los huecos, aplicaciones desinstaladas |
| `test_jaime0_tiempo.py` | Tiempo: Open-Meteo de mentira, homónimos, caché, sin red |
| `test_jaime0_diagnostico.py` | Diagnóstico: que no salgan datos personales y que no falle sin comandos |
| `test_integridad_repo.py` | Lo que puede romper el instalador o la ISO sin que falle ningún programa: cada paso de Calamares existe y lo que ejecuta está en la imagen; lo que desinstala al terminar no lo usa Jaime0 (p. ej. un `import QtQuick.Effects` cuando se desinstala ese módulo); cada programa externo que usa Jaime0 viene de un paquete de las listas; lo que arrancan las unidades de systemd existe; y un inventario de secciones, órdenes del servicio, programas y ajustes que no pueden desaparecer sin cambiar la lista |
| `test_jaime0_hardware.py` | Detección de hardware: portátil híbrido, solo integrada, máquina virtual, sensores, ventiladores, voltajes y errores de lectura |

`validar-repo.sh` además falla si se ejecutan menos pruebas que las de `pruebas/minimo-pruebas.txt`: así no desaparecen pruebas sin querer (si se quitan a propósito, se baja el mínimo en el mismo commit). Se ha comprobado que las pruebas de integridad fallan de verdad: un QML que importa un módulo que el instalador desinstala, un paso de Calamares que ejecuta un programa inexistente y una sección que desaparece se detectan los tres.

### Antes de integrar un cambio importante

```bash
scripts/validar-repo.sh                                  # lo mismo que GitHub Actions
python3 -m unittest discover -s pruebas -v              # si solo se quieren las pruebas
```

Con una ISO nueva, además, en la VM de compilación (Linux, sin root):

```bash
scripts/verificar-iso.sh jaime0-VERSION-amd64.iso --repo .
```

`verificar-iso.sh` no arranca la ISO: comprueba arranque BIOS y UEFI (El Torito, shim, GRUB, núcleo, initrd y menú), que el sistema de archivos se lee entero, los programas imprescindibles y sus permisos (lo que corre como root es de root y no lo puede escribir nadie más), que no haya claves privadas, la versión, que estén instalados todos los paquetes de `config/package-lists` y qué archivos del repositorio faltan o son distintos en la ISO. Resultado con la ISO publicada 0.4.0-beta.1 (16-11-2026): 47 correctos, 0 fallos, en 1 min; una copia truncada de la ISO falla. Después se arranca y se instala en la VM (sección 3) y, en la sesión, `verificar-sesion.sh`.

La instalación con el instalador gráfico (Calamares) no está automatizada: se hace en la VM siguiendo la sección 3. Lo que sí se comprueba sin VM es que la configuración del instalador sea coherente (`test_integridad_repo.py`) y el resultado (`verificar-iso.sh`, `verificar-instalador.sh` sobre el chroot y `verificar-sesion.sh` en el sistema instalado).

## 2. Sesión en marcha

```bash
bash scripts/verificar-sesion.sh
```

Desde una terminal de la sesión (VM o equipo real). Comprueba Hyprland, los procesos de la sesión, los ajustes de ida y vuelta, las ancladas, los widgets, el servicio de Jaime0 y el Control Center (cada orden del socket responde, `estado.json` al día, la ventana abre sin errores de QML), `jaime0-diagnostico`, `jaime0-reglas`, `jaime0-perfil`, `jaime0-update`, las herramientas básicas y las notificaciones (con No molestar activo no se exige que se vean), y deja tus ajustes como estaban.

**Resultado (16-11-2026, VM `jaime0-fase2`, sesión en vivo 0.4.0-beta.1 con los archivos de la evolución encima):** 47 correctos, 0 fallos.

**Resultado (13-11-2026, VM `jaime0-pruebas`, sesión en vivo 0.1 con los archivos 0.2 encima, tras entrar de nuevo con tuigreet):** 21 correctos, 0 fallos.

## 3. Pruebas en máquina virtual

### 0.3.0-beta.1 (13-11-2026): ISO para el Acer Nitro AN515-55

ISO SHA-256 `e7e91e9e…46d2`, 1,77 GB (la 0.2 ocupaba 2,06 GB). En una VM no hay NVIDIA: lo que depende de la gráfica real queda para el portátil.

| Prueba | Estado | Notas |
|---|---|---|
| Compilar la ISO | Probado | El módulo de NVIDIA 550 compila para el núcleo 7.2.15; Brave se instala desde su repositorio |
| `verificar-todo.sh` (9 scripts) | Probado | 0 fallos. Pendientes solo las pruebas gráficas que la VM de compilación no puede hacer (sin 3D) |
| Sin clave privada en la imagen | Probado | Ni `mok.key` ni `mok.pub` en `/var/lib/dkms`; ninguna `PRIVATE KEY` en `/etc` |
| Solo el firmware del portátil | Probado | Sin firmware de Broadcom, AMD, Atheros, Qualcomm ni MediaTek, ni microcódigo de AMD |
| Arranque en vivo UEFI | Probado | `verificar-sesion.sh` 21/21; indicador de energía en la barra; `prime-run` sin NVIDIA avisa y usa la gráfica normal; asociaciones de vídeo, imagen, PDF, comprimidos y web |
| `jaime0-nvidia recompilar` | Probado | Clave nueva en cada ejecución y módulo firmado con ella (`modinfo -F sig_key` = número de serie de `mok.pub`); `mok.key` 600 y `mok.pub` 644. 1 min 56 s en la VM |
| Instalación UEFI en ext4 con el instalador gráfico | Probado | El paso `shellprocess@nvidia` tarda 2 min 5 s; el sistema instalado arranca hasta tuigreet, sesión 21/21, sin servicios fallidos, módulo firmado con la clave propia de la instalación. Arranque en 19,7 s y 815 MiB usados con la sesión abierta (VM, 4 GiB) |
| Registro de la clave con MokManager, `prime-run` con NVIDIA, ahorro de energía y HDMI | **Pendiente del portátil** | Ver [nvidia.md](nvidia.md) |
| Escala 1.25 en `eDP-1`, perfiles de energía y thermald reales | **Pendiente del portátil** | En la VM la pantalla es `Virtual-1` (escala 1) y thermald no arranca (CPU virtual) |

### 0.2

VM de VirtualBox 7.1 en Windows 11: UEFI, 4 GB, 4 CPU, aceleración 3D. Las pruebas de sesión de la 0.2 se hicieron primero sobre la ISO 0.1.x en vivo con los archivos 0.2 encima; después se compiló la ISO 0.2.0-beta.1 (13-11-2026, SHA-256 `ae831ddc…0607`) y se repitieron arranque, instalación y `verificar-sesion.sh` con ella. La compilación final (SHA-256 `bd206dd5…1774`) solo añade el límite de 5 s de `notificaciones` y los scripts de prueba al día; con ella se repitió el arranque en vivo UEFI (`verificar-sesion.sh` 21/21) y no la instalación, cuyo contenido no cambia. La 0.2.0-beta.2 (SHA-256 `4cb56434…bf67`) solo cambia la versión y la clave de firma: arranque en vivo UEFI 21/21, firma del paquete publicado comprobada con la clave de la ISO y `jaime0-update comprobar` contra GitHub correcto.

| Prueba | Estado | Notas |
|---|---|---|
| Compilar la ISO 0.2 (`lb build`) | Probado | En la VM de compilación (Debian Forky) |
| Arranque en vivo UEFI con la ISO 0.2 | Probado | `verificar-sesion.sh` 21/21; zram y UFW activos desde el primer arranque |
| Instalación UEFI en ext4 con la ISO 0.2 | Probado | Primer arranque, tuigreet, sesión 21/21; Quickshell y sus dependencias siguen tras la limpieza del instalador |
| Instalación UEFI en Btrfs + LUKS con la ISO 0.2 | Probado | Subvolúmenes `@`, `@home`, `@log`, `@cache`, `@swap`; snapper configurado; pre/post de `apt`; Plymouth pide la clave y llega a tuigreet; sesión 21/21 |
| Arranque BIOS, Secure Boot, junto a otro sistema, ISO conectada como USB | Probado en la 0.1.x (ver README) | **Pendiente con la ISO 0.2** |
| Inicio de sesión 0.2 completo (ajustes, ancladas, widgets, barra, notificaciones) | Probado | `verificar-sesion.sh` |
| `jaime0-ajustes`: todos los ajustes y la aplicación gráfica | Probado | Sin ratón: los clics llaman a las mismas órdenes |
| Redimensionar arrastrando el borde | Configuración probada | Arrastre con ratón **no probado** |
| Ancladas: abrir, enfocar, punto de abiertas | Probado | |
| Widgets (6), en caliente, consumo | Probado | Música con mpv |
| swaync, wob, modo noche, selector de color, nwg-displays | Probado | |
| Bloqueo hyprlock, clave incorrecta y correcta, relevo a swaylock | Probado | |
| Inactividad: bloqueo y pantalla apagada (tiempos cortos) | Probado | |
| Suspender y reanudar | **Parcial** | Bloquea antes y reanuda bloqueada. VirtualBox no despierta con la alarma del reloj, a veces tampoco con el teclado, y si queda congelada más de 3 min el vigilante de systemd reinicia logind y la red no vuelve sola. Es un efecto de la VM: **pendiente de hardware real** |
| Cortafuegos UFW: salida, DNS, `apt update`, DHCP, SLAAC; puerto entrante cerrado | Probado | Puerto cerrado comprobado desde otro espacio de red (veth) |
| zram: se activa con 4 GiB (zstd, prioridad 100); no se activa por encima del límite | Probado | Límite probado de verdad con 2 GiB y simulado con varias cantidades de RAM |
| Instantáneas de snapper con `apt` | Probado (orden en un Btrfs real y gancho de `apt` en un sistema instalado en Btrfs) | **Pendiente:** `undochange` en el sistema instalado |
| Avisos de seguridad (apt + debsecan) | Probado | 49 paquetes pendientes, 0 con correcciones de seguridad en ese momento |
| Primer arranque con UFW y zram desde la ISO | Probado | ISO 0.2 en vivo |
| `apt full-upgrade` | Pendiente | Con la ISO 0.2 |
| NVMe, varios monitores | Pendiente | VirtualBox: NVMe solo con el paquete de extensión; varios monitores, configurable |

## 4. Pruebas en hardware real (pendientes)

Ninguna de estas se ha hecho todavía. Para cada equipo, adjunta a una [incidencia](https://github.com/Jaime-202/jaime0/issues) el informe de `jaime0-diagnostico` (no recoge datos personales) y la salida de `bash scripts/verificar-sesion.sh`.

| Área | Qué comprobar |
|---|---|
| Arranque | USB grabado en modo imagen; BIOS y UEFI; Secure Boot activado; modo seguro |
| Gráfica Intel | Escritorio fluido, Quickshell y hyprlock con OpenGL (no por software) |
| Gráfica AMD | Igual que Intel |
| Gráfica NVIDIA | Nouveau por defecto; controlador propietario con los pasos del README |
| Wi-Fi | Detección del chip, firmware, conexión desde la barra (SSID visible) |
| Bluetooth | Adaptador, emparejar unos auriculares |
| Sonido | Altavoces, auriculares, micrófono, teclas multimedia con indicador |
| Portátil | Batería en la barra y en el widget, brillo (teclas e indicador, widget), touchpad, cierre de tapa |
| Suspensión | Suspender por inactividad y por menú, reanudar con la pantalla bloqueada y con red |
| USB | Montar una memoria desde Thunar |
| Varios monitores | nwg-displays, ancladas y widgets en la pantalla principal |
| Instalación | Disco entero, LUKS, junto a Windows, en NVMe |

## 5. Problemas conocidos

- **Waybar y Debian:** Debian tiene marcado Waybar para salir de testing el 22-11-2026 por errores en dependencias lejanas. La versión instalada está parcheada, fijada y retenida (`apt-mark hold`), así que una actualización no la retira. Si en el futuro una biblioteca suya desaparece, `apt` retendrá esa actualización. Una compilación nueva de la ISO posterior a esa fecha podría no resolver sus dependencias de compilación.
- **Rama de pruebas:** Forky es Debian testing y una actualización puede romper algo, en especial si cambia Hyprland. Durante el desarrollo pasó de 0.56 a 0.57 y hubo que retirar una opción.
- **Fallos aislados en VirtualBox:** en pruebas sobre Windows con VirtualBox funcionando encima de Hyper-V (Integridad de memoria activada), un arranque de cada 11 en una VM se quedó congelado por un fallo de `systemd`, con un trozo de `libc` leído como ceros en memoria, y otra VM reanudada tras muchas horas tuvo programas que fallaban al azar. Reiniciarla lo resolvió: ocho reinicios seguidos entraron bien y no se pudo reproducir. Todo apunta a la capa de virtualización y no a Jaime0, pero no se ha podido demostrar. Por si ocurre, Jaime0 reinicia solo si `systemd` falla al arrancar (`CrashAction=reboot`). No se ha visto en otras condiciones, y no se ha probado en hardware real.
- **Textos en inglés:** `tuigreet` y `swaylock` (solo de respaldo) no tienen traducción. El centro de notificaciones muestra la hora relativa en inglés, así que se oculta. Algunas entradas de GRUB y las de otros sistemas salen en inglés.
- **Instalador:** el mapa, el teclado de muestra y la franja de particiones usan colores fijos de Calamares.
- **`btop` en mosaicos muy pequeños:** necesita 80x24. Abierto con `CTRL + SHIFT + Escape` usa letra de 7 puntos y cabe en un cuarto de pantalla a 1280x800; más pequeño, lo avisa.
- **Teclados virtuales:** algunos usan códigos de tecla que coinciden con las teclas multimedia y Hyprland ejecuta esos atajos. Con un teclado físico no pasa.
