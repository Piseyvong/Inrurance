# Frontend image: Vite/React SPA built once, then served as static files by nginx.
#
# VITE_API_BASE_URL is compiled into the JS bundle at build time (Vite env
# vars are not readable at container runtime), so it must be passed as a
# build ARG pointing at wherever the backend is actually publicly reachable —
# rebuild this image if that address ever changes.
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
