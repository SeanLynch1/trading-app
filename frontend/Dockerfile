# The website for the server: builds the React app, then serves it with Caddy.
# Caddy also forwards /api/... to the FastAPI container and gets an HTTPS certificate automatically.
# Built by docker-compose.prod.yml; you don't run this by hand.

# ---------- Stage 1: build the React app into plain files ----------
FROM node:22-alpine AS build
WORKDIR /app

# Install packages first (cached until package-lock.json changes), exactly as locked.
COPY package.json package-lock.json ./
RUN npm ci

# Copy the code and build it. VITE_API_URL is baked into the JavaScript at build time,
# e.g. https://your-domain/api (docker-compose.prod.yml passes it in).
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---------- Stage 2: a small web server holding only the built files ----------
# Node and node_modules are left behind in stage 1; only dist/ is kept.
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
