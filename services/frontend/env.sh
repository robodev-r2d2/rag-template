#!/bin/sh
# Generate config.js with environment variables starting with VITE_
echo "window.config = {" > /usr/share/nginx/html/config.js
for i in $(env | grep VITE_)
do
    key=$(echo $i | cut -d '=' -f 1)
    value=$(echo $i | cut -d '=' -f 2-)
    echo "  \"$key\": \"$value\"," >> /usr/share/nginx/html/config.js
done
echo "};" >> /usr/share/nginx/html/config.js

