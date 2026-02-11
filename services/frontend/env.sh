#!/bin/sh
# Replace all environment variables starting with VITE_ in the files in /usr/share/nginx/html
#
# Notes:
# - This script is used to inject runtime env vars into a Vite-built static app by replacing
#   placeholder strings (e.g. "VITE_API_URL") in built JS/CSS files.
# - It must correctly handle values containing spaces and "=".

TARGET_DIR="${TARGET_DIR:-/usr/share/nginx/html}"

env | grep '^VITE_' | while IFS= read -r line; do
    key="${line%%=*}"
    value="${line#*=}"

    # Escape replacement string for sed (delimiter is "|")
    escaped_value=$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')

    find "$TARGET_DIR" -type f \( -name '*.js' -o -name '*.css' \) \
      -exec sed -i "s|${key}|${escaped_value}|g" '{}' +
done

# Generate config.js for runtime config consumers.
CONFIG_FILE="${TARGET_DIR}/config.js"
echo "window.config = {" > "$CONFIG_FILE"
env | grep '^VITE_' | while IFS= read -r line; do
    key="${line%%=*}"
    value="${line#*=}"
    escaped_json_value=$(printf '%s' "$value" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
    echo "  \"$key\": \"$escaped_json_value\"," >> "$CONFIG_FILE"
done
echo "};" >> "$CONFIG_FILE"
