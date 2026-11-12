-- ~/.config/hypr/hyprland.lua
-- Configuracion de Hyprland de Jaime0, sobre Debian Forky (sintaxis Lua de Hyprland 0.56 y 0.57).
-- Paleta jaime0: negro #080b0d, verde #54e58a (solo lo activo) y bordes #26343a.
-- Separaciones, bordes, esquinas, efectos, acento y fondo salen de jaime0-ajustes.
--
-- Los atajos se declaran con atajo(): cada uno lleva su descripcion, que es lo que lista
-- el comando "atajos". Los atajos propios del usuario van en atajos-usuario.lua, junto a
-- este archivo; los gestiona "atajos añadir / quitar / editar".

--------------------------------------------------------------------------------
-- Programas
--------------------------------------------------------------------------------
local mainMod     = "SUPER"
local terminal    = "kitty"
local fileManager = "thunar"
local launcher    = "rofi -show drun"
local clipboard   = "cliphist list | rofi -dmenu -p portapapeles | cliphist decode | wl-copy"
local screenshot  = "captura area"
local navegador   = "abrir-navegador"
local monitorSis  = "abrir-btop"
local polkitAgent = "/usr/bin/lxpolkit"
local fondo       = "/usr/share/backgrounds/jaime0/jaime0.png"

--------------------------------------------------------------------------------
-- Entorno: maquina virtual y teclado
--------------------------------------------------------------------------------
local function enMaquinaVirtual()
    local salida = io.popen("systemd-detect-virt --vm 2>/dev/null")
    if not salida then
        return false
    end
    local tipo = salida:read("*l")
    salida:close()
    return tipo ~= nil and tipo ~= "" and tipo ~= "none"
end

-- En una maquina virtual se dibuja por software: se quitan blur y animaciones,
-- y el cursor pasa a dibujarse en software, que en VirtualBox va fluido.
local esVirtual = enMaquinaVirtual()

-- La distribucion de teclado es la del sistema, la que se eligio al instalar.
local function tecladoSistema(clave, porDefecto)
    local archivo = io.open("/etc/default/keyboard", "r")
    if not archivo then
        return porDefecto
    end
    local valor = nil
    for linea in archivo:lines() do
        local encontrado = linea:match("^" .. clave .. "=\"?([^\"]*)\"?")
        if encontrado then
            valor = encontrado
        end
    end
    archivo:close()
    if valor == nil or (valor == "" and porDefecto ~= "") then
        return porDefecto
    end
    return valor
end

-- Carpeta de este archivo, para cargar atajos-usuario.lua de al lado.
local function carpetaConfig()
    if debug and debug.getinfo then
        local ok, info = pcall(debug.getinfo, 1, "S")
        if ok and info and info.source and info.source:sub(1, 1) == "@" then
            local carpeta = info.source:sub(2):match("^(.*)/[^/]*$")
            if carpeta then
                return carpeta
            end
        end
    end
    return (os.getenv("HOME") or "") .. "/.config/hypr"
end

--------------------------------------------------------------------------------
-- Ajustes de Jaime0 (jaime0-ajustes): predeterminados del sistema y, encima, los del
-- usuario en ~/.config/jaime0/ajustes. Un valor mal escrito se ignora y se usa el
-- predeterminado, para que un error nunca deje la sesion sin abrir.
--------------------------------------------------------------------------------
local function leerClaves(ruta, destino)
    local archivo = io.open(ruta, "r")
    if not archivo then
        return
    end
    for linea in archivo:lines() do
        if not linea:match("^%s*#") then
            local clave, valor = linea:match("^%s*([%w_.]+)%s*=%s*(.-)%s*$")
            if clave then
                destino[clave] = valor
            end
        end
    end
    archivo:close()
end

local ajustes = {}
do
    local predet, usuario = {}, {}
    leerClaves("/usr/share/jaime0/ajustes.predeterminados", predet)
    local xdg = os.getenv("XDG_CONFIG_HOME")
    if not xdg or xdg == "" then
        xdg = (os.getenv("HOME") or "") .. "/.config"
    end
    leerClaves(xdg .. "/jaime0/ajustes", usuario)
    ajustes.predet, ajustes.usuario = predet, usuario
end

-- Valor de un ajuste ya comprobado: primero el del usuario, luego el predeterminado y,
-- si ninguno sirve, el de reserva.
local function ajuste(clave, comprobar, reserva)
    for _, origen in ipairs({ ajustes.usuario, ajustes.predet }) do
        local v = origen[clave]
        if v ~= nil then
            local ok = comprobar(v)
            if ok ~= nil then
                return ok
            end
        end
    end
    return reserva
end

local function entero(v) local n = tonumber(v); return n and math.floor(n) end
local function decimal(v) return tonumber((v:gsub(",", "."))) end
local function sino(v)
    if v == "si" then return true end
    if v == "no" then return false end
    return nil
end
local function color(v)
    local hex = ajustes.predet["tema." .. v] or v
    local rgb = hex:match("^#(%x%x%x%x%x%x)$")
    return rgb and rgb:lower()
end
local function imagen(v)
    local f = io.open(v, "r")
    if f then f:close(); return v end
    return nil
end

local acento = ajuste("acento", color, "54e58a")
fondo = ajuste("fondo", imagen, fondo)

--------------------------------------------------------------------------------
-- Monitores
--------------------------------------------------------------------------------
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = esVirtual and 1 or "auto",
})

--------------------------------------------------------------------------------
-- Variables de entorno
--------------------------------------------------------------------------------
-- Cursor discreto: Adwaita a 24 px (solo XCursor; no hay version hyprcursor).
hl.env("XCURSOR_THEME", "Adwaita")
hl.env("XCURSOR_SIZE", "24")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("GDK_BACKEND", "wayland,x11")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("MOZ_ENABLE_WAYLAND", "1")
-- Sin lector de pantalla instalado, GTK no busca el bus de accesibilidad.
hl.env("NO_AT_BRIDGE", "1")

--------------------------------------------------------------------------------
-- Inicio automatico: solo lo imprescindible, para que la sesion sea ligera.
-- La red y el Bluetooth se gestionan desde la barra (nmtui y blueman-manager al hacer
-- clic), sin applets residentes. Los USB los monta Thunar con gvfs al pulsar en ellos.
--------------------------------------------------------------------------------
hl.on("hyprland.start", function()
    -- La GPU virtual de VirtualBox (SVGA3D) tumba a los clientes que la usan directamente,
    -- como kitty o GTK4. Solo ahi se fuerza el dibujado por software.
    if esVirtual then
        hl.env("LIBGL_ALWAYS_SOFTWARE", "1")
        hl.env("GSK_RENDERER", "cairo")
    end
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE HYPRLAND_INSTANCE_SIGNATURE NO_AT_BRIDGE")
    hl.exec_cmd("xdg-user-dirs-update")
    hl.exec_cmd("sh -c 'test -d /run/live/medium && sleep 4 && notify-send \"Sistema en vivo\" \"Pulsa SUPER + Espacio y busca: Instalar el sistema. SUPER + F1 muestra los atajos.\"'")
    hl.exec_cmd(polkitAgent)
    hl.exec_cmd("swaybg --image " .. fondo .. " --mode fill")
    -- Los archivos que lee Waybar (altura, posicion, acento) se generan antes de abrirla.
    hl.exec_cmd("sh -c 'jaime0-ajustes generar; exec waybar'")
    hl.exec_cmd("dunst")
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
    -- Bloqueo a los 10 min, pantalla apagada a los 11 y suspension a los 30 (no en vivo).
    hl.exec_cmd("inactividad")
end)

--------------------------------------------------------------------------------
-- Aspecto
--------------------------------------------------------------------------------
hl.config({
    general = {
        layout       = "dwindle",
        gaps_in      = ajuste("separacion_interior", entero, 4),
        gaps_out     = ajuste("separacion_exterior", entero, 8),
        border_size  = ajuste("borde", entero, 2),
        -- Borde fino: el acento, algo apagado, en la ventana activa; gris en las demas.
        col = {
            active_border   = "rgba(" .. acento .. "cc)",
            inactive_border = "rgba(26343aff)",
        },
        -- Redimensionar arrastrando el borde (ademas de SUPER + clic derecho y SUPER + CTRL + flechas).
        resize_on_border = true,
        allow_tearing    = false,
    },

    decoration = {
        rounding           = ajuste("esquinas", entero, 8),
        rounding_power     = 2,
        -- Opacas por defecto: el texto se lee mejor y no hay que difuminar lo que hay detras.
        -- Las inactivas pueden ser algo translucidas con jaime0-ajustes (opacidad_inactiva).
        active_opacity     = 1.0,
        inactive_opacity   = ajuste("opacidad_inactiva", decimal, 1.0),
        fullscreen_opacity = 1.0,

        -- Sin sombras: no aportan con bordes de color y cuestan una pasada por ventana.
        shadow = {
            enabled = false,
        },

        -- Blur minimo (una pasada) solo para lo translucido: kitty, rofi y dunst.
        -- En maquina virtual se apaga.
        blur = {
            enabled           = ajuste("desenfoque", sino, true) and not esVirtual,
            size              = 3,
            passes            = 1,
            noise             = 0.0,
            vibrancy          = 0.0,
            brightness        = 0.80,
            new_optimizations = true,
            xray              = false,
            ignore_opacity    = true,
        },
    },

    animations = {
        enabled = ajuste("animaciones", sino, true) and not esVirtual,
    },

    -- En VM el cursor por hardware va a saltos: se dibuja por software.
    cursor = {
        no_hardware_cursors = esVirtual,
        hide_on_key_press   = false,
    },

    -- Sin XWayland: todos los programas del sistema son Wayland nativos y asi se ahorran
    -- unos 120 MB. Para usar un programa X11, cambia a true y reinicia la sesion.
    xwayland = {
        enabled = false,
    },

    dwindle = {
        preserve_split = true,
    },

    -- Sin ventanas de novedades ni donativos de Hyprland al iniciar la sesion.
    ecosystem = {
        no_update_news  = true,
        no_donation_nag = true,
    },

    misc = {
        force_default_wallpaper  = 0,
        disable_hyprland_logo    = true,
        disable_splash_rendering = true,
    },

    input = {
        kb_layout    = tecladoSistema("XKBLAYOUT", "es"),
        kb_variant   = tecladoSistema("XKBVARIANT", ""),
        follow_mouse  = 1,
        -- Movimiento plano y predecible: sin aceleracion ni cambios de sensibilidad.
        accel_profile = "flat",
        sensitivity   = 0,
        touchpad = {
            natural_scroll = false,
        },
    },
})

--------------------------------------------------------------------------------
-- Animaciones: cortas (unos 200-300 ms) y con pocas curvas
--------------------------------------------------------------------------------
hl.curve("suave",  { type = "bezier", points = { {0.25, 1.0}, {0.5, 1.0} } })
hl.curve("salida", { type = "bezier", points = { {0.4, 0.0},  {0.2, 1.0} } })

hl.animation({ leaf = "windowsIn",   enabled = true,  speed = 3, bezier = "suave",  style = "popin 85%" })
hl.animation({ leaf = "windowsOut",  enabled = true,  speed = 2, bezier = "salida", style = "popin 85%" })
hl.animation({ leaf = "windowsMove", enabled = true,  speed = 3, bezier = "suave" })
hl.animation({ leaf = "fade",        enabled = true,  speed = 2, bezier = "salida" })
hl.animation({ leaf = "border",      enabled = false, speed = 1, bezier = "suave" })
hl.animation({ leaf = "layers",      enabled = true,  speed = 2, bezier = "suave" })
hl.animation({ leaf = "workspaces",  enabled = true,  speed = 3, bezier = "suave",  style = "slide" })

hl.gesture({
    fingers   = 3,
    direction = "horizontal",
    action    = "workspace",
})

--------------------------------------------------------------------------------
-- Atajos. atajo(teclas, accion, descripcion[, opciones])
-- accion puede ser un texto (se ejecuta como orden) o un dispatcher de hl.dsp.
--------------------------------------------------------------------------------
function atajo(teclas, accion, descripcion, opciones)
    local o = {}
    for k, v in pairs(opciones or {}) do
        o[k] = v
    end
    o.description = descripcion
    if type(accion) == "string" then
        accion = hl.dsp.exec_cmd(accion)
    end
    return hl.bind(teclas, accion, o)
end

atajo(mainMod .. " + Return",    terminal,        "Abrir la terminal (Kitty)")
atajo(mainMod .. " + space",     launcher,        "Lanzador de aplicaciones")
atajo(mainMod .. " + F1",        "atajos --rofi", "Ver todos los atajos")
atajo(mainMod .. " + Q",         hl.dsp.window.close(), "Cerrar la ventana")
atajo(mainMod .. " + F",         hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }), "Pantalla completa (oculta la barra)")
atajo(mainMod .. " + M",         hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" }), "Maximizar (mantiene la barra)")
atajo(mainMod .. " + V",         hl.dsp.window.float({ action = "toggle" }), "Alternar ventana flotante")
atajo(mainMod .. " + E",         fileManager,     "Gestor de archivos (Thunar)")
atajo(mainMod .. " + SHIFT + V", clipboard,       "Historial del portapapeles")
atajo(mainMod .. " + Escape",    "menu-energia",  "Menú de energía")
atajo("Print",                   screenshot,      "Captura de un área (archivo y portapapeles)")

atajo(mainMod .. " + left",  hl.dsp.focus({ direction = "left" }),  "Foco a la izquierda")
atajo(mainMod .. " + right", hl.dsp.focus({ direction = "right" }), "Foco a la derecha")
atajo(mainMod .. " + up",    hl.dsp.focus({ direction = "up" }),    "Foco arriba")
atajo(mainMod .. " + down",  hl.dsp.focus({ direction = "down" }),  "Foco abajo")

atajo(mainMod .. " + SHIFT + left",  hl.dsp.window.swap({ direction = "left" }),  "Intercambiar con la ventana de la izquierda")
atajo(mainMod .. " + SHIFT + right", hl.dsp.window.swap({ direction = "right" }), "Intercambiar con la ventana de la derecha")
atajo(mainMod .. " + SHIFT + up",    hl.dsp.window.swap({ direction = "up" }),    "Intercambiar con la ventana de arriba")
atajo(mainMod .. " + SHIFT + down",  hl.dsp.window.swap({ direction = "down" }),  "Intercambiar con la ventana de abajo")

for i = 1, 9 do
    atajo(mainMod .. " + " .. i,         hl.dsp.focus({ workspace = i }),       "Ir al escritorio " .. i)
    atajo(mainMod .. " + SHIFT + " .. i, hl.dsp.window.move({ workspace = i }), "Mover la ventana al escritorio " .. i)
end

atajo(mainMod .. " + mouse:272", hl.dsp.window.drag(),   "Mover ventana con el ratón (arrastrar)", { mouse = true })
atajo(mainMod .. " + mouse:273", hl.dsp.window.resize(), "Redimensionar ventana con el ratón (arrastrar)", { mouse = true })
atajo(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), "Escritorio siguiente (rueda del ratón)")
atajo(mainMod .. " + mouse_up",   hl.dsp.focus({ workspace = "e-1" }), "Escritorio anterior (rueda del ratón)")

-- Ventanas y mosaico
atajo(mainMod .. " + CTRL + left",  hl.dsp.window.resize({ x = -40, y = 0, relative = true }), "Estrechar la ventana", { repeating = true })
atajo(mainMod .. " + CTRL + right", hl.dsp.window.resize({ x = 40,  y = 0, relative = true }), "Ensanchar la ventana", { repeating = true })
atajo(mainMod .. " + CTRL + up",    hl.dsp.window.resize({ x = 0, y = -40, relative = true }), "Acortar la ventana", { repeating = true })
atajo(mainMod .. " + CTRL + down",  hl.dsp.window.resize({ x = 0, y = 40,  relative = true }), "Alargar la ventana", { repeating = true })
atajo(mainMod .. " + J",            hl.dsp.layout("togglesplit"), "Cambiar la orientación del mosaico")
atajo(mainMod .. " + P",            hl.dsp.window.pseudo(),       "Pseudo-mosaico (tamaño propio dentro del hueco)")
atajo(mainMod .. " + C",            hl.dsp.window.center(),       "Centrar la ventana flotante")
atajo(mainMod .. " + BackSpace",    hl.dsp.focus({ workspace = "previous" }), "Volver al escritorio anterior")

-- Programas y menús
atajo(mainMod .. " + B",              navegador,          "Navegador (avisa si no hay ninguno instalado)")
atajo(mainMod .. " + Tab",            "rofi -show window", "Cambiar de ventana (lista)")
atajo(mainMod .. " + R",              "rofi -show run",    "Ejecutar una orden")
atajo("CTRL + SHIFT + Escape",        monitorSis,          "Monitor del sistema (btop)")
atajo(mainMod .. " + A",              "pavucontrol",       "Control de sonido")
atajo(mainMod .. " + W",              "kitty --class nmtui-flotante -e nmtui", "Red y Wi-Fi")
atajo(mainMod .. " + N",              "dunstctl history-pop", "Volver a mostrar la última notificación")
atajo(mainMod .. " + SHIFT + N",      "dunstctl close-all",   "Cerrar todas las notificaciones")
atajo(mainMod .. " + L",              "bloquear",          "Bloquear la pantalla")
atajo(mainMod .. " + SHIFT + R",      "hyprctl reload",    "Recargar la configuración de Hyprland")
atajo("SHIFT + Print",                "captura pantalla",  "Captura de la pantalla entera (archivo y portapapeles)")
atajo(mainMod .. " + Print",          "captura ventana",   "Captura de la ventana activa (archivo y portapapeles)")

-- Teclas multimedia (funcionan también con la pantalla bloqueada). Sus atajos quedan en
-- atajosMultimedia por si hace falta desactivarlos, por ejemplo con un teclado virtual:
--   hyprctl eval 'for _, b in ipairs(atajosMultimedia) do b:set_enabled(false) end'
atajosMultimedia = {}
local function multimedia(teclas, orden, descripcion, opciones)
    table.insert(atajosMultimedia, atajo(teclas, orden, descripcion, opciones))
end
multimedia("XF86AudioRaiseVolume",  "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+", "Subir el volumen", { locked = true, repeating = true })
multimedia("XF86AudioLowerVolume",  "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-",      "Bajar el volumen", { locked = true, repeating = true })
multimedia("XF86AudioMute",         "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",      "Silenciar o activar el sonido", { locked = true })
multimedia("XF86AudioMicMute",      "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle",    "Silenciar o activar el micrófono", { locked = true })
multimedia("XF86MonBrightnessUp",   "brightnessctl -q set 5%+", "Subir el brillo", { locked = true, repeating = true })
multimedia("XF86MonBrightnessDown", "brightnessctl -q set 5%-", "Bajar el brillo", { locked = true, repeating = true })
multimedia("XF86AudioPlay",         "playerctl play-pause", "Reproducir o pausar", { locked = true })
multimedia("XF86AudioPause",        "playerctl play-pause", "Reproducir o pausar", { locked = true })
multimedia("XF86AudioNext",         "playerctl next",       "Pista siguiente", { locked = true })
multimedia("XF86AudioPrev",         "playerctl previous",   "Pista anterior", { locked = true })

-- Atajos del usuario, gestionados por el comando "atajos".
do
    local propios = carpetaConfig() .. "/atajos-usuario.lua"
    local f = io.open(propios, "r")
    if f then
        f:close()
        dofile(propios)
    end
end

--------------------------------------------------------------------------------
-- Reglas de ventana (se evaluan en orden; la ultima coincidencia gana)
--------------------------------------------------------------------------------

-- La opacidad de las ventanas sale de los ajustes (opacidad_inactiva). Kitty lleva ademas
-- su propia transparencia de fondo, muy ligera (kitty.conf).

-- Flotantes y centradas
hl.window_rule({
    name   = "flotantes-sistema",
    match  = { class = "^(org\\.pulseaudio\\.pavucontrol|pavucontrol|blueman-manager|\\.blueman-manager-wrapped|nm-connection-editor)$" },
    float  = true,
    center = true,
})

hl.window_rule({
    name   = "flotante-instalador",
    match  = { class = "^(io\\.calamares\\.calamares|calamares)$" },
    float  = true,
    center = true,
})

hl.window_rule({
    name   = "flotante-polkit",
    match  = { class = "^(lxpolkit|.*polkit.*)$" },
    float  = true,
    center = true,
})

hl.window_rule({
    name   = "flotante-utilidades",
    match  = { class = "^(nmtui-flotante|atajos-flotante)$" },
    float  = true,
    center = true,
    size   = { "monitor_w*0.62", "monitor_h*0.72" },
})

-- Aplicacion de ajustes (jaime0-ajustes, en Quickshell)
hl.window_rule({
    name   = "flotante-ajustes",
    match  = { class = "^org\\.quickshell$", title = "^Ajustes de Jaime0$" },
    float  = true,
    center = true,
    size   = { "560", "640" },
})

hl.window_rule({
    name   = "dialogos-por-titulo",
    match  = { title = "^(Abrir|Guardar|Guardar como|Open|Save|Save As|Confirmar|Confirm|Reemplazar|Replace|Eliminar|Delete).*" },
    float  = true,
    center = true,
})

hl.window_rule({
    name   = "dialogos-modales",
    match  = { modal = true },
    float  = true,
    center = true,
})

hl.window_rule({
    name   = "dialogos-portal",
    match  = { class = "^xdg-desktop-portal-(gtk|hyprland)$" },
    float  = true,
    center = true,
})

-- Pantalla completa siempre
hl.window_rule({
    name       = "completa-reproductores",
    match      = { class = "^(mpv|vlc|org\\.videolan\\.VLC)$", modal = false },
    fullscreen = true,
})

hl.window_rule({
    name       = "completa-juegos",
    match      = { class = "^(steam_app_.*|gamescope|.*\\.exe)$" },
    fullscreen = true,
})

hl.window_rule({
    name       = "completa-contenido-juego",
    match      = { content = "game" },
    fullscreen = true,
})

-- Opacidad 1.0 real en pantalla completa y en video. Van al final para ganar.
hl.window_rule({
    name    = "opaca-pantalla-completa",
    match   = { fullscreen_state_internal = 2 },
    opacity = "1.0 override 1.0 override 1.0 override",
    opaque  = true,
    no_blur = true,
})

hl.window_rule({
    name    = "opaca-contenido-video",
    match   = { content = "video" },
    opacity = "1.0 override 1.0 override 1.0 override",
    opaque  = true,
    no_blur = true,
})

hl.window_rule({
    name    = "opaca-reproductores",
    match   = { class = "^(mpv|vlc|org\\.videolan\\.VLC)$" },
    opacity = "1.0 override 1.0 override 1.0 override",
    opaque  = true,
    no_blur = true,
})

--------------------------------------------------------------------------------
-- Reglas de capa: blur en lanzador y notificaciones, que son algo translucidos.
-- La barra tiene fondo opaco: difuminar detras de ella no se veria y costaria una pasada.
--------------------------------------------------------------------------------
hl.layer_rule({
    name         = "blur-rofi",
    match        = { namespace = "^rofi$" },
    blur         = true,
    ignore_alpha = 0.3,
})

hl.layer_rule({
    name         = "blur-notificaciones",
    match        = { namespace = "^(dunst|notifications)$" },
    blur         = true,
    ignore_alpha = 0.3,
})
