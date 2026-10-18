(function(root) {
  function summarize(records, grain, location) {
    const groups=new Map();
    for(const r of records) {
      if(location!=="all"&&r.location!==location)continue;
      const key=r.date.slice(0,grain==="year"?4:7);
      if(!groups.has(key))groups.set(key,{period:key,count:0,paired:0,grid:0,stored:0,anomalies:0});
      const g=groups.get(key);g.count++;
      if(r.grid_kwh!=null) {
        g.paired++;g.grid+=r.grid_kwh;g.stored+=r.estimated_kwh;
        if(r.grid_kwh<r.estimated_kwh)g.anomalies++;
      }
    }
    return [...groups.values()].map(g=>({...g,loss:g.paired?g.grid-g.stored:null,
      rate:g.grid>0?(g.grid-g.stored)/g.grid*100:null}))
      .sort((a,b)=>b.period.localeCompare(a.period));
  }
  if(typeof module!=="undefined")module.exports=summarize;
  else root.chargeComparison=summarize;
})(globalThis);
