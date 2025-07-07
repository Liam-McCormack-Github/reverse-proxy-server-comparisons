FROM python:3.11-slim
ARG TARGET_SERVER_PORT
WORKDIR /app
COPY server.py .
EXPOSE ${TARGET_SERVER_PORT}
CMD ["python", "-u", "server.py"]
