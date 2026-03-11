FROM node:22-alpine

WORKDIR /app

COPY package.json ./
COPY tsconfig.base.json ./
COPY src/api/package.json ./src/api/package.json
COPY src/web/package.json ./src/web/package.json

RUN npm install

COPY src/web ./src/web

WORKDIR /app/src/web

CMD ["npm", "run", "dev"]
