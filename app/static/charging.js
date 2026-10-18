"use strict";
window.Charging = (() => {
  let records = [], meters = [], editing = null, loading = false, saving = false, meterRevision = "";
  const el = id => document.getElementById(id);
  const fixed = n => Number(n).toFixed(2);
  const locations = {home:"家充", public:"公共充电", other:"其他"};
  let rangeKind="month";
  let lossGrain="month",lossPage=0;
  const meterLabel=document.createElement("label");meterLabel.textContent="电表对比月份（独立于上方统计范围）";
  const meterMonth=document.createElement("input");meterMonth.type="month";meterMonth.id="chargeMeterMonth";meterMonth.value=today().slice(0,7);meterMonth.max=today().slice(0,7);meterMonth.required=true;
  meterLabel.append(meterMonth);el("chargeMeterForm").prepend(meterLabel);
  const meterValueLabel=el("chargeMeter").parentElement;
  meterValueLabel.firstChild.textContent="所选月电表总用电（度，可留空）";
  meterMonth.onchange=()=>{if(!meterMonth.value)meterMonth.value=today().slice(0,7);paint();};
  el("chargeMonth").value = today().slice(0,7);
  el("chargeMonth").parentElement.firstChild.textContent="或指定单月 ";
  el("chargeMonth").max = today().slice(0,7);
  function metric(label, value) {
    const d = document.createElement("div");
    const t = document.createElement("span"); t.textContent = label;
    const v = document.createElement("strong"); v.textContent = value;
    d.append(t,v); return d;
  }
  function paint() {
    const month = el("chargeMonth").value, location = el("chargeLocation").value;
    const period=chargeRangeBounds(rangeKind,today(),month);
    const selected=records.filter(r=>(!period.start||r.date>=period.start)&&(!period.end||r.date<=period.end));
    const rows = selected.filter(r => location === "all" || r.location === location);
    el("chargeRangeCaption").textContent=period.start?period.start+" — "+period.end+" · 按充电结束日期":"全部历史充电记录";
    document.querySelectorAll("[data-charge-range]").forEach(b=>{const active=b.dataset.chargeRange===rangeKind;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
    const paired = rows.filter(r => r.grid_kwh !== null);
    const estimated = rows.reduce((s,r)=>s+r.estimated_kwh,0);
    const grid = paired.reduce((s,r)=>s+r.grid_kwh,0);
    const pairedEstimate = paired.reduce((s,r)=>s+r.estimated_kwh,0);
    paintComparison();
    renderLoss(el("chargeLossHero"), grid, pairedEstimate, paired.length, rows.length);
    el("chargeSummary").replaceChildren(
      metric("充电次数", rows.length+" 次"),
      metric("估算充入",fixed(estimated)+" 度"),
      metric("已补电表用电",paired.length ? fixed(grid)+" 度":"待补充"));
    el("chargeStatus").textContent = "电表已补 "+paired.length+" / "+rows.length+" 笔"+(grid && grid<pairedEstimate ? " · 电表小于估算充入，请核对读数；负差额不代表实际负损耗。":"");
    const meter = meters.find(r=>r.month===meterMonth.value);
    if(document.activeElement !== el("chargeMeter")) {
      meterRevision = meter?.revision || "";
      el("chargeMeter").value = meter?.kwh ?? "";
    }
    const home = records.filter(r=>r.date.startsWith(meterMonth.value)&&r.location==="home");
    const homeTotal = home.reduce((s,r)=>s+r.estimated_kwh,0);
    const comparison = el("chargeMeterComparison");
    comparison.replaceChildren();
    for (const [label, value] of [["家充估算充入",homeTotal],["月度电表用电",meter?.kwh]]) {
      const line = metric(label,value==null ? "待补充":fixed(value)+" 度");
      if(value!=null) {
        const bar = document.createElement("progress"); bar.max=Math.max(homeTotal,meter?.kwh||0,1);bar.value=value;bar.setAttribute("aria-label",label+" "+fixed(value)+"度");line.append(bar);
      }
      comparison.append(line);
    }
    const note = document.createElement("p");note.className="muted";
    note.textContent = meter?.kwh > 0 && home.length
      ? "月度估算差额 "+fixed(meter.kwh-homeTotal)+" 度 · 差额占比 "+fixed((meter.kwh-homeTotal)/meter.kwh*100)+"%。仅在家充记录完整、月份一致时才可近似理解为损耗。"
      : "补齐家充记录和月度电表后可比较；本月未结束时，请使用同一截止时间。";
    comparison.append(note);
    const list = el("chargeList");list.replaceChildren();
    if(!rows.length) {const p=document.createElement("p");p.className="muted";p.textContent="这个时间范围还没有充电记录，点击“记录充电”开始。";list.append(p);}
    for(const r of rows) {
      const b=document.createElement("button");b.className="charge-row";
      const h=document.createElement("strong");h.textContent=r.date+" · "+locations[r.location];
      const s=document.createElement("span");s.textContent=r.start_pct+"% → "+r.end_pct+"% · 估算充入 "+fixed(r.estimated_kwh)+" 度";
      const t=document.createElement("small");t.textContent=r.grid_kwh===null ? "电表待补充 · 点击补录或修改":"电表 "+fixed(r.grid_kwh)+" 度 · 估算损耗 "+fixed(r.loss_kwh)+" 度 / "+fixed(r.loss_pct)+"%"+(r.loss_kwh<0?" · 请核对":"");
      const badge=document.createElement("span");
      badge.className="charge-loss-badge"+(r.loss_kwh<0?" is-anomaly":r.grid_kwh===null?" is-pending":"");
      badge.textContent=r.grid_kwh===null?"损耗待计算 · 补录电表":r.loss_kwh<0?"负差额 "+fixed(r.loss_pct)+"% · 请核对":"估算损耗率 "+fixed(r.loss_pct)+"%";
      b.append(h,badge,s,t);if(r.note){const n=document.createElement("small");n.textContent=r.note;b.append(n);}
      b.onclick=()=>open(r);list.append(b);
    }
  }
  function paintComparison() {
    const groups=chargeComparison(records,lossGrain,el("chargeLocation").value);
    lossPage=Math.min(lossPage,Math.max(0,Math.ceil(groups.length/12)-1));
    const shown=groups.slice(lossPage*12,lossPage*12+12);
    const chart=el("lossCompareChart"),table=el("lossCompareRows");chart.replaceChildren();table.replaceChildren();
    const scale=Math.max(1,...groups.map(g=>Math.abs(g.rate??0)));
    if(!shown.length){const p=document.createElement("p");p.textContent="暂无充电记录";chart.append(p);}
    for(const g of shown){
      const row=document.createElement("div");row.className="loss-compare-row";
      const label=document.createElement("span");label.textContent=g.period;
      const track=document.createElement("div");track.className="loss-compare-track";
      const fill=document.createElement("span");fill.className=g.rate<0?"negative":"";
      fill.style.width=(g.rate===null?0:Math.abs(g.rate)/scale*100)+"%";track.append(fill);
      track.setAttribute("role","img");track.setAttribute("aria-label",g.period+" "+(g.rate===null?"待补电表":fixed(g.rate)+"%"));
      const value=document.createElement("strong");value.textContent=g.rate===null?"待补":fixed(g.rate)+"%";if(g.rate<0)value.className="error";
      row.append(label,track,value);
      const detail=document.createElement("small");detail.textContent="配对 "+g.paired+"/"+g.count+" 笔"+(g.anomalies?" · "+g.anomalies+" 笔负差额待核对":g.paired<g.count?" · 部分数据":"");
      row.append(detail);chart.append(row);
      const tr=document.createElement("tr");
      [g.period,g.paired?fixed(g.grid):"—",g.paired?fixed(g.stored):"—",g.loss===null?"—":fixed(g.loss),g.rate===null?"—":fixed(g.rate)+"%",g.paired+" / "+g.count+(g.anomalies?" · 待核对":"")].forEach((v,i)=>{const td=document.createElement(i===0?"th":"td");if(i===0)td.scope="row";td.textContent=v;tr.append(td);});table.append(tr);
    }
    el("lossComparePage").textContent=groups.length?"第 "+(lossPage+1)+" / "+Math.ceil(groups.length/12)+" 页 · 条长按本组最大绝对值缩放":"暂无数据";
    el("lossCompareNewer").disabled=lossPage===0;el("lossCompareOlder").disabled=(lossPage+1)*12>=groups.length;
  }
  document.querySelectorAll("[data-loss-grain]").forEach(b=>b.onclick=()=>{lossGrain=b.dataset.lossGrain;lossPage=0;document.querySelectorAll("[data-loss-grain]").forEach(x=>{x.classList.toggle("active",x===b);x.setAttribute("aria-pressed",String(x===b));});paintComparison();});
  el("lossCompareNewer").onclick=()=>{lossPage--;paintComparison();};
  el("lossCompareOlder").onclick=()=>{lossPage++;paintComparison();};
  function renderLoss(target, grid, stored, count, total) {
    target.replaceChildren();
    target.className="charge-loss-hero"+(grid>0 && stored>grid?" is-anomaly":"");
    const heading=document.createElement("h3");heading.textContent="充电估算损耗率";
    const value=document.createElement("div");value.className="charge-loss-value";
    const loss=grid-stored;
    value.textContent=grid>0?fixed(loss/grid*100)+"%":"—";
    const state=document.createElement("span");state.className="charge-loss-badge";
    state.textContent=!count?"等待电表数据":loss<0?"负差额 · 请核对":count<total?"部分记录已配对":"已配对记录";
    const subtitle=document.createElement("p");subtitle.className="muted";
    subtitle.textContent=!count?"补充单次电表用电后，自动计算。":loss<0
      ?"估算充入大于电表用电，不代表实际负损耗；请核对百分比与电表读数。"
      :"每使用 100 度电，约 "+fixed(loss/grid*100)+" 度未计入估算充入电量。";
    target.append(heading,value,state,subtitle);
    if(count) {
      if(loss>=0) {
        const bar=document.createElement("div");bar.className="charge-loss-track";
        bar.setAttribute("role","img");bar.setAttribute("aria-label","估算充入 "+fixed(stored)+" 度，估算损耗 "+fixed(loss)+" 度");
        const fill=document.createElement("span");fill.style.width=(stored/grid*100)+"%";bar.append(fill);target.append(bar);
      }
      const labels=document.createElement("div");labels.className="charge-loss-parts";
      labels.append(metric("● 估算充入电池",fixed(stored)+" 度"),metric(loss<0?"● 负差额":"● 估算损耗",fixed(loss)+" 度"));
      target.append(labels);
    }
    const scope=document.createElement("p");scope.className="charge-loss-scope";
    scope.textContent="所选时间范围与地点 · 电表已补 "+count+" / "+total+" 笔。"+(count?"按这 "+count+" 笔合计计算，未补电表记录不参与。":"未补数据不计作 0。");
    target.append(scope);
  }
  async function load() {
    if(loading)return;loading=true;
    try {const payload=await(await api("/api/charging")).json();records=payload.records;meters=payload.meters;paint();}
    catch(e){el("chargeStatus").textContent=e.message;}
    finally{loading=false;}
  }
  function estimate() {
    const a=Number(el("chargeStart").value),b=Number(el("chargeEnd").value);
    const ready=el("chargeStart").value!==""&&el("chargeEnd").value!==""&&b>a&&a>=0&&b<=100;
    el("chargeEnd").setCustomValidity(ready?"":"结束电量应大于开始电量");
    const kwh=81.9*(b-a)/100,g=Number(el("chargeGrid").value);
    el("chargeEstimate").textContent=ready ? "估算充入 "+fixed(kwh)+" 度"+(g>0?" · 估算损耗率 "+fixed((g-kwh)/g*100)+"%"+(g<kwh?"（负差额，请核对）":""):""):"按电池容量 81.9 度估算";
  }
  function open(row=null) {
    if(!token){showDialog("loginDialog");return;}
    editing=row;
    el("chargeForm").reset();el("chargeTitle").textContent=row?"修改充电记录":"记录充电";
    el("chargeDate").value=row?.date||today();el("chargeDate").max=today();
    el("chargeStart").value=row?.start_pct??"";el("chargeEnd").value=row?.end_pct??100;
    el("chargeGrid").value=row?.grid_kwh??"";el("chargePlace").value=row?.location||"home";el("chargeNote").value=row?.note||"";
    el("chargeError").textContent="";el("chargeDelete").hidden=!row;estimate();showDialog("chargeDialog");
  }
  el("chooseCharge").onclick=()=>{el("recordChoice").close();open();};
  el("newCharge").onclick=()=>open();
  ["chargeStart","chargeEnd","chargeGrid"].forEach(id=>el(id).oninput=estimate);
  el("chargeMonth").onchange=()=>{if(!el("chargeMonth").value)el("chargeMonth").value=today().slice(0,7);rangeKind="custom";paint();};el("chargeLocation").onchange=paint;
  document.querySelectorAll("[data-charge-range]").forEach(b=>b.onclick=()=>{rangeKind=b.dataset.chargeRange;paint();});
  el("chargeForm").onsubmit=async e=>{
    e.preventDefault();if(saving||!el("chargeForm").reportValidity())return;saving=true;el("chargeSave").disabled=true;el("chargeDelete").disabled=true;
    try {
      const body={date:el("chargeDate").value,start_pct:Number(el("chargeStart").value),end_pct:Number(el("chargeEnd").value),grid_kwh:el("chargeGrid").value===""?null:Number(el("chargeGrid").value),location:el("chargePlace").value,note:el("chargeNote").value,expected_revision:editing?.revision||""};
      await api("/api/charging"+(editing?"/"+editing.id:""),{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      el("chargeDialog").close();el("chargeMonth").value=body.date.slice(0,7);rangeKind="custom";el("chargeLocation").value=body.location;notify("充电记录已保存");await load();
    }catch(error){el("chargeError").textContent=error.message;}
    finally{saving=false;el("chargeSave").disabled=false;el("chargeDelete").disabled=false;}
  };
  el("chargeDelete").onclick=async()=>{
    if(saving||!editing||!confirm("删除这条充电记录？它将从统计中移除，其他数据不变。"))return;
    saving=true;el("chargeDelete").disabled=true;el("chargeSave").disabled=true;
    try{await api("/api/charging/"+editing.id,{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_revision:editing.revision})});el("chargeDialog").close();await load();notify("充电记录已删除（保留审计记录）");}
    catch(e){el("chargeError").textContent=e.message;}
    finally{saving=false;el("chargeDelete").disabled=false;el("chargeSave").disabled=false;}
  };
  el("chargeMeterForm").onsubmit=async e=>{
    e.preventDefault();if(saving||!meterMonth.value)return;saving=true;el("saveMeter").disabled=true;
    try{await api("/api/charging/meter",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({month:meterMonth.value,kwh:el("chargeMeter").value===""?null:Number(el("chargeMeter").value),expected_revision:meterRevision})});await load();notify("月度电表已保存");}
    catch(error){el("chargeStatus").textContent=error.message;}
    finally{saving=false;el("saveMeter").disabled=false;}
  };
  // Keep DOM order and keyboard order identical to the visual five-item dock.
  const nav=document.querySelector(".primary-nav");
  nav.insertBefore(el("mobileUpload"),nav.querySelector('[data-page="energy"]'));
  return {load};
})();
