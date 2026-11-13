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
| `test_jaime0_diagnostico.py` | Diagnóstico: que no salgan datos personales y que no falle sin comandos |

## 2. Sesión en marcha

```bash
bash scripts/verificar-sesion.sh
```

Desde una terminal de la sesión (VM o equipo real). Comprueba Hyprland, los procesos de la sesión, los ajustes de ida y vuelta, las ancladas, los widgets y las notificaciones, y deja tus ajustes como estaban.

**Resultado (13-11-2026, VM `jaime0-pruebas`, sesión en vivo 0.1 con los archivos 0.2 encima, tras entrar de nuevo con tuigreet):** 21 correctos, 0 fallos.

## 3. Pruebas en máquina virtual

VM de VirtualBox 7.1 en Windows 11: UEFI, 4 GB, 4 CPU, aceleración 3D. Las pruebas de la 0.2 se han hecho sobre la ISO 0.1.x en vivo con los archivos 0.2 copiados encima, porque aún no hay una ISO 0.2 compilada.

| Prueba | Estado | Notas |
|---|---|---|
| Arranque en vivo UEFI | Probado (0.1.x) | |
| Arranque BIOS, Secure Boot, instalación normal, LUKS, junto a otro sistema, ISO conectada como USB | Probado en la 0.1.x (ver README) | **Pendiente con la ISO 0.2** |
| Inicio de sesión 0.2 completo (ajustes, ancladas, widgets, barra, notificaciones) | Probado | `verificar-sesion.sh` |
| `jaime0-ajustes`: todos los ajustes y la aplicación gráfica | Probado | Sin ratón: los clics llaman a las mismas órdenes |
| Redimensionar arrastrando el borde | Configuración probada | Arrastre con ratón **no probado** |
| Ancladas: abrir, enfocar, punto de abiertas | Probado | |
| Widgets (6), en caliente, consumo | Probado | Música con mpv |
| swaync, wob, modo noche, selector de color, nwg-displays | Probado | |
| Bloqueo hyprlock, clave incorrecta y correcta, relevo a swaylock | Probado | |
| Inactividad: bloqueo y pantalla apagada (tiempos cortos) | Probado | |
| Suspender y reanudar | **Parcial** | Bloquea antes y reanuda bloqueada. VirtualBox no despierta con la alarma del reloj, a veces tampoco con el teclado, y si queda congelada más de 3 min el vigilante de systemd reinicia logind y la red no vuelve sola. Es un efecto de la VM: **pendiente de hardware real** |
| `apt full-upgrade` | Pendiente | Con la ISO 0.2 |
| Migración 0.1.2 → 0.2 con `jaime0-update` | Pendiente | Necesita una publicación 0.2 firmada (fase de actualizaciones) |
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
