# Recuperación y mantenimiento

Qué hace Jaime0 para volver atrás cuando algo sale mal, qué no puede hacer todavía y por qué.

## Lo que hay hoy

| Problema | Cómo se recupera | Alcance |
|---|---|---|
| Una actualización de Jaime0 sale mal | `jaime0-update revertir` (sistema) y `jaime0-update revertir --usuario` | Solo los archivos de Jaime0 (configuración, scripts, temas). Copia de cada archivo antes de cambiarlo |
| Una actualización se corta a medias (apagón, error) | Se deshace sola al volver a ejecutar `jaime0-update`, o `sudo jaime0-update recuperar` | Igual: archivos de Jaime0 |
| Una configuración tuya entra en conflicto | Se conserva la tuya; la nueva queda al lado (`.jaime0-nuevo`). `jaime0-update resolver` | Archivo a archivo |
| La gráfica no deja arrancar el escritorio | Entrada **Modo seguro** en el menú de arranque (`nomodeset`) y consola de reparación | Arranque |
| Un paquete de Debian se rompe al actualizar | **Sin Btrfs: no hay vuelta atrás automática.** Con Btrfs y snapper: ver abajo | — |

## Estudio: Btrfs con instantáneas

**Objetivo:** poder deshacer también los cambios de paquetes de Debian, no solo los archivos de Jaime0.

### Lo comprobado (Debian Forky, noviembre de 2026)

| Pieza | Resultado | Cómo se comprobó |
|---|---|---|
| snapper 0.10.6 | Disponible. Trae `/etc/apt/apt.conf.d/80snapper`: **cada operación de apt crea una instantánea antes y otra después** si existe la configuración `root` | Instalado en la VM |
| `snapper create -t pre/post -p` y `undochange` | Funcionan sin D-Bus (`--no-dbus`); `undochange PRE..POST` devolvió un archivo cambiado y borró uno creado | Btrfs real (imagen de 1 GB) en la VM |
| Calamares 3.4.3 | Sabe crear subvolúmenes (`btrfsSubvolumes` en `mount.conf`, por defecto `@` → `/` y `@home` → `/home`), los escribe en el fstab con `subvol=` y crea un subvolumen aparte para el archivo de intercambio | Código de los módulos `mount` y `fstab` de la VM |
| grub-btrfs (arrancar instantáneas desde el menú de GRUB) | **No está en Debian** | `apt-cache` |
| `/boot` | En Jaime0 es una partición ext4 aparte (necesaria para LUKS con la clave pedida una sola vez) | `partition.conf` |

### Lo que daría y lo que no

- **Paquetes:** con la configuración de snapper hecha, `sudo snapper undochange PRE..POST` deshace una operación de apt o una actualización de Jaime0. `jaime0-update` ya crea su propio par de instantáneas (antes de instalar los paquetes nuevos y después de cambiar los archivos), las anota en `/var/lib/jaime0/ultima.json` y `jaime0-update revertir` indica la orden exacta.
- **Núcleo y GRUB: no.** `/boot` está fuera de Btrfs. Si se deshace una actualización que cambió el núcleo, `/boot` conserva el núcleo nuevo y el sistema vuelto atrás no tiene sus módulos. Debian guarda el núcleo anterior y se puede elegir en **Opciones avanzadas** de GRUB, pero no es automático.
- **Arrancar una instantánea:** sin grub-btrfs no se puede elegir desde el menú. Si el sistema no arranca, la recuperación es desde el USB en vivo: montar el disco y sustituir el subvolumen `@` por una instantánea.
- **`snapper rollback` no sirve tal cual** con la disposición de Calamares (`subvol=@` en el fstab): esa orden cambia el subvolumen por defecto, pero el fstab sigue montando `@`.

**Conclusión: con Btrfs y snapper, Jaime0 podría deshacer cambios de paquetes y de archivos mientras el sistema arranca. No sería un rollback completo:** ni el núcleo ni GRUB vuelven atrás, y un sistema que no arranca se recupera a mano desde el USB.

### Decisión

1. **Hecho:** `jaime0-update` crea instantáneas pre/post cuando `/` está en Btrfs con la configuración `root` de snapper; si snapper falla, la actualización sigue y avisa. No hace nada en ext4. Probado con pruebas automáticas y la orden comprobada en un Btrfs real.
2. **Pendiente de la ISO 0.2 (fase de integración):** ofrecer Btrfs en el instalador **como opción** (ext4 sigue por defecto), con:
   - `partition.conf`: `availableFileSystemTypes: [ "ext4", "btrfs" ]`, y la partición del sistema sin sistema de archivos fijo para que use el elegido.
   - `mount.conf`: subvolúmenes `@` (`/`), `@home`, `@log` (`/var/log`) y `@cache` (`/var/cache`), para que las instantáneas no guarden registros ni cachés; opciones `noatime,compress=zstd:1`.
   - Un paso `shellprocess` tras instalar: si `/` es Btrfs, `snapper --no-dbus -c root create-config /` con un límite de 10 instantáneas numeradas y sin las horarias (`TIMELINE_CREATE="no"`), y `snapper-cleanup.timer` activo.
   - `snapper` y `btrfs-progs` en la ISO.
   
   No se ha cambiado el instalador ahora porque no se puede probar sin compilar la ISO, y un error ahí deja equipos sin instalar. Se hará junto con las pruebas de instalación.
3. **Futuro:** un asistente en el USB en vivo (`jaime0-recuperar`) que liste las instantáneas de un disco Btrfs y sustituya `@` por la elegida.

## Cortafuegos

UFW viene activado: **entrante denegado, saliente permitido y ninguna regla abierta** (Jaime0 no trae servidores). Las reglas base de UFW ya dejan pasar lo que necesita un equipo cliente: respuestas a tus conexiones, DHCP, ICMP/ICMPv6 y mDNS. Se carga en el arranque antes de la red y no deja ningún proceso en marcha. No registra los paquetes bloqueados, para no llenar el diario con difusiones de la red.

```bash
sudo ufw status verbose
```
```bash
sudo ufw allow 22/tcp
```

Para investigar algo: `sudo ufw logging low`. Probado en la VM: navegación, DNS, `apt update`, DHCP y SLAAC funcionan; un puerto abierto en el equipo (servidor de prueba en el 8000) no responde desde otra red con el cortafuegos activo y sí sin él.

## zram

En equipos con **8 GiB de RAM o menos**, parte de la memoria se usa como swap comprimido (zstd): la mitad de la RAM, como mucho 4 GiB, con prioridad sobre el archivo de intercambio del instalador. Solo ocupa memoria lo que se comprime de verdad (unos 20 KiB en reposo). Con más de 8 GiB no se crea.

Configuración: `/etc/systemd/zram-generator.conf`. Para desactivarlo, borra la sección `[zram0]` y reinicia, o arranca una vez con el parámetro `systemd.zram=0`.

## Flatpak (opcional)

No viene instalado. Si lo quieres:

```bash
jaime0-flatpak activar
```

Explica qué va a hacer y pregunta antes: instala `flatpak` con apt y añade Flathub para todo el sistema. `jaime0-flatpak estado` muestra cómo está y `jaime0-flatpak desactivar` lo quita (pregunta antes de desinstalar aplicaciones). Las aplicaciones aparecen en el lanzador después de cerrar sesión y volver a entrar.

## Avisos de actualizaciones de Debian

Forky es la rama de pruebas de Debian: no tiene repositorio de seguridad propio y las correcciones llegan con las actualizaciones normales. Para saber cuáles importan:

- `/etc/apt/apt.conf.d/20jaime0-listas` hace que `apt-daily` refresque las listas de paquetes una vez al día. **Solo las listas: no descarga ni instala nada.**
- `jaime0-update comprobar` (el temporizador diario del aviso) cuenta los paquetes por actualizar y, con **debsecan**, cuáles corrigen vulnerabilidades conocidas según el rastreador de seguridad de Debian.
- Si hay correcciones de seguridad, el icono de la barra se pone en ámbar y llega una notificación (una vez por cada conjunto nuevo). Los paquetes normales pendientes no molestan: se ven con `jaime0-update comprobar`.
- Se instalan cuando quieras: `sudo apt full-upgrade`, o `jaime0-update`, que lo ofrece al final.

Medido en la VM: la comprobación tarda unos 5 s (consulta a security-tracker.debian.org incluida). En ese momento había 49 paquetes por actualizar y ninguno con correcciones de seguridad disponibles.
