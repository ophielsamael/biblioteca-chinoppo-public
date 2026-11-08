# Artwork Studio for the Biblioteca Chinoppo (Next.js). Built by the main compose.yaml.
FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:20-slim
ENV NODE_ENV=production DATA_DIR=/app/data PORT=3001
WORKDIR /app
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./
RUN mkdir -p /app/data
EXPOSE 3001
CMD ["sh", "-c", "exec npx next start -p ${PORT}"]
