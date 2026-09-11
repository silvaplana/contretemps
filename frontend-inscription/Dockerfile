# Même patron 2 étapes que frontend/Dockerfile — voir ce fichier pour le
# détail des commentaires.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=/api
RUN echo "VITE_API_URL=${VITE_API_URL}" > .env.production

RUN npm run build

FROM caddy:alpine

COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80
