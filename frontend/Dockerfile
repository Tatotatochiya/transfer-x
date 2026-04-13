# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Declare build-time arg so Railway can inject VITE_API_BASE_URL at build time
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ARG VITE_WS_URL
ENV VITE_WS_URL=$VITE_WS_URL
RUN npx vite build

# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
RUN npm install -g serve
EXPOSE 3000
# PORT is injected by Railway at runtime; fall back to 3000 locally
CMD ["sh", "-c", "serve -s dist -l ${PORT:-3000} --no-clipboard"]
