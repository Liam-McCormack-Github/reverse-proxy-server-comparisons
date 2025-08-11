# --- Stage 1: Build Environment ---
# Use a Node.js image that includes the full build toolchain.
# Alpine versions are small and secure.
FROM node:22.18.0-alpine AS builder

# Set the working directory inside the container
WORKDIR /app

# Copy configuration files first to leverage Docker layer caching.
# This layer will only be rebuilt if these files change.
COPY package*.json tsconfig.json .eslintrc.js .prettierrc.json ./
COPY .eslintignore .

# Install all dependencies, including development dependencies needed for building.
RUN npm install

# Copy the application source code
COPY ./src ./src

# Run the build script from package.json to compile TypeScript to JavaScript.
# This will create the 'dist' directory.
RUN npm run build


# --- Stage 2: Production Environment ---
# Start from a fresh, lightweight Node.js image.
FROM node:22.18.0-alpine

WORKDIR /app

# Copy package files again
COPY package*.json ./

# Install *only* the production dependencies.
# The --omit=dev flag skips all packages listed in devDependencies.
RUN npm install --omit=dev

# Copy the compiled JavaScript code from the 'builder' stage.
COPY --from=builder /app/dist ./dist

# Copy the SSL certificates needed by the HTTPS server.
COPY cert.pem .
COPY key.pem .

# Get the port number from the docker-compose file.
ARG NODE_PROXY_SERVER_PORT
EXPOSE ${NODE_PROXY_SERVER_PORT}

# The command to run when the container starts.
CMD ["node", "dist/index.js"]
