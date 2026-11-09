<svelte:window on:keydown={handleWindowKeydown} />
<div class="plugin__mobile-header">{title}</div>
<section class="plugin__content">
  <div class="plugin__title plugin__title--chevron-back" role="button" tabindex="0" on:click={openWindyMenu} on:keydown={handleTitleKeydown}>{title}</div>

    <p class="title">Identifiant de la course</p>
    <label>
        ID:
        <input name="race-id" bind:value={raceInput} inputmode="numeric" placeholder="Ex. 845" />
    </label>

    <button class="button" on:click={saveSettings}>Suivre cette course</button>

    {#if !latestPosition}
    <p class="status" role="status" aria-live="polite">{status}</p>
    {/if}
    <p class="title">Routages </p>
    <label for="gpx-file-input">
        (4 fichiers GPX maximum)
    </label>
        <input
            type="file"
            id="gpx-file-input"
            name="gpx-file"
            accept=".gpx,application/gpx+xml,application/xml,text/xml"
            multiple
            disabled={routes.length >= MAX_ROUTES}
            on:change={importGpx}
        />
    {#each routes as route (route.id)}
        <div class="route-info">
            <span class="route-color" style={`background-color: ${route.color}`}></span>
            <span class:route-hidden={route.hidden}>{route.name}</span>
            <button class="route-button route-button-first" on:click={() => toggleRouteVisibility(route.id)} aria-label={`${route.hidden ? 'Afficher' : 'Masquer'} le routage ${route.name}`} title={route.hidden ? 'Afficher' : 'Masquer'}>{route.hidden ? '◌' : '👁'}</button>
            <button class="route-button" on:click={() => removeRoute(route.id)} aria-label={`Retirer le routage ${route.name}`} title="Retirer">×</button>
        </div>
    {/each}
    <p class="route-status" role="status" aria-live="polite">{routeStatus}</p>

    {#if fleetCount > 1}
        <p class="title">
            Concurrents AIS :
        </p>
        <p class="route-status">{fleetCount} concurrents affichés.</p>
    {:else if fleetCount === 1}
        <p class="route-status">{fleetCount} concurrent affiché.</p>
    {/if}
    {#if latestPosition}
            <p class="title">
                Le {latestDate} à {latestHour} :
            </p>

        <div class="position">
            <div class="coordinates">
                {formatCoordinate(latestPosition.lat, 'N', 'S')} -
                {formatCoordinate(latestPosition.lon, 'E', 'W')}
            </div>
            <BoatMeasurements position={latestPosition} />
        </div>
        <button class="button" on:click={centerOnBoat}>Centrer la carte sur le bateau</button>
    {/if}
    <footer>
        {#if weatherMetadata}
        <p class="route-status" role="status">
            Modèle mis à jour il y a {formatUpdateAge(weatherMetadata.updateTimestamp)}
            (ref {weatherMetadata.referenceHour}Z)
        </p>
        {:else if weatherMetadataError}
            <p class="route-status" role="status">{weatherMetadataError}</p>
        {/if}
        <p>© 2026 Malouce Software</p>
    </footer>
</section>
<script>
    import bcast from '@windy/broadcast';
    import { map } from '@windy/map';
    import store from '@windy/store';
    import { onDestroy, onMount } from 'svelte';

    import BoatMeasurements from './BoatMeasurements.svelte';
    import config from './pluginConfig';

    const { title } = config;
    const POLL_INTERVAL_MS = 1500;
    const MAX_POLL_INTERVAL_MS = 30000;
    const WEATHER_METADATA_POLL_INTERVAL_MS = 5 * 60 * 1000;
    const DEFAULT_WEATHER_PRODUCT = 'gfs';
    const PROXY_PORT = 8085;
    const MAX_ROUTES = 4;
    const ROUTE_COLORS = ['#ffb000', '#e53935', '#8e44ad', '#00a878'];
    const WINDY_METADATA_MODEL_IDS = {
        ecmwf: 'ecmwf-hres',
        ecmwfAnalysis: 'ecmwf-hres',
        cams: 'cams-global',
        camsEu: 'cams-eu',
        icon: 'icon-global',
        iconEu: 'icon-eu',
        iconD2: 'icon-d2',
        bomAccess: 'bom-access',
        bomAccessAd: 'bom-access-c-ad',
        bomAccessBn: 'bom-access-c-bn',
        bomAccessDn: 'bom-access-c-dn',
        bomAccessNq: 'bom-access-c-nq',
        bomAccessPh: 'bom-access-c-ph',
        bomAccessSy: 'bom-access-c-sy',
        bomAccessVt: 'bom-access-c-vt',
        aromeAntilles: 'arome-antilles',
        aromeFrance: 'arome-france',
        aromeReunion: 'arome-reunion',
        nems: 'mbeurope',
        hrrrConus: 'hrrr-conus',
        hrrrAlaska: 'hrrr-alaska',
        drought: 'intersucho',
        fireDanger: 'intersucho-firerisk-hourly',
        ecmwfWaves: 'ecmwf-wam',
        gfsWaves: 'gfs-wave',
        efi: 'ecmwf-efi',
        jmaMsm: 'jma-msm',
        jmaCwmWaves: 'jma-cwm',
        canHrdps: 'can-hrdps',
        canRdwpsWaves: 'can-rdwps',
        czeAladin: 'cze-aladin',
    };
    const SAIL_NAMES = [0, "Jib", "Spi", "Stay", "LJ", "C0", "HG", "LG", 8, 9,
                     // VR sends sailNo + 10 to indicate autoSail. We use sailNo mod 10 to find the sail name sans Auto indication.
                     "Auto", "Jib &#x24B6;", "Spi &#x24B6;", "Stay &#x24B6;", "LJ &#x24B6;", "C0 &#x24B6;", "HG &#x24B6;", "LG &#x24B6;"];

    let raceId = '';
    let raceInput = '';
    let status = 'Saisis l’identifiant de la course puis active NMEA output dans ITYC.';
    let latestPosition = null;
    let latestDate = null;
    let latestHour = null;
    let boatMarker = null;
    let boatPopup = null;
    let boatPopupContent = '';
    let boatPopupPinned = false;
    let courseVector = null;
    let fleetMarkers = new Map();
    let fleetCount = 0;
    let routes = [];
    let nextRouteId = 0;
    let routeStatus = 'Sélectionne un ou plusieurs fichiers GPX pour afficher les routages.';
    let pollTimer;
    let nextPollIntervalMs = POLL_INTERVAL_MS;
    let activeRequest;
    let mounted = false;
    let configured = false;
    let configurationError = false;
    let weatherMetadata = null;
    let weatherMetadataError = '';
    let weatherMetadataProduct = null;
    let weatherMetadataRequest;
    let weatherMetadataPollTimer;

    function openWindyMenu() { bcast.emit('rqstOpen', 'menu'); }

    function formatUpdateAge(timestamp) {
        const elapsedMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
        if (elapsedMinutes < 60) {
            return elapsedMinutes === 0 ? 'moins d’une minute' : `${elapsedMinutes} min`;
        }
        const elapsedHours = Math.floor(elapsedMinutes / 60);
        if (elapsedHours < 24) return `${elapsedHours} h`;
        return `${Math.floor(elapsedHours / 24)} j`;
    }

    async function updateWeatherMetadata() {
        weatherMetadataRequest?.abort();
        weatherMetadataRequest = null;
        const product = store.get('product');
        if (product !== weatherMetadataProduct) {
            weatherMetadata = null;
            weatherMetadataProduct = product;
        }
        if (typeof product !== 'string' || product.length === 0) {
            weatherMetadata = null;
            weatherMetadataError = 'Modèle météo Windy non disponible.';
            return;
        }

        const modelId = WINDY_METADATA_MODEL_IDS[product] || product;
        if (!/^[\w-]+$/.test(modelId)) {
            weatherMetadata = null;
            weatherMetadataError = `Identifiant de modèle Windy invalide : ${product}.`;
            return;
        }

        const request = new AbortController();
        weatherMetadataRequest = request;
        weatherMetadataError = '';

        try {
            const response = await fetch(
                `https://node.windy.com/metadata/v1.0/forecast/${modelId}/minifest.json`,
                { cache: 'no-store', signal: request.signal },
            );
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const metadata = await response.json();
            const updateTimestamp = Date.parse(metadata.update);
            const referenceTimestamp = Date.parse(metadata.ref);
            if (!Number.isFinite(updateTimestamp) || !Number.isFinite(referenceTimestamp)) {
                throw new Error('Horodatages absents ou invalides dans le manifeste.');
            }
            if (weatherMetadataRequest !== request) return;

            weatherMetadata = {
                updateTimestamp,
                referenceHour: String(new Date(referenceTimestamp).getUTCHours()).padStart(2, '0'),
            };
        } catch (error) {
            if (!request.signal.aborted && weatherMetadataRequest === request) {
                weatherMetadata = null;
                weatherMetadataError = `Mise à jour météo Windy indisponible pour ${product} : ${error.message}`;
            }
        } finally {
            if (weatherMetadataRequest === request) weatherMetadataRequest = null;
        }
    }

    function handleTitleKeydown(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openWindyMenu();
        }
    }

    function activeDialog() {
        if (visualOpen) return visualDialog;
        if (analysisOpen) return analysisDialog;
        return null;
    }

    function handleWindowKeydown(event) {
        const dialog = activeDialog();
        if (!dialog) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            if (visualOpen) closeVisual(); else closeAnalysis();
            return;
        }
        trapFocus(event, dialog, typeof document !== 'undefined' ? document.activeElement : null);
    }


    function clearFleet() {
        fleetMarkers.forEach(marker => map.removeLayer(marker));
        fleetMarkers.clear();
        fleetCount = 0;
    }

    function displayFleet(boats) {
        const seen = new Set();
        boats.forEach(boat => {
            if (!Number.isFinite(boat.lat) || !Number.isFinite(boat.lon)) return;
            const key = String(boat.name || boat.mmsi || `${boat.lat},${boat.lon}`);
            seen.add(key);
            const label = escapeHtml(boat.name || 'Concurrent');
            const popup = `<strong>${label}</strong><br>${formatCoordinate(boat.lat, 'N', 'S')} - ${formatCoordinate(boat.lon, 'E', 'W')}<br>HDG ${Number(boat.heading).toFixed(0)}° - ${Number(boat.speed).toFixed(1)} nds`;
            const existing = fleetMarkers.get(key);
            if (existing) {
                existing.setLatLng([boat.lat, boat.lon]).setPopupContent(popup);
            } else {
                const marker = L.marker([boat.lat, boat.lon], {
                    icon: L.divIcon({
                        className: 'ityc-boat-marker',
                        html: '<span class="ityc-boat-marker__dot ityc-fleet-marker__dot"></span>',
                        iconSize: [14, 14],
                        iconAnchor: [7, 7],
                    }),
                }).addTo(map);
                marker.bindPopup(popup);
                marker.bindTooltip(label);
                fleetMarkers.set(key, marker);
            }
        });
        fleetMarkers.forEach((marker, key) => {
            if (!seen.has(key)) {
                map.removeLayer(marker);
                fleetMarkers.delete(key);
            }
        });
        fleetCount = fleetMarkers.size;
    }

    async function pollFleet(signal) {
        try {
            const response = await fetch(`http://localhost:${PROXY_PORT}/fleet/${raceId}`, {
                cache: 'no-store',
                signal,
                targetAddressSpace: 'loopback',
            });
            if (response.ok) {
                const boats = await response.json();
                if (Array.isArray(boats)) displayFleet(boats);
            }
        } catch (error) {
            // Fleet is optional; position polling reports proxy errors
        }
    }

    function clearMapFeatures() {
        clearFleet();
        boatPopup?.remove();
        boatPopup = null;
        boatPopupPinned = false;
        if (boatMarker) {
            map.removeLayer(boatMarker);
            boatMarker = null;
        }
        if (courseVector) {
            map.removeLayer(courseVector);
            courseVector = null;
        }
    }

    function removeRouteItems(items) {
        for (const { layer, popup } of items) {
            try {
                if (popup) map.closePopup(popup);
            } catch (error) {
                console.warn('ITYC : fermeture du popup impossible', error);
            }
            try {
                layer.off();
                map.removeLayer(layer);
                // Filet de sécurité si Windy laisse l’icône dans le DOM.
                layer._icon?.remove();
            } catch (error) {
                console.warn('ITYC : retrait du calque impossible', error);
            }
        }
    }

    function toggleRouteVisibility(routeId) {
        const route = routes.find(item => item.id === routeId);
        if (!route) return;
        const hidden = !route.hidden;
        for (const { layer, popup } of route.items) {
            try {
                if (hidden) {
                    if (popup) map.closePopup(popup);
                    map.removeLayer(layer);
                } else {
                    layer.addTo(map);
                }
            } catch (error) {
                console.warn('ITYC : changement de visibilité impossible', error);
            }
        }
        routes = routes.map(item => item.id === routeId ? { ...item, hidden } : item);
        //routeStatus = `Routage ${hidden ? 'masqué' : 'affiché'} : ${route.name}.`;
    }

    function removeRoute(routeId) {
        const route = routes.find(item => item.id === routeId);
        if (!route) return;
        removeRouteItems(route.items);
        routes = routes.filter(item => item.id !== routeId);
        //routeStatus = `Routage retiré : ${route.name}.`;
    }

    function getDirectChildren(element, localName) {
        return Array.from(element.children).filter(child => child.localName === localName);
    }

    function getDirectChildText(element, localName) {
        return getDirectChildren(element, localName)[0]?.textContent?.trim() || '';
    }

    function readGpxPoint(point) {
        const latitude = point.getAttribute('lat');
        const longitude = point.getAttribute('lon');
        const lat = Number(latitude);
        const lon = Number(longitude);
        if (latitude === null || longitude === null || latitude.trim() === '' || longitude.trim() === '' ||
            !Number.isFinite(lat) || lat < -90 || lat > 90 ||
            !Number.isFinite(lon) || lon < -180 || lon > 180) {
            throw new Error('Le fichier contient un point avec des coordonnées invalides.');
        }
        return [lat, lon];
    }

    function readGpxWaypoint(point) {
        const [lat, lon] = readGpxPoint(point);
        const timeText = getDirectChildText(point, 'time');
        const timestamp = timeText ? Date.parse(timeText) : NaN;
        return {
            lat,
            lon,
            name: getDirectChildText(point, 'name'),
            details: parseWaypointDescription(getDirectChildText(point, 'desc')),
            timestamp: Number.isFinite(timestamp) ? timestamp : null,
        };
    }

    function parseWaypointDescription(description) {
        const readValue = key => description.match(new RegExp(`\\b${key}\\s*=\\s*(\\S+)`))?.[1] ?? null;
        return {
            cog: readValue('COG'),
            sog: readValue('SOG'),
            twa: readValue('TWA'),
            sail: readValue('SAIL'),
        };
    }

    function formatTwa(twa) {
        const angle = Number.parseFloat(twa.replace(',', '.'));
        if (!Number.isFinite(angle)) return twa;
        const side = angle > 180 ? ' Bd' : ' Td';
        const value = angle > 180 ? 360 - angle : angle;
        return `${value.toFixed(2).replace('.', ',')}°${side}`;
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, character => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        })[character]);
    }

    function parseGpxRoute(xmlText) {
        if (/<!DOCTYPE/i.test(xmlText)) {
            throw new Error('Les déclarations DOCTYPE ne sont pas acceptées dans les fichiers GPX.');
        }

        const document = new DOMParser().parseFromString(xmlText, 'application/xml');
        if (
            document.getElementsByTagName('parsererror').length > 0 ||
            document.documentElement.localName !== 'gpx'
        ) {
            throw new Error('Le fichier sélectionné ne contient pas un GPX valide.');
        }

        const waypoints = Array.from(document.getElementsByTagNameNS('*', 'wpt'))
            .map(readGpxWaypoint);
        const metadata = getDirectChildren(document.documentElement, 'metadata')[0];
        console.log('Metadata:', metadata);
        const routeName = metadata ? (getDirectChildText(metadata, 'name') || (metadata ? getDirectChildText(metadata, 'link') : 'Unnamed')) : 'Unnamed';

        console.log('Route name:', routeName);
        const segments = [];
        for (const track of document.getElementsByTagNameNS('*', 'trk')) {
            for (const segment of getDirectChildren(track, 'trkseg')) {
                const coordinates = getDirectChildren(segment, 'trkpt').map(readGpxPoint);
                if (coordinates.length >= 2) segments.push(coordinates);
            }
        }

        for (const route of document.getElementsByTagNameNS('*', 'rte')) {
            const coordinates = getDirectChildren(route, 'rtept').map(readGpxPoint);
            if (coordinates.length >= 2) segments.push(coordinates);
        }

        if (segments.length === 0) {
            if (waypoints.length >= 2) {
                segments.push(waypoints.map(point => [point.lat, point.lon]));
            }
        }

        if (segments.length === 0) {
            throw new Error('Aucun tracé, itinéraire ou groupe de waypoints GPX avec au moins deux points.');
        }
        return { segments, waypoints, routeName };
    }

    // Pas entre deux marqueurs : 1 h jusqu'à H+6, 3 h jusqu'à H+12, puis 12 h.
    function getMarkerStepHours(hour) {
        if (hour < 6) return 1;
        if (hour < 12) return 3;
        return 12;
    }

    function getMarkerWaypoints(waypoints) {
        const timedWaypoints = waypoints
            .filter(point => point.timestamp !== null)
            .sort((left, right) => left.timestamp - right.timestamp);
        if (timedWaypoints.length === 0) return [];

        const firstTimestamp = timedWaypoints[0].timestamp;
        const lastTimestamp = timedWaypoints[timedWaypoints.length - 1].timestamp;
        const hourlyWaypoints = [];
        let candidateIndex = 0;

        for (
            let hour = 0;
            firstTimestamp + hour * 3600000 <= lastTimestamp;
            hour += getMarkerStepHours(hour)
        ) {
            const targetTimestamp = firstTimestamp + hour * 3600000;
            while (
                candidateIndex < timedWaypoints.length - 1 &&
                Math.abs(timedWaypoints[candidateIndex + 1].timestamp - targetTimestamp) <=
                    Math.abs(timedWaypoints[candidateIndex].timestamp - targetTimestamp)
            ) {
                candidateIndex += 1;
            }

            const waypoint = timedWaypoints[candidateIndex];
            const previous = hourlyWaypoints[hourlyWaypoints.length - 1];
            if (waypoint !== previous?.waypoint) {
                hourlyWaypoints.push({
                    label: hour === 0 ? 'H' : `H+${hour}`,
                    waypoint,
                });
            }
        }
        return hourlyWaypoints;
    }

    function createHourlyWaypointMarker({ label, waypoint }, routeName, routeColor) {
        const marker = L.marker([waypoint.lat, waypoint.lon], {
            icon: L.divIcon({
                className: 'ityc-hour-waypoint',
                html: `<span class="ityc-hour-waypoint__label" style="background-color: ${routeColor}">${label}</span>`,
                iconSize: [44, 26],
                iconAnchor: [22, 13],
            }),
        });
        const waypointTime = new Date(waypoint.timestamp).toLocaleString();
        const waypointName = waypoint.name ? `<br>${escapeHtml(waypoint.name)}` : '';
        const { cog, sog, twa, sail } = waypoint.details;
        const detailLines = [
            cog && `<strong>COG :</strong> ${escapeHtml(cog)}`,
            sog && `<strong>SOG :</strong> ${escapeHtml(sog)}`,
            twa && `<strong>TWA :</strong> ${escapeHtml(formatTwa(twa))}`,
            sail && `<strong>SAIL :</strong> ${escapeHtml(sail)}`,
        ].filter(Boolean).map(line => `<br>${line}`).join('');
        const content = `<strong>${label}</strong>${waypointName}<br>${escapeHtml(waypointTime)}${detailLines}`;
        const popup = L.popup({
            autoClose: false,
            closeOnClick: false,
            offset: [0, -10],
        }).setLatLng(marker.getLatLng()).setContent(content);
        marker.on('mouseover', () => popup.openOn(map));
        marker.on('mouseout', () => map.closePopup(popup));
        marker.on('click', () => {
            try {
                const myTimestamp = Math.round(waypoint.timestamp/3600/1000)*3600*1000;
                console.log('Setting timestamp to', new Date(myTimestamp).toLocaleString());
                store.set('timestamp', myTimestamp);
                // routeStatus = `Timeline Windy positionnée sur ${label} (${routeName}) : ${waypointTime}.`;
            } catch (error) {
                routeStatus = `Impossible de régler la timeline Windy : ${error.message}`;
            }
        });
        return { layer: marker, popup };
    }

    function createRouteItems(segments, hourlyWaypoints, color, name) {
        return [
            ...segments.map(segment => ({
                layer: L.polyline(segment, {
                    color,
                    weight: 3,
                    opacity: 0.9,
                }),
            })),
            ...hourlyWaypoints.map(({ label, waypoint }) =>
                createHourlyWaypointMarker({ label, waypoint }, name, color)),
        ];
    }

    async function importGpx(event) {
        const input = event.currentTarget;
        const selectedFiles = Array.from(input.files || []);
        input.value = '';
        if (selectedFiles.length === 0) return;

        const availableSlots = MAX_ROUTES - routes.length;
        const filesToImport = selectedFiles.slice(0, availableSlots);
        const results = [];
        const boundsLayers = [];
        const errors = [];

        for (const file of filesToImport) {
            try {
                if (file.size > 25 * 1024 * 1024) {
                    throw new Error('Le fichier dépasse la taille maximale de 25 Mo.');
                }

                const { segments, waypoints , routeName} = parseGpxRoute(await file.text());
                const fileDate = file.lastModified ? new Date(file.lastModified).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '';
                console.log('File date:', fileDate);
                const name = routeName.split(" ")[0] + (fileDate ? ` ${fileDate}` : '') || file.name;
                //const name = file.name;
                const hourlyWaypoints = getMarkerWaypoints(waypoints);
                const usedColors = new Set(routes.map(route => route.color));
                const color = ROUTE_COLORS.find(candidate => !usedColors.has(candidate));
                const items = createRouteItems(segments, hourlyWaypoints, color, name);
                const bounds = L.featureGroup(items.map(item => item.layer)).getBounds();

                if (!bounds.isValid()) {
                    throw new Error('Aucun point exploitable dans ce fichier GPX.');
                }

                items.forEach(item => item.layer.addTo(map));
                routes = [...routes, {
                    id: nextRouteId++,
                    name: name,
                    color,
                    items,
                }];
                boundsLayers.push(...items.map(item => item.layer));
                const pointCount = segments.reduce((total, segment) => total + segment.length, 0);
                results.push(`${file.name} (${pointCount} points${hourlyWaypoints.length ? `, ${hourlyWaypoints.length} marqueurs horaires` : ''})`);
            } catch (error) {
                errors.push(`${file.name} : ${error.message}`);
            }
        }

        if (boundsLayers.length > 0) {
            const bounds = L.featureGroup(boundsLayers).getBounds();
            map.fitBounds(bounds, { padding: [24, 24] });
        }

        if (selectedFiles.length > availableSlots) {
            errors.push(`Limite de ${MAX_ROUTES} routages : seuls ${availableSlots} fichier(s) supplémentaire(s) ont été pris en compte.`);
        }
        routeStatus = [
                results.length > 0 ? `` : '',
                errors.length > 0 ? `Import non effectué : ${errors.join(' ')}` : '',
            ].filter(Boolean).join(' ');

        if (store.get('product') !== DEFAULT_WEATHER_PRODUCT) {
            store.set('product', DEFAULT_WEATHER_PRODUCT);
        }
        centerOnBoat();
    }

    function formatCoordinate(value, positiveHemisphere, negativeHemisphere) {
        const hundredthsOfSeconds = Math.round(Math.abs(value) * 360000);
        const degrees = Math.floor(hundredthsOfSeconds / 360000);
        const remainder = hundredthsOfSeconds % 360000;
        const minutes = Math.floor(remainder / 6000);
        const seconds = ((remainder % 6000) / 100).toFixed(2).padStart(5, '0');
        const hemisphere = value < 0 ? negativeHemisphere : positiveHemisphere;
        return `${degrees}°${String(minutes).padStart(2, '0')}'${seconds}"${hemisphere}`;
    }

    function destinationPoint(position, bearingDegrees, distanceMeters) {
        const earthRadiusMeters = 6371008.8;
        const angularDistance = distanceMeters / earthRadiusMeters;
        const bearing = bearingDegrees * Math.PI / 180;
        const latitude = position.lat * Math.PI / 180;
        const longitude = position.lon * Math.PI / 180;

        const destinationLatitude = Math.asin(
            Math.sin(latitude) * Math.cos(angularDistance) +
            Math.cos(latitude) * Math.sin(angularDistance) * Math.cos(bearing),
        );
        const destinationLongitude = longitude + Math.atan2(
            Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude),
            Math.cos(angularDistance) - Math.sin(latitude) * Math.sin(destinationLatitude),
        );
        const normalizedLongitude = ((destinationLongitude * 180 / Math.PI + 540) % 360) - 180;

        return [destinationLatitude * 180 / Math.PI, normalizedLongitude];
    }

    function getOneHourVector(position) {
        const start = [position.lat, position.lon];
        const distanceMeters = position.speed * 1852;
        const destination = destinationPoint(position, position.heading, distanceMeters);
        const arrowWingLength = distanceMeters * 0.12;
        const leftWing = destinationPoint(
            { lat: destination[0], lon: destination[1] },
            position.heading + 150,
            arrowWingLength,
        );
        const rightWing = destinationPoint(
            { lat: destination[0], lon: destination[1] },
            position.heading - 150,
            arrowWingLength,
        );
        return [start, destination, leftWing, destination, rightWing];
    }

    function saveSettings() {
        const selectedRace = raceInput.trim();
        if (!/^\d{1,5}$/.test(selectedRace)) {
            status = 'Identifiant de course invalide : saisis uniquement des chiffres.';
            return;
        }

        try {
            localStorage.setItem('ityc-windy-race-id', selectedRace);
        } catch (error) {
            status = `Impossible d’enregistrer la configuration : ${error.message}`;
            return;
        }

        activeRequest?.abort();
        clearTimeout(pollTimer);
        nextPollIntervalMs = POLL_INTERVAL_MS;
        raceId = selectedRace;
        latestPosition = null;
        clearMapFeatures();
        configured = true;
        configurationError = false;
        status = 'Connexion au proxy ITYC…';
        pollPosition();
    }

    function showBoatPopup() {
        if (!boatMarker) return;
        if (!boatPopup) {
            boatPopup = L.popup({
                autoClose: false,
                closeOnClick: false,
                offset: [0, -8],
            });
            boatPopup.on('remove', () => {
                boatPopupPinned = false;
            });
        }
        boatPopup.setLatLng(boatMarker.getLatLng()).setContent(boatPopupContent).openOn(map);
    }

    function hideBoatPopup() {
        boatPopup?.remove();
    }

    function displayPosition(position) {
        const latLng = [position.lat, position.lon];
        const coordinates = `${formatCoordinate(position.lat, 'N', 'S')} - ${formatCoordinate(position.lon, 'E', 'W')}`;
        const popup = `<strong>Position du bateau ITYC</strong><br>${coordinates}<br>${new Date(position.timestamp).toLocaleString()}`;

        boatPopupContent = popup;
        if (!boatMarker) {
            boatMarker = L.marker(latLng, {
                icon: L.divIcon({
                    className: 'ityc-boat-marker',
                    html: '<span class="ityc-boat-marker__dot"></span>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10],
                }),
                zIndexOffset: 1000,
            }).addTo(map);
            boatMarker.on('mouseover', () => showBoatPopup());
            boatMarker.on('mouseout', () => {
                if (!boatPopupPinned) hideBoatPopup();
            });
            boatMarker.on('click', () => {
                boatPopupPinned = !boatPopupPinned;
                if (boatPopupPinned) showBoatPopup();
                else hideBoatPopup();
            });
        } else {
            boatMarker.setLatLng(latLng);
            if (boatPopup) boatPopup.setLatLng(latLng).setContent(popup);
        }

        if (position.heading !== null && position.speed !== null) {
            const vector = getOneHourVector(position);
            if (!courseVector) {
                courseVector = L.polyline(vector, {
                    color: '#00a8ff',
                    weight: 2,
                    opacity: 0.9,
                }).addTo(map);
            } else {
                courseVector.setLatLngs(vector);
            }
        } else if (courseVector) {
            map.removeLayer(courseVector);
            courseVector = null;
        }
    }

    function isValidPosition(value) {
        return value &&
            Number.isFinite(value.lat) && value.lat >= -90 && value.lat <= 90 &&
            Number.isFinite(value.lon) && value.lon >= -180 && value.lon <= 180 &&
            Number.isFinite(value.timestamp) &&
            (value.heading === null || Number.isFinite(value.heading)) &&
            (value.speed === null || (Number.isFinite(value.speed) && value.speed >= 0));
    }

    async function pollPosition() {
        if (!mounted) return;
        if (!configured) {
            if (!configurationError) {
                status = 'Saisis l’identifiant de la course puis active NMEA output dans ITYC.';
            }
            return;
        }

        const request = new AbortController();
        activeRequest = request;
        pollFleet(request.signal);
        try {
            const response = await fetch(
                `http://localhost:${PROXY_PORT}/position/${raceId}`,
                {
                    cache: 'no-store',
                    signal: request.signal,
                    targetAddressSpace: 'loopback',
                },
            );
            if (response.status === 404) {
                status = `Aucune position pour la course ${raceId}. Vérifie l’ID et l’option NMEA output.`;
                nextPollIntervalMs = Math.min(
                    Math.max(nextPollIntervalMs * 2, 5000),
                    MAX_POLL_INTERVAL_MS,
                );
                return;
            }
            if (!response.ok) {
                throw new Error(`Le proxy a répondu HTTP ${response.status}.`);
            }

            const position = await response.json();
            if (!isValidPosition(position)) {
                throw new Error('La réponse du proxy ne contient pas une position valide.');
            }
            if  (!latestPosition) {
                centerChart(position);
                store.set('timestamp', position.timestamp);
            } else if (latestPosition.lat !== position.lat || latestPosition.lon !== position.lon) {
                centerChart(position);
            }
            latestPosition = position;
            displayPosition(position);
            nextPollIntervalMs = POLL_INTERVAL_MS;
            latestDate = `${new Date(position.timestamp).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}`;
            latestHour = `${new Date(position.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;


        } catch (error) {
            if (!request.signal.aborted) {
                status = `Accès au proxy local refusé ou indisponible : ${error.message} Vérifie l’autorisation d’accès au réseau local pour Windy et le proxy sur le port ${PROXY_PORT}.`;
                nextPollIntervalMs = Math.min(nextPollIntervalMs * 2, MAX_POLL_INTERVAL_MS);
            }
        } finally {
            if (activeRequest === request) {
                activeRequest = null;
                if (mounted) pollTimer = setTimeout(pollPosition, nextPollIntervalMs);
            }
        }
    }
    function centerChart(position) {
        if (position) map.panTo([position.lat, position.lon]);
    }

    function centerOnBoat() {
        if (latestPosition) map.panTo([latestPosition.lat, latestPosition.lon]);
    }

    export const onopen = () => {
        if (latestPosition) centerOnBoat();
    };

    onMount(() => {
        mounted = true;
        if (store.get('product') !== DEFAULT_WEATHER_PRODUCT) {
            store.set('product', DEFAULT_WEATHER_PRODUCT);
        }
        store.on('product', updateWeatherMetadata);
        updateWeatherMetadata();
        weatherMetadataPollTimer = setInterval(
            updateWeatherMetadata,
            WEATHER_METADATA_POLL_INTERVAL_MS,
        );
        try {
            const savedRaceId = localStorage.getItem('ityc-windy-race-id') || '';
            if (/^\d{1,5}$/.test(savedRaceId)) {
                raceId = savedRaceId;
                raceInput = savedRaceId;
                configured = true;
            }
        } catch (error) {
            configurationError = true;
            status = `Impossible de lire la configuration enregistrée : ${error.message}`;
        }

        pollPosition();
    });

    onDestroy(() => {
        mounted = false;
        clearTimeout(pollTimer);
        clearInterval(weatherMetadataPollTimer);
        activeRequest?.abort();
        weatherMetadataRequest?.abort();
        store.off('product', updateWeatherMetadata);
        clearMapFeatures();
        routes.forEach(route => removeRouteItems(route.items));
        routes = [];
    });
</script>

<style>
    * {-moz-box-sizing: border-box; box-sizing: border-box;}
    .plugin__content {
        padding: 8px 12px 16px;
    }
    .title {
        margin-top: 32px;
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 8px;
        text-decoration-line: underline;
        text-decoration-color: #ff5733;
        text-decoration-style: solid; /*wavy;*/
        text-decoration-thickness: 2px;
        text-underline-offset: 4px;
    }

    label {
        display: block;
        margin-top: 12px;
        font-size: 13px;
    }

    input{
        background: transparent;
        box-sizing: border-box;
        display: block;
        width: 100%;
        margin-top: 5px;
        padding: 7px;
        color: #ffffff;
    }

    /* Masque l'indication native « Aucun fichier choisi » */
    input[type="file"] {
        color: transparent;
    }

    input::file-selector-button {
        background: #666666;
        border: 0;
        border-radius: 8px;
        color: #ffffff;
        cursor: pointer;
        font-size: 14px;
        height: 28px;
        margin-right: 8px;
        padding: 0 12px;
    }

    input::file-selector-button:disabled,
    input:disabled::file-selector-button {
        cursor: default;
        opacity: 0.5;
    }

    button {
        background: #666666;
        flex: 0 0 auto;
        font-size: 14px;
        height: 28px;
        line-height: 1;
        margin: 0;
        width: 100%;
        border: 0;
        border-radius: 8px;
        padding: 0 12px;
    }

    .button {
        margin-top: 12px;
    }

    .status {
        font-size: 14px;
        line-height: 1.4;
        white-space: pre-line;
    }

    .position {
        font-size: 13px;
        line-height: 1.6;
    }

    .route-info,
    .route-status {
        font-size: 12px;
        line-height: 1.4;
        overflow-wrap: anywhere;
    }

    .route-info {
        align-items: center;
        display: flex;
        gap: 8px;
        margin-top: 8px;
    }

    .route-color {
        border-radius: 50%;
        flex: 0 0 12px;
        height: 12px;
    }

    .route-info span:nth-child(2) {
        flex: 1 1 auto;
        min-width: 0;
    }

    .route-button {
        font-size: 16px;
        padding: 0;
        width: 28px;
    }

    .route-button-first {
        margin-left: auto;
    }

    .route-hidden {
        opacity: 0.5;
        text-decoration: line-through;
    }

    :global(.ityc-boat-marker) {
        background: transparent;
        border: 0;
        cursor: pointer;
    }

    :global(.ityc-boat-marker__dot.ityc-fleet-marker__dot) {
        background: #ff9800;
        height: 8px;
        margin: 3px;
        width: 8px;
    }

    :global(.ityc-boat-marker__dot) {
        background: #00a8ff;
        border: 2px solid #ffffff;
        border-radius: 50%;
        box-shadow: 0 0 3px #00000099;
        box-sizing: border-box;
        display: block;
        height: 12px;
        margin: 4px;
        width: 12px;
    }

    :global(.ityc-hour-waypoint) {
        background: transparent;
        border: 0;
    }

    :global(.ityc-hour-waypoint__label) {
        align-items: center;
        background: #ffb000;
        border: 2px solid #ffffff;
        border-radius: 12px;
        box-shadow: 0 1px 4px #00000080;
        color: #17212b;
        display: flex;
        font-size: 11px;
        font-weight: 700;
        height: 22px;
        justify-content: center;
        white-space: nowrap;
        width: 40px;
    }
    footer {
        position: absolute;
        bottom: 0;
        text-align: right;
        padding: 5px;
        background-color: transparent;
        color: black;
    }
</style>
