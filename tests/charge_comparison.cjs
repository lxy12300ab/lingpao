const assert=require('node:assert/strict');
const summarize=require('../app/static/charge-comparison.js');
const rows=[
 {date:'2026-01-01',location:'home',grid_kwh:100,estimated_kwh:90},
 {date:'2026-02-01',location:'home',grid_kwh:10,estimated_kwh:8},
 {date:'2026-02-02',location:'home',grid_kwh:null,estimated_kwh:40},
 {date:'2025-12-01',location:'home',grid_kwh:10,estimated_kwh:12},
 {date:'2026-03-01',location:'public',grid_kwh:100,estimated_kwh:95},
 {date:'2026-04-01',location:'home',grid_kwh:null,estimated_kwh:60}
];
const m=summarize(rows,'month','home');
assert.equal(m[0].rate,null);
assert.equal(m[1].period,'2026-02');
assert.equal(m[1].rate,20);
assert.equal(m[1].paired,1);
assert.equal(m[1].count,2);
assert.equal(m.at(-1).rate,-20);
assert.equal(m.at(-1).anomalies,1);
const y=summarize(rows,'year','home')[0];
assert.equal(y.grid,110);
assert.equal(y.stored,98);
assert.ok(Math.abs(y.rate-12/110*100)<1e-9);
assert.equal(summarize(rows,'year','all')[0].grid,210);
assert.deepEqual(summarize([],'month','home'),[]);
console.log('Charge comparison: all checks passed');
