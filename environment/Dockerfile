# Preinstall the exact Codex CLI so Harbor detects it and skips its runtime
# NVM bootstrap (which otherwise clones from GitHub during each trial).
FROM node:22-bookworm-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d AS codex_builder
RUN npm install --global @openai/codex@0.163.0 \
    && codex --version

FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db

# Copy only the Node runtime and the globally installed, pinned Codex CLI.
COPY --from=codex_builder /usr/local/bin/ /usr/local/bin/
COPY --from=codex_builder /usr/local/lib/node_modules/ /usr/local/lib/node_modules/

WORKDIR /app
COPY project/ /app/
RUN useradd --create-home --uid 10001 auditor \
    && chown -R auditor:auditor /app \
    && node --version \
    && codex --version
USER auditor
CMD ["sh", "-c", "sleep infinity"]
