# Builder stage: Compiles the Go applications
FROM golang:1.24-alpine AS builder
WORKDIR /app

# --- FIX 1: Install C compiler for cgo ---
# The go-sqlite3 driver requires a C compiler (gcc) to build.
RUN apk add --no-cache gcc musl-dev

# --- FIX 2: Paths updated for the new build context ---
# The build context is now 'target-server', so paths are relative to it.
COPY ./go-target-server/go/go.mod ./go-target-server/go/go.sum ./
RUN go mod download
COPY ./go-target-server/go/ ./

# --- FIX 3: Enable CGO for the build commands ---
# Set CGO_ENABLED=1 to allow Go to compile the C-based SQLite driver.
RUN CGO_ENABLED=1 go build -o /bin/server ./cmd/server
RUN CGO_ENABLED=1 go build -o /bin/create_proxy_user ./cmd/create_proxy_user
RUN CGO_ENABLED=1 go build -o /bin/generate_new_token ./cmd/generate_new_token

# Final stage: Creates the minimal production image
FROM alpine:latest
ARG TARGET_SERVER_PORT

# Create a non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# --- FIX 4: Paths updated for the new build context ---
# The build context is now 'target-server', so paths are relative to it.
COPY --chown=appuser:appgroup ./website/ /app/website/
COPY --chown=appuser:appgroup ./cert.pem ./key.pem /app/
COPY --chown=appuser:appgroup ./master_token.txt /app/

# Copy the compiled binaries from the builder stage
COPY --from=builder /bin/server /app/server
COPY --from=builder /bin/create_proxy_user /app/create_proxy_user
COPY --from=builder /bin/generate_new_token /app/generate_new_token

# Switch to the non-root user
USER appuser
WORKDIR /app

# Expose the port and set the default command
EXPOSE ${TARGET_SERVER_PORT}
CMD ["./server"]
