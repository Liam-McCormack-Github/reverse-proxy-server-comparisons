FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/proxy -ldflags "-w -s" .

FROM scratch
WORKDIR /app
COPY --from=builder /app/proxy .
ARG PROXY_SERVER_GO_PORT
EXPOSE ${PROXY_SERVER_GO_PORT}
CMD ["/app/proxy"]