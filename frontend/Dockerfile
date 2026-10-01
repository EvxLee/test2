FROM node:20-alpine AS development-dependencies-env
COPY . /app
WORKDIR /app
RUN npm ci

FROM node:20-alpine AS production-dependencies-env
COPY ./package.json package-lock.json /app/
WORKDIR /app
RUN npm ci --omit=dev

FROM node:20-alpine AS build-env
COPY . /app/
COPY --from=development-dependencies-env /app/node_modules /app/node_modules
WORKDIR /app

ARG VITE_KEYCLOAK_AUTH_URL
ARG VITE_KEYCLOAK_CLIENT_ID
ARG VITE_ATLAS_FRONTEND_URL
ARG VITE_ATLAS_API_URL
ARG VITE_ATLAS_API_TOKEN
ARG VITE_KEYCLOAK_REALM
ARG VITE_KEYCLOAK_URL

ENV VITE_KEYCLOAK_AUTH_URL=$VITE_KEYCLOAK_AUTH_URL
ENV VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID
ENV VITE_ATLAS_FRONTEND_URL=$VITE_ATLAS_FRONTEND_URL
ENV VITE_ATLAS_API_URL=$VITE_ATLAS_API_URL
ENV VITE_ATLAS_API_TOKEN=$VITE_ATLAS_API_TOKEN
ENV VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
RUN npm run build

FROM node:20-alpine
COPY ./package.json package-lock.json /app/
COPY --from=production-dependencies-env /app/node_modules /app/node_modules
COPY --from=build-env /app/build /app/build
WORKDIR /app
CMD ["npm", "run", "start"]