# Snippets — Bash

## Boucle for sur fichiers
```bash
for f in ./*.log; do
    echo "=== $f ==="
    tail -n 20 "$f"
done
```

## Grep + awk (extraction d'IPs depuis logs)
```bash
grep -E "Failed password" /var/log/auth.log \
  | awk '{for(i=1;i<=NF;i++) if($i=="from") print $(i+1)}' \
  | sort | uniq -c | sort -rn | head
```

## Template script avec gestion d'erreurs
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

trap 'echo "[ERREUR] ligne $LINENO (code $?)" >&2' ERR

log() { printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }

main() {
    local input="${1:-}"
    if [[ -z "$input" ]]; then
        echo "Usage: $0 <fichier>" >&2
        exit 1
    fi

    [[ -f "$input" ]] || { log "Fichier introuvable : $input"; exit 2; }

    log "Traitement de $input"
    # ... traitement ...
    log "Terminé"
}

main "$@"
```

## Watch parallélisé avec xargs
```bash
find . -type f -name '*.mp4' -print0 \
  | xargs -0 -n1 -P4 -I{} ffmpeg -i {} -c:v libx264 {}.out.mp4
```

## Rotation simple d'un fichier
```bash
file=/var/log/app.log
mv "$file" "$file.$(date +%Y%m%d)"
: > "$file"
```
