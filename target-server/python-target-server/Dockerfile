FROM python:3.11-slim
ARG TARGET_SERVER_PORT
WORKDIR /app
COPY ./python-target-server/python/ ./
COPY ./website/ ./website/
COPY ./cert.pem .
COPY ./key.pem .
COPY ./master_token.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE ${TARGET_SERVER_PORT}
CMD ["python", "-u", "server.py"]
