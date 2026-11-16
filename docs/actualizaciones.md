# Actualizaciones

Jaime0 se actualiza de dos maneras, cada una con lo suyo:

| Qué | Cómo | Cuándo |
|---|---|---|
| **Programas y sistema** (paquetes de Debian, Brave, el controlador de NVIDIA) | `apt`, desde sus repositorios oficiales | Cuando quieras: `actualizaciones` o `sudo apt full-upgrade` |
| **Lo propio de Jaime0** (configuración de Hyprland y la barra, scripts, temas) | Una ISO nueva | Al reinstalar |

Hasta la 0.2 existía `jaime0-update`, que descargaba versiones firmadas desde GitHub. Desde la 0.3 la ISO está pensada para un solo equipo, así que se ha retirado: menos piezas que mantener.

## El aviso de la barra

Una vez al día (y diez minutos después de arrancar) `actualizaciones comprobar` mira las listas de `apt` y, con **debsecan**, cuáles de los paquetes pendientes corrigen vulnerabilidades conocidas según el rastreador de seguridad de Debian. No usa la red por su cuenta: las listas las refresca `apt-daily`.

- Si hay correcciones de seguridad, aparece un icono ámbar en la barra y llega una notificación (una vez por cada conjunto nuevo).
- Los paquetes normales pendientes no molestan: Forky (testing) recibe cambios a diario.
- Nunca instala nada por su cuenta.

## Instalar

```bash
actualizaciones
```

Muestra lo pendiente y pregunta si instalarlo con `sudo apt full-upgrade`. Pulsar el icono de la barra hace lo mismo en una terminal. También vale directamente:

```bash
sudo apt update && sudo apt full-upgrade
```

Si instalaste en **Btrfs**, cada operación de `apt` crea una instantánea antes y otra después (snapper), y se puede deshacer: ver [recuperacion.md](recuperacion.md).

## El controlador de NVIDIA y el núcleo

Cuando `apt` instala un núcleo nuevo, DKMS vuelve a compilar el módulo de NVIDIA para él y lo firma con la clave de tu instalación, que ya está registrada: no hay que hacer nada. Si tras reiniciar `jaime0-nvidia` dice que el módulo no está cargado, el detalle está en `journalctl -b -k | grep -i nvidia`.

## Lo propio de Jaime0: una ISO nueva

Los cambios en la configuración de Jaime0 llegan reconstruyendo la ISO (ver el README) y reinstalando. Tus ajustes viven en `~/.config/jaime0/ajustes` y tus datos en `/home`: haz copia de ambos antes de reinstalar, o instala sin formatear la partición de `/home` si usas particionado manual.
