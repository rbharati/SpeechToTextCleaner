import { mkdir, writeFile } from 'node:fs/promises';
import { networkInterfaces } from 'node:os';
import selfsigned from 'selfsigned';

const certDir = new URL('../certs/', import.meta.url);

function getLanIp() {
  const interfaces = networkInterfaces();

  for (const addresses of Object.values(interfaces)) {
    for (const address of addresses ?? []) {
      if (
        address.family === 'IPv4'
        && !address.internal
        && /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.)/.test(address.address)
      ) {
        return address.address;
      }
    }
  }

  return '127.0.0.1';
}

const lanIp = getLanIp();
const certificate = selfsigned.generate(
  [
    { name: 'commonName', value: lanIp },
    { name: 'organizationName', value: 'Speech Cleaner Local HTTPS' },
  ],
  {
    algorithm: 'sha256',
    days: 365,
    keySize: 2048,
    extensions: [
      { name: 'basicConstraints', cA: false },
      {
        name: 'keyUsage',
        digitalSignature: true,
        keyEncipherment: true,
      },
      { name: 'extKeyUsage', serverAuth: true },
      {
        name: 'subjectAltName',
        altNames: [
          { type: 2, value: 'localhost' },
          { type: 2, value: lanIp },
          { type: 7, ip: '127.0.0.1' },
          { type: 7, ip: lanIp },
        ],
      },
    ],
  },
);

await mkdir(certDir, { recursive: true });
await writeFile(new URL('lan-cert.pem', certDir), certificate.cert);
await writeFile(new URL('lan-key.pem', certDir), certificate.private);

console.log(`Generated HTTPS certificate for localhost and ${lanIp}`);
console.log(`Open on phone: https://${lanIp}:5174`);
