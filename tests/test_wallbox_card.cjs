const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
let Card;
const context = {HTMLElement: class {attachShadow(){this.shadowRoot={};}}, customElements:{get:()=>false,define:(_,c)=>{Card=c;}},window:{},CustomEvent:class {constructor(name,options){this.name=name;this.options=options;}}, console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/wallbox/wallbox-card.js'),'utf8'),context);
function fixture(status='Bereit') {
 const card=new Card();card._render=()=>{};card.setConfig({entities:{cost_day:'sensor.cost'}});
 const state=(value,attributes={})=>({state:value,attributes});
 card._hass={states:{'sensor.wallbox_charger_status':state(status),'button.50five_laden_start':state('unknown'),'button.50five_laden_stop':state('unknown'),'sensor.wallbox_power_draw':state('10800',{unit_of_measurement:'W'})}};
 // A newly created HA button can have state "unknown" until first press; it is still available.
 return {card,state};
}
test('HA button with no previous press is still usable; unavailable is blocked',()=>{
 const {card}=fixture();assert.equal(card._can('start'),true);card._hass.states['button.50five_laden_start'].state='unavailable';assert.equal(card._can('start'),false);
});
test('status gates start and stop, including missing state',()=>{
 const {card}=fixture('Laden');assert.equal(card._can('start'),false);assert.equal(card._can('stop'),true);
 card._hass.states['sensor.wallbox_charger_status'].state='unavailable';assert.equal(card._can('stop'),false);
});
test('double click sends one service call to configured target',async()=>{
 const {card}=fixture();let resolve;const calls=[];
 card._hass.callService=(...args)=>{calls.push(args);return new Promise(r=>resolve=r);};
 const pending=card._press('start');await card._press('start');assert.equal(calls.length,1);assert.equal(calls[0][2].entity_id,'button.50five_laden_start');assert.equal(card._busy,true);resolve();await pending;assert.equal(card._busy,false);
});
test('failed service calls unlock controls and display error',async()=>{
 const {card}=fixture();card._hass.callService=async()=>{throw new Error('offline');};await card._press('start');assert.match(card._error,/offline/);assert.equal(card._busy,false);
});
test('missing, incomplete costs and untrusted state text',()=>{
 const {card,state}=fixture();assert.equal(card._format('cost_month'),'Nicht verfügbar');
 card._hass.states['sensor.cost']=state('3.72',{unit_of_measurement:'EUR',cost_complete:false});assert.match(card._costs(),/3,72 €\*/);assert.match(card._costs(),/Unvollständig/);
 card._hass.states['sensor.wallbox_charger_status']=state('<img onerror=alert(1)>');assert.ok(!card._main().includes('<img onerror'));
});
test('power converts W to kW, invalid SOC never overflows',()=>{
 const {card,state}=fixture();assert.equal(card._power()[0],'10,8');card._hass.states['sensor.vehicle_soc_primary']=state('180',{unit_of_measurement:'%'});assert.match(card._vehicle(),/width:0%/);
});
test('details use actual configured entities and do not fabricate daily energy',()=>{
 const {card}=fixture();assert.ok(!card._detailView().includes('Heute geladen'));assert.match(card._detailView(),/Kosten Sitzung/);assert.match(card._detailView(),/Wallbox-Zählerstand/);
});
test('vehicle shows charging state without inferring plug connection',()=>{
 const {card,state}=fixture();
 const id='sensor.vehicle_charge_state';
 card._hass.states[id]=state('NOT_READY_FOR_CHARGING');
 assert.match(card._vehicle(),/Nicht ladebereit/);
 assert.ok(!card._vehicle().includes('Nicht verbunden'));
 card._hass.states[id]=state('CHARGE_STATE_CHARGING_HV_BATTERY');
 assert.match(card._vehicle(),/Lädt/);
 card._hass.states[id]=state('unavailable');
 assert.match(card._vehicle(),/Ladestatus nicht verfügbar/);
});
