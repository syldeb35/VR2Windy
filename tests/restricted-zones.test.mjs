import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

import { parseRestrictedZones } from '../src/restrictedZones.js';

const ring = [[-10, 43], [-9, 43], [-9, 42], [-10, 43]];
const collection = geometry => ({
    type: 'FeatureCollection',
    features: [{ type: 'Feature', properties: { name: 'Zone' }, geometry }],
});

test('accepts named polygons with holes and multipolygons', () => {
    const data = collection({ type: 'Polygon', coordinates: [ring, ring] });
    data.features.push({
        type: 'Feature',
        properties: { name: 'Another zone' },
        geometry: { type: 'MultiPolygon', coordinates: [[ring], [ring]] },
    });
    assert.deepEqual(parseRestrictedZones(JSON.stringify(data)), data);
});

test('rejects invalid JSON, empty collections and invalid polygon coordinates', () => {
    const invalid = [
        '{',
        JSON.stringify({ type: 'FeatureCollection', features: [] }),
        JSON.stringify(collection({ type: 'Point', coordinates: [0, 0] })),
        JSON.stringify(collection({ type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1]]] })),
        JSON.stringify(collection({ type: 'Polygon', coordinates: [[[181, 0], [1, 0], [1, 1], [181, 0]]] })),
        JSON.stringify(collection({ type: 'MultiPolygon', coordinates: [] })),
    ];
    for (const text of invalid) {
        assert.throws(() => parseRestrictedZones(text), /invalidRestrictedZones/);
    }
});

function createImportHarness() {
    const source = fs.readFileSync(new URL('../src/plugin.svelte', import.meta.url), 'utf8');
    const escapeHtml = source.slice(source.indexOf('    function escapeHtml('), source.indexOf('    /**\n     * Parses a GPX'));
    const handlers = source.slice(source.indexOf('    async function importRestrictedZones('), source.indexOf('    /**\n     * Handles the import of GPX'));
    const layers = new Set();
    const context = vm.createContext({
        mounted: true,
        restrictedZonesLayer: null,
        restrictedZonesName: '',
        restrictedZonesStatus: '',
        restrictedZonesRequest: 0,
        parseRestrictedZones,
        t: (key, values = {}) => `${key}${values.errors ? `: ${values.errors}` : ''}`,
        map: {
            removeLayer: layer => layers.delete(layer),
        },
        L: {
            geoJSON: (data, options) => {
                const layer = {
                    features: [],
                    addTo() { layers.add(this); return this; },
                };
                assert.equal(options.interactive, true);
                for (const feature of data.features) {
                    const handlers = {};
                    options.onEachFeature(feature, { on: (event, handler) => { handlers[event] = handler; } });
                    layer.features.push(handlers);
                }
                return layer;
            },
            tooltip: () => ({
                setLatLng(latlng) { this.latlng = latlng; return this; },
                setContent(content) { this.content = content; return this; },
                addTo() { layers.add(this); return this; },
            }),
        },
    });
    vm.runInContext(`${escapeHtml}\n${handlers}`, context);
    return { context, layers };
}

function fileEvent(name, contents, size = 1) {
    return { currentTarget: { files: [{ name, size, text: () => Promise.resolve(contents) }], value: name } };
}

test('imports, replaces and removes zones; failed imports preserve the previous layer', async () => {
    const { context, layers } = createImportHarness();
    const data = collection({ type: 'Polygon', coordinates: [ring] });
    data.features[0].properties.name = '<img src=x onerror=alert(1)>';
    const event = fileEvent('zones.json', JSON.stringify(data));
    await context.importRestrictedZones(event);
    const firstLayer = context.restrictedZonesLayer;
    assert.equal(event.currentTarget.value, '');
    assert.equal(layers.size, 1);
    assert.equal(context.restrictedZonesName, 'zones.json');
    firstLayer.features[0].mouseover({ latlng: [43, -9] });
    const tooltip = [...layers].find(layer => layer !== firstLayer);
    assert.equal(tooltip.content, '&lt;img src=x onerror=alert(1)&gt;');
    firstLayer.features[0].mousemove({ latlng: [42, -9] });
    assert.deepEqual(tooltip.latlng, [42, -9]);
    firstLayer.features[0].remove();
    assert.equal(layers.size, 1);

    await context.importRestrictedZones(fileEvent('bad.json', '{'));
    assert.equal(context.restrictedZonesLayer, firstLayer);
    assert.equal(layers.size, 1);
    assert.match(context.restrictedZonesStatus, /invalidRestrictedZones/);

    await context.importRestrictedZones(fileEvent('big.json', '{}', 25 * 1024 * 1024 + 1));
    assert.equal(context.restrictedZonesLayer, firstLayer);
    assert.match(context.restrictedZonesStatus, /fileTooLarge/);

    await context.importRestrictedZones(fileEvent('new.json', JSON.stringify(data)));
    assert.equal(layers.size, 1);
    assert.equal(layers.has(firstLayer), false);
    assert.equal(context.restrictedZonesName, 'new.json');
    context.removeRestrictedZones();
    assert.equal(layers.size, 0);
    assert.equal(context.restrictedZonesLayer, null);
});

test('reports the original error and cleanup failure when adding a layer fails', async () => {
    const { context } = createImportHarness();
    const warnings = [];
    context.console = { warn: (...args) => warnings.push(args) };
    context.L.geoJSON = () => ({ addTo() { throw new Error('add failed'); } });
    context.map.removeLayer = () => { throw new Error('cleanup failed'); };
    const data = collection({ type: 'Polygon', coordinates: [ring] });
    await context.importRestrictedZones(fileEvent('zones.json', JSON.stringify(data)));
    assert.match(context.restrictedZonesStatus, /add failed/);
    assert.match(context.restrictedZonesStatus, /restrictedZonesCleanupError/);
    assert.equal(warnings.length, 1);
});

test('ignores a pending import after removal or a newer selection', async () => {
    const { context, layers } = createImportHarness();
    const data = JSON.stringify(collection({ type: 'Polygon', coordinates: [ring] }));
    let finishRead;
    const event = { currentTarget: { files: [{
        name: 'slow.json',
        size: 1,
        text: () => new Promise(resolve => { finishRead = resolve; }),
    }], value: 'slow.json' } };
    const pending = context.importRestrictedZones(event);
    await context.importRestrictedZones(fileEvent('new.json', data));
    finishRead(data);
    await pending;
    assert.equal(context.restrictedZonesName, 'new.json');
    assert.equal(layers.size, 1);

    const pendingRemoval = context.importRestrictedZones(event);
    context.removeRestrictedZones();
    finishRead(data);
    await pendingRemoval;
    assert.equal(layers.size, 0);
    assert.equal(context.restrictedZonesLayer, null);
});
