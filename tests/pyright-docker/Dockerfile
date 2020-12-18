FROM node:14.15.3-alpine3.10
RUN npm install -g pyright
CMD ["node", "/usr/local/lib/node_modules/pyright/langserver.index.js", "--stdio"]
