export function parseRestrictedZones(text) {
    let data;
    try {
        data = JSON.parse(text);
    } catch (error) {
        throw new Error('invalidRestrictedZones');
    }

    const validPosition = position => Array.isArray(position)
        && position.length >= 2
        && position.every(Number.isFinite)
        && position[0] >= -180 && position[0] <= 180
        && position[1] >= -90 && position[1] <= 90;
    const validRing = ring => Array.isArray(ring)
        && ring.length >= 4
        && ring.every(validPosition)
        && ring[0][0] === ring[ring.length - 1][0]
        && ring[0][1] === ring[ring.length - 1][1];
    const validPolygon = polygon => Array.isArray(polygon)
        && polygon.length > 0
        && polygon.every(validRing);

    if (
        !data || data.type !== 'FeatureCollection'
        || !Array.isArray(data.features) || data.features.length === 0
        || !data.features.every(feature => {
            if (!feature || feature.type !== 'Feature' || !feature.geometry) return false;
            const { type, coordinates } = feature.geometry;
            if (type === 'Polygon') return validPolygon(coordinates);
            return type === 'MultiPolygon' && Array.isArray(coordinates)
                && coordinates.length > 0 && coordinates.every(validPolygon);
        })
    ) {
        throw new Error('invalidRestrictedZones');
    }
    return data;
}
