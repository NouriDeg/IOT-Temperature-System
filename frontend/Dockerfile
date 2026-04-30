FROM nginx:alpine

# Kopiere Konfiguration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Kopiere statische Dateien
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]