import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { compile } from 'svelte/compiler';

const source = fs.readFileSync(new URL('../src/BoatMeasurements.svelte', import.meta.url), 'utf8');
const compiled = compile(source, { generate: 'ssr' });
const code = compiled.js.code
    .replace('"svelte/internal"', JSON.stringify(import.meta.resolve('svelte/internal')))
    .replace(
        /from (["'])\.\/i18n\.js\1/,
        `from ${JSON.stringify(import.meta.resolve('../src/i18n.js'))}`,
    );
const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)).default;

test('displays the received measurements in English', () => {
    const { html } = component.render({
        language: 'en',
        position: {
            heading: 90,
            speed: 5,
            instruments: {
                boat_heading: 205.66065,
                true_wind: { angle: 125, speed: 7.80234 },
                apparent_wind: { angle: 42.11247, speed: 9.53089, side: 'R' },
                sail: 7,
                energy: 100,
            },
        },
    });
    for (const expected of [
        'COG :</strong> 90.0°',
        'SOG :</strong> 5.0 kn',
        'True :</strong> 125.0° starboard / 7.8 kn',
        'Apparent :</strong> 42.1° starboard / 9.5 kn',
        'Energy :</strong> 100% <strong>stamina</strong>',
        'Sail :</strong>',
    ]) {
        assert.ok(html.includes(expected), `Missing: ${expected}\n${html}`);
    }
});

test('displays French measurements and handles missing instruments', () => {
    const empty = component.render({
        language: 'fr',
        position: { heading: null, speed: null },
    }).html;
    assert.doesNotMatch(empty, /COG|SOG|Réel|Apparent|Énergie :|Voile :|Foiling :/);
    const { html } = component.render({
        language: 'fr',
        position: {
            heading: 0,
            speed: 0,
            instruments: { apparent_wind: { angle: 10, speed: 0, side: 'L' }, energy: 0 },
        },
    });
    assert.match(html, /SOG :<\/strong> 0\.0 nds/);
    assert.match(html, /10\.0° bâbord \/ 0\.0 nds/);
    assert.match(html, /Énergie :<\/strong> 0% <strong>endurance<\/strong>/);
    assert.doesNotMatch(html, /True :|Wind|Energy :|Foiling :/);
});
