/**
 * Copie les assets de vendors npm vers `static/vendor/...`
 * pour que WhiteNoise puisse les servir au lieu d'un CDN.
 *
 * Usage: `npm run vendor:copy`
 */
const fs = require('fs');
const path = require('path');

const SRC_DIR = path.join(__dirname, '..', 'node_modules');
const DEST_DIR = path.join(__dirname, '..', 'static', 'vendor');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyFile(src, dest) {
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
  // eslint-disable-next-line no-console
  console.log(`  ${path.relative(process.cwd(), dest)}`);
}

function copyDir(src, dest) {
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else copyFile(s, d);
  }
}

// === Alpine.js ===
copyFile(
  path.join(SRC_DIR, 'alpinejs', 'dist', 'cdn.min.js'),
  path.join(DEST_DIR, 'alpinejs', 'cdn.min.js')
);
copyFile(
  path.join(SRC_DIR, '@alpinejs', 'collapse', 'dist', 'cdn.min.js'),
  path.join(DEST_DIR, 'alpinejs', 'plugin-collapse.min.js')
);

// === SweetAlert2 ===
copyFile(
  path.join(SRC_DIR, 'sweetalert2', 'dist', 'sweetalert2.min.css'),
  path.join(DEST_DIR, 'sweetalert2', 'sweetalert2.min.css')
);
copyFile(
  path.join(SRC_DIR, 'sweetalert2', 'dist', 'sweetalert2.all.min.js'),
  path.join(DEST_DIR, 'sweetalert2', 'sweetalert2.all.min.js')
);

// === FontAwesome (CSS + webfonts) ===
copyFile(
  path.join(SRC_DIR, '@fortawesome', 'fontawesome-free', 'css', 'all.min.css'),
  path.join(DEST_DIR, 'fontawesome', 'css', 'all.min.css')
);
copyDir(
  path.join(SRC_DIR, '@fortawesome', 'fontawesome-free', 'webfonts'),
  path.join(DEST_DIR, 'fontawesome', 'webfonts')
);

// eslint-disable-next-line no-console
console.log('\nVendor assets copiés dans static/vendor/');
