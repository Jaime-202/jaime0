# Recuperación y mantenimiento

Qué hace Jaime0 para volver atrás cuando algo sale mal, qué no puede hacer y por qué.

## Lo que hay

| Problema | Cómo se recupera | Alcance |
|---|---|---|
| Un paquete se rompe al actualizar | Instalado en **Btrfs**: `sudo snapper -c root list` y `sudo snapper undochange PRE..POST`. En **ext4**: no hay vuelta atrás automática | Btrfs: todo `/` salvo `/home`, `/var/log`, `/var/cache` y `/boot` |
| La gráfica no deja arrancar el escritorio | Entrada **Modo seguro** en el menú de arranque (`nomodeset`) y consola de reparación | Arranque |
| La NVIDIA no funciona | `jaime0-nvidia` dice qué falta; el escritorio sigue en la Intel | Solo lo abierto con `prime-run` |
| Has estropeado tu configuración | Copia el archivo de `/etc/skel/.config/...` sobre el tuyo, o `jaime0-ajustes restablecer CLAVE` | Archivo a archivo |

## Btrfs con instantáneas

El instalador ofrece Btrfs **como opción** (ext4 sigue por defecto; en el paso de particiones, "Sistema de archivos"):

- Subvolúmenes `@` (`/`), `@home`, `@log` (`/var/log`) y `@cache` (`/var/cache`), para que las instantáneas no guarden datos personales, registros ni cachés, y `@swap` para el archivo de intercambio. Opciones de montaje: las de Calamares (`relatime`, `discard=async`), sin compresión.
- Al instalar, `hypr-configurar-snapper` crea la configuración `root` de snapper: 10 instantáneas numeradas como mucho (5 importantes), sin las horarias, con `snapper-cleanup.timer` activo.
- El gancho de apt de snapper (`/etc/apt/apt.conf.d/80snapper`) crea **una instantánea antes y otra después de cada operación de apt**.

Para deshacer la última actualización:

```bash
sudo snapper -c root list
```
```bash
sudo snapper -c root undochange PRE..POST
```

Lo que **no** vuelve atrás:

- **Núcleo y GRUB.** `/boot` es una partición ext4 aparte (necesaria para LUKS con la clave pedida una sola vez). Si se deshace una actualización que cambió el núcleo, `/boot` conserva el nuevo. Debian guarda el anterior en **Opciones avanzadas** de GRUB.
- **Arrancar una instantánea.** grub-btrfs no está en Debian. Si el sistema no arranca, se recupera desde el USB en vivo: montar el disco y sustituir el subvolumen `@` por una instantánea.
- **`snapper rollback`** no sirve tal cual con la disposición de Calamares (`subvol=@` en el fstab).

Probado (13-11-2026, VM UEFI, Btrfs + LUKS): subvolúmenes y fstab, configuración de snapper, par de instantáneas de `apt install`, arranque con Plymouth y clave LUKS y sesión 21/21. Pendiente: `undochange` en el sistema instalado y el portátil real.

## Cortafuegos

UFW viene activado: **entrante denegado, saliente permitido y ninguna regla abierta**. Las reglas base dejan pasar lo que necesita un equipo cliente: respuestas a tus conexiones, DHCP, ICMP/ICMPv6 y mDNS. No registra los paquetes bloqueados.

```bash
sudo ufw status verbose
```
```bash
sudo ufw allow 22/tcp
```

Probado en la VM: navegación, DNS, `apt update`, DHCP y SLAAC funcionan; un puerto abierto en el equipo no responde desde otra red con el cortafuegos activo y sí sin él.

## zram

Con **8 GiB de RAM o menos**, parte de la memoria se usa como swap comprimido (zstd). El portátil para el que está pensada esta ISO tiene 16 GiB, así que ahí no se activa; queda para otros equipos. Configuración: `/etc/systemd/zram-generator.conf`.

## Actualizaciones de seguridad

Forky es la rama de pruebas de Debian: no tiene repositorio de seguridad propio y las correcciones llegan con las actualizaciones normales. El aviso de la barra (`actualizaciones`) dice cuáles importan: ver [actualizaciones.md](actualizaciones.md).
