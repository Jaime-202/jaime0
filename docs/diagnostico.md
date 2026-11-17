# Diagnóstico

`jaime0-diagnostico comprobar` revisa el equipo una vez, interpreta lo que encuentra y explica cada problema: qué se ha visto, por qué puede pasar, qué consecuencias tiene y qué hacer. No vigila nada de forma continua: las temperaturas, la memoria, el disco y la batería en tiempo real son cosa de **HEALTH** (`jaime0-servicio`, `jaime0-salud`).

```bash
jaime0-diagnostico comprobar           # en la terminal
jaime0-diagnostico comprobar --sudo    # también el diario del sistema, el registro del núcleo y SMART
jaime0-diagnostico historial           # problemas vistos, resueltos y reparaciones
jaime0-diagnostico reparar ID          # aplica la reparación de un problema
```

`--json` da una sola línea JSON (la que usa el Control Center). El informe de siempre (`jaime0-diagnostico`, `--pantalla`, `--sudo`) no cambia.

## Qué comprueba

| Área | Comprobaciones |
|---|---|
| HARDWARE | sensores de temperatura, gráficas detectadas, programas cerrados por falta de memoria en este arranque (`oom_kill`), raíz llena (menos de 1 GiB o 98 %) o en solo lectura, SMART (con `--sudo`), salud de la batería (menos del 50 %) |
| SYSTEM | unidades fallidas del sistema y de usuario (con sus últimas líneas del diario), mensajes críticos del arranque, `dpkg --audit`, errores de configuración de Hyprland, JSON de Waybar, avisos de `jaime0-ajustes`, permisos de lo que se ejecuta como root (ayudante de pkexec, política `es.jaime0.*` y `/usr/local/lib/jaime0`), actualización de ZYRON interrumpida, seguridad de Debian pendiente |
| GRAPHICS | NVIDIA (módulo cargado, construido para el núcleo en uso y para el siguiente, clave de Secure Boot, nouveau), sesión de Hyprland, monitores desactivados o sin usar, aceleración (modo seguro, sin controlador) |
| CONNECTIVITY | NetworkManager, conectividad (completa, limitada, portal), Wi-Fi (chip sin interfaz, bloqueos), Bluetooth (adaptador, bloqueos, servicio) |
| POWER | power-profiles-daemon (fallido, rendimiento limitado), batería y cargador, fallos al suspender o reanudar en este arranque |

## Estados

`OK`, `INFO`, `WARNING`, `ERROR` y `CRITICAL` dicen lo que se ha visto. `NO_DISPONIBLE` es que no se pudo comprobar (falta una herramienta o un permiso: por ejemplo, sin `--sudo` el diario del sistema no se lee, y eso **no** quiere decir que no haya errores). `NO_APLICA` es que el equipo no tiene esa pieza (sin NVIDIA, sin batería, sin Wi-Fi, o una máquina virtual). Ninguno de los dos es un problema.

En el resumen, `CRITICAL`, `ERROR`, `WARNING` e `INFO` cuentan problemas; `NO_DISPONIBLE` y `NO_APLICA`, comprobaciones.

## Cómo leer un problema

- **Título y gravedad:** p. ej. `NVIDIA DRIVER WARNING`.
- **Detectado:** los datos tal cual (`dkms status`, líneas del diario, permisos...), sin datos personales.
- **Causas probables:** nunca confirmadas; son las explicaciones más habituales para lo detectado.
- **Consecuencias** y **qué hacer**, en orden.
- **Reparación** (si la hay): las órdenes exactas que se ejecutarían.

Cada ejecución se guarda en `~/.local/state/jaime0/diagnosticos.jsonl` (las últimas 500) y cada problema en `diagnosticos.json`: primera y última vez, cuántas veces, si sigue activo o cuándo se resolvió, y las reparaciones con su resultado. Un problema solo se da por resuelto cuando la comprobación que lo vio ha podido mirar otra vez: si ahora falta un permiso, sigue como estaba.

## Reparaciones

`reparar ID` vuelve a comprobar el área, enseña lo que se va a modificar y las órdenes, pide confirmación `[s/N]` y solo entonces las ejecuta; después comprueba otra vez y anota el resultado. Sin una terminal interactiva no hace nada. Si el problema ya no está, lo dice y no hace nada.

| Problema | Reparación |
|---|---|
| Unidad de usuario fallida | `systemctl --user reset-failed` y `restart` de esa unidad |
| NetworkManager, Bluetooth o power-profiles-daemon fallidos | `sudo /usr/bin/systemctl reset-failed` y `restart` del servicio |
| Paquetes a medio instalar | `sudo /usr/bin/dpkg --configure -a` |
| Raíz llena | `sudo /usr/bin/apt-get clean` |
| Permisos inseguros | `chown root:root` y `chmod go-w` solo en las rutas afectadas |
| Actualización de ZYRON interrumpida | `sudo /usr/local/bin/jaime0-update recuperar` |
| NVIDIA sin módulo para un núcleo | `sudo /usr/sbin/dkms autoinstall -k NÚCLEO` (con la clave que ya hay); sin clave, `sudo /usr/local/bin/jaime0-nvidia recompilar` |
| NVIDIA instalada pero sin cargar | `sudo /usr/sbin/modprobe` del módulo |
| Configuración de Hyprland con errores | `hyprctl reload` (solo sirve si ya corregiste el archivo) |
| `config.jsonc` de Waybar roto | copia la de fábrica; antes guarda la tuya como `config.jsonc.antes-de-reparar-FECHA` |
| Wi-Fi o Bluetooth apagados | `nmcli radio wifi on` / `rfkill unblock bluetooth` |

Tras `sudo` van siempre rutas completas (el `secure_path` de ZYRON no incluye `/usr/local/bin`). Límite: nada que borre datos, nada sobre tus archivos sin copia, y nada que necesite decidir por ti (registrar la clave MOK, instalar cabeceras o paquetes, editar tu configuración): eso queda en «qué hacer».
