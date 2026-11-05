FROM node:22-slim AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
COPY deploy/docker/npm-cache /npm-cache
RUN if [ -d /npm-cache/_cacache ]; then \
        npm ci --offline --cache /npm-cache --no-fund --no-audit; \
    else \
        npm ci --no-fund --no-audit; \
    fi
COPY dashboard/index.html dashboard/tsconfig.json dashboard/vite.config.ts ./
COPY dashboard/src ./src
RUN npm run build

FROM nginx:alpine
COPY deploy/docker/dashboard.nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
