FROM python:3.12-alpine

ENV PUPPETEER_SKIP_DOWNLOAD=true

RUN apk add --no-cache \
      chromium \
      font-noto-cjk \
      git \
      nodejs \
      npm \
    && npm install --global --omit=dev @mermaid-js/mermaid-cli@11.16.0 \
    && npm cache clean --force \
    && addgroup -S wiki \
    && adduser -S -G wiki wiki

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check \
      -r /tmp/requirements.txt

COPY docker/sync-loop.sh /usr/local/bin/wiki-sync
COPY docker/git-askpass.sh /usr/local/bin/wiki-git-askpass
COPY docker/publish-local.sh /usr/local/bin/wiki-publish-local
RUN chmod 0755 \
      /usr/local/bin/wiki-sync \
      /usr/local/bin/wiki-git-askpass \
      /usr/local/bin/wiki-publish-local \
    && mkdir -p /repo /site \
    && chown -R wiki:wiki /repo /site

USER wiki
ENTRYPOINT ["/usr/local/bin/wiki-sync"]
