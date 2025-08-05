FROM maven:3.9-eclipse-temurin-24 AS builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn package

FROM eclipse-temurin:24-jre-alpine
RUN apk add --no-cache openssl
WORKDIR /app
COPY --from=builder /app/target/java-proxy-1.0-SNAPSHOT.jar app.jar
COPY cert.pem .
COPY key.pem .
RUN openssl pkcs12 -export -in cert.pem -inkey key.pem -out keystore.p12 -name java-proxy -passout pass:password
ARG JAVA_PROXY_SERVER_PORT
EXPOSE ${JAVA_PROXY_SERVER_PORT}
CMD ["java", "-jar", "app.jar"]