const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, '..', 'src', 'nodes', 'OneCai', 'icons');
const destDir = path.join(__dirname, '..', 'dist', 'nodes', 'OneCai', 'icons');

function copyRecursive(source, destination) {
  if (!fs.existsSync(source)) return;

  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const srcPath = path.join(source, entry.name);
    const destPath = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

copyRecursive(srcDir, destDir);

