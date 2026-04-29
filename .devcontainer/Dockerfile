FROM mcr.microsoft.com/devcontainers/rust:2-1-bookworm

RUN apt update && apt install -y curl
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && apt-get install -y nodejs
RUN npm i -g vercel
RUN cargo install cargo-zigbuild
RUN curl -sL https://ziglang.org/download/0.16.0/zig-x86_64-linux-0.16.0.tar.xz | tar -xJ -C /usr/local && ln -sf /usr/local/zig-x86_64-linux-0.16.0/zig /usr/local/bin/zig
RUN chown -R vscode:vscode /usr/local/cargo/registry
RUN apt install -y python3-pip python3-full python3-dev
