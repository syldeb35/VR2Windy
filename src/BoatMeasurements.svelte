<script>
    export let position;
    let SAIL_NAMES = [];
    let STAMINA_EMOTICON = [];
    function convertTrueWindAngle(angle) {
        let side;
        if (angle > 180) {
            side = 'bâbord';
            return { angle: 360 - angle, side };
        }
        side = 'tribord';
        return { angle: angle, side };
    }
    function getLang() {
        if (navigator.languages !== undefined) {
            console.log("Detected language: " + navigator.languages[0]);
            return navigator.languages[0]; 
        }
        return navigator.language;
    }
    if (getLang().startsWith("fr")) {
        SAIL_NAMES = [0, "Génois (Jib) &#x24C2;", "Spi &#x24C2;", "Trinquette (Stay) &#x24C2;", "Génois Léger(LJ) &#x24C2;", "Code 0 &#x24C2;", "Spi Lourd(HG) &#x24C2;", "Spi Léger (LG) &#x24C2;", 8, 9,
                        "Auto", "Génois (Jib) &#x24B6;", "Spi &#x24B6;", "Trinquette (Stay) &#x24B6;", "Génois Léger(LJ) &#x24B6;", "Code 0 &#x24B6;", "Spi Lourd(HG) &#x24B6;", "Spi Léger (LG) &#x24B6;"];
    } else {
        SAIL_NAMES = [0, "Jib &#x24C2;", "Spi &#x24C2;", "Stay &#x24C2;", "LJ &#x24C2;", "C0 &#x24C2;", "HG &#x24C2;", "LG &#x24C2;", 8, 9,
                        "Auto", "Jib &#x24B6;", "Spi &#x24B6;", "Stay &#x24B6;", "LJ &#x24B6;", "C0 &#x24B6;", "HG &#x24B6;", "LG &#x24B6;"];
    }
    STAMINA_EMOTICON = ["😫", "😳", "😒", "😴", "😐", "🙂", "😊", "😀", "😁", "🤩"];
    $: instruments = position.instruments || {};
</script>

{#if position.heading !== null}
    <div class="marge"><strong>COG :</strong> {position.heading.toFixed(1)}°</div>
{/if}
{#if position.speed !== null}
    <div class="marge"><strong>SOG :</strong> {position.speed.toFixed(1)} nds</div>
{/if}
<!-- {#if Number.isFinite(instruments.boat_heading)}
    <div><strong>Cap :</strong> {instruments.boat_heading.toFixed(1)}°</div>
{/if} -->


<div class="title"><strong>Vent</strong></div>
{#if instruments.true_wind && Number.isFinite(instruments.true_wind.angle) && Number.isFinite(instruments.true_wind.speed)}
    <div class="marge"><strong>Réel :</strong> {convertTrueWindAngle(instruments.true_wind.angle).angle.toFixed(1)}° {convertTrueWindAngle(instruments.true_wind.angle).side} / {instruments.true_wind.speed.toFixed(1)} nds</div>
{/if}
{#if instruments.apparent_wind && Number.isFinite(instruments.apparent_wind.angle) && Number.isFinite(instruments.apparent_wind.speed) && ['L', 'R'].includes(instruments.apparent_wind.side)}
    <div class="marge"><strong>Apparent :</strong> {instruments.apparent_wind.angle.toFixed(1)}° {instruments.apparent_wind.side === 'R' ? 'tribord' : 'bâbord'} / {instruments.apparent_wind.speed.toFixed(1)} nds</div>
{/if}


<div class="title"><strong>Énergie et Voile</strong></div>
{#if Number.isFinite(instruments.energy)}
    <div class="marge">{instruments.energy}% de <strong>stamina</strong> {@html STAMINA_EMOTICON[Math.min(Math.max(instruments.energy, 0), 9)]}</div>
{/if}
{#if Number.isInteger(instruments.sail)}
    <div class="marge"><strong>Voile :</strong> {@html SAIL_NAMES[instruments.sail]}</div>
{/if}
{#if Number.isFinite(instruments.foil)}
    <div class="marge"><strong>Foiling :</strong> {instruments.foil.toFixed(0)}%</div>
{/if}
<style>

    .title {
        margin-top: 16px;
        font-size: 14px;
        font-weight: bold;
        margin-bottom: 4px;
        text-decoration-line: underline;
        text-decoration-color: #ffffff;
        text-decoration-style: solid; /*wavy;*/
        text-decoration-thickness: 2px;
        text-underline-offset: 4px;
    }

    .marge {
        margin-left: 10px;
    }
</style>