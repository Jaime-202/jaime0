# Actualizaciones

ZYRON se actualiza por dos caminos, cada uno con lo suyo:

| Qué | Con qué | Cómo |
|---|---|---|
| **Paquetes de Debian**: núcleo, Hyprland, programas, bibliotecas, Brave, el controlador de NVIDIA | `apt`, desde sus repositorios oficiales | `actualizaciones` (o `sudo apt full-upgrade`) |
| **Lo propio de ZYRON**: configuración de Hyprland y la barra (`/etc/skel` y tu `~/.config`), scripts de `/usr/local/bin`, el servicio y la ventana del Control Center, temas, fondo, unidades de systemd propias | `jaime0-update`, desde publicaciones firmadas de GitHub Releases | `jaime0-update` |

No hay un gestor de paquetes paralelo ni `git pull` sobre el sistema. Ninguno de los dos instala nada por su cuenta: avisan, y tú decides.

## El aviso diario y la barra

Una vez al día (y diez minutos después de entrar) el temporizador de usuario `actualizaciones-aviso.timer` ejecuta, en este orden:

1. `actualizaciones comprobar --notificar --silencioso`: mira las listas de `apt` (las refresca `apt-daily`) y, con **debsecan**, cuáles de los paquetes pendientes corrigen vulnerabilidades conocidas.
2. `jaime0-update comprobar --notificar --silencioso`: mira si hay una versión de ZYRON más nueva en tu canal. No repite la consulta de `apt`: usa lo que acaba de dejar el paso anterior.

El icono de la barra (`actualizaciones barra`, sin red) aparece si hay correcciones de seguridad de Debian (ámbar) o una versión de ZYRON más nueva que la instalada; el texto emergente dice cuál. Los paquetes normales pendientes no molestan: Forky (testing) recibe cambios a diario. Llega una notificación por cada conjunto nuevo de correcciones de seguridad y otra por cada versión nueva de ZYRON. Al pulsar el icono se abre una terminal con `actualizaciones`. Al instalar, el icono desaparece solo.

Para desactivarlo: `systemctl --user disable --now actualizaciones-aviso.timer`.

## Paquetes de Debian: `actualizaciones`

```bash
actualizaciones
```

Muestra lo pendiente (y si hay una versión nueva de ZYRON) y pregunta si instalarlo con `sudo apt full-upgrade`. También vale directamente `sudo apt update && sudo apt full-upgrade`. `jaime0-update` te lo ofrece igualmente al terminar.

Si instalaste en **Btrfs**, cada operación de `apt` crea una instantánea antes y otra después (snapper) y se puede deshacer: ver [recuperacion.md](recuperacion.md).

Cuando `apt` instala un núcleo nuevo, DKMS vuelve a compilar el módulo de NVIDIA y lo firma con la clave de tu instalación, ya registrada. Si tras reiniciar `jaime0-nvidia` dice que el módulo no está cargado, el detalle está en `journalctl -b -k | grep -i nvidia`.

## Lo propio de ZYRON: `jaime0-update`

```bash
jaime0-update
```

Busca la versión más nueva de tu canal y enseña la versión, el canal, la fecha, los cambios, los componentes afectados, los requisitos y los problemas conocidos. Después lista qué archivos cambian y pide confirmación. Instala la parte del sistema (pide la clave de `sudo`), luego tu configuración personal y, por último, ofrece actualizar los paquetes con `apt`.

| Orden | Para qué |
|---|---|
| `jaime0-update` | Buscar, revisar e instalar |
| `jaime0-update --revisar` / `--detalle` / `--sin-paquetes` | Ver las diferencias antes de preguntar / listar todos los archivos / no ofrecer `apt` |
| `jaime0-update comprobar [--json]` | Solo mira si hay versión nueva (código 100 si la hay) |
| `jaime0-update cambios [VERSIÓN]` | Notas de la versión disponible o de una concreta |
| `jaime0-update estado [--json]` | Versión, canal, conflictos, operación en curso o interrumpida (sin red) |
| `jaime0-update canal [stable\|beta\|experimental]` | Ver o cambiar el canal |
| `jaime0-update conflictos` | Archivos tuyos que no se han sobrescrito |
| `jaime0-update resolver RUTA --diferencias\|--usar-nueva\|--mantener` | Resolver un conflicto |
| `jaime0-update historial [-n N] [--json]` | Registro de operaciones |
| `jaime0-update revertir [--usuario]` | Deshacer la última actualización de los archivos de ZYRON |
| `jaime0-update recuperar` | Deshacer una actualización que se cortó a medias |
| `jaime0-update usuario` | Aplicar a tu carpeta la configuración nueva (útil para otros usuarios del equipo) |

`-s` / `--si` responde que sí a todo. Sin terminal interactiva, si no lo pones, no se instala nada.

### Canales

| Canal | Recibe | Etiqueta en GitHub |
|---|---|---|
| `stable` (por defecto) | Solo versiones estables | `vX.Y.Z` |
| `beta` | Estables y beta | `vX.Y.Z-beta.N` (pre-release) |
| `experimental` | Todo | `vX.Y.Z-exp.N` (pre-release) |

El canal está en `/etc/jaime0/update.conf`. El canal va **dentro del manifiesto firmado** y se comprueba que corresponda a la versión: un sistema en `stable` nunca recibe una beta. Al volver a un canal más estable no se desinstala nada. Orden: `0.5.0-exp.1 < 0.5.0-beta.1 < 0.5.0 < 0.5.1`. Mientras ZYRON solo publique betas, usa `jaime0-update canal beta`.

### Desde el Control Center

La sección UPDATES no instala nada: lee `jaime0-update estado --json` (sin red) y, al pulsar BUSCAR, `jaime0-update comprobar --json`; INSTALAR, REVERTIR y RECUPERAR abren una terminal con `jaime0-update`, que enseña los cambios y pide autorización. Las salidas `--json` son una sola línea, sin colores:

- `estado --json`: `{"ok", "version_instalada", "version_actualizador", "canal", "comprobado" (epoch o null), "disponible" ({version, canal, fecha, cambios, problemas_conocidos, componentes, paquetes, requisitos} o null), "nueva", "en_curso" ({fase, version, desde} o null), "ultima" ({operacion, version, fecha, resultado, detalle} o null), "conflictos" ([{ruta, ambito}]), "interrumpida", "puede_revertir", "configuracion": {"version"}}`. `comprobado` y `disponible` son lo que guardó la última comprobación (`~/.local/state/jaime0/disponible.json`).
- `comprobar --json`: `{"ok", "error"?, "nueva", "disponible", "plan": {"sistema": {...}, "usuario": {...}}}`, con `crear`, `reemplazar`, `conflictos`, `retirar` y `conservar` en cada parte. El plan es la misma clasificación que usaría la instalación; para calcularlo basta el manifiesto firmado: no se descarga la carga ni se escribe nada. Si la versión no se puede instalar (requisitos), `ok` es `false`, `error` lo explica y `plan` es `null`.
- `historial --json [-n N]`: `{"ok": true, "operaciones": [{"t", "operacion", "version", "resultado", "detalle"}]}`, interpretando los registros. `resultado` es `ok` o `fallo`.

**Fase visible.** Durante `actualizar`, `revertir` y `recuperar`, la fase de sistema escribe `/run/jaime0-update.estado` (de root, 0644, escritura atómica) con `{"fase": "descargando|verificando|instalando|terminado|fallo", "version", "desde", "detalle"}` y el pid del proceso; la de usuario, `~/.local/state/jaime0/progreso.json`. No hay porcentajes. `en_curso` solo aparece si el proceso que lo escribió sigue vivo (se comprueba el pid y su instante de arranque en `/proc`, así que un archivo viejo o un pid reutilizado no dan falsos positivos).

## Qué rutas gestiona

Solo lo que lista el manifiesto, y solo dentro de estas rutas. Aunque un manifiesto firmado pidiera otra, se rechaza:

`/etc/skel` (y desde ahí tu `~/.config`), `/etc/jaime0`, `/etc/default/grub.d`, `/etc/fonts`, `/etc/systemd`, `/etc/apt/apt.conf.d/20jaime0-*`, `/usr/local/bin`, `/usr/local/lib/jaime0` (paquete de `jaime0-servicio`), `/usr/local/libexec/jaime0-*` (ayudantes que `pkexec` ejecuta como root), `/usr/local/share/marca`, `/usr/local/share/dbus-1/services`, `/usr/lib/systemd/user`, `/usr/share/jaime0` (versión, clave, Control Center, ajustes, widgets), `/usr/share/backgrounds/jaime0`, `/usr/share/glib-2.0/schemas`, `/usr/share/grub/themes`, `/usr/share/plymouth/themes/zyron` (animación de arranque), `/usr/share/polkit-1/actions/es.jaime0.*` y `/usr/share/qt6ct`.

Nunca: bytecode de Python (`__pycache__`, `.pyc`: lo genera cada equipo), documentos, datos personales ni programas que hayas instalado. Quedan fuera **a propósito**:

| Fuera | Por qué |
|---|---|
| Instalador y sistema en vivo (`/etc/calamares`, `/usr/share/calamares`, `/etc/live`, `/usr/lib/live`, `/usr/local/sbin/hypr-*`, `instalar-sistema`, `setxkbmap`) | Solo existen en la ISO; el instalador los borra |
| Repositorio y clave de Brave (`/etc/apt/sources.list.d`, `/usr/share/keyrings`) | Deciden en qué confía `apt`; los mantiene el paquete de Brave |
| `/etc/greetd/config.toml` | Un error deja el equipo sin pantalla de acceso; llega con una ISO nueva |
| NVIDIA del núcleo (`/etc/modprobe.d/jaime0-nvidia.conf`, `/etc/udev/rules.d/80-jaime0-nvidia-pm.rules`) | Necesitan regenerar el initramfs y reiniciar, y un fallo deja sin gráfica; llegan con una ISO nueva |
| Lo que generan los hooks al compilar (el tema sencillo de Plymouth, fuentes y cursores descargados) | No está en el repositorio como archivo |

## Tus personalizaciones están protegidas

Cada archivo se clasifica comparando tres huellas SHA-256: la del disco, la de la versión nueva y las de **todas las versiones oficiales anteriores** (el manifiesto lleva ese histórico).

| Situación | Qué hace |
|---|---|
| Está como en alguna versión oficial (no lo has tocado) | Se reemplaza (con copia) |
| Lo has cambiado tú | **No se toca.** El nuevo queda al lado como `ARCHIVO.jaime0-nuevo` y se anota como conflicto |
| Es nuevo en esta versión | Se crea |
| Lo borraste tú (en tu carpeta o en `/etc`) | No se vuelve a crear |
| Un archivo de sistema de `/usr` borrado | Se repone |
| ZYRON lo retira y no lo has tocado | Se borra (con copia) |
| ZYRON lo retira pero lo has cambiado | Se conserva |
| Es un enlace simbólico, o su carpeta apunta fuera de tu carpeta personal | No se toca |
| `/etc/jaime0/update.conf` | Solo se crea si falta: tu canal no cambia |
| Versión, manifiesto y clave de `/usr/share/jaime0` | Son del actualizador: siempre se reemplazan |

```bash
jaime0-update conflictos
jaime0-update resolver ~/.config/hypr/hyprland.lua --diferencias
jaime0-update resolver ~/.config/hypr/hyprland.lua --usar-nueva   # guarda copia de la tuya
jaime0-update resolver ~/.config/hypr/hyprland.lua --mantener     # borra el .jaime0-nuevo
```

## Después de instalar

Lo hace `jaime0-update` solo, según lo que haya cambiado:

- **Siempre** (también tras `revertir` y `recuperar`): `/usr/local/lib/jaime0` queda `root:root` con directorios 755 y archivos 644; los ayudantes `/usr/local/libexec/jaime0-*`, `root:root` 755; las políticas `/usr/share/polkit-1/actions/es.jaime0.*`, `root:root` 644. Si alguien pudiera escribir en ellos, podría cambiar lo que `pkexec` ejecuta como root.
- Paquete del servicio: borra los `__pycache__` y lo vuelve a compilar (`python3 -m compileall -q /usr/local/lib/jaime0`).
- GRUB: copia el tema a `/boot/grub/themes/hypr` (con el disco cifrado GRUB no lee `/usr`) y `update-grub` (y pide reiniciar). Animación de arranque: `update-initramfs -u` (y pide reiniciar); si llega por primera vez y se usaba el tema anterior (`jaime0`), la deja por defecto, una sola vez. Esquemas de GLib: `glib-compile-schemas`. `/etc/systemd`: `systemctl daemon-reload`. Temporizadores de usuario nuevos: `systemctl --global enable`. Versión: `VERSION` y `VERSION_ID` de `/usr/lib/os-release`.
- Fase de usuario: si cambió el servicio o la ventana del Control Center (por la huella de sus componentes), `systemctl --user try-restart jaime0-servicio.service` (sin sesión no pasa nada: arrancará con la versión nueva al volver a entrar) y avisa de cerrar y abrir el Control Center.

## Versiones

| Versión | Dónde | Para qué |
|---|---|---|
| De la distribución | `/usr/share/jaime0/version` (`0.5.0-beta.1`) | La de la ISO o la última instalada. La copian `/usr/lib/os-release`, el manifiesto y la etiqueta `vX.Y.Z` |
| De los componentes | El manifiesto: cada archivo con su SHA-256 y su componente (`escritorio`, `herramientas`, `servicio`, `control-center`, `temas`, `sistema`); `huellas_componentes` da una huella de conjunto de cada uno y `componentes`, los que cambian respecto a la anterior | Saber si un componente cambió |
| De tu configuración | `version` de `~/.local/state/jaime0/estado.json` | La última versión aplicada a tu carpeta personal |
| Del actualizador | `VERSION_ACTUALIZADOR` en `jaime0-update` (entero; ahora 2) | Un manifiesto puede exigir uno mínimo (`requisitos.actualizador_minimo`). Si el tuyo es más viejo, no se instala nada y el error dice cómo actualizarlo a mano (abajo) |

El formato del manifiesto sigue siendo `1`: los campos nuevos son opcionales y un actualizador que no los conoce los ignora. `requisitos.version_minima` sigue funcionando igual (versión de ZYRON instalada mínima).

## Seguridad

- **Firma:** cada `manifiesto.json` va firmado con Ed25519; la clave pública está en `/usr/share/jaime0/firma-actualizaciones.pem` y se comprueba con `openssl`. Sin firma válida no se instala nada.
- **Integridad:** el manifiesto lleva el SHA-256 de la carga y de cada archivo. La carga debe contener exactamente esos archivos; se rechazan enlaces, dispositivos, rutas con `..` y bytecode.
- **Sin reversiones forzadas:** no se instala una versión igual o anterior, ni de otro canal (un administrador puede forzarlo con `sudo /usr/local/bin/jaime0-update _sistema VERSIÓN --reinstalar`).
- **Lo que revisas es lo que se instala:** la fase de sistema recibe la huella del manifiesto que viste y se niega a seguir si la publicación ha cambiado entretanto.
- **Límites:** firma ≤ 1 KiB, manifiesto y lista de GitHub ≤ 8 MiB, carga del tamaño que dice el manifiesto firmado; ninguna descarga dura más de 15 minutos. **Solo HTTPS**, comprobado en cada redirección.
- **Diarios de confianza:** un diario de copias solo se usa si es del usuario que lo ejecuta, y solo restaura rutas gestionadas (o de tu carpeta) desde su propia carpeta de copias.
- **Privilegios mínimos:** consulta, vista previa y tu configuración van como tu usuario. Solo la fase de sistema usa `sudo`, siempre con `/usr/local/bin/jaime0-update`, que vuelve a descargar y verificar por su cuenta.
- **Un solo proceso a la vez** (cerrojo `/run/jaime0-update.lock`, de root; no sigue enlaces). El estado visible (`/run/jaime0-update.estado`) no lleva rutas ni datos personales.

## Copias, registro y recuperación

- Antes de cambiar un archivo se copia y se anota en un diario que llega al disco **antes** del cambio. Cada archivo se escribe en un temporal y se renombra: nunca queda uno a medias. La versión se escribe la última.
- Copias del sistema: `/var/backups/jaime0/` (solo root); las tuyas: `~/.local/state/jaime0/copias/`. Se conservan las 5 últimas. Registro: `/var/log/jaime0-update.log` y `~/.local/state/jaime0/registro.log`.
- **Corte a mitad** (apagón, Ctrl+C, error): la siguiente ejecución lo deshace antes de seguir, o `jaime0-update recuperar`. Mientras tanto, `/var/lib/jaime0/transaccion-abierta.json` deja ver a cualquiera (también al Control Center) que algo quedó a medias.
- **`jaime0-update revertir`** devuelve los archivos de ZYRON a como estaban antes de la última actualización (guardando antes lo que había) y repite lo de «Después de instalar».

### Qué NO se puede revertir

- Los paquetes de Debian actualizados con `apt`, ni los que una versión pida instalar (campo `paquetes`). Debian no guarda versiones anteriores: la vía es `apt` o reinstalar.
- Lo que generan los hooks al compilar la ISO (el tema sencillo de Plymouth, fuentes, cursores) ni lo que queda fuera de las rutas gestionadas.

En ext4 (la opción por defecto) no hay rollback completo. En Btrfs, `jaime0-update` y `apt` crean instantáneas pre/post con snapper y `revertir` indica la orden `snapper undochange` exacta; ni así vuelven atrás el núcleo ni `/boot` (ver [recuperacion.md](recuperacion.md)).

## Instalar o actualizar `jaime0-update` a mano

Las ISO 0.3 y 0.4 no traen `jaime0-update` (se retiró mientras el repositorio era privado). Para instalarlo una vez, o para actualizarlo cuando una versión exija un actualizador más nuevo, sustituye `V` por la versión publicada:

```bash
V=0.4.0-beta.2
cd "$(mktemp -d)"
for f in manifiesto.json manifiesto.json.sig "jaime0-$V.tar.gz"; do curl -fLO "https://github.com/Jaime-202/zyron/releases/download/v$V/$f"; done
curl -fsSL -o firma.pem https://raw.githubusercontent.com/Jaime-202/zyron/main/config/includes.chroot_after_packages/usr/share/jaime0/firma-actualizaciones.pem
openssl pkey -pubin -in firma.pem -outform DER | sha256sum      # debe ser la huella de abajo
openssl pkeyutl -verify -pubin -inkey firma.pem -rawin -in manifiesto.json -sigfile manifiesto.json.sig
python3 -c 'import hashlib,json,sys; m=json.load(open("manifiesto.json")); assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==m["carga"]["sha256"]; print("Carga verificada")' "jaime0-$V.tar.gz"
tar -xzf "jaime0-$V.tar.gz" usr/local/bin/jaime0-update usr/share/jaime0/firma-actualizaciones.pem etc/jaime0/update.conf
python3 -c 'import hashlib,json,sys; m=json.load(open("manifiesto.json")); [print("OK " if hashlib.sha256(open(r,"rb").read()).hexdigest()==m["archivos"][r]["sha256"] else "MAL", r) for r in sys.argv[1:]]' usr/local/bin/jaime0-update usr/share/jaime0/firma-actualizaciones.pem etc/jaime0/update.conf
sudo install -o root -g root -m 755 usr/local/bin/jaime0-update /usr/local/bin/jaime0-update
sudo install -D -o root -g root -m 644 usr/share/jaime0/firma-actualizaciones.pem /usr/share/jaime0/firma-actualizaciones.pem
[ -e /etc/jaime0/update.conf ] || sudo install -D -m 644 etc/jaime0/update.conf /etc/jaime0/update.conf
sudo install -d -m 700 /var/backups/jaime0 /var/cache/jaime0-update && sudo install -d -m 755 /var/lib/jaime0
jaime0-update canal beta
jaime0-update
```

Si la firma no se verifica (`Signature Verification Failure`) o alguna línea dice `MAL`, para. La huella SHA-256 (DER) de la clave pública buena es:

```
3a5d37d572023bda6147d91cbf3672b957eab93afeecc36ac74a48e2148c4d54
```

Sin manifiesto previo (equipos 0.3 y 0.4), los archivos que no has tocado se reconocen por el histórico de huellas de las versiones etiquetadas (desde `v0.4.0-beta.1`); si tu ISO no salió exactamente de una etiqueta, algunos aparecerán como conflicto (se conservan los tuyos), y lo que hubieras borrado de tu `~/.config` puede volver a crearse.

## Publicar una versión (mantenimiento)

La versión vive en un solo sitio: `config/includes.chroot_after_packages/usr/share/jaime0/version`.

1. Cambia la versión y escribe sus notas en `publicaciones/VERSIÓN.toml` (`fecha`, `cambios`, `problemas_conocidos`, `paquetes`, `[requisitos] version_minima` y, solo si un actualizador anterior la instalaría mal, `actualizador_minimo`; por defecto 2).
2. Commit y etiqueta: `git tag vVERSIÓN`. El histórico de huellas sale de las etiquetas anteriores.
3. Empaqueta y firma (la clave privada **nunca** dentro del repositorio):

   ```bash
   python3 scripts/empaquetar-actualizacion.py --clave ~/.jaime0/firma-actualizaciones.pem
   ```

   Deja en `dist/VERSIÓN/` el manifiesto, su firma, la carga y `notas.md`, comprueba la firma con la clave pública del repositorio y escribe la orden `gh release create` exacta (con `--prerelease` si no es estable).
4. Compila la ISO de esa versión: `auto/build` aborta si hay una clave privada en `config/` y genera antes el manifiesto que la ISO instala como punto de partida.

**La clave.** `openssl genpkey -algorithm ed25519 -out ~/.jaime0/firma-actualizaciones.pem` crea la privada; `openssl pkey -in ... -pubout` saca la pública del repositorio. Guarda una copia de la privada fuera del equipo: si se pierde, los equipos instalados no pueden verificar firmas de otra clave sin una ISO nueva (o una versión firmada con la vieja que traiga la nueva). El empaquetador se niega a usar una clave dentro del repositorio o en OneDrive y `.gitignore` excluye nombres típicos de claves privadas.

Límite conocido: no hay caducidad de publicaciones. Quien controle la cuenta de GitHub sin la clave puede ocultar publicaciones (no instalar nada).

## Pruebas

```bash
python3 -m unittest discover -s pruebas -v
```

`pruebas/test_jaime0_update.py` monta un sistema de mentira (`JAIME0_RAIZ`, que se ignora con root) con publicaciones locales firmadas de verdad: flujo completo, conflictos, borrados, firma falsa o de otra clave, carga alterada, cortada, incompleta o con un archivo cambiado, rutas fuera de lo permitido, requisitos no cumplidos, cortes y recuperación, reversión, servicio/ayudante/política con permisos forzados, reinicio del servicio, salidas `--json`, `en_curso` sin falsos positivos y la barra de `actualizaciones`. En una imagen compilada, `scripts/verificar-actualizador.sh` (con sudo) revisa el chroot y repite las pruebas con su `python3`.
