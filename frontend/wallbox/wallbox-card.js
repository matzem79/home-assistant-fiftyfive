/* Wallbox dashboard card. No dependencies or external network requests. */
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const defaults = {
  status: 'sensor.wallbox_charger_status', power: 'sensor.wallbox_power_draw',
  energy: 'sensor.wallbox_energy_delivered_during_transaction', duration: 'sensor.wallbox_transaction_duration',
  card: 'sensor.wallbox_card_in_use', soc: 'sensor.vehicle_soc_primary',
  connected: 'sensor.vehicle_charge_state', end: 'sensor.vehicle_charging_estimated_date_reached',
  start: 'button.50five_laden_start', stop: 'button.50five_laden_stop',
};
class WallboxCard extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: 'open'}); this._hours = 24; this._details = false; this._busy = false; }
  setConfig(config) {
    this._config = {...config, entities: {...defaults, ...config.entities}};
    this._signature = null;
    this._chart = null;
    this._chartToken = (this._chartToken || 0) + 1;
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    if (this._chart) this._chart.hass = hass;
    if (!this._config) return;
    const signature = JSON.stringify([Object.values(this._config.entities).map(id => hass.states[id]), hass.themes?.darkMode, hass.locale]);
    if (signature !== this._signature) { this._signature = signature; this._render(); }
  }
  getCardSize() { return this._details ? 15 : 9; }
  _state(key) { return this._hass?.states[this._config?.entities[key]]; }
  _valid(key) { const state = this._state(key); return !!state && !['unknown','unavailable',''].includes(state.state); }
  _number(key) { return this._valid(key) && Number.isFinite(Number(this._state(key).state)) ? Number(this._state(key).state) : null; }
  _format(key) {
    if (!this._valid(key)) return 'Nicht verfügbar';
    const state = this._state(key);
    const number = this._number(key);
    if (state.attributes.device_class === 'timestamp') {
      const date = new Date(state.state);
      return Number.isFinite(date.getTime()) ? date.toLocaleString('de-DE', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : state.state;
    }
    if (number === null) return state.state;
    const unit = state.attributes.unit_of_measurement || '';
    const money = key.startsWith('cost_');
    const displayUnit = unit === 'EUR' ? '€' : unit;
    return `${number.toLocaleString('de-DE', {minimumFractionDigits:money ? 2 : 0, maximumFractionDigits:money ? 2 : 1})}${displayUnit ? ' ' + displayUnit : ''}`;
  }
  _power() {
    let n = this._number('power');
    if (n === null) return ['—', 'kW'];
    const unit = this._state('power').attributes.unit_of_measurement;
    if (unit === 'W') n /= 1000;
    else if (unit !== 'kW') return [this._format('power'), ''];
    return [n.toLocaleString('de-DE',{maximumFractionDigits:1}), 'kW'];
  }
  _status() { return this._valid('status') ? this._state('status').state : 'Nicht verfügbar'; }
  _can(action) {
    const status = this._status();
    const states = action === 'start' ? (this._config.start_states || ['Bereit']) : (this._config.stop_states || ['Laden', 'Laden (voll)']);
    // Buttons have state 'unknown' before their first press; that is usable.
    const button = this._state(action);
    return !this._busy && !!button && button.state !== 'unavailable' && this._valid('status') && states.includes(status);
  }
  async _press(action) {
    if (!['start','stop'].includes(action) || !this._can(action)) return;
    this._busy = true; this._error = ''; this._render();
    try { await this._hass.callService('button', 'press', {entity_id: this._config.entities[action]}); }
    catch (error) { this._error = `Aktion fehlgeschlagen: ${error.message || error}`; }
    finally { this._busy = false; this._render(); }
  }
  _info(key) {
    const id = this._config.entities[key];
    if (id && this._state(key)) this.dispatchEvent(new CustomEvent('hass-more-info', {detail:{entityId:id}, bubbles:true, composed:true}));
  }
  _value(key, label) {
    const incomplete = this._state(key)?.attributes.cost_complete === false;
    return `<button class="metric" data-info="${esc(key)}"><strong>${esc(this._format(key))}${incomplete ? '*' : ''}</strong><span>${esc(label)}</span></button>`;
  }
  _row(key, label) { return `<button class="row" data-info="${esc(key)}"><span>${esc(label)}</span><b>${esc(this._format(key))}</b></button>`; }
  _vehicle() {
    const soc = this._number('soc');
    const validSoc = soc !== null && soc >= 0 && soc <= 100;
    const chargeState = this._state('connected')?.state;
    const chargeLabels = {
      INVALID: 'Ungültiger Ladestatus', DISCHARGING: 'Entlädt',
      CHARGE_PURPOSE_REACHED_AND_NOT_CONSERVATION_CHARGING: 'Ladeziel erreicht · ohne Erhaltungsladung',
      CHARGE_PURPOSE_REACHED_AND_CONSERVATION: 'Ladeziel erreicht · Erhaltungsmodus',
      CHARGING_ERROR: 'Ladefehler',
      NOT_READY_FOR_CHARGING: 'Nicht ladebereit', READY_FOR_CHARGING: 'Ladebereit',
      CHARGING: 'Lädt', CHARGING_HV_BATTERY: 'Lädt',
      CONSERVATION_CHARGING: 'Erhaltungsladung', COMPLETED: 'Laden abgeschlossen',
      CHARGING_COMPLETED: 'Laden abgeschlossen', OFF: 'Laden aus', ERROR: 'Ladefehler',
      on: 'Verbunden', off: 'Nicht verbunden',
    };
    const normalizedState = chargeState?.replace(/^CHARGE_STATE_/, '');
    const connection = !this._valid('connected') ? 'Ladestatus nicht verfügbar' : chargeLabels[normalizedState] || chargeState;
    return `<section class="vehicle"><div class="eyebrow">FAHRZEUG</div><div class="vehicle-title"><span>${esc(this._config.vehicle_name || 'Mein Fahrzeug')}</span><button data-info="soc">${validSoc ? esc(this._format('soc')) : '—'}</button></div><div class="track" role="img" aria-label="${validSoc ? `Akku ${soc} Prozent` : 'Akku nicht verfügbar'}"><div style="width:${validSoc ? soc : 0}%"></div></div><div class="vehicle-meta"><button data-info="connected">${esc(connection)}</button><button data-info="end">Ladeende ${esc(this._format('end'))}</button></div></section>`;
  }
  _costs() {
    const incomplete = ['cost_day','cost_month','cost_session'].some(k => this._state(k)?.attributes.cost_complete === false);
    return `<div class="metrics costs">${this._value('cost_day','Kosten heute')}${this._value('cost_month','Diesen Monat')}</div>${incomplete ? '<p class="note">* Unvollständig: Für einen Teil der Energie fehlt der Preis.</p>' : ''}`;
  }
  _main() {
    const [power, unit] = this._power();
    // Clip original pixels to the charger body; no redrawing, cable or stand.
    const image = this._config.image || '/local/wallbox/homeAdvanced.png';
    const safeImage = /^(\/local\/|\/wallbox\/)/.test(image) ? image : '/local/wallbox/homeAdvanced.png';
    return `<div class="hero"><div><div class="muted">Aktuelle Leistung</div><button class="power" data-info="power">${esc(power)} <small>${esc(unit)}</small></button><p class="active">${esc(this._status())}</p><button class="muted card-name" data-info="card">Karte · ${esc(this._format('card'))}</button></div><svg class="charger" viewBox="120 8 185 410" aria-label="Wallbox" role="img"><image href="${esc(safeImage)}" width="482" height="904"/></svg></div>${this._vehicle()}<div class="metrics">${this._value('energy','Geladen · Sitzung')}${this._value('duration','Ladezeit')}</div>${this._costs()}<div class="actions"><button data-action="start" ${this._can('start') ? '' : 'disabled'}>▶ Laden starten</button><button class="primary" data-action="stop" ${this._can('stop') ? '' : 'disabled'}>■ Laden stoppen</button></div><button class="link" data-action="details">Details und Verlauf <span>→</span></button>`;
  }
  _detailView() {
    const active = ['Laden','Laden (voll)','Transaktion abschließen'].includes(this._status());
    const price = this._state('cost_day')?.attributes.current_price_per_kwh;
    const currency = this._state('cost_day')?.attributes.unit_of_measurement;
    return `<section><h2>Ladeleistung</h2><div class="periods" role="group" aria-label="Verlaufszeitraum">${[[24,'24 h'],[168,'7 Tage'],[720,'30 Tage']].map(([h,l])=>`<button data-hours="${h}" aria-pressed="${h===this._hours}">${l}</button>`).join('')}</div><div id="chart" aria-live="polite">Verlauf wird geladen …</div><p class="note">Zeigt den gespeicherten Verlauf. Ältere Daten hängen von der Recorder-Aufbewahrung ab.</p>${this._config.entities.energy_day ? this._row('energy_day','Heute geladen') : ''}</section><section><h2>${active ? 'Aktuelle Sitzung' : 'Sitzungsdaten'}</h2>${!active ? '<p class="note">Aktuell kein laufender Ladevorgang. Sitzungswerte können vom letzten Ladevorgang stammen.</p>' : ''}${this._vehicle()}${this._row('energy','Geladene Energie')}${this._row('duration','Ladezeit')}${this._row('cost_session','Kosten Sitzung')}${this._row('card','Verwendete Karte')}<button class="link" data-info="soc">Fahrzeugdaten öffnen <span>→</span></button></section><section><h2>Ladekosten</h2>${this._costs()}${this._row('cost_session','Kosten Sitzung')}${Number.isFinite(price) && currency ? `<p class="note">Aktueller Preis: ${esc(price.toLocaleString('de-DE',{maximumFractionDigits:4}))} ${esc(currency)}/kWh</p>` : ''}<p class="note">Kosten seit Aktivierung der Erfassung. Keine rückwirkende Monatsabrechnung.</p></section><details ${this._technicalOpen ? 'open' : ''}><summary>Technische Details</summary>${this._row('meter','Wallbox-Zählerstand')}${this._row('status','Portalstatus')}<button class="link" data-info="power">Sensor und Verlauf öffnen <span>→</span></button></details>`;
  }
  _render() {
    if (!this._config || !this._hass) return;
    const color = {'Laden':'#287cf0','Bereit':'#b58a00','Laden (voll)':'#258b4b','Transaktion abschließen':'#c87819'}[this._status()] || '#7a8590';
    this.shadowRoot.innerHTML = `<style>${WallboxCard.styles}</style><ha-card><header>${this._details ? '<button class="back" data-action="back" aria-label="Zurück">←</button>' : ''}<div><h1>${esc(this._config.title || 'Wallbox')}</h1>${this._details ? '<span class="muted">Details und Verlauf</span>' : ''}</div><button class="badge" data-info="status" style="--status:${color}"><span>●</span> ${esc(this._status())}</button></header><main>${this._details ? this._detailView() : this._main()}${this._error ? `<p role="alert" class="error">${esc(this._error)}</p>` : ''}</main></ha-card>`;
    this.shadowRoot.querySelectorAll('[data-info]').forEach(el => el.onclick = () => this._info(el.dataset.info));
    this.shadowRoot.querySelectorAll('[data-action]').forEach(el => el.onclick = () => {
      const action = el.dataset.action;
      if (action === 'start' || action === 'stop') { void this._press(action); return; }
      this._details = action === 'details'; this._chartToken = (this._chartToken || 0) + 1; this._render();
      this.shadowRoot.querySelector('header').scrollIntoView?.({block:'nearest',behavior:'smooth'});
      this.shadowRoot.querySelector(this._details ? '.back' : '[data-action="details"]')?.focus();
    });
    this.shadowRoot.querySelectorAll('[data-hours]').forEach(el => el.onclick = () => {this._hours = Number(el.dataset.hours); this._chart = null; this._chartToken = (this._chartToken || 0) + 1; this._render();});
    const details = this.shadowRoot.querySelector('details');
    if (details) details.ontoggle = () => { this._technicalOpen = details.open; };
    if (this._details) void this._mountChart();
  }
  async _mountChart() {
    const token = this._chartToken;
    const host = this.shadowRoot.querySelector('#chart');
    try {
      if (!this._state('power')) { host.textContent = 'Leistungssensor nicht gefunden.'; return; }
      if (!this._chart) {
        const helpers = await window.loadCardHelpers();
        if (token !== this._chartToken || !this._details || host !== this.shadowRoot.querySelector('#chart')) return;
        this._chart = helpers.createCardElement({type:'history-graph', entities:[this._config.entities.power], hours_to_show:this._hours});
      }
      if (host !== this.shadowRoot.querySelector('#chart')) return;
      this._chart.hass = this._hass; host.replaceChildren(this._chart);
    } catch { if (host === this.shadowRoot.querySelector('#chart')) host.textContent = 'Verlauf nicht verfügbar. Tippe auf die Leistung, um den Sensor zu öffnen.'; }
  }
  static styles = `
    :host{display:block;--wb-text:var(--primary-text-color,#19252e);--wb-muted:var(--secondary-text-color,#74808b);--wb-line:var(--divider-color,#e8edf0);--wb-soft:var(--secondary-background-color,#f0f3f6);--wb-accent:var(--primary-color,#287cf0)}
    *{box-sizing:border-box}ha-card{overflow:hidden;color:var(--wb-text);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif);border-radius:24px;background:var(--ha-card-background,var(--card-background-color,#fff))}
    button{font:inherit;color:inherit;cursor:pointer;background:none;border:0;text-align:left;padding:0}button:focus-visible,summary:focus-visible{outline:2px solid var(--wb-accent);outline-offset:4px}button:disabled{cursor:default;opacity:.42}
    header{display:flex;align-items:center;gap:12px;padding:24px 24px 12px}h1{font-size:24px;margin:0;font-weight:600}h2{font-size:18px;margin:0 0 18px;font-weight:600}.muted,.note{color:var(--wb-muted);font-size:13px}.note{line-height:1.55;margin:10px 0}.badge{margin-left:auto;font-size:12px;max-width:50%;border-radius:18px;padding:8px 10px;background:var(--wb-soft);line-height:1.4}.badge span{color:var(--status)}main{padding:12px 24px 24px}.hero{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:210px}.hero>div{min-width:0;flex:1}.power{display:block;font-size:clamp(40px,10vw,68px);font-weight:600;letter-spacing:-2px;margin:10px 0;white-space:nowrap}.power small{font-size:20px;font-weight:400;letter-spacing:0;color:var(--wb-muted)}.active{color:var(--wb-accent);font-size:14px}.card-name{overflow-wrap:anywhere}.charger{width:28%;max-width:118px;height:220px;overflow:hidden;border-radius:12px;background:#fcfcfc;flex-shrink:0}
    .vehicle{padding:24px 0;border-top:1px solid var(--wb-line)}.eyebrow{font-size:10px;letter-spacing:1px;color:var(--wb-muted);margin-bottom:14px}.vehicle-title{display:flex;justify-content:space-between;align-items:center;font-size:22px;font-weight:600;gap:10px}.vehicle-title button{white-space:nowrap}.track{height:7px;border-radius:4px;background:var(--wb-soft);margin:16px 0;overflow:hidden}.track>div{height:100%;background:var(--wb-accent);border-radius:4px}.vehicle-meta{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--wb-muted);line-height:1.5}.vehicle-meta button:last-child{text-align:right}
    .metrics{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:16px 0 24px}.metric{min-width:0}.metric strong{display:block;font-size:clamp(19px,5vw,26px);font-weight:600;overflow-wrap:anywhere}.metric span{display:block;margin-top:8px;color:var(--wb-muted);font-size:10px;text-transform:uppercase;letter-spacing:.6px}.costs{border-top:1px solid var(--wb-line);padding-top:22px}.actions{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0 20px}.actions button{padding:15px 9px;text-align:center;border-radius:12px;background:var(--wb-soft);font-size:13px;font-weight:600}.actions .primary{background:var(--wb-accent);color:var(--text-primary-color,#fff)}.link{width:100%;display:flex;justify-content:space-between;gap:12px;color:var(--wb-accent);font-size:14px;padding:18px 0 4px}.back{font-size:26px;color:var(--wb-accent);padding:6px}.row{display:flex;justify-content:space-between;gap:20px;width:100%;padding:12px 0;font-size:13px;line-height:1.5}.row span{color:var(--wb-muted)}.row b{font-weight:500;text-align:right;overflow-wrap:anywhere}.periods{display:flex;gap:5px;background:var(--wb-soft);border-radius:10px;padding:4px;width:fit-content;margin-bottom:16px}.periods button{padding:8px 12px;border-radius:7px;font-size:12px}.periods button[aria-pressed=true]{background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--wb-accent)}section+section{border-top:1px solid var(--wb-line);padding-top:24px;margin-top:24px}section .vehicle{border:0;padding-top:4px}#chart{min-height:160px;font-size:13px;color:var(--wb-muted)}details{border-top:1px solid var(--wb-line);padding-top:24px;margin-top:24px}summary{cursor:pointer;font-size:17px;font-weight:600;padding-bottom:12px}.error{color:var(--error-color,#b91c1c);font-size:13px;line-height:1.5}
    @media(max-width:360px){header{padding:18px 16px 10px}main{padding:10px 16px 20px}.hero{min-height:185px}.charger{height:180px}.vehicle-title{font-size:19px}.actions{gap:8px}.actions button{font-size:12px}.badge{font-size:11px}}
  `;
}
if (!customElements.get('wallbox-card')) customElements.define('wallbox-card', WallboxCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === 'wallbox-card')) window.customCards.push({type:'wallbox-card', name:'Wallbox', description:'Wallbox mit Ladeaktionen, Kosten und Detailansicht'});
