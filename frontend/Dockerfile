FROM nginx:alpine

# Static assets (HTML/CSS/JS). API_BASE is same-origin: the Ingress routes API
# paths to the backend, so nginx only needs to serve the static files.
COPY frontend/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
