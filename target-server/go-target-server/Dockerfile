FROM golang:1.24-alpine AS builder
WORKDIR /app
RUN apk add --no-cache gcc musl-dev
COPY ./go-target-server/go/go.mod ./go-target-server/go/go.sum ./
RUN go mod download
COPY ./go-target-server/go/ ./
RUN CGO_ENABLED=1 go build -o /bin/server ./cmd/server
RUN CGO_ENABLED=1 go build -o /bin/create_proxy_user ./cmd/create_proxy_user
RUN CGO_ENABLED=1 go build -o /bin/generate_new_token ./cmd/generate_new_token

FROM alpine:latest
ARG TARGET_SERVER_PORT
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup ./website/ /app/website/
COPY --chown=appuser:appgroup ./cert.pem ./key.pem /app/
COPY --chown=appuser:appgroup ./master_token.txt /app/
COPY --from=builder /bin/server /app/server
COPY --from=builder /bin/create_proxy_user /app/create_proxy_user
COPY --from=builder /bin/generate_new_token /app/generate_new_token
USER appuser
WORKDIR /app
EXPOSE ${TARGET_SERVER_PORT}
CMD ["./server"]
