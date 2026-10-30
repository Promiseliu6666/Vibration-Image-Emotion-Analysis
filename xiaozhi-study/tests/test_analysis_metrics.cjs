const assert=require('node:assert/strict');
const metrics=require('../static/analysis-metrics.js');
const rows=[
 {start_time:'2026-10-12T16:00:00Z',valid_samples:10,primary:{data:4},behaviors:{engaged:3,phone:2,away:1}},
 {start_time:'2026-10-13T15:59:59Z',valid_samples:20,primary:{data:5},behaviors:{engaged:8,phone:1,rest:2,fatigue:1}},
 {start_time:'2026-10-13T16:00:00Z',valid_samples:5,primary:{data:1},behaviors:{phone:1,engaged:3}}
];
const s=metrics.summarize(rows);
assert.equal(s.samples,35);assert.equal(s.confirmed,25);assert.equal(s.confirmedPct,71);
assert.equal(s.days.length,2);assert.equal(s.days[0].date,'2026-10-13');assert.equal(s.days[0].samples,30);assert.equal(s.days[1].date,'2026-10-14');
assert.equal(Object.values(s.behaviors).reduce((a,b)=>a+b),s.samples);
assert.equal(metrics.summarize([]).confirmedPct,null);
assert.equal(metrics.summarize(rows.slice(2)).samples,5);
const csv=metrics.csv([['=SUM(A1:A2)','带"引号,中文','行\n文']]);
assert.ok(csv.startsWith('\ufeff"\'=SUM'));assert.ok(csv.includes('带""引号,中文'));assert.ok(csv.includes('"行\n文"'));
console.log('PASS range aggregation, Shanghai dates, non-overlapping totals, empty state and safe CSV.');
