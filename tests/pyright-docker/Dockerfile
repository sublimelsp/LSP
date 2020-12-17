FROM node:15.4.0-alpine3.10
RUN npm install -g pyright
CMD ["node", "/usr/local/lib/node_modules/pyright/langserver.index.js", "--stdio"]
