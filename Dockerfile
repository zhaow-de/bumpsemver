FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    PYENV_ROOT="/.pyenv" \
    PATH="/.pyenv/shims:/.pyenv/bin:${PATH}" \
    # prevent *.pyc files
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update -qq > /dev/null && \
    apt-get install -y -qq --no-install-recommends locales > /dev/null 2>&1 && \
    localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8  && \
    apt-get install -y -qq --no-install-recommends \
        build-essential ca-certificates curl git git-core gnupg libbz2-dev libffi-dev libncurses5-dev libreadline-dev \
        libsqlite3-dev libssl-dev libxml2-dev libxmlsec1-dev llvm make tk-dev wget xz-utils zlib1g-dev > /dev/null && \
    apt-get clean -qq > /dev/null && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY python-versions.txt ./

RUN git config --global user.email "bumpsemver_test@example.org" && \
    git config --global user.name "Bumpsemver Test" && \
    curl -sS -L https://pyenv.run | bash

# version-specific things start here
RUN xargs -P 4 -n 1 pyenv install < python-versions.txt && \
pyenv global $(pyenv versions --bare) && \
find $PYENV_ROOT/versions -type d '(' -name '__pycache__' -o -name 'test' -o -name 'tests' ')' -exec rm -rf '{}' + && \
find $PYENV_ROOT/versions -type f '(' -name '*.py[co]' -o -name '*.exe' ')' -exec rm -f '{}' +

RUN mv -v -- /python-versions.txt $PYENV_ROOT/version && \
    # only install certain versions for tox to use
    pyenv local 3.8.8 && \
    pyenv versions && \
    pyenv global 3.8.8 && \
    python -m pip install -U pip && \
    python -m pip install tox==3.14.0 && \
    pyenv rehash

WORKDIR /app

COPY . .

CMD tox
