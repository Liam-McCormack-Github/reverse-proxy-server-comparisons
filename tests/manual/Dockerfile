FROM alpine:latest
RUN apk update && apk add --no-cache netcat-openbsd busybox-extras curl wget
WORKDIR /app
COPY ./scripts/test.sh /app/test.sh
RUN chmod +x /app/test.sh
CMD ["sleep", "infinity"]