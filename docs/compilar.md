# Compilar la ISO

Hace falta un Debian 13 (recomendado en una máquina virtual dedicada) con unos 30 GB libres y conexión a internet:

```bash
sudo apt install live-build debootstrap squashfs-tools xorriso mtools dosfstools grub-pc-bin grub-efi-amd64-bin python3 git openssl
```

1. Clona el repositorio y entra en él. En adelante se trabaja desde esta carpeta.

2. Da permisos de ejecución:

   ```bash
   chmod +x auto/* config/hooks/normal/*.hook.* config/includes.chroot_after_packages/usr/local/bin/* config/includes.chroot_after_packages/usr/local/sbin/* config/includes.chroot_after_packages/usr/lib/live/config/* scripts/*.sh
   ```

3. Completa la carpeta del menú de GRUB con las plantillas que faltan, sin pisar las propias:

   ```bash
   cp -an /usr/share/live/build/bootloaders/grub-pc/. config/bootloaders/grub-pc/
   ```

4. Compila Waybar parcheado en un chroot de Forky desechable, con `/proc` montado y red, y deja el paquete en `config/packages.chroot/`:

   ```bash
   sudo ./scripts/construir-waybar.sh /ruta/al/chroot-forky config/packages.chroot
   ```

5. Compila:

   ```bash
   lb config
   ```
   ```bash
   sudo lb build
   ```

   La compilación descarga el repositorio de Brave y compila el módulo de NVIDIA para el núcleo de la ISO (unos minutos más).

6. Para verificarlo, copia los scripts junto a `chroot/` y ejecútalos. Instalan herramientas de prueba en `chroot/`, así que hay que hacerlo después de generar la ISO:

   ```bash
   cp scripts/verificar-*.sh scripts/coords-*.sh scripts/atajos-prueba.sh . && ./verificar-todo.sh
   ```

   Las pruebas en vivo necesitan una VM con aceleración 3D. `scripts/coords-barra.sh` guarda las posiciones de los módulos de la barra a 1280 px: si cambia la barra, hay que volver a medirlas.

   La ISO terminada se verifica sin arrancarla (arranque BIOS y UEFI, sistema de archivos, permisos, claves, versión, paquetes y diferencias con el repositorio), sin root:

   ```bash
   scripts/verificar-iso.sh jaime0-amd64.hybrid.iso --repo .
   ```

   Las comprobaciones que no necesitan la ISO (permisos, shellcheck, sintaxis de Python, JSON, Lua y QML, y las pruebas automáticas) están en `scripts/validar-repo.sh`, que GitHub Actions ejecuta en cada cambio. Qué se ha probado y qué falta: [docs/pruebas.md](pruebas.md).

Para recompilar, ejecuta `sudo lb clean` y repite desde `lb config`. Forky cambia a diario: si llega otra versión de Hyprland, revalida la configuración con `Hyprland --verify-config`.

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `auto/` | Opciones de live-build |
| `config/package-lists/` | Paquetes de la imagen |
| `config/hooks/normal/` | Ajustes que se aplican al compilar |
| `config/archives/` | Preferencias de APT: bloqueo de escritorios y Xorg, fijado de Waybar |
| `config/bootloaders/` | Menú y tema de GRUB del medio en vivo |
| `config/includes.chroot_after_packages/` | Archivos del sistema: `/etc/skel`, instalador, scripts |
| `scripts/` | Construcción de Waybar y traducciones, fondo y verificaciones |
| `pruebas/` | Pruebas automáticas (ajustes, ancladas, tiempo, diagnóstico, Control Center) |
| `.github/workflows/` | Validación automática en GitHub Actions (no publica nada) |
| `docs/` | [Arquitectura](arquitectura.md), [actualizaciones](actualizaciones.md), [ajustes](ajustes.md), [NVIDIA](nvidia.md), [recuperación y seguridad](recuperacion.md), [Control Center](control-center.md), [compilar](compilar.md) y [pruebas](pruebas.md) |
| `capturas/` | Capturas del sistema |
| `.claude/`, `CLAUDE-ROUTING.md` | Configuración de los agentes de Claude Code usados para desarrollar ZYRON |

## Cambiar el nombre del sistema

Edita `PRODUCTO` en `config/includes.chroot_after_packages/usr/local/share/marca/marca.conf` y recompila: es el único sitio donde está escrito. `auto/config` lo lee para la ISO y el nombre del equipo; los programas, el Control Center y GRUB lo leen al ejecutarse; y el hook `0395-marca` lo pone al compilar en los archivos con los marcadores `@PRODUCTO@` y `@PRODUCTO_MINUSCULAS@` (acceso de greetd, usuario del instalador y política de polkit). `pruebas/test_integridad_repo.py` falla si el nombre aparece escrito en otro sitio. El logo está en `usr/local/share/marca/` (`zyron-simbolo.svg` y `zyron-logo.svg`; el del instalador, `etc/calamares/branding/hypr/logo.svg`, es una copia del símbolo) y la animación de arranque en `usr/share/plymouth/themes/zyron/` (ver [arranque.md](arranque.md)). Los títulos internos de ventana («Jaime0 Control Center», «Ajustes de Jaime0») y los identificadores (`jaime0-*`, rutas, servicios) no cambian con el nombre: los usan las reglas de Hyprland y las instalaciones existentes.
