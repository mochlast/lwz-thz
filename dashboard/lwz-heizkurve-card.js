/* LWZ Heizkurve — zeigt die Heizkurve (FHEM function_heatSetTemp) aus
 * p13 (Steilheit), p14 (Fußpunkt), p15 (Raumeinfluss) mit dem aktuellen
 * Betriebspunkt (gefilterte Außentemperatur / Vorlauf-Soll).
 *
 * Karten-Konfiguration:
 *   type: custom:lwz-heizkurve-card
 *   gradient / low_end / room_influence / room_set / inside / outside / heat_set: entity_ids
 */
class LwzHeizkurveCard extends HTMLElement {
  setConfig(config) {
    if (!config.gradient || !config.room_set) {
      throw new Error("gradient und room_set sind erforderlich");
    }
    this._c = config;
    this._key = null;
  }

  _n(hass, id, dflt) {
    const s = id && hass.states[id];
    const v = s ? parseFloat(s.state) : NaN;
    return Number.isFinite(v) ? v : dflt;
  }

  set hass(hass) {
    const c = this._c;
    const p13 = this._n(hass, c.gradient, 0.4);
    const p14 = this._n(hass, c.low_end, 0);
    const p15 = this._n(hass, c.room_influence, 0);
    const rSet = this._n(hass, c.room_set, 20);
    const rIst = this._n(hass, c.inside, rSet);
    const tOut = this._n(hass, c.outside, NaN);
    const vSet = this._n(hass, c.heat_set, NaN);

    const key = [p13, p14, p15, rSet, rIst, tOut, vSet].join("|");
    if (key === this._key) return; // nichts geändert -> kein Re-Render
    this._key = key;

    // FHEM 00_THZ.pm function_heatSetTemp
    const a = 0.7 + rSet * (1 + p13 * 0.87) + p14 + (p15 * p13 * (rSet - rIst)) / 10;
    const b = (-14 * p13) / rSet;
    const cq = -p13 / 75;
    const f = (x) => Math.max(5, cq * x * x + b * x + a);

    const X0 = -20, X1 = 20;
    const pts = [];
    for (let x = X0; x <= X1; x++) pts.push([x, f(x)]);
    const ys = pts.map((p) => p[1]);
    if (Number.isFinite(vSet)) ys.push(vSet);
    const yMin = Math.floor(Math.min(...ys) - 2);
    const yMax = Math.ceil(Math.max(...ys) + 2);

    const W = 600, H = 300, L = 42, R = 14, T = 14, B = 36;
    const sx = (x) => L + ((x - X0) / (X1 - X0)) * (W - L - R);
    const sy = (y) => T + ((yMax - y) / (yMax - yMin)) * (H - T - B);
    const path = pts
      .map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`)
      .join("");

    let grid = "", labels = "";
    for (let x = X0; x <= X1; x += 5) {
      grid += `<line x1="${sx(x)}" y1="${T}" x2="${sx(x)}" y2="${H - B}"/>`;
      labels += `<text x="${sx(x)}" y="${H - B + 16}" text-anchor="middle">${x}</text>`;
    }
    const stepY = yMax - yMin > 24 ? 5 : 2;
    for (let y = Math.ceil(yMin / stepY) * stepY; y <= yMax; y += stepY) {
      grid += `<line x1="${L}" y1="${sy(y)}" x2="${W - R}" y2="${sy(y)}"/>`;
      labels += `<text x="${L - 6}" y="${sy(y) + 4}" text-anchor="end">${y}</text>`;
    }

    let marker = "";
    if (Number.isFinite(tOut) && Number.isFinite(vSet)) {
      marker =
        `<line x1="${sx(tOut)}" y1="${T}" x2="${sx(tOut)}" y2="${H - B}" ` +
        `stroke="var(--accent-color,#ff9800)" stroke-dasharray="4 4" stroke-width="1"/>` +
        `<circle cx="${sx(tOut)}" cy="${sy(vSet)}" r="5" fill="var(--accent-color,#ff9800)"/>` +
        `<text x="${sx(tOut) + 8}" y="${sy(vSet) - 8}" font-size="11" ` +
        `fill="var(--primary-text-color,#ddd)">${vSet.toFixed(1)} °C @ ${tOut.toFixed(1)} °C</text>`;
    }

    this.innerHTML = `<ha-card header="${c.title || "Heizkurve"}">
      <div style="padding:0 16px 12px">
        <svg viewBox="0 0 ${W} ${H}" style="width:100%;display:block">
          <g stroke="var(--divider-color,#666)" stroke-dasharray="3 3" stroke-width="0.8">${grid}</g>
          <g fill="var(--secondary-text-color,#999)" font-size="11">
            ${labels}
            <text x="${(L + W - R) / 2}" y="${H - 3}" text-anchor="middle">Au&#223;entemperatur (gefiltert) &#176;C</text>
          </g>
          <path d="${path}" fill="none" stroke="var(--primary-color,#03a9f4)" stroke-width="2.5"/>
          ${marker}
        </svg>
        <div style="color:var(--secondary-text-color);font-size:12px;margin-top:4px">
          Steilheit ${p13} &#183; Fu&#223;punkt ${p14} K &#183; Raumeinfluss ${p15} % &#183; Raum-Soll ${rSet} &#176;C
        </div>
      </div>
    </ha-card>`;
  }

  getCardSize() {
    return 4;
  }
}
customElements.define("lwz-heizkurve-card", LwzHeizkurveCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "lwz-heizkurve-card",
  name: "LWZ Heizkurve",
  description: "Heizkurve der Stiebel Eltron LWZ / Tecalor THZ mit aktuellem Betriebspunkt",
});
