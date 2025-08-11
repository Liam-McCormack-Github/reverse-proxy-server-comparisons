FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/proxy -ldflags "-w -s" ./cmd/proxy

FROM scratch
WORKDIR /app
COPY --from=builder /app/proxy .
COPY --from=builder /app/cert.pem .
COPY --from=builder /app/key.pem .
ARG GO_PROXY_SERVER_PORT
EXPOSE ${GO_PROXY_SERVER_PORT}
CMD ["/app/proxy"]