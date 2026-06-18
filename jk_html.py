"""jk_html.py — JK BMS Dashboard HTML"""
HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JK BMS</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
<style>
:root{--bg:#0b0d14;--surf:#12151f;--surf2:#181b27;--bdr:#232635;
  --txt:#d0d4e8;--muted:#555b77;--accent:#4f7fff;
  --green:#22c97a;--red:#f04f4f;--amber:#f5a623;
  --blue:#4f9fff;--cyan:#22c4d4;--purple:#a78bfa;--r:8px;--r2:5px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:'Segoe UI',system-ui,sans-serif;font-size:13px}
/* Header */
.hdr{background:var(--surf);border-bottom:1px solid var(--bdr);display:flex;align-items:center;height:48px;position:sticky;top:0;z-index:50}
.hdr-logo{padding:0 14px;font-weight:700;font-size:14px;color:var(--accent);display:flex;align-items:center;gap:6px;white-space:nowrap}
.nav{display:flex;height:100%}
.nav-btn{background:none;border:none;border-bottom:2px solid transparent;color:var(--muted);padding:0 16px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:5px;transition:.15s;white-space:nowrap}
.nav-btn.on{color:var(--txt);border-bottom-color:var(--accent)}
.nav-btn:hover:not(.on){color:var(--txt)}
.hdr-right{margin-left:auto;display:flex;align-items:center;gap:10px;padding:0 12px}
.conn-pill{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--red);transition:.3s}
.dot.live{background:var(--green)}
.amb{display:flex;gap:6px;align-items:center}
.amb-pill{display:flex;align-items:center;gap:3px;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;border:1px solid transparent}
.amb-pill.cold{background:#0a1f2e;border-color:#1a4d72;color:#60b4f0}
.amb-pill.warm{background:#1a1205;border-color:#6b3d10;color:var(--amber)}
.amb-pill.hot{background:#280808;border-color:#6b1f1f;color:var(--red)}
.amb-pill.normal{background:#0a1a10;border-color:#1d5530;color:var(--green)}
.amb-pill.humid{background:#1a1030;border-color:#4a2d80;color:var(--purple)}
.amb-pill.dry{background:#141010;border-color:#402010;color:#c08060}
/* Panel */
.panel{display:none;padding:14px 14px 32px;max-width:720px;margin:0 auto}
.panel.on{display:block}
/* Alarm */
.alarm-bar{display:none;margin-bottom:12px;background:#2d0f0f;border:1px solid #6b1f1f;border-radius:var(--r);padding:9px 13px;color:#f08080;font-size:12px;align-items:center;gap:7px}
.alarm-bar.show{display:flex;animation:blink 1.4s infinite}
@keyframes blink{50%{opacity:.65}}
/* State row */
.state-row{display:flex;gap:7px;margin-bottom:12px;flex-wrap:wrap;align-items:center}
.state-pill{padding:4px 13px;border-radius:20px;font-size:12px;font-weight:600;background:var(--surf2);border:1px solid var(--bdr);color:var(--muted)}
.state-pill.chg-on{background:#0a2718;border-color:#1d6640;color:var(--green)}
.state-pill.dsg-on{background:#0a1f2e;border-color:#1a4d72;color:var(--blue)}
.state-pill.bal-on{background:#1e1530;border-color:#5c3d9a;color:var(--purple);animation:blink 1.4s infinite}
.run-badge{font-size:11px;color:var(--cyan);padding:3px 10px;border-radius:5px;background:var(--surf2);border:1px solid var(--bdr);margin-left:auto}
/* Info blocks */
.info-block{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);margin-bottom:12px;overflow:hidden}
.info-title{background:var(--surf2);padding:7px 13px;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;display:flex;align-items:center;gap:6px;border-bottom:1px solid var(--bdr)}
.info-row{display:flex;align-items:center;padding:8px 13px;border-bottom:1px solid var(--bdr)}
.info-row:last-child{border-bottom:none}
.info-lbl{flex:1;color:var(--muted);font-size:12px}
.info-val{font-size:13px;font-weight:600;color:var(--txt);text-align:right}
.info-unit{font-size:11px;color:var(--muted);margin-left:3px;min-width:18px}
.vc{color:var(--cyan)}.vg{color:var(--green)}.vr{color:var(--red)}.va{color:var(--amber)}.vb{color:var(--blue)}
/* SOC */
.soc-wrap{margin-bottom:12px;background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:12px 13px}
.soc-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px}
.soc-pct{font-size:32px;font-weight:800;line-height:1}
.soc-cap{font-size:12px;color:var(--muted)}
.soc-track{background:var(--bdr);border-radius:4px;height:10px;overflow:hidden}
.soc-fill{height:100%;border-radius:4px;transition:width .5s,background .5s}
/* Cell grid */
.cell-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.cell-box{background:var(--surf2);border:1px solid var(--bdr);border-radius:var(--r2);padding:8px 6px;text-align:center;transition:.25s}
.cell-num{font-size:10px;color:var(--muted);margin-bottom:3px}
.cell-mv{font-size:20px;font-weight:700;color:#fff;letter-spacing:-.5px}
.cell-vv{font-size:11px;color:var(--muted);margin-left:1px}
.cell-res{font-size:10px;color:var(--purple);margin-top:3px}
.c-ok{border-color:#1a4030;background:#081a10}
.c-warn{border-color:#4a3010;background:#1a0f04}
.c-bad{border-color:var(--red);background:#280a0a}
.c-max{box-shadow:0 0 0 1.5px var(--green)}
.c-min{box-shadow:0 0 0 1.5px var(--red)}
.c-ph{opacity:.28}
/* Loading */
.loading{text-align:center;padding:40px;color:var(--muted)}
.spin{display:inline-block;width:18px;height:18px;border:2px solid var(--bdr);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;margin-right:8px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.dot-anim::after{content:'...';animation:dots 1.2s steps(4,end) infinite}
@keyframes dots{0%,100%{content:''}25%{content:'.'}50%{content:'..'}75%{content:'...'}}
/* Settings */
.cfg-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.cfg-hdr h2{font-size:14px;font-weight:600}
.btn-sm{background:var(--surf2);border:1px solid var(--bdr);border-radius:var(--r2);padding:5px 12px;color:var(--txt);font-size:12px;cursor:pointer}
.btn-sm:hover{border-color:var(--accent);color:var(--accent)}
.cfg-section{margin-bottom:10px;border-radius:var(--r);border:1px solid var(--bdr)}
.cfg-sec-hdr{background:var(--surf2);padding:8px 13px;font-size:11px;font-weight:600;display:flex;justify-content:space-between;align-items:center;cursor:pointer;text-transform:uppercase;letter-spacing:.05em;user-select:none}
.cfg-sec-hdr.basic{color:var(--blue)}.cfg-sec-hdr.adv_volt{color:var(--green)}
.cfg-sec-hdr.adv_curr{color:var(--amber)}.cfg-sec-hdr.adv_temp{color:var(--red)}
.cfg-arrow{transition:.2s;font-size:10px}
.cfg-section.closed .cfg-arrow{transform:rotate(-90deg)}
.cfg-section.closed .cfg-rows{display:none}
.cfg-rows{background:var(--surf)}
.cfg-row{display:flex;align-items:center;padding:7px 13px;border-top:1px solid var(--bdr);gap:8px}
.cfg-lbl{flex:1;font-size:12px;color:var(--muted)}
.cfg-cur{font-size:13px;font-weight:600;color:var(--txt);min-width:68px;text-align:right}
.cfg-unit{font-size:11px;color:var(--muted);min-width:26px}
.cfg-inp{background:var(--bg);border:1px solid var(--bdr);border-radius:var(--r2);padding:4px 7px;color:var(--txt);font-size:12px;width:80px;text-align:right}
.cfg-inp:focus{outline:none;border-color:var(--accent)}
.cfg-save{background:var(--accent);border:none;border-radius:var(--r2);padding:4px 10px;color:#fff;font-size:11px;cursor:pointer}
.cfg-save:hover{opacity:.85}
.cfg-res{font-size:11px;min-width:36px;text-align:right}
.cfg-res.ok{color:var(--green)}.cfg-res.err{color:var(--red)}
/* History */
.hist-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.hist-toolbar h2{font-size:14px;font-weight:600;flex:1}
.tf-btn{background:var(--surf2);border:1px solid var(--bdr);border-radius:var(--r2);padding:5px 14px;color:var(--muted);font-size:12px;cursor:pointer;transition:.15s}
.tf-btn.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tf-btn:hover:not(.on){color:var(--txt);border-color:var(--muted)}
.chart-wrap{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:14px;margin-bottom:14px}
.chart-title{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.chart-canvas{width:100%!important;height:200px!important}
.hist-loading{text-align:center;padding:30px;color:var(--muted);font-size:12px}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-logo"><i class="ti ti-battery-charging-2"></i> JK BMS</div>
  <div class="nav">
    <button class="nav-btn on" id="btn-status"   onclick="showTab('status')"><i class="ti ti-layout-list"></i> Status</button>
    <button class="nav-btn"    id="btn-settings" onclick="showTab('settings')"><i class="ti ti-adjustments-horizontal"></i> Settings</button>
    <button class="nav-btn"    id="btn-history"  onclick="showTab('history')"><i class="ti ti-chart-line"></i> History</button>
  </div>
  <div class="hdr-right">
    <div class="conn-pill"><span class="dot" id="dot"></span></div>
    <div class="amb">
      <span style="font-size:11px;color:var(--muted);margin-right:2px">Ambient</span>
      <span class="amb-pill normal" id="amb-t"><i class="ti ti-thermometer"></i> --°C</span>
      <span class="amb-pill humid"  id="amb-h"><i class="ti ti-droplet"></i> --%</span>
    </div>
  </div>
</div>

<!-- STATUS -->
<div class="panel on" id="tab-status">
  <div class="alarm-bar" id="alarm-bar"><i class="ti ti-alert-triangle"></i><span id="alarm-txt"></span></div>
  <div id="st-loading" class="loading"><span class="spin"></span>Connecting<span class="dot-anim"></span></div>
  <div id="st-main" style="display:none">
    <div class="state-row">
      <span class="state-pill" id="pill-chg"><i class="ti ti-plug"></i> Charge</span>
      <span class="state-pill" id="pill-dsg"><i class="ti ti-bolt"></i> Discharge</span>
      <span class="state-pill" id="pill-bal"><i class="ti ti-git-merge"></i> Balance</span>
      <span class="run-badge"  id="v-run"><i class="ti ti-clock" style="font-size:10px"></i> --</span>
    </div>
    <div class="soc-wrap">
      <div class="soc-top">
        <div>
          <div style="font-size:11px;color:var(--muted);margin-bottom:3px">State of Charge</div>
          <span class="soc-pct vg" id="v-soc">--%</span>
        </div>
        <div class="soc-cap" id="v-cap">-- / -- Ah</div>
      </div>
      <div class="soc-track"><div class="soc-fill" id="soc-fill" style="width:0%"></div></div>
    </div>
    <div class="info-block">
      <div class="info-title"><i class="ti ti-battery-2"></i> Pack</div>
      <div class="info-row"><span class="info-lbl">Pack Voltage</span><span class="info-val vc" id="v-pvolt">--</span><span class="info-unit">V</span></div>
      <div class="info-row"><span class="info-lbl">Current</span><span class="info-val" id="v-curr">--</span><span class="info-unit">A</span></div>
      <div class="info-row"><span class="info-lbl">Power</span><span class="info-val va" id="v-pwr">--</span><span class="info-unit">W</span></div>
      <div class="info-row"><span class="info-lbl">Remain Capacity</span><span class="info-val vb" id="v-rem">--</span><span class="info-unit">Ah</span></div>
      <div class="info-row"><span class="info-lbl">Full Capacity</span><span class="info-val" id="v-full">--</span><span class="info-unit">Ah</span></div>
      <div class="info-row"><span class="info-lbl">Cycle Capacity</span><span class="info-val vp" id="v-ccap">--</span><span class="info-unit">Ah</span></div>
      <div class="info-row"><span class="info-lbl">Cycle Count</span><span class="info-val" id="v-cyc">--</span><span class="info-unit">times</span></div>
      <div class="info-row"><span class="info-lbl">SOH</span><span class="info-val vg" id="v-soh">--%</span><span class="info-unit"></span></div>
    </div>
    <div class="info-block">
      <div class="info-title"><i class="ti ti-thermometer"></i> Temperature</div>
      <div class="info-row"><span class="info-lbl">MOS (PCB FET)</span><span class="info-val" id="v-tmos">--</span><span class="info-unit">°C</span></div>
      <div class="info-row"><span class="info-lbl">Battery Temp 1</span><span class="info-val" id="v-tbat1">--</span><span class="info-unit">°C</span></div>
      <div class="info-row"><span class="info-lbl">Battery Temp 2</span><span class="info-val" id="v-tbat2">--</span><span class="info-unit">°C</span></div>
    </div>
    <div class="info-block">
      <div class="info-title"><i class="ti ti-chart-bar"></i> Cell Statistics</div>
      <div class="info-row"><span class="info-lbl">Average</span><span class="info-val" id="v-cavg">--</span><span class="info-unit">mV</span></div>
      <div class="info-row"><span class="info-lbl">Maximum</span><span class="info-val vg" id="v-cmax">--</span><span class="info-unit">mV</span></div>
      <div class="info-row"><span class="info-lbl">Minimum</span><span class="info-val vr" id="v-cmin">--</span><span class="info-unit">mV</span></div>
      <div class="info-row"><span class="info-lbl">Difference</span><span class="info-val" id="v-cdiff">--</span><span class="info-unit">mV</span></div>
    </div>
    <div class="info-block">
      <div class="info-title"><i class="ti ti-grid-3x3"></i> Cell Voltages &amp; Wire Resistance</div>
      <div style="padding:10px"><div class="cell-grid" id="cell-grid"></div></div>
    </div>
  </div>
</div>

<!-- SETTINGS -->
<div class="panel" id="tab-settings">
  <div class="cfg-hdr"><h2><i class="ti ti-adjustments"></i> Settings</h2>
    <button class="btn-sm" onclick="refreshCfg()"><i class="ti ti-refresh"></i> Refresh</button></div>
  <div id="cfg-loading" style="display:none" class="loading"><span class="spin"></span>Loading<span class="dot-anim"></span></div>
  <div id="cfg-content"></div>
</div>

<!-- HISTORY -->
<div class="panel" id="tab-history">
  <div class="hist-toolbar">
    <h2><i class="ti ti-chart-line"></i> History</h2>
    <button class="tf-btn on" id="tf-24h" onclick="setTF('24h')">24H</button>
    <button class="tf-btn"    id="tf-7d"  onclick="setTF('7d')">7D</button>
    <button class="tf-btn"    id="tf-30d" onclick="setTF('30d')">30D</button>
    <button class="btn-sm"    onclick="loadHistory()"><i class="ti ti-refresh"></i></button>
  </div>
  <div id="hist-loading" class="hist-loading" style="display:none">
    <span class="spin"></span>Loading data<span class="dot-anim"></span>
  </div>
  <div class="chart-wrap">
    <div class="chart-title"><i class="ti ti-plug"></i> Voltage (V) &amp; Current (A)</div>
    <canvas id="chart-vi" class="chart-canvas"></canvas>
  </div>
  <div class="chart-wrap">
    <div class="chart-title"><i class="ti ti-thermometer"></i> Temperature (°C)</div>
    <canvas id="chart-temp" class="chart-canvas"></canvas>
  </div>
</div>

<script>
// Socket.IO was removed entirely (see app.py docstring for why) — REST
// polling of /api/status every 2s is now the only data path for Status.
// The connection dot now reflects whether the last poll succeeded.
const $=id=>document.getElementById(id);

let lastPollOk = false;
setInterval(async ()=>{
  try{
    const r = await fetch('/api/status');
    if(r.ok){
      const d = await r.json();
      if(d.read_ok){
        updateSt(d);
        if(!lastPollOk){ $('dot').classList.add('live'); lastPollOk = true; }
        return;
      }
    }
    if(lastPollOk){ $('dot').classList.remove('live'); lastPollOk = false; }
  }catch(e){
    if(lastPollOk){ $('dot').classList.remove('live'); lastPollOk = false; }
  }
}, 2000);

let cfgPending=true, histTF='24h', chartVI=null, chartTemp=null;

function showTab(n){
  ['status','settings','history'].forEach(t=>{
    $('tab-'+t).classList.toggle('on',t===n);
    $('btn-'+t).classList.toggle('on',t===n);
  });
  if(n==='settings'&&cfgPending) loadCfg();
  if(n==='history') loadHistory();
}

function fmt(v,d=2){ return typeof v==='number'?v.toFixed(d):String(v??'--'); }

function updateSt(d){
  if(!d.read_ok) return;
  $('st-loading').style.display='none'; $('st-main').style.display='block';
  if(d.alarms&&d.alarms.length) showAlarm(d.alarms); else $('alarm-bar').classList.remove('show');
  $('pill-chg').className='state-pill '+(d.charging?'chg-on':'');
  $('pill-dsg').className='state-pill '+(d.discharging?'dsg-on':'');
  $('pill-bal').className='state-pill '+(d.balancing?'bal-on':'');
  $('v-run').innerHTML='<i class="ti ti-clock" style="font-size:10px"></i> Run Time : '+(d.run_str||'--');
  $('v-cyc').textContent=d.cycle_count;
  $('v-ccap').textContent=fmt(d.cycle_cap,1);
  $('v-soh').textContent=(d.soh||0)+'%';
  const s=d.soc;
  $('v-soc').textContent=s+'%'; $('v-soc').className='soc-pct '+(s>50?'vg':s>20?'va':'vr');
  $('soc-fill').style.width=Math.min(100,s)+'%';
  $('soc-fill').style.background=s>50?'var(--green)':s>20?'var(--amber)':'var(--red)';
  $('v-cap').textContent=fmt(d.rem_cap)+' / '+fmt(d.full_cap)+' Ah';
  $('v-pvolt').textContent=fmt(d.pack_volt,3);
  const ce=$('v-curr');
  ce.textContent=(d.pack_curr>=0?'+':'')+fmt(d.pack_curr,2);
  ce.className='info-val '+(d.pack_curr>0?'vg':d.pack_curr<0?'va':'');
  $('v-pwr').textContent=fmt(d.pack_power,1);
  $('v-rem').textContent=fmt(d.rem_cap,2); $('v-full').textContent=fmt(d.full_cap,2);
  function setT(id,t){ const e=$(id); e.textContent=fmt(t,1); e.className='info-val '+(t>55?'vr':t>45?'va':'vc'); }
  setT('v-tmos',d.temp_mos); setT('v-tbat1',d.temp_bat1); setT('v-tbat2',d.temp_bat2);
  $('v-cavg').textContent=fmt(d.cell_avg,1); $('v-cmax').textContent=d.cell_max; $('v-cmin').textContent=d.cell_min;
  const de=$('v-cdiff'); de.textContent=d.cell_diff; de.className='info-val '+(d.cell_diff>30?'vr':d.cell_diff>15?'va':'vg');
  buildCells(d.cell_mv,d.cell_res||[],d.cell_max,d.cell_min,d.cell_avg);
}

function showAlarm(a){ $('alarm-txt').textContent=a.join(' · '); $('alarm-bar').classList.add('show'); }

function buildCells(mv,res,mx,mn,avg){
  const g=$('cell-grid');
  if(g.children.length!==8){ g.innerHTML='';
    for(let i=0;i<8;i++){ const b=document.createElement('div'); b.id='cb'+i;
      b.innerHTML=`<div class="cell-num">0${i+1}</div>`+
        `<div style="line-height:1.1"><span class="cell-mv" id="cmv${i}">-.---</span><span class="cell-vv" id="cvv${i}">V</span></div>`+
        `<div class="cell-res" id="crs${i}">--mΩ</div>`;
      g.appendChild(b); } }
  for(let i=0;i<8;i++){ const v=mv[i]; const r=res[i]; const box=$('cb'+i);
    if(!v){ box.className='cell-box c-ph'; $('cmv'+i).textContent='-.---'; $('cvv'+i).textContent='V'; $('crs'+i).textContent='--mΩ'; continue; }
    const d=Math.abs(v-avg); let c='cell-box '+(d>30?'c-bad':d>15?'c-warn':'c-ok');
    if(v===mx) c+=' c-max'; if(v===mn) c+=' c-min'; box.className=c;
    $('cmv'+i).textContent=(v/1000).toFixed(3);
    $('cvv'+i).textContent='V';
    $('crs'+i).textContent=(r!=null?Number(r).toFixed(1):'--')+'mΩ'; }
}

function ambTempClass(t){ if(t>=35)return 'hot'; if(t>=28)return 'warm'; if(t<18)return 'cold'; return 'normal'; }
function ambHumClass(h){  if(h>70) return 'humid'; if(h<30)return 'dry'; return 'normal'; }
async function fetchAmb(){
  try{ const d=await(await fetch('/api/ambient')).json();
    if(d.temp!=null){ $('amb-t').innerHTML='<i class="ti ti-thermometer"></i> '+d.temp+'°C'; $('amb-t').className='amb-pill '+ambTempClass(d.temp); }
    if(d.hum!=null){  $('amb-h').innerHTML='<i class="ti ti-droplet"></i> '+d.hum+'%';  $('amb-h').className='amb-pill '+ambHumClass(d.hum); }
  }catch(e){} }
fetchAmb(); setInterval(fetchAmb,30000);

/* ── Settings ── */
const GROUPS={basic:'Basic Settings',adv_volt:'Advance — Voltage',adv_curr:'Advance — Current / OCP',adv_temp:'Advance — Temperature'};
async function loadCfg(){
  $('cfg-loading').style.display='block'; $('cfg-content').innerHTML='';
  try{ const r=await fetch('/api/config'); if(r.ok){ buildCfg(await r.json()); cfgPending=false; }
  else $('cfg-loading').innerHTML='<span style="color:var(--red)">Load failed</span>';
  }catch(e){ $('cfg-loading').innerHTML='<span style="color:var(--red)">Error</span>'; } }
async function refreshCfg(){
  cfgPending=true; $('cfg-loading').style.display='block'; $('cfg-content').innerHTML='';
  try{ const r=await fetch('/api/config/refresh'); if(r.ok){ buildCfg(await r.json()); cfgPending=false; }
  }catch(e){ $('cfg-loading').innerHTML='<span style="color:var(--red)">Error</span>'; } }
function buildCfg(cfg){
  if(!cfg||!Object.keys(cfg).length){ $('cfg-loading').innerHTML='<span style="color:var(--red)">No data</span>'; return; }
  $('cfg-loading').style.display='none';
  const groups={};
  Object.entries(cfg).forEach(([k,f])=>{ (groups[f.group]||(groups[f.group]=[])).push({key:k,...f}); });
  let html='';
  Object.entries(GROUPS).forEach(([gk,gn])=>{
    const fl=groups[gk]||[]; if(!fl.length) return;
    const open=(gk==='basic'||gk==='adv_volt');
    html+=`<div class="cfg-section${open?'':' closed'}"><div class="cfg-sec-hdr ${gk}" onclick="toggleSec(this)">${gn}<span class="cfg-arrow">▼</span></div><div class="cfg-rows">`;
    fl.forEach(f=>{
      const disp=typeof f.value==='number'?(f.unit==='°C'?f.value.toFixed(1):Number.isInteger(f.value)?String(f.value):f.value.toFixed(3)):String(f.value??'--');
      html+=`<div class="cfg-row"><span class="cfg-lbl">${f.label}</span><span class="cfg-cur">${disp}</span><span class="cfg-unit">${f.unit||''}</span><input class="cfg-inp" id="inp_${f.key}" value="${f.raw}" type="number"><button class="cfg-save" onclick="saveFld('${f.key}',${f.write_off},'inp_${f.key}','res_${f.key}')">Save</button><span class="cfg-res" id="res_${f.key}"></span></div>`; });
    html+='</div></div>'; });
  $('cfg-content').innerHTML=html; }
function toggleSec(el){ el.closest('.cfg-section').classList.toggle('closed'); }
async function saveFld(key,woff,inpId,resId){
  const v=parseInt($(inpId).value); if(isNaN(v)){ $(resId).textContent='?'; $(resId).className='cfg-res err'; return; }
  $(resId).textContent='…'; $(resId).className='cfg-res';
  try{ const r=await fetch('/api/write',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({write_off:woff,value:v})});
    const d=await r.json(); $(resId).textContent=d.ok?'✓':'✗ '+(d.error||'?'); $(resId).className='cfg-res '+(d.ok?'ok':'err');
  }catch(e){ $(resId).textContent='✗'; $(resId).className='cfg-res err'; }
  setTimeout(()=>{ $(resId).textContent=''; },4000); }

/* ── History Charts ── */
const CHART_DEFAULTS = {
  responsive:true, maintainAspectRatio:false, animation:false,
  spanGaps:false,
  interaction:{mode:'index',intersect:false},
  plugins:{legend:{labels:{color:'#6b7280',boxWidth:12,padding:12}},tooltip:{backgroundColor:'#12151f',borderColor:'#232635',borderWidth:1,titleColor:'#d0d4e8',bodyColor:'#d0d4e8'}},
  scales:{
    x:{type:'time',time:{tooltipFormat:'dd/MM HH:mm',displayFormats:{hour:'HH:mm',day:'dd/MM'}},ticks:{color:'#555b77',maxTicksLimit:8},grid:{color:'#1e2130'}},
    y:{ticks:{color:'#555b77'},grid:{color:'#1e2130'}}
  }
};

function mkChart(id, datasets, yLabel, y2Label, mirrorY2){
  const ctx = $(id).getContext('2d');
  const cfg = JSON.parse(JSON.stringify(CHART_DEFAULTS));
  cfg.scales.y.title = {display:true, text:yLabel, color:'#555b77', font:{size:11}};
  if(y2Label || mirrorY2){
    cfg.scales.y2 = {
      position:'right',
      title:{display:true, text:y2Label||yLabel, color:'#555b77', font:{size:11}},
      ticks:{color:'#555b77'}, grid:{drawOnChartArea:false}
    };
    // mirrored axis: keep same min/max as left axis so it's a pure duplicate
    if(mirrorY2){ cfg.scales.y2.afterDataLimits = (axis)=>{
      const left = axis.chart.scales.y;
      if(left){ axis.min = left.min; axis.max = left.max; }
    }; }
  }
  return new Chart(ctx, {type:'line', data:{datasets}, options:cfg});
}

function tsToDate(ts){ return new Date(ts*1000); }

function setTF(tf){
  histTF=tf;
  ['24h','7d','30d'].forEach(t=>$('tf-'+t).classList.toggle('on',t===tf));
  loadHistory();
}

async function loadHistory(){
  $('hist-loading').style.display='block';
  try{
    const rows = await(await fetch('/api/history?range='+histTF)).json();
    $('hist-loading').style.display='none';
    if(!rows.length){
      $('hist-loading').style.display='block';
      $('hist-loading').textContent='No data yet — data is logged every 60 seconds';
      return;
    }

    // Insert a null-value gap marker wherever the time jump between two
    // consecutive rows is much larger than the normal ~60s sample interval.
    // Without this, Chart.js (even with spanGaps:false) just draws a
    // straight line between the two real points on either side of the gap,
    // since there's no missing-row marker for it to skip.
    const GAP_THRESHOLD_SEC = 150;  // > ~2.5x the 60s sample rate
    const filled = [];
    for(let i=0;i<rows.length;i++){
      if(i>0 && (rows[i].ts - rows[i-1].ts) > GAP_THRESHOLD_SEC){
        filled.push({ts: rows[i-1].ts + 1, _gap:true});
      }
      filled.push(rows[i]);
    }

    const ts   = filled.map(r=>tsToDate(r.ts));
    const volt = filled.map(r=>r._gap?null:r.pack_volt);
    const curr = filled.map(r=>r._gap?null:r.pack_curr);
    const tmos = filled.map(r=>r._gap?null:r.temp_mos);
    const tb1  = filled.map(r=>r._gap?null:r.temp_bat1);
    const tb2  = filled.map(r=>r._gap?null:r.temp_bat2);
    const tamb = filled.map(r=>r._gap?null:r.ambient_temp);

    // V & I chart — has a real right axis (Current), so plot area is
    // narrower than a single-axis chart. We mirror the same right-axis
    // layout on the Temp chart below so both x-axes line up exactly.
    const dsVI = [
      {label:'Voltage (V)', data:volt.map((v,i)=>({x:ts[i],y:v})),
       borderColor:'#22c4d4',backgroundColor:'rgba(34,196,212,.08)',borderWidth:1.5,pointRadius:0,tension:.3,yAxisID:'y'},
      {label:'Current (A)', data:curr.map((v,i)=>({x:ts[i],y:v})),
       borderColor:'#f5a623',backgroundColor:'rgba(245,166,35,.08)',borderWidth:1.5,pointRadius:0,tension:.3,yAxisID:'y2'},
    ];
    if(chartVI){ chartVI.destroy(); }
    chartVI = mkChart('chart-vi', dsVI, 'Voltage (V)', 'Current (A)', false);

    // Temp chart — mirrored y2 (duplicate of left axis) purely so the
    // plotted area width matches the V/I chart above, making the two
    // x-axes line up for easy visual comparison at the same timestamp.
    const dsT = [
      {label:'MOS',     data:tmos.map((v,i)=>({x:ts[i],y:v})), borderColor:'#f04f4f',backgroundColor:'rgba(240,79,79,.08)',borderWidth:1.5,pointRadius:0,tension:.3,yAxisID:'y'},
      {label:'Bat 1',   data:tb1.map((v,i)=>({x:ts[i],y:v})),  borderColor:'#4f9fff',backgroundColor:'rgba(79,159,255,.08)',borderWidth:1.5,pointRadius:0,tension:.3,yAxisID:'y'},
      {label:'Bat 2',   data:tb2.map((v,i)=>({x:ts[i],y:v})),  borderColor:'#22c97a',backgroundColor:'rgba(34,201,122,.08)',borderWidth:1.5,pointRadius:0,tension:.3,yAxisID:'y'},
      {label:'Ambient', data:tamb.map((v,i)=>({x:ts[i],y:v})), borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,.06)',borderWidth:1.5,pointRadius:0,tension:.3,borderDash:[4,3],yAxisID:'y'},
    ];
    if(chartTemp){ chartTemp.destroy(); }
    chartTemp = mkChart('chart-temp', dsT, 'Temperature (°C)', 'Temperature (°C)', true);

  }catch(e){
    $('hist-loading').style.display='block';
    $('hist-loading').textContent='Error loading history: '+e.message;
  }
}
</script>
</body>
</html>"""
