FROM node:20-alpine

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY apps/docs/package.json apps/docs/package.json
COPY packages/api-client/package.json packages/api-client/package.json
COPY packages/config/package.json packages/config/package.json
COPY packages/ui/package.json packages/ui/package.json

RUN pnpm install --frozen-lockfile

COPY apps/docs apps/docs

EXPOSE 5175

CMD ["pnpm", "--filter", "@makershub/docs", "exec", "vitepress", "dev", "docs", "--host", "0.0.0.0", "--port", "5175"]
