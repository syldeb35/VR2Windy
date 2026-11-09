import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { compile } from 'svelte/compiler';

const source = fs.readFileSync(new URL('../src/BoatMeasurements.svelte', import.meta.url), 'utf8');
const compiled = compile(source, { generate: 'ssr' });
const code = compiled.js.code.replace('"svelte/internal"', JSON.stringify(import.meta.resolve('svelte/internal')));
const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)).default;

test('displays the received measurements next to COG and SOG', () => {
    const { html } = component.render({
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
        'SOG :</strong> 5.00 nds',
        'Cap :</strong> 205.7°',
        'Vent réel :</strong> 125.0° / 7.80 nds',
        'Vent apparent :</strong> 42.1° tribord / 9.53 nds',
        'Énergie :</strong> 100',
        'Voile :</strong> 7',
    ]) {
        assert.ok(html.includes(expected), `Missing: ${expected}\n${html}`);
    }
});

test('handles missing instruments and displays port wind and zero energy', () => {
    const empty = component.render({ position: { heading: null, speed: null } }).html;
    assert.doesNotMatch(empty, /COG|SOG|Vent|Énergie|Voile|Cap/);
    const { html } = component.render({
        position: {
            heading: 0,
            speed: 0,
            instruments: { apparent_wind: { angle: 10, speed: 0, side: 'L' }, energy: 0 },
        },
    });
    assert.match(html, /10\.0° bâbord \/ 0\.00 nds/);
    assert.match(html, /Énergie :<\/strong> 0/);
    assert.doesNotMatch(html, /Vent réel|Voile|Cap/);
});
