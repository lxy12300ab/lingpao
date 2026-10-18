(function(root) {
  function bounds(kind, today, month) {
    const y=Number(today.slice(0,4)), m=Number(today.slice(5,7));
    const start=(year,mon)=>year+"-"+String(mon).padStart(2,"0")+"-01";
    const end=(year,mon)=>new Date(Date.UTC(year,mon,0)).toISOString().slice(0,10);
    if(kind==="all")return {start:"",end:""};
    if(kind==="year")return {start:start(y,1),end:end(y,12)};
    if(kind==="lastyear")return {start:start(y-1,1),end:end(y-1,12)};
    if(kind==="quarter"){const q=Math.floor((m-1)/3)*3+1;return {start:start(y,q),end:end(y,q+2)};}
    let year=y,mon=m;
    if(kind==="lastmonth"){mon=m===1?12:m-1;year=m===1?y-1:y;}
    if(kind==="custom"){year=Number(month.slice(0,4));mon=Number(month.slice(5,7));}
    return {start:start(year,mon),end:end(year,mon)};
  }
  if(typeof module!=="undefined")module.exports=bounds;
  else root.chargeRangeBounds=bounds;
})(globalThis);
