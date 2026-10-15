# ---- Étape 1 : "build" — compile l'app React avec Node ----
# Cette étape produit des fichiers HTML/CSS/JS statiques (dist/).
# Node ne sera PAS présent dans l'image finale : il ne sert qu'à construire.
FROM node:22-alpine AS build

WORKDIR /app

# On copie d'abord package.json / package-lock.json seuls : tant que les
# dépendances ne changent pas, Docker réutilise le cache et évite de
# relancer "npm ci" (qui est l'étape la plus longue) à chaque build.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# URL de l'API utilisée par le frontend une fois compilé (voir
# docker-compose.yml pour la valeur réelle : l'app est servie sous un
# sous-chemin du domaine partagé, pas à sa racine).
ARG VITE_API_URL=/api
# "Sauvegarder École" -> Google Drive (voir .env.example) — PAS secret
# (voir sa docstring), vide par défaut : sans lui, seule la destination
# "Cet appareil" est proposée, sans erreur (voir utils/googleDrive.js).
ARG VITE_GOOGLE_CLIENT_ID=
# Adresses d'école (spec §2.7, service "frontend-ecoles" de
# docker-compose.yml) : l'app à la racine, et le nom de l'école dans
# index.html (voir vite.config.js : enteteEcole). Vides : build de
# l'adresse générique /contretemps/.
ARG VITE_BASE=
ARG VITE_ENTETE_ECOLE=
ENV VITE_ENTETE_ECOLE=${VITE_ENTETE_ECOLE}
# Page d'inscription (« Inscription élève » d'Admin > Élèves) : sur une
# adresse d'école, elle reste sur silvaplana.cloud, d'où une adresse complète.
ARG VITE_INSCRIPTION_URL=
RUN printf 'VITE_API_URL=%s\nVITE_GOOGLE_CLIENT_ID=%s\n' "${VITE_API_URL}" "${VITE_GOOGLE_CLIENT_ID}" > .env.production \
    && if [ -n "$VITE_INSCRIPTION_URL" ]; then printf 'VITE_INSCRIPTION_URL=%s\n' "$VITE_INSCRIPTION_URL" >> .env.production; fi

RUN if [ -n "$VITE_BASE" ]; then VITE_BASE="$VITE_BASE" npm run build; else npm run build; fi

# ---- Étape 2 : image finale — juste Caddy + les fichiers statiques ----
# Caddy sert ici les fichiers statiques et fait le reverse proxy vers
# l'API, en interne uniquement (pas de TLS ici, voir Caddyfile : c'est
# le Caddy "gateway" partagé du VPS qui gère le domaine/HTTPS et route
# vers ce conteneur).
FROM caddy:alpine

COPY --from=build /app/dist /srv
# Caddyfile (adresse générique /contretemps/) ou Caddyfile.ecoles (adresses
# d'école), voir docker-compose.yml.
ARG CADDYFILE=Caddyfile
COPY ${CADDYFILE} /etc/caddy/Caddyfile

EXPOSE 80
