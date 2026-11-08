import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';

const directory = '.local-ssl';
const keyPath = `${directory}/localhost-key.pem`;
const certificatePath = `${directory}/localhost-cert.pem`;

if (!existsSync(keyPath) || !existsSync(certificatePath)) {
    mkdirSync(directory, { recursive: true });
    try {
        execFileSync('openssl', [
            'req',
            '-x509',
            '-newkey',
            'rsa:2048',
            '-keyout',
            keyPath,
            '-out',
            certificatePath,
            '-days',
            '365',
            '-nodes',
            '-subj',
            '/CN=localhost',
            '-addext',
            'subjectAltName=DNS:localhost,IP:127.0.0.1',
        ], { stdio: 'inherit' });
    } catch (error) {
        throw new Error('Unable to create the local HTTPS certificate. Install OpenSSL and retry.', {
            cause: error,
        });
    }
}
