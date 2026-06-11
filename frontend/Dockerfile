FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
ARG VITE_API_URL=https://ai-ecotourism-backend.onrender.com
ARG VITE_INTRO_VIDEO_URL
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_INTRO_VIDEO_URL=$VITE_INTRO_VIDEO_URL
RUN npm run build

FROM node:20-slim

WORKDIR /app

COPY --from=builder /app/dist ./dist

RUN npm install -g serve@14

EXPOSE 5173

CMD ["sh", "-c", "npx serve -s dist -l tcp://0.0.0.0:${PORT:-5173}"]
