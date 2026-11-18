# Código fuente del software incluido en la ISO

La ISO de Jaime0 contiene software libre de terceros, parte bajo la GPL. Esta página indica cómo obtener su código fuente correspondiente.

## Paquetes de Debian

La lista exacta de paquetes y versiones de la ISO publicada está en [`SOURCES-paquetes.txt`](SOURCES-paquetes.txt). Cada uno se puede descargar desde Debian, en un sistema con líneas `deb-src` de Forky:

```bash
apt-get source nombre-del-paquete=version
```

Si la versión ya no está en la rama actual, Debian conserva todas las versiones publicadas en [snapshot.debian.org](https://snapshot.debian.org/), donde se puede buscar cada paquete fuente por nombre y versión.

## Waybar

Waybar se compila aparte con [`scripts/construir-waybar.sh`](scripts/construir-waybar.sh): parte del paquete fuente `waybar 0.15.0-1` de Debian Forky y aplica los cambios a `src/modules/hyprland/workspace.cpp` que se ven en el propio script.

## Otros componentes

- **JetBrainsMono Nerd Font:** se descarga al compilar desde [ryanoasis/nerd-fonts](https://github.com/ryanoasis/nerd-fonts), con versión y SHA256 fijados en `config/hooks/normal/0330-fuente-nerd.hook.chroot`.
- **Traducciones del instalador:** los archivos `.qm` y `.mo` salen de las traducciones de [Calamares](https://github.com/calamares/calamares) con las correcciones de `scripts/construir-traduccion.py` y `scripts/construir-traduccion-extra.py`.
- **Configuración de Jaime0:** este repositorio.

Si necesitas el código de alguna versión y no lo encuentras, abre una [incidencia](https://github.com/Jaime-202/zyron/issues).
