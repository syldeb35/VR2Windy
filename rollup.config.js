import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import terser from '@rollup/plugin-terser';
import serve from 'rollup-plugin-serve';
import rollupSvelte from 'rollup-plugin-svelte';
import config from './src/pluginConfig.js';

function windyPluginMetadata() {
    return {
        name: 'windy-plugin-metadata',
        renderChunk(code, chunk, outputOptions) {
            const outputDirectory = dirname(outputOptions.file);
            mkdirSync(outputDirectory, { recursive: true });

            const pluginConfig = {
                ...config,
                built: Date.now(),
                builtReadable: new Date().toISOString(),
            };
            const formattedConfig = JSON.stringify(pluginConfig, null, 2);
            writeFileSync(join(outputDirectory, 'plugin.json'), formattedConfig);

            const namedImportsRewritten = code.replace(
                /import\s+\{([^}]+)\}\s+from\s+(['"])@windy\/([^'"]+)\2\s*;?/g,
                (_match, imports, _quote, moduleName) => `const {${imports}} = W.${moduleName};`,
            );
            const importsRewritten = namedImportsRewritten.replace(
                /import\s+([A-Za-z_$][\w$]*)\s+from\s+(['"])@windy\/([^'"]+)\2\s*;?/g,
                (_match, importedName, _quote, moduleName) => `const ${importedName} = W.${moduleName};`,
            );
            if (importsRewritten.includes("from '@windy/") || importsRewritten.includes('from "@windy/')) {
                this.error('Unprocessed @windy import in plugin bundle.');
            }

            return {
                code: `const __pluginConfig = ${formattedConfig};\n${importsRewritten}\nexport { __pluginConfig };\n`,
                map: null,
            };
        },
    };
}

function localTlsOptions() {
    return {
        key: readFileSync('.local-ssl/localhost-key.pem'),
        cert: readFileSync('.local-ssl/localhost-cert.pem'),
    };
}

export default {
    input: 'src/plugin.svelte',
    output: [
        {
            file: 'dist/plugin.js',
            format: 'module',
            sourcemap: true,
        },
        {
            file: 'dist/plugin.min.js',
            format: 'module',
            plugins: [terser()],
        },
    ],
    external: id => id.startsWith('@windy/'),
    plugins: [
        rollupSvelte({ emitCss: false }),
        resolve({
            browser: true,
            mainFields: ['module', 'jsnext:main', 'main'],
            preferBuiltins: false,
            dedupe: ['svelte'],
        }),
        commonjs(),
        windyPluginMetadata(),
        process.env.SERVE !== 'false' &&
            serve({
                contentBase: 'dist',
                host: 'localhost',
                port: 9999,
                headers: {
                    'Access-Control-Allow-Origin': '*',
                },
                https: localTlsOptions(),
            }),
    ],
};
