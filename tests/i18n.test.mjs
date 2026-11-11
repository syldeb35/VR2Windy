import assert from 'node:assert/strict';
import test from 'node:test';

import { getLanguage, translate } from '../src/i18n.js';

test('uses French for French browser locales and English otherwise', () => {
    const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    try {
        Object.defineProperty(globalThis, 'navigator', {
            configurable: true,
            value: { languages: ['fr-CA'], language: 'fr-CA' },
        });
        assert.equal(getLanguage(), 'fr');

        Object.defineProperty(globalThis, 'navigator', {
            configurable: true,
            value: { languages: ['de-DE'], language: 'de-DE' },
        });
        assert.equal(getLanguage(), 'en');

        Object.defineProperty(globalThis, 'navigator', {
            configurable: true,
            value: undefined,
        });
        assert.equal(getLanguage(), 'en');
    } finally {
        if (originalNavigator) {
            Object.defineProperty(globalThis, 'navigator', originalNavigator);
        } else {
            delete globalThis.navigator;
        }
    }
});

test('interpolates values and falls back to English for unknown languages', () => {
    assert.equal(translate('noPosition', { raceId: 845 }, 'fr'), 'Aucune position pour la course 845. Vérifie l’ID et l’option NMEA output.');
    assert.equal(translate('followRace', {}, 'de'), 'Follow this race');
});
