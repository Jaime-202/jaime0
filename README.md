# Jaime0

Sistema operativo ligero, en vivo e instalable, basado en Debian Forky (testing), con Hyprland sobre Wayland. Trae terminales en mosaico sobre negro profundo, con un verde discreto que solo marca lo activo, un escritorio vacío al entrar, un instalador gráfico propio y actualizaciones sin reinstalar con `jaime0-update`.

Este repositorio contiene todo lo necesario para reconstruir la imagen: configuración de live-build, dotfiles de `/etc/skel`, hooks y scripts de verificación. La ISO lista para usar está en [Releases](https://github.com/Jaime-202/jaime0/releases).

> **Estado:** probado solo en máquinas virtuales (VirtualBox, BIOS y UEFI con arranque seguro). Todavía no se ha probado en un equipo físico. Revisa [Qué no se ha probado](#qué-no-se-ha-probado) antes de instalarlo en un equipo con datos importantes, y haz copia de seguridad.

![Mosaico con btop, Neovim y Fastfetch](capturas/mosaico.png)

| Escritorio al entrar | Lista de atajos |
|---|---|
| ![Escritorio vacío](capturas/escritorio-vacio.png) | ![Atajos](capturas/atajos.png) |
| **Instalador** | **Acceso** |
| ![Instalador](capturas/instalador.png) | ![Acceso](capturas/acceso.png) |

## Características

- **Ligero:** unos 530 MiB de RAM con el escritorio en reposo y arranque en unos 15 s (sistema instalado 0.2.0-beta.1, medido con `free -m` y `systemd-analyze` en una VM UEFI con 4 GiB), sin applets residentes ni XWayland activo.
- **Hyprland con configuración Lua**, con mosaico `dwindle`, bordes finos, ventanas opacas, blur mínimo y animaciones cortas.
- **Barra fina** (26 px), opaca y continua: escritorios a la izquierda, aplicaciones ancladas en el centro y estado y hora a la derecha. No sondea lo que llega por eventos: el reloj se redibuja una vez por minuto, y la campana y las ancladas solo cuando cambian.
- **Aplicaciones ancladas:** hasta 6 en el centro de la barra. Un punto marca las abiertas; al pulsar, se enfoca su ventana o se inicia. Se gestionan con `jaime0-anclar firefox`, `jaime0-anclar quitar firefox` o desde `jaime0-ajustes`.
- **Actualizaciones sin reinstalar:** `jaime0-update` instala versiones firmadas desde GitHub Releases (canales stable, beta y experimental), respeta tus personalizaciones, guarda copias y puede revertir. Los paquetes de Debian siguen con `apt`. Ver [docs/actualizaciones.md](docs/actualizaciones.md).
- **Ajustes en un solo sitio:** `jaime0-ajustes` cambia acento, fondo, separación, bordes, esquinas, opacidad, desenfoque, animaciones y altura y posición de la barra, y lo aplica al momento. Tus ajustes viven en `~/.config/jaime0/ajustes` y ninguna actualización los toca. Ver [docs/ajustes.md](docs/ajustes.md).
- **Comando `atajos`:** lista todos los atajos reales y permite añadir los tuyos, comprobando antes que la configuración es válida.
- **Instalador gráfico** basado en Calamares: borrar el disco, instalar junto a otro sistema o particionar a mano, con cifrado LUKS opcional y sin necesidad de red.
- **Arranque seguro (Secure Boot):** con shim y GRUB firmados por Debian, en el sistema en vivo y en el instalado.
- **BIOS y UEFI**, y arranque desde USB grabado en modo imagen.
- **Modo seguro** en el menú de arranque, para equipos cuya gráfica dé problemas.

## Requisitos

| | Mínimo |
|---|---|
| Procesador | x86-64 |
| Memoria | 2 GiB |
| Disco | 15 GiB |
| Gráfica | Intel, AMD o NVIDIA con Nouveau, con aceleración compatible con Wayland (NVIDIA propietario: ver [Tarjetas NVIDIA](#tarjetas-nvidia)) |
| USB | 4 GB o más para grabar la ISO |

## Instalación

### 1. Descargar y comprobar la ISO

Descarga `jaime0-*-amd64.iso` y su `.sha256` desde [Releases](https://github.com/Jaime-202/jaime0/releases). Para comprobarla en Linux, desde la carpeta de la descarga:

```bash
sha256sum -c jaime0-*-amd64.iso.sha256
```

En Windows, compara la suma que muestra este comando con la del archivo `.sha256`:

```powershell
Get-FileHash .\jaime0-*-amd64.iso -Algorithm SHA256
```

### 2. Grabar en un USB

Grabar **borra todo el contenido del USB**.

**Windows, con [Rufus](https://rufus.ie):** elige la ISO, pulsa **Empezar** y selecciona **Escribir en modo Imagen DD**. El modo ISO de Rufus no se ha probado.

**Linux**, sustituyendo `/dev/sdX` por tu USB (compruébalo antes con `lsblk`):

```bash
sudo dd if=jaime0-AAAAMMDD-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

### 3. Arrancar e instalar

Arranca el equipo desde el USB. El sistema entra solo en la sesión en vivo.

| Dato | Valor |
|---|---|
| Usuario en vivo | `user` |
| Contraseña en vivo | `live` |
| Instalar | `SUPER + Espacio` y busca **Instalar el sistema** |
| Acceso tras instalar | Pantalla de texto: usuario, Intro, contraseña, Intro |

El usuario que crees en el instalador hereda toda la configuración. El equipo se llama `jaime0` por defecto.

Con cifrado, `/boot` queda sin cifrar y la clave se pide una sola vez al arrancar. El registro del instalador queda en `~/instalador.log` de la sesión en vivo.

### Si la pantalla se queda en negro o no entra al escritorio

En el menú de arranque del USB elige **Modo seguro**, que arranca con `nomodeset`. En un sistema ya instalado, elige en GRUB **Opciones avanzadas** y la entrada **(modo seguro)**.

Si Hyprland no puede abrirse, Jaime0 muestra un mensaje con la causa más probable y una consola para reparar el sistema. Con `nomodeset` la gráfica queda desactivada, así que el escritorio no llegará a abrirse: ese modo sirve para entrar y arreglar el controlador.

### Tarjetas NVIDIA

Por defecto se usa el controlador libre Nouveau, que puede ir lento o fallar en tarjetas recientes. Estos pasos instalan el controlador propietario de Debian; **no se han probado**:

```bash
sudo apt update
```
```bash
sudo apt install linux-headers-amd64 nvidia-driver firmware-misc-nonfree
```

Añade `nvidia-drm.modeset=1` a `GRUB_CMDLINE_LINUX_DEFAULT` en `/etc/default/grub.d/90-hypr.cfg`, ejecuta `sudo update-grub` y reinicia. Con arranque seguro, el módulo necesita además una clave MOK propia (`sudo dpkg-reconfigure nvidia-kernel-dkms` la propone); si no quieres gestionarla, desactiva el arranque seguro.

## Uso

### Atajos de teclado

`SUPER + F1` o el comando `atajos` muestran siempre la lista completa y real.

**Programas y menús**

| Atajo | Acción |
|---|---|
| `SUPER + Intro` | Terminal (Kitty) |
| `SUPER + Espacio` | Lanzador de aplicaciones |
| `SUPER + R` | Ejecutar una orden |
| `SUPER + Tab` | Cambiar de ventana (lista) |
| `SUPER + E` | Thunar |
| `SUPER + B` | Navegador (avisa si no hay ninguno instalado) |
| `CTRL + SHIFT + Esc` | Monitor del sistema (btop) |
| `SUPER + A` | Control de sonido |
| `SUPER + W` | Red y Wi-Fi |
| `SUPER + SHIFT + V` | Historial del portapapeles |
| `SUPER + N` / `SUPER + SHIFT + N` | Volver a mostrar la última notificación / cerrar todas |
| `SUPER + L` | Bloquear la pantalla |
| `SUPER + Escape` | Menú de energía |
| `SUPER + SHIFT + R` | Recargar la configuración de Hyprland |
| `SUPER + F1` | Lista de todos los atajos |

**Ventanas y escritorios**

| Atajo | Acción |
|---|---|
| `SUPER + Q` | Cerrar ventana |
| `SUPER + F` / `SUPER + M` | Pantalla completa / maximizar |
| `SUPER + V` / `SUPER + C` | Ventana flotante / centrarla |
| `SUPER + J` / `SUPER + P` | Cambiar la orientación del mosaico / pseudo-mosaico |
| `SUPER + flechas` | Mover el foco |
| `SUPER + SHIFT + flechas` | Mover la ventana a izquierda, derecha, arriba o abajo |
| `SUPER + CTRL + flechas` | Redimensionar la ventana |
| `SUPER + 1-9` / `SUPER + SHIFT + 1-9` | Ir a un escritorio / mover la ventana a él |
| `SUPER + Retroceso` | Volver al escritorio anterior |
| `SUPER + rueda del ratón` | Escritorio siguiente o anterior |
| `SUPER + arrastrar` (clic izquierdo / derecho) | Mover / redimensionar con el ratón |
| Arrastrar el borde de una ventana | Redimensionarla |

**Capturas y teclas especiales**

| Atajo | Acción |
|---|---|
| `Impr Pant` | Captura de un área |
| `SHIFT + Impr Pant` | Captura de la pantalla entera |
| `SUPER + Impr Pant` | Captura de la ventana activa |
| Teclas de volumen, silencio y micrófono | Subir, bajar, silenciar |
| Teclas de brillo | Subir o bajar el brillo |
| Teclas de reproducción | Reproducir o pausar, pista siguiente o anterior |

Las capturas van a `Imágenes/Capturas` y al portapapeles. La pantalla se bloquea a los 10 minutos sin uso, se apaga al minuto siguiente y el equipo se suspende a los 30 minutos (en la sesión en vivo no).

### Ajustes

```bash
jaime0-ajustes ver
```
```bash
jaime0-ajustes poner acento cian
```
```bash
jaime0-ajustes poner barra_posicion abajo
```

Cada cambio se aplica al momento y se guarda en `~/.config/jaime0/ajustes`, que solo contiene lo que has cambiado. `jaime0-ajustes restablecer CLAVE` vuelve al valor de fábrica. Todos los ajustes y sus límites: [docs/ajustes.md](docs/ajustes.md).

### Aplicaciones ancladas

```bash
jaime0-anclar firefox
```
```bash
jaime0-anclar quitar thunar
```
```bash
jaime0-anclar mover firefox 1
```

`jaime0-anclar` sin argumentos muestra las ancladas y `jaime0-anclar disponibles`, las que se pueden anclar. El nombre puede ser corto: `firefox` encuentra `firefox-esr`. Vienen ancladas Kitty y Thunar, y puedes quitarlas. Detalles en [docs/ajustes.md](docs/ajustes.md#aplicaciones-ancladas).

### El comando `atajos`

Lee la configuración que Hyprland tiene cargada, así que la lista siempre es la real.

```bash
atajos
```
```bash
atajos añadir "SUPER+O" "kitty -e nvim" "Abrir Neovim"
```
```bash
atajos quitar "SUPER+O"
```
```bash
atajos editar
```

Antes de aplicar un cambio, `atajos` comprueba la configuración con `Hyprland --verify-config`; si hay un error, no cambia nada. Los atajos propios se guardan en `~/.config/hypr/atajos-usuario.lua`.

### Instalar programas

Jaime0 usa los repositorios de Debian Forky, así que se instala con `apt`:

```bash
sudo apt update
```
```bash
sudo apt install nombre-del-programa
```

Lo instalado desde la sesión en vivo se pierde al reiniciar.

**Firefox:**

```bash
sudo apt install firefox-esr firefox-esr-l10n-es-es
```

**Brave**, desde su repositorio oficial ([brave.com/linux](https://brave.com/linux/)):

```bash
sudo curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
```
```bash
sudo curl -fsSLo /etc/apt/sources.list.d/brave-browser-release.sources https://brave-browser-apt-release.s3.brave.com/brave-browser.sources
```
```bash
sudo apt update
```
```bash
sudo apt install brave-browser
```

Después ábrelo con `SUPER + B`. Para abrir PDF, imágenes o comprimidos desde Thunar, instala también el programa que prefieras, como `zathura`, `imv` o `file-roller`. Solo están bloqueados los escritorios completos, `nautilus`, `dolphin` y Xorg.

### Programas X11

XWayland viene instalado pero apagado, y así se ahorran unos 120 MB. Para usar un programa X11, cambia `enabled = false` por `true` en el bloque `xwayland` de `~/.config/hypr/hyprland.lua` y vuelve a iniciar la sesión.

### Probar en VirtualBox

Activa la aceleración 3D (`--accelerate-3d on --vram 128`) y usa ratón de tipo tableta USB (`--mouse usbtablet`). Sin 3D, Hyprland no arranca.

Dentro de una VM, Jaime0 se aligera solo: los programas dibujan por software, se apagan el blur y las animaciones, el cursor se dibuja por software y la escala queda fija en 1. En hardware real no se aplica nada de esto.

En Windows con la **Integridad de memoria** activada, VirtualBox funciona sobre Hyper-V y va bastante más lento, incluido el ratón.

## Paleta

Negro profundo `#080b0d` y negro secundario `#101519` de base, bordes `#26343a`, gris claro `#d8e2e8` y gris secundario `#71818c` para el texto, y un único acento verde `#54e58a` para lo importante: ventana y escritorio activos, selección y botón principal. El cian `#55cde0` aparece solo como acento secundario. Tonos derivados: superficie `#151c21`, gris medio `#a7b4bc`, gris apagado `#45545c` y blanco de selección `#eef4f7`. El rojo `#d9625b` y el ámbar `#d9a54a` solo avisan de errores. La consola de texto (`vt.default_*`), el acceso y los 16 colores ANSI de Kitty usan la misma paleta, con los colores de `git` y `ls` apagados pero distinguibles.

El fondo de pantalla es propio: una malla digital oscura con líneas geométricas y pequeños puntos verdes, generada de forma determinista con `scripts/generar-fondo.py` (Python y Pillow) y guardada en el repositorio. La compilación no descarga nada para él.

## Qué lleva

| Área | Programas |
|---|---|
| Escritorio | Hyprland, Waybar, Rofi, Dunst, swaybg, `lxpolkit`, Quickshell (aplicación de ajustes) |
| Acceso | `greetd` con `tuigreet`, en la consola |
| Terminal | Kitty, Zsh, Starship, Fastfetch, btop, Neovim |
| Archivos | Thunar, con `gvfs` para montar USB al pulsarlos |
| Sistema | PipeWire con `pavucontrol`, NetworkManager (`nmtui`), Bluetooth con `blueman`, portapapeles, capturas, firmware |
| Herramientas | `git`, `curl`, `wget`, `unzip`, `openssh-client`, `atajos` |
| Arranque e instalación | Plymouth, GRUB, shim firmado, `cryptsetup` y Calamares; `os-prober` y `ntfs-3g` para convivir con otros sistemas |

La red se gestiona desde la barra, con `nmtui`, y el Bluetooth con `blueman-manager`. La imagen no trae navegador.

## Reconstruir la ISO

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

   `lb build` llama antes a `scripts/empaquetar-actualizacion.py` para generar el manifiesto de la versión (`usr/share/jaime0/version`) que la ISO instala como punto de partida de `jaime0-update`.

6. Para verificarlo, copia los scripts junto a `chroot/` y ejecútalos. Instalan herramientas de prueba en `chroot/`, así que hay que hacerlo después de generar la ISO:

   ```bash
   cp scripts/verificar-*.sh scripts/coords-*.sh scripts/atajos-prueba.sh . && ./verificar-todo.sh
   ```

   Las pruebas en vivo necesitan una VM con aceleración 3D. `scripts/coords-barra.sh` guarda las posiciones de los módulos de la barra a 1280 px: si cambia la barra, hay que volver a medirlas.

   Las pruebas del actualizador y de los ajustes no necesitan la ISO: `python3 -m unittest discover -s pruebas -v`.

Para recompilar, ejecuta `sudo lb clean` y repite desde `lb config`. Forky cambia a diario: si llega otra versión de Hyprland, revalida la configuración con `Hyprland --verify-config`.

### Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `auto/` | Opciones de live-build |
| `config/package-lists/` | Paquetes de la imagen |
| `config/hooks/normal/` | Ajustes que se aplican al compilar |
| `config/archives/` | Preferencias de APT: bloqueo de escritorios y Xorg, fijado de Waybar |
| `config/bootloaders/` | Menú y tema de GRUB del medio en vivo |
| `config/includes.chroot_after_packages/` | Archivos del sistema: `/etc/skel`, instalador, scripts |
| `scripts/` | Construcción de Waybar y traducciones, fondo, empaquetado de actualizaciones y verificaciones |
| `publicaciones/` | Notas de cada versión publicada con `jaime0-update` |
| `pruebas/` | Pruebas automáticas del actualizador y de los ajustes |
| `docs/` | [Arquitectura](docs/arquitectura.md), [actualizaciones](docs/actualizaciones.md) y [ajustes](docs/ajustes.md) |
| `capturas/` | Capturas del sistema |

### Cambiar el nombre del sistema

Edita `PRODUCTO` en `config/includes.chroot_after_packages/usr/local/share/marca/marca.conf` y recompila. Llevan el nombre escrito a mano: `--iso-volume`, `--iso-application`, `--image-name` y `hostname=` en `auto/config`; `--greeting` en `etc/greetd/config.toml`; y `template` en `etc/calamares/modules/users.conf`. El logo es `etc/calamares/branding/hypr/logo.svg`.

## Decisiones técnicas

| Tema | Decisión | Motivo |
|---|---|---|
| Configuración de Hyprland | `hyprland.lua` con `hl.window_rule` | Hyprland 0.56 y 0.57 usan Lua |
| Acceso | `greetd` con `tuigreet` | Mucho más ligero que SDDM con su compositor |
| Agente de permisos | `lxpolkit` | El de KDE arrastra KDE Frameworks |
| Waybar | `0.15.0-1+hypr1`, parcheado, fijado y retenido | El de Debian no cambia de escritorio con la configuración Lua |
| Actualizaciones | `jaime0-update`: carga firmada (Ed25519) + `apt` | Actualiza los archivos propios sin ISO ni repositorio APT propio; los paquetes siguen con el gestor oficial. Detalles en [docs/arquitectura.md](docs/arquitectura.md) |
| Red y Bluetooth | Se abren desde la barra | Sin applets residentes |
| Qt | Lo necesitan Quickshell (aplicación de ajustes) y el instalador; Calamares se retira al instalar | Quickshell no es imprescindible: sin él, `jaime0-ajustes` funciona desde la terminal y el escritorio arranca igual |
| Base | `debootstrap` con `minbase`, sin recomendados | Lleva solo lo necesario |

## Problemas conocidos

- **Waybar y Debian:** Debian tiene marcado Waybar para salir de testing el 22-11-2026 por errores en dependencias lejanas. La versión instalada está parcheada, fijada y retenida (`apt-mark hold`), así que una actualización no la retira. Si en el futuro una biblioteca suya desaparece, `apt` retendrá esa actualización. Una compilación nueva de la ISO posterior a esa fecha podría no resolver sus dependencias de compilación.
- **Rama de pruebas:** Forky es Debian testing y una actualización puede romper algo, en especial si cambia Hyprland. Durante el desarrollo pasó de 0.56 a 0.57 y hubo que retirar una opción.
- **Fallos aislados en VirtualBox:** en pruebas sobre Windows con VirtualBox funcionando encima de Hyper-V (Integridad de memoria activada), un arranque de cada 11 en una VM se quedó congelado por un fallo de `systemd`, con un trozo de `libc` leído como ceros en memoria, y otra VM reanudada tras muchas horas tuvo programas que fallaban al azar. Reiniciarla lo resolvió: ocho reinicios seguidos entraron bien y no se pudo reproducir. Todo apunta a la capa de virtualización y no a Jaime0, pero no se ha podido demostrar. Por si ocurre, Jaime0 reinicia solo si `systemd` falla al arrancar (`CrashAction=reboot`). No se ha visto en otras condiciones, y no se ha probado en hardware real.
- **Textos en inglés:** `tuigreet` y `swaylock` no tienen traducción. Algunas entradas de GRUB y las de otros sistemas salen en inglés.
- **Instalador:** el mapa, el teclado de muestra y la franja de particiones usan colores fijos de Calamares.
- **`btop` en mosaicos muy pequeños:** necesita 80x24. Abierto con `CTRL + SHIFT + Escape` usa letra de 7 puntos y cabe en un cuarto de pantalla a 1280x800; más pequeño, lo avisa.
- **Teclados virtuales:** algunos usan códigos de tecla que coinciden con las teclas multimedia y Hyprland ejecuta esos atajos. Con un teclado físico no pasa.

## Qué no se ha probado

Todas las pruebas se han hecho en VirtualBox, en UEFI con arranque seguro y en BIOS. Sin un equipo físico **no se puede garantizar** nada de lo siguiente:

- Arranque en hardware real y desde un USB físico (se probó la imagen conectada como disco en la VM)
- Gráficas reales: Intel, AMD, Nouveau y NVIDIA propietario
- Wi-Fi y Bluetooth reales
- Teclado, touchpad, cierre de tapa, batería, teclas de brillo y suspensión de un portátil
- Sonido escuchado de verdad
- Discos NVMe (VirtualBox los ofrece solo con su paquete de extensión)
- Varios monitores y escalado en pantallas HiDPI

Si lo pruebas en un equipo físico, abre una [incidencia](https://github.com/Jaime-202/jaime0/issues) con lo que funcione y lo que no.

## Licencia

El trabajo original se publica bajo licencia [MIT](LICENSE). Los archivos derivados de otros proyectos y el software incluido en la ISO conservan sus licencias: ver [CREDITS.md](CREDITS.md) y [SOURCES.md](SOURCES.md). Jaime0 no está afiliado al proyecto Debian.
