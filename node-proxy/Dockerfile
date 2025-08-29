FROM node:22.18.0-alpine AS builder
WORKDIR /app
COPY package*.json tsconfig.json .eslintrc.js .prettierrc.json ./
COPY .eslintignore .
RUN npm install
COPY ./src ./src
RUN npm run build

FROM node:22.18.0-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY --from=builder /app/dist ./dist
COPY cert.pem .
COPY key.pem .
ARG NODE_PROXY_SERVER_PORT
EXPOSE ${NODE_PROXY_SERVER_PORT}
CMD ["node", "dist/index.js"]
