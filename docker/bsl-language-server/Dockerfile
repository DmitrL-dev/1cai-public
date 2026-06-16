FROM eclipse-temurin:17-jre-jammy

ARG BSL_LS_VERSION=0.24.2
ARG BSL_LS_SHA256
ENV BSL_LS_VERSION=${BSL_LS_VERSION}
ENV BSL_LS_SHA256=${BSL_LS_SHA256}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --uid 1200 --create-home bsl

WORKDIR /opt/bsl-language-server

RUN curl -fsSL --retry 5 --retry-all-errors \
        -o bsl-language-server.jar \
        "https://github.com/1c-syntax/bsl-language-server/releases/download/v${BSL_LS_VERSION}/bsl-language-server-${BSL_LS_VERSION}-exec.jar" \
    && if [[ -n "${BSL_LS_SHA256}" ]]; then \
        echo "${BSL_LS_SHA256}  bsl-language-server.jar" | sha256sum -c - ; \
    fi \
    && chown bsl:bsl bsl-language-server.jar

EXPOSE 8080

USER bsl

ENTRYPOINT ["java", "-jar", "/opt/bsl-language-server/bsl-language-server.jar"]

