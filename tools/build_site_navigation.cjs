'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const {ROOT,applyNavigation}=require('./site_navigation.cjs');
const files=cp.execFileSync('git',['ls-files','-z','--','*.html'],{cwd:ROOT,maxBuffer:4*1024*1024}).toString('utf8').split('\0').filter(Boolean);
let changed=0,checked=0;const skipped=[];
for(const rel of files){if(rel.startsWith('tools/'))continue;const file=path.join(ROOT,rel);const previous=fs.readFileSync(file,'utf8');const next=applyNavigation(previous);if(next===null){skipped.push(rel);continue;}checked++;if(next!==previous){fs.writeFileSync(file,next);changed++;}}
console.log(JSON.stringify({checked,changed,skipped}));
