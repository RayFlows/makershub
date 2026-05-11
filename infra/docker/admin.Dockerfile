FROM node:26-alpine AS deps

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN if command -v corepack >/dev/null 2>&1; then \
        corepack enable; \
    else \
        npm install --global pnpm@9.15.9; \
    fi

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY apps/docs/package.json apps/docs/package.json
COPY packages/api-client/package.json packages/api-client/package.json
COPY packages/config/package.json packages/config/package.json
COPY packages/ui/package.json packages/ui/package.json

RUN pnpm install --frozen-lockfile

FROM deps AS dev

COPY apps/admin apps/admin
COPY packages packages

EXPOSE 5174

CMD ["pnpm", "--filter", "@makershub/admin", "dev"]

FROM deps AS build

COPY apps/admin apps/admin
COPY packages packages

RUN pnpm --filter @makershub/admin build

FROM nginx:1.29-alpine

RUN apk upgrade --no-cache

COPY infra/docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/admin/dist /usr/share/nginx/html

EXPOSE 80
