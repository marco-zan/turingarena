ARG BASE_IMAGE=turingarena/turingarena-base
FROM $BASE_IMAGE

COPY . /usr/local/turingarena/
RUN true \
    && ssh-keygen -A \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && ln -s /usr/lib/jvm/default-jvm/bin/javac /usr/local/bin/javac \
    && ln -s /usr/lib/jvm/default-jvm/bin/jcmd /usr/local/bin/jcmd \
    && cd /usr/local/turingarena/ \
    && python setup.py develop \
    && turingarena pythonsite \
    && turingarena install examples \
    && mkdir /problems \
    && turingarena install /problems \
    && true

ENTRYPOINT ["turingarena"]
WORKDIR /problems
