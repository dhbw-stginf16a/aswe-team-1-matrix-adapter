FROM python:3.6-alpine

LABEL maintainer="Leon Schuermann"

RUN adduser -D flask && pip install pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock openapi api app.py bot.py prefclient.py /app/

RUN pipenv install --deploy --system && chown -R flask:flask /app

USER flask

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:application"]
