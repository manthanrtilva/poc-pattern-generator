FROM mcr.microsoft.com/devcontainers/rust:2-1-bookworm

RUN apt update && apt install -y curl
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && apt-get install -y nodejs