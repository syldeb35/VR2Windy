<script>
    import { getLanguage, translate } from './i18n.js';

    export let position;
    export let language = getLanguage();
    const t = (key, values) => translate(key, values, language);
    let SAIL_NAMES = [];
    let STAMINA_EMOTICON = [];
    function convertTrueWindAngle(angle) {
        let side;
        if (angle > 180) {
            side = t('port');
            return { angle: 360 - angle, side };
        }
        side = t('starboard');
        return { angle: angle, side };
    }
    if (language === 'fr') {
        SAIL_NAMES = [0, "Génois (Jib) &#x24C2;", "Spi &#x24C2;", "Trinquette (Stay) &#x24C2;", "Génois Léger(LJ) &#x24C2;", "Code 0 &#x24C2;", "Spi Lourd(HG) &#x24C2;", "Spi Léger (LG) &#x24C2;", 8, 9,
                        "Auto", "Génois (Jib) &#x24B6;", "Spi &#x24B6;", "Trinquette (Stay) &#x24B6;", "Génois Léger(LJ) &#x24B6;", "Code 0 &#x24B6;", "Spi Lourd(HG) &#x24B6;", "Spi Léger (LG) &#x24B6;"];
    } else {
        SAIL_NAMES = [0, "Jib &#x24C2;", "Spi &#x24C2;", "Stay &#x24C2;", "LJ &#x24C2;", "C0 &#x24C2;", "HG &#x24C2;", "LG &#x24C2;", 8, 9,
                        "Auto", "Jib &#x24B6;", "Spi &#x24B6;", "Stay &#x24B6;", "LJ &#x24B6;", "C0 &#x24B6;", "HG &#x24B6;", "LG &#x24B6;"];
    }
    STAMINA_EMOTICON = ["😫", "😫", "😳", "😒", "😴", "😐", "🙂", "😊", "😀", "😁", "🤩"];
    
    $: instruments = position?.instruments || {};
</script>
{#if instruments.distanceToEnd !== undefined && Number.isFinite(instruments.distanceToEnd)}
    <div class="marge"><strong>{t('remainingDistance')} :</strong> {instruments.distanceToEnd.toFixed(1)} NM</div>
{/if}
{#if position.heading !== null}
    <div class="marge"><strong>COG :</strong> {position.heading.toFixed(1)}°</div>
{/if}
{#if position.speed !== null}
    <div class="marge"><strong>SOG :</strong> {position.speed.toFixed(1)} {t('knots')}</div>
{/if}
<!-- {#if Number.isFinite(instruments.boat_heading)}
    <div><strong>Cap :</strong> {instruments.boat_heading.toFixed(1)}°</div>
{/if} -->


<div class="title"><strong>{t('wind')}</strong></div>
{#if instruments.true_wind && Number.isFinite(instruments.true_wind.angle) && Number.isFinite(instruments.true_wind.speed)}
    <div class="marge"><strong>{t('trueWind')} :</strong> {convertTrueWindAngle(instruments.true_wind.angle).angle.toFixed(1)}° {convertTrueWindAngle(instruments.true_wind.angle).side} / {instruments.true_wind.speed.toFixed(1)} {t('knots')}</div>
{/if}
{#if instruments.apparent_wind && Number.isFinite(instruments.apparent_wind.angle) && Number.isFinite(instruments.apparent_wind.speed) && ['L', 'R'].includes(instruments.apparent_wind.side)}
    <div class="marge"><strong>{t('apparentWind')} :</strong> {instruments.apparent_wind.angle.toFixed(1)}° {instruments.apparent_wind.side === 'R' ? t('starboard') : t('port')} / {instruments.apparent_wind.speed.toFixed(1)} {t('knots')}</div>
{/if}


<div class="title"><strong>{t('energyAndSails')}</strong></div>
{#if Number.isFinite(instruments.energy)}
    <div class="marge"><strong>{t('energy')} :</strong> {instruments.energy}% <strong>{t('stamina')}</strong> {@html STAMINA_EMOTICON[(instruments.energy/10).toFixed(0)]}</div>
{/if}
{#if Number.isInteger(instruments.sail)}
    <div class="marge"><strong>{t('sail')} :</strong> {@html SAIL_NAMES[instruments.sail]}</div>
{/if}
{#if instruments['option[1]'] === 'foil'}
    <div class="marge"><strong>{t('Options')} :</strong> {instruments['option[1]']}</div>
    <div class="marge"><strong>{t('foiling')} :</strong> {instruments.foil.toFixed(0)}%</div>
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