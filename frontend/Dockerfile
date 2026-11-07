# syntax=docker/dockerfile:1

FROM node:26-alpine AS deps
WORKDIR /app
# sharp ships prebuilt musl binaries, so no libc6-compat layer (and no apk
# network round-trip) is needed for Next.js image optimisation.
COPY package.json package-lock.json ./
RUN npm ci

# Kept as a separate target so docker-compose-dev.yml can run `next dev`
# against the same dependency set.
FROM deps AS builder
WORKDIR /app
COPY . .
ARG NEXT_PUBLIC_API_URL=/api
ARG NEXT_PUBLIC_SITE_URL=
ARG NEXT_PUBLIC_CSRF_HEADER_NAME=X-CSRF-Token
ARG SITE_INDEXABLE=true
ARG NEXT_PUBLIC_WELCOME_CREDITS=15
ARG NEXT_PUBLIC_SUPPORT_EMAIL=
ARG NEXT_PUBLIC_PRIVACY_URL=
ARG NEXT_PUBLIC_TERMS_URL=
ARG NEXT_PUBLIC_TELEGRAM_BOT_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_CSRF_HEADER_NAME=$NEXT_PUBLIC_CSRF_HEADER_NAME \
    SITE_INDEXABLE=$SITE_INDEXABLE \
    NEXT_PUBLIC_WELCOME_CREDITS=$NEXT_PUBLIC_WELCOME_CREDITS \
    NEXT_PUBLIC_SUPPORT_EMAIL=$NEXT_PUBLIC_SUPPORT_EMAIL \
    NEXT_PUBLIC_PRIVACY_URL=$NEXT_PUBLIC_PRIVACY_URL \
    NEXT_PUBLIC_TERMS_URL=$NEXT_PUBLIC_TERMS_URL \
    NEXT_PUBLIC_TELEGRAM_BOT_URL=$NEXT_PUBLIC_TELEGRAM_BOT_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:26-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./package.json
COPY --from=builder --chown=nextjs:nodejs /app/next.config.ts ./next.config.ts
COPY --from=builder --chown=nextjs:nodejs /app/tsconfig.json ./tsconfig.json

USER nextjs
EXPOSE 3000

CMD ["npm", "run", "start"]
