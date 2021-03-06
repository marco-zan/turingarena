#!/usr/bin/env bash

python -m turingarena.api.make_hypersh_files_request $1 | sudo docker run \
    --rm \
    -i \
    --mount=type=bind,src=$(dirname $(realpath $0))/..,dst=/usr/local/turingarena/,readonly \
    --env AWS_DEFAULT_REGION=$(aws configure get region) \
    --env AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id) \
    --env AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key) \
    turingarena/turingarena \
    python -m turingarena.api.hypersh_api