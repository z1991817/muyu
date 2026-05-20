FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "click>=8.3.1" \
    "rich>=14.3.3" \
    "seesea==2.2.2" \
    "seesea-core>=2.0.4"

EXPOSE 8080

CMD ["seesea", "server", "--host", "0.0.0.0", "--port", "8080"]
