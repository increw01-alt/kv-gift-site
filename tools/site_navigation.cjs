'use strict';
const fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const sharedHeader=()=>fs.readFileSync(path.join(__dirname,'templates/site-header.html'),'utf8');
const assets='<!-- KV_SHARED_NAV_ASSETS_START -->\n<link rel="stylesheet" href="/css/payment-tokens.css?v=20261029a">\n<link rel="stylesheet" href="/css/site-navigation.css?v=20261029-menu1">\n<script src="/js/site-navigation.js?v=20261029-menu1" defer></script>\n<!-- KV_SHARED_NAV_ASSETS_END -->';
function legacyRange(html){const start=/<div\b[^>]*\bid="general_head"[^>]*>/.exec(html);if(!start)return null;const tags=/<\/?div\b[^>]*>/g;tags.lastIndex=start.index;let depth=0,m;while((m=tags.exec(html))){depth+=m[0].startsWith('</')?-1:1;if(!depth)return[start.index,tags.lastIndex]}throw Error('Unclosed legacy header');}
function applyNavigation(html){
 const header=sharedHeader();
 if(html.includes('<!-- KV_SHARED_HEADER_START -->'))html=html.replace(/<!-- KV_SHARED_HEADER_START -->[\s\S]*?<!-- KV_SHARED_HEADER_END -->/,()=>header);
 else if(/<header class="site-header">/.test(html))html=html.replace(/<header class="site-header">[\s\S]*?<\/header>/,()=>header);
 else {const range=legacyRange(html);if(!range)return null;html=html.slice(0,range[0])+header+html.slice(range[1]);}
 if(html.includes('<!-- KV_SHARED_NAV_ASSETS_START -->'))html=html.replace(/<!-- KV_SHARED_NAV_ASSETS_START -->[\s\S]*?<!-- KV_SHARED_NAV_ASSETS_END -->/,()=>assets);
 else html=html.replace('</head>',assets+'\n</head>');
 return html;
}
module.exports={ROOT,sharedHeader,applyNavigation,legacyRange};
