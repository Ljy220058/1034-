const http = require('http');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, 'frontend');
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8'
};
const port = Number(process.env.PORT || 19091);

const server = http.createServer((request, response) => {
  const requestUrl = new URL(request.url, `http://127.0.0.1:${port}`);
  const targetPath = requestUrl.pathname === '/' ? 'index.html' : requestUrl.pathname.replace(/^\//, '');
  const filePath = path.resolve(root, targetPath);

  if (!filePath.startsWith(root)) {
    response.writeHead(403);
    response.end('forbidden');
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      response.writeHead(404);
      response.end('not found');
      return;
    }
    response.writeHead(200, { 'content-type': types[path.extname(filePath)] || 'application/octet-stream' });
    response.end(data);
  });
});

server.listen(port, '127.0.0.1', () => {
  process.stderr.write(`static server ready http://127.0.0.1:${port}\n`);
});
