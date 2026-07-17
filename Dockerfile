FROM python:3.12-alpine

RUN apk add --no-cache \
      chromium \
      font-noto-cjk \
      git \
    && addgroup -S wiki \
    && adduser -S -G wiki wiki

COPY wiki-requirements.txt /tmp/wiki-requirements.txt
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check \
      -r /tmp/wiki-requirements.txt

COPY docker/sync-loop.sh /usr/local/bin/wiki-sync
RUN chmod 0755 /usr/local/bin/wiki-sync \
    && mkdir -p /repo /site \
    && chown -R wiki:wiki /repo /site

USER wiki
ENTRYPOINT ["/usr/local/bin/wiki-sync"]
