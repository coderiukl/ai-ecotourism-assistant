FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

FROM node:20-slim

WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY package.json ./

RUN npm install --production --ignore-scripts serve

EXPOSE 5173

CMD ["sh", "-c", "npx serve -s dist -l tcp://0.0.0.0:${PORT:-5173}"]
