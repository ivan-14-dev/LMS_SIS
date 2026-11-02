FROM node:22.22.1-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY . .

ARG SIS_MODE=secondaire
ARG SIS_AUTH_MODE=lms
ARG BASE_URL
ARG LMS_BASE_URL
ARG STUDIO_BASE_URL
ARG SIS_SECONDAIRE_API_URL
ARG SIS_SUPERIEUR_API_URL
ARG SIS_ADMIN_API_URL
ARG SITE_NAME=SIS
ARG SUPPORT_URL
ARG SUPPORT_EMAIL
ARG TERMS_OF_SERVICE_URL
ARG PRIVACY_POLICY_URL
ENV USE_MOCK_API=false
RUN npm run build

FROM nginx:1.28.0-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
