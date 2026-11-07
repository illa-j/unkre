# syntax=docker/dockerfile:1

FROM nginx:1.30-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY 404.html /usr/share/nginx/html/404.html

# This project uses a complete nginx.conf instead of conf.d/default.conf.
RUN rm -f /etc/nginx/conf.d/default.conf && nginx -t

EXPOSE 80 81

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=6 \
    CMD wget -q --spider http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
