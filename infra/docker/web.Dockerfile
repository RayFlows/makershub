FROM node:22-alpine AS deps

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

FROM deps AS dev

COPY apps/web apps/web
COPY packages packages

EXPOSE 5173

CMD ["pnpm", "--filter", "@makershub/web", "dev"]

FROM deps AS build

COPY apps/web apps/web
COPY packages packages

RUN pnpm --filter @makershub/web build

FROM nginx:1.29-alpine

RUN apk upgrade --no-cache

COPY infra/docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html

EXPOSE 80
