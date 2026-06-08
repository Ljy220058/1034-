const http = require('http');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, 'frontend');
const server = http.createServer((req, res) => {
  const filePath = path.join(root, req.url === '/' ? 'index.html' : req.url);
  fs.readFile(filePath, (error, buffer) => {
    if (error) {
      res.statusCode = 404;
      res.end('not found');
      return;
    }
    res.end(buffer);
  });
});
server.listen(8092, () => process.stdout.write('ready\n'));
setTimeout(() => server.close(), 12000);
