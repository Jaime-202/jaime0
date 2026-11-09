# ~/.zshrc

# Historial
HISTFILE="$HOME/.zsh_history"
HISTSIZE=10000
SAVEHIST=10000
setopt APPEND_HISTORY SHARE_HISTORY HIST_IGNORE_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS

# Comportamiento
setopt AUTO_CD INTERACTIVE_COMMENTS NO_BEEP

# Teclas estilo Emacs, con Inicio, Fin, Supr y Ctrl+Flechas
bindkey -e
bindkey '^[[H'    beginning-of-line
bindkey '^[[F'    end-of-line
bindkey '^[[3~'   delete-char
bindkey '^[[1;5C' forward-word
bindkey '^[[1;5D' backward-word

# Autocompletado
autoload -Uz compinit
compinit -d "$HOME/.zcompdump"
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

# Alias
alias ls='ls --color=auto --group-directories-first'
alias ll='ls -lh'
alias la='ls -lAh'
alias grep='grep --color=auto'

# Autosugerencias en gris de la paleta jaime0
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=#565c78'
if [[ -r /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
    source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# Titulo de la terminal: el directorio en reposo y la orden mientras se ejecuta.
# Kitty lo muestra en la etiqueta inferior de cada terminal.
autoload -Uz add-zsh-hook
_titulo_reposo() { print -Pn '\e]2;%~\a' }
_titulo_orden() { print -n "\e]2;${1%% *}\a" }
add-zsh-hook precmd _titulo_reposo
add-zsh-hook preexec _titulo_orden

# Prompt
if command -v starship >/dev/null 2>&1; then
    eval "$(starship init zsh)"
fi

# Resaltado de sintaxis: debe cargarse el ultimo
if [[ -r /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
    source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

# Fastfetch solo al abrir un kitty interactivo
if [[ -o interactive && -n "$KITTY_WINDOW_ID" ]] && command -v fastfetch >/dev/null 2>&1; then
    if (( COLUMNS >= 86 )); then
        fastfetch
    else
        fastfetch --logo none
    fi
fi
