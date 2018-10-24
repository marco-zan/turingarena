#!/usr/bin/env bash

true \
    && cd /src/cli/ \
    && echo "VERSION='$CLI_VERSION'" > turingarena_common/build_version.py \
    && python3 setup.py egg_info bdist_wheel \
    && twine upload dist/* \
    && cd / \
    && hyper \
        config \
        --default-region=us-west-1 \
        --accesskey=$HYPERSH_ACCESS_KEY \
        --secretkey=$HYPERSH_SECRET_KEY \
    && hyper pull $DOCKER_IMAGE \
    && HYPERSH_DANGLING_IMAGES=$(hyper images -q --filter "dangling=true") \
    && echo HYPERSH_DANGLING_IMAGES=$HYPERSH_DANGLING_IMAGES >&2 \
    && ( hyper rmi $HYPERSH_DANGLING_IMAGES || true ) \
    && ( hyper func rm $HYPERSH_FUNC_NAME || true ) \
    && hyper func create \
        --name $HYPERSH_FUNC_NAME \
        --env AWS_DEFAULT_REGION=us-east-1 \
        --env AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
        --env AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
        --env DYNAMODB_EVALUATION_EVENTS_TABLE=turingarena-$SERVERLESS_STAGE-EvaluationEventsTable \
        --env S3_FILES_BUCKET=turingarena-$SERVERLESS_STAGE-files \
        $DOCKER_IMAGE \
        python -m turingarena_impl.api.hypersh_api \
    && export HYPERSH_FUNC_ID=$(hyper func inspect $HYPERSH_FUNC_NAME | jq -r .[0].UUID) \
    && echo HYPERSH_FUNC_ID=$HYPERSH_FUNC_ID >&2 \
    && cd /src/backend/ \
    && npm install \
    && serverless deploy --stage $SERVERLESS_STAGE \
    && true

exit $?
