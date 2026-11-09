<script>
    export let position;
    const SAIL_NAMES = [0, "Jib", "Spi", "Stay", "LJ", "C0", "HG", "LG", 8, 9,
                     // VR sends sailNo + 10 to indicate autoSail. We use sailNo mod 10 to find the sail name sans Auto indication.
                     "Auto", "Jib &#x24B6;", "Spi &#x24B6;", "Stay &#x24B6;", "LJ &#x24B6;", "C0 &#x24B6;", "HG &#x24B6;", "LG &#x24B6;"];

    $: instruments = position.instruments || {};
</script>

{#if position.heading !== null}
    <div><strong>COG :</strong> {position.heading.toFixed(1)}°</div>
{/if}
{#if position.speed !== null}
    <div><strong>SOG :</strong> {position.speed.toFixed(2)} nds</div>
{/if}
{#if Number.isFinite(instruments.boat_heading)}
    <div><strong>Cap :</strong> {instruments.boat_heading.toFixed(1)}°</div>
{/if}
{#if instruments.true_wind && Number.isFinite(instruments.true_wind.angle) && Number.isFinite(instruments.true_wind.speed)}
    <div><strong>Vent réel :</strong> {instruments.true_wind.angle.toFixed(1)}° / {instruments.true_wind.speed.toFixed(2)} nds</div>
{/if}
{#if instruments.apparent_wind && Number.isFinite(instruments.apparent_wind.angle) && Number.isFinite(instruments.apparent_wind.speed) && ['L', 'R'].includes(instruments.apparent_wind.side)}
    <div><strong>Vent apparent :</strong> {instruments.apparent_wind.angle.toFixed(1)}° {instruments.apparent_wind.side === 'R' ? 'tribord' : 'bâbord'} / {instruments.apparent_wind.speed.toFixed(2)} nds</div>
{/if}
{#if Number.isFinite(instruments.energy)}
    <div><strong>Énergie :</strong> {instruments.energy}</div>
{/if}
{#if Number.isInteger(instruments.sail)}
    <div><strong>Voile :</strong> {@html SAIL_NAMES[instruments.sail]}</div>
{/if}
