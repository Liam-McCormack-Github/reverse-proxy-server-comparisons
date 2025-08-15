FROM python:3.11-slim
ARG TARGET_SERVER_PORT

WORKDIR /app

# --- FIX: Paths updated for the new build context ---
# The build context is now 'target-server', so paths are relative to it.
COPY ./python-target-server/python/ ./
COPY ./website/ ./website/
COPY ./cert.pem .
COPY ./key.pem .
COPY ./master_token.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port and set the default command
EXPOSE ${TARGET_SERVER_PORT}
CMD ["python", "-u", "server.py"]
