FROM python:3.6-alpine

LABEL maintainer="Leon Schuermann"

RUN apk add --update git
RUN adduser -D flask && pip install pipenv

WORKDIR /app
ADD deploy.tar /app/

RUN git clone https://github.com/shawnanastasio/python-matrix-bot-api.git -b 962941c
RUN mv python-matrix-bot-api/matrix_bot_api .

RUN pipenv install --deploy --system && chown -R flask:flask /app

USER flask

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:application"]
