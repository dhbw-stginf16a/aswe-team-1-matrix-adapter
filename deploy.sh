#!/bin/bash

echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
docker build -t asweteam1/matrix-adapter:latest -t asweteam1/matrix-adapter:$TRAVIS_TAG --label version="$TRAVIS_TAG" .
docker push asweteam1/matrix-adapter:latest
docker push asweteam1/matrix-adapter:$TRAVIS_TAG
