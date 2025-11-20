# syntax=docker/dockerfile:1

# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies first for better layer caching
COPY package*.json ./
RUN npm ci

# Copy the remaining source and build the production bundle
COPY . .
RUN npm run build

# Runtime stage
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx already serves on 80; expose for clarity
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
