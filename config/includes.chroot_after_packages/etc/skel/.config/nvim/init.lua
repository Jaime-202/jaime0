-- ~/.config/nvim/init.lua
-- Neovim sin plugins ni dependencias de red: paleta jaime0, fondo transparente y linea
-- de estado de capsulas con modo en color, rama, archivo, diagnosticos, posicion y hora.

local o = vim.opt

o.termguicolors = true
o.number = true
o.relativenumber = true
o.cursorline = true
o.signcolumn = "yes"
o.scrolloff = 5
o.tabstop = 4
o.shiftwidth = 4
o.expandtab = true
o.smartindent = true
o.ignorecase = true
o.smartcase = true
o.mouse = "a"
o.clipboard = "unnamedplus"
o.splitright = true
o.splitbelow = true
o.showmode = false
o.laststatus = 2
o.showtabline = 2
o.swapfile = false
o.undofile = true
o.updatetime = 300
o.fillchars = { eob = " ", vert = "│" }

--------------------------------------------------------------------------------
-- Colores
--------------------------------------------------------------------------------
local p = {
    rosewater = "#f2f4fb", flamingo = "#ffb3cf", pink = "#ff6ea9", mauve = "#b59bff",
    red = "#ff5c72", maroon = "#ff8a99", peach = "#ffab6e", yellow = "#ffe57a",
    green = "#a6e87a", teal = "#6ee7f2", sky = "#6ee7f2", sapphire = "#7ab0ff",
    blue = "#7ab0ff", lavender = "#b59bff", text = "#e0e4f2", subtext1 = "#b6bcd4",
    subtext0 = "#9aa0bc", overlay2 = "#7a819e", overlay1 = "#565c78", overlay0 = "#454a64",
    surface2 = "#343a52", surface1 = "#252939", surface0 = "#171a26", base = "#12141d",
    mantle = "#0b0d14", crust = "#0b0d14",
}

vim.cmd("highlight clear")
vim.g.colors_name = "jaime0-transparente"
o.background = "dark"

local grupos = {
    -- Interfaz. Sin bg: se ve el fondo de la terminal, que ya es translucida.
    Normal = { fg = p.text },
    NormalNC = { fg = p.text },
    NormalFloat = { fg = p.text, bg = p.mantle },
    FloatBorder = { fg = p.lavender, bg = p.mantle },
    SignColumn = {},
    EndOfBuffer = {},
    LineNr = { fg = p.overlay0 },
    CursorLineNr = { fg = p.sky, bold = true },
    CursorLine = { bg = p.surface0, blend = 0 },
    ColorColumn = { bg = p.surface0 },
    Visual = { bg = "#2e3350" },
    Search = { fg = p.base, bg = p.yellow },
    IncSearch = { fg = p.base, bg = p.peach },
    MatchParen = { fg = p.peach, bold = true },
    WinSeparator = { fg = p.surface2 },
    VertSplit = { fg = p.surface2 },
    Pmenu = { fg = p.text, bg = p.mantle },
    PmenuSel = { fg = p.rosewater, bg = "#2e3350" },
    NonText = { fg = p.surface2 },
    Whitespace = { fg = p.surface1 },
    Directory = { fg = p.sky },
    Title = { fg = p.sky, bold = true },
    ErrorMsg = { fg = p.red },
    WarningMsg = { fg = p.yellow },
    MoreMsg = { fg = p.green },
    Question = { fg = p.blue },
    DiffAdd = { fg = p.green },
    DiffChange = { fg = p.yellow },
    DiffDelete = { fg = p.red },

    -- Sintaxis
    Comment = { fg = p.overlay1 },
    Constant = { fg = p.yellow },
    String = { fg = p.sky },
    Character = { fg = p.teal },
    Number = { fg = p.yellow },
    Boolean = { fg = p.yellow },
    Identifier = { fg = p.text },
    Function = { fg = p.sky },
    Statement = { fg = p.mauve },
    Keyword = { fg = p.pink },
    Conditional = { fg = p.pink },
    Repeat = { fg = p.pink },
    Operator = { fg = p.sky },
    PreProc = { fg = p.pink },
    Include = { fg = p.mauve },
    Type = { fg = p.mauve },
    Special = { fg = p.pink },
    Delimiter = { fg = p.overlay2 },
    Todo = { fg = p.base, bg = p.yellow, bold = true },
    Error = { fg = p.red },

    -- Treesitter y diagnosticos
    ["@variable"] = { fg = p.text },
    ["@property"] = { fg = p.subtext1 },
    ["@parameter"] = { fg = p.maroon },
    ["@function.builtin"] = { fg = p.peach },
    ["@keyword.function"] = { fg = p.pink },
    ["@keyword.return"] = { fg = p.pink },
    ["@constructor"] = { fg = p.sapphire },
    ["@string.escape"] = { fg = p.pink },
    ["@punctuation.bracket"] = { fg = p.overlay2 },
    DiagnosticError = { fg = p.red },
    DiagnosticWarn = { fg = p.yellow },
    DiagnosticInfo = { fg = p.sky },
    DiagnosticHint = { fg = p.teal },

    -- Linea de estado y pestanas
    StatusLine = { fg = p.text },
    StatusLineNC = { fg = p.overlay0 },
    TabLineFill = {},
    Capsula = { fg = p.text, bg = p.surface1 },
    CapsulaBorde = { fg = p.surface1 },
    CapsulaRama = { fg = p.mauve, bg = p.surface1, bold = true },
    CapsulaError = { fg = p.red, bg = p.surface1 },
    CapsulaAviso = { fg = p.yellow, bg = p.surface1 },
    CapsulaPos = { fg = p.base, bg = p.teal, bold = true },
    CapsulaPosBorde = { fg = p.teal },
    CapsulaHora = { fg = p.base, bg = p.green, bold = true },
    CapsulaHoraBorde = { fg = p.green },
    PestanaActiva = { fg = p.sky, bold = true },
    PestanaInactiva = { fg = p.overlay1 },
    PestanaSeparador = { fg = p.surface2 },
}
for nombre, valor in pairs(grupos) do
    vim.api.nvim_set_hl(0, nombre, valor)
end

local colores_modo = {
    n = { "NORMAL", p.blue }, i = { "INSERT", p.pink }, v = { "VISUAL", p.mauve },
    V = { "V-LINE", p.mauve }, ["\22"] = { "V-BLOCK", p.mauve }, c = { "COMMAND", p.yellow },
    R = { "REPLACE", p.red }, t = { "TERMINAL", p.green }, s = { "SELECT", p.peach },
    S = { "S-LINE", p.peach },
}
for letra, datos in pairs(colores_modo) do
    local id = letra == "\22" and "Bloque" or (letra:match("%u") and "M" .. letra or letra)
    datos[3] = "Modo" .. id
    vim.api.nvim_set_hl(0, datos[3], { fg = p.base, bg = datos[2], bold = true })
    vim.api.nvim_set_hl(0, datos[3] .. "Borde", { fg = datos[2] })
end

--------------------------------------------------------------------------------
-- Linea de estado
--------------------------------------------------------------------------------
local glifo = vim.fn.nr2char
local RAMA, RELOJ = glifo(0xe0a0), glifo(0xf017)
local IZQ, DER = glifo(0xe0b6), glifo(0xe0b4)
local ERR, AVISO = glifo(0xf057), glifo(0xf071)

local function actualizar_rama()
    local carpeta = vim.fn.expand("%:p:h")
    if carpeta == "" or vim.fn.isdirectory(carpeta) == 0 or vim.fn.executable("git") == 0 then
        vim.b.rama_git = ""
        return
    end
    local salida = vim.fn.systemlist({ "git", "-C", carpeta, "branch", "--show-current" })
    vim.b.rama_git = (vim.v.shell_error == 0 and salida[1]) or ""
end

vim.api.nvim_create_autocmd({ "BufEnter", "FocusGained", "DirChanged" }, {
    callback = actualizar_rama,
})

-- Capsula redondeada: media luna del color de fondo, texto y otra media luna.
local function capsula(borde, relleno, texto)
    return "%#" .. borde .. "#" .. IZQ .. "%#" .. relleno .. "#" .. texto .. "%#" .. borde .. "#" .. DER .. "%*"
end

local function diagnosticos()
    if not vim.diagnostic or not vim.diagnostic.count then
        return ""
    end
    local n = vim.diagnostic.count(0)
    local e = n[vim.diagnostic.severity.ERROR] or 0
    local w = n[vim.diagnostic.severity.WARN] or 0
    if e + w == 0 then
        return ""
    end
    return capsula("CapsulaBorde", "CapsulaError", ERR .. " " .. e .. " %#CapsulaAviso#" .. AVISO .. " " .. w) .. " "
end

function _G.LineaEstado()
    local modo = colores_modo[vim.fn.mode()] or colores_modo.n
    local partes = { capsula(modo[3] .. "Borde", modo[3], " " .. modo[1] .. " "), " " }
    local rama = vim.b.rama_git or ""
    if rama ~= "" then
        partes[#partes + 1] = capsula("CapsulaBorde", "CapsulaRama", RAMA .. " " .. rama)
        partes[#partes + 1] = " "
    end
    local archivo = vim.fn.expand("%:~:.")
    partes[#partes + 1] = capsula("CapsulaBorde", "Capsula", (archivo == "" and "[sin nombre]" or archivo) .. "%m%r")
    partes[#partes + 1] = "%="
    partes[#partes + 1] = diagnosticos()
    partes[#partes + 1] = capsula("CapsulaPosBorde", "CapsulaPos", "%p%% %l:%c")
    partes[#partes + 1] = " "
    partes[#partes + 1] = capsula("CapsulaHoraBorde", "CapsulaHora", RELOJ .. " " .. os.date("%H:%M"))
    return table.concat(partes)
end

o.statusline = "%!v:lua.LineaEstado()"

-- Mantiene la hora al dia aunque no se pulse ninguna tecla.
vim.fn.timer_start(30000, function()
    vim.cmd.redrawstatus()
end, { ["repeat"] = -1 })

--------------------------------------------------------------------------------
-- Pestanas: una por cada archivo abierto
--------------------------------------------------------------------------------
function _G.LineaPestanas()
    local partes = { " " }
    local actual = vim.api.nvim_get_current_buf()
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
        if vim.bo[b].buflisted then
            local nombre = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(b), ":t")
            if nombre == "" then
                nombre = "[sin nombre]"
            end
            local marca = vim.bo[b].modified and " " .. glifo(0x25cf) or ""
            local grupo = b == actual and "PestanaActiva" or "PestanaInactiva"
            partes[#partes + 1] = "%#" .. grupo .. "# " .. nombre .. marca .. " %#PestanaSeparador#│"
        end
    end
    partes[#partes + 1] = "%#TabLineFill#"
    return table.concat(partes)
end

o.tabline = "%!v:lua.LineaPestanas()"
