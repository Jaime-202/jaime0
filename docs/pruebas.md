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
| `test_jaime0_update.py` | Actualizador: firmas, canales, fusión a tres bandas, conflictos, copias, reversión y recuperación |
| `test_jaime0_ajustes.py` | Ajustes: validación, archivo del usuario, generados para Waybar/rofi/swaync/hyprlock/wob/widgets |
| `test_jaime0_anclar.py` | Ancladas: nombres, máximo, orden, estado de los huecos, aplicaciones desinstaladas |
| `test_jaime0_tiempo.py` | Tiempo: Open-Meteo de mentira, homónimos, caché, sin red |
| `test_jaime0_flatpak.py` | Flatpak opcional: preguntas, cancelaciones y órdenes, con programas de mentira |
| `test_jaime0_diagnostico.py` | Diagnóstico: que no salgan datos personales y que no falle sin comandos |

## 2. Sesión en marcha

```bash
bash scripts/verificar-sesion.sh
```

Desde una terminal de la sesión (VM o equipo real). Comprueba Hyprland, los procesos de la sesión, los ajustes de ida y vuelta, las ancladas, los widgets y las notificaciones, y deja tus ajustes como estaban.

**Resultado (13-11-2026, VM `jaime0-pruebas`, sesión en vivo 0.1 con los archivos 0.2 encima, tras entrar de nuevo con tuigreet):** 21 correctos, 0 fallos.

## 3. Pruebas en máquina virtual

VM de VirtualBox 7.1 en Windows 11: UEFI, 4 GB, 4 CPU, aceleración 3D. Las pruebas de sesión de la 0.2 se hicieron primero sobre la ISO 0.1.x en vivo con los archivos 0.2 encima; después se compiló la ISO 0.2.0-beta.1 (13-11-2026, SHA-256 `ae831ddc…0607`) y se repitieron arranque, instalación y `verificar-sesion.sh` con ella.

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
| `jaime0-flatpak` activar y desactivar | Probado | Sin instalar ninguna aplicación |
| Instantáneas de snapper en `jaime0-update` | Probado (pruebas automáticas, orden en un Btrfs real y gancho de `apt` en un sistema instalado en Btrfs) | **Pendiente:** una actualización real de `jaime0-update` y `undochange` en el sistema instalado |
| Avisos de seguridad (apt + debsecan) | Probado | 49 paquetes pendientes, 0 con correcciones de seguridad en ese momento |
| Primer arranque con UFW y zram desde la ISO | Probado | ISO 0.2 en vivo |
| `apt full-upgrade` | Pendiente | Con la ISO 0.2 |
| Migración 0.1.x → 0.2 con `jaime0-update` | **Simulado** (13-11-2026) | Partiendo de la ISO 0.1 en vivo sin nada de 0.2: instalación manual de `jaime0-update` según `docs/actualizaciones.md` (firma y carga verificadas), publicación 0.2 servida por HTTPS local con una clave de prueba, `/run/live` oculto para que la sesión pase por instalada. Resultado: 8 paquetes nuevos instalados, sistema y configuración en 0.2 en 42 s, personalización de `kitty.conf` conservada con su `.jaime0-nuevo`, dunst y `notificaciones-waybar` retirados, indicador de la barra que aparece y desaparece, y `verificar-sesion.sh` correcto tras volver a entrar. **Pendiente:** un sistema instalado de verdad, con reinicio, y la publicación firmada con la clave oficial |
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
