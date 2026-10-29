'use strict';
const fs=require('node:fs'),path=require('node:path');
const {applyNavigation}=require('./site_navigation.cjs');
const {renderCard,renderNotes,renderPersonal}=require('./payment_card_render.cjs');
const ROOT=path.resolve(__dirname,'..');
const data=JSON.parse(fs.readFileSync(path.join(ROOT,'data/payment-cards.json'),'utf8'));
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const allowedHosts=new Set(['www.lottecard.co.kr','www.shinhancard.com','www.hyundaicard.com','card.kbcard.com','www.hanacard.co.kr','m.hanacard.co.kr','www.samsungcard.com']);
function officialUrl(value,id){const url=new URL(value);if(url.protocol!=='https:'||!allowedHosts.has(url.hostname))throw Error('Official HTTPS source required '+id);}
const ids=new Set(),issuers=new Map();
for(const c of data.cards){
 if(!['personal','corporate'].includes(c.audience))throw Error('Audience required '+c.id);
 if(c.verification?.basis!=='official_explicit'||!['purchase_benefit','performance','exclusion'].includes(c.verification.result))throw Error('Explicit official verification required '+c.id);
 if(c.verification.result==='performance'&&c.performanceType!=='included')throw Error('Performance claim must be explicit '+c.id);
 if(ids.has(c.id))throw Error('Duplicate card '+c.id);ids.add(c.id);
 if(!['excluded','not_required','confirm','included'].includes(c.performanceType))throw Error('Unknown condition '+c.id);
 if(!['excluded','conditional'].includes(c.benefitType))throw Error('Unknown benefit '+c.id);
 if((c.benefitType==='conditional'||c.verification.result==='performance')&&!c.source.evidence)throw Error('Evidence basis required '+c.id);
 for(const field of ['name','scope','performance','performanceNote','benefit','benefitNote','note'])if(!c[field])throw Error('Missing '+field+' '+c.id);
 const url=new URL(c.source.url);
 if(url.protocol!=='https:'||!allowedHosts.has(url.hostname))throw Error('Official HTTPS source required '+c.id);
 if(c.issuance){if(!['application_open','closed'].includes(c.issuance.status)||!/^\d{4}-\d{2}-\d{2}$/.test(c.issuance.checkedAt)||!c.issuance.method)throw Error('Issuance evidence required '+c.id);officialUrl(c.issuance.sourceUrl,c.id);}
 for(const link of c.source.related||[])officialUrl(link.url,c.id);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(c.source.checkedAt)||!c.source.sections.length)throw Error('Source date and sections required '+c.id);
 issuers.set(c.issuerKey,c.issuer);
}
const personal=data.cards.filter(c=>c.audience==='personal'&&c.issuance?.status==='application_open'&&['purchase_benefit','performance'].includes(c.verification.result));
const corporate=data.cards.filter(c=>c.audience==='corporate'&&c.issuance?.status==='application_open'&&['purchase_benefit','performance'].includes(c.verification.result));
const personalIds=new Set(personal.map(c=>c.id));
const reference=data.cards.filter(c=>c.audience==='personal'&&!personalIds.has(c.id));
const referenceIssuers=new Map(reference.map(c=>[c.issuerKey,c.issuer]));
const home=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
function snippet(re){const m=home.match(re);if(!m)throw Error('Existing analytics snippet missing: '+re);return m[0];}
const head=snippet(/<!-- Google Tag Manager \(기존 코드 유지\) -->[\s\S]*?<!-- End Google Tag Manager -->/)+ '\n'+snippet(/<!-- Google tag \(gtag.js\) \(기존 코드 유지\) -->[\s\S]*?<\/script>\s*<script>[\s\S]*?<\/script>/);
const body=snippet(/<!-- Google Tag Manager \(noscript\) -->[\s\S]*?<!-- End Google Tag Manager \(noscript\) -->/);
const foot=snippet(/<!-- 네이버 애널리틱스 \(기존 코드 유지\) -->[\s\S]*?<\/script>\s*<script[^>]*>[\s\S]*?<\/script>/);
let html=fs.readFileSync(path.join(__dirname,'templates/payment-page.html'),'utf8');
const faqMatches=[...html.matchAll(/<details><summary>([^<]+)<span[\s\S]*?<\/summary><p>([\s\S]*?)<\/p><\/details>/g)];
const structured={'@context':'https://schema.org','@graph':[
 {'@type':'WebPage','@id':'https://kv-gift.co.kr/payment/#webpage',url:'https://kv-gift.co.kr/payment/',name:'상품권 카드결제 조건과 비용 확인 안내',description:'상품권 관련 전월실적·적립·할인 조건과 결제비용을 확인하는 정보 페이지',inLanguage:'ko-KR',dateModified:data.updated},
 {'@type':'BreadcrumbList',itemListElement:[{'@type':'ListItem',position:1,name:'홈',item:'https://kv-gift.co.kr/'},{'@type':'ListItem',position:2,name:'상품권 결제 정보',item:'https://kv-gift.co.kr/payment/'}]},
 {'@type':'FAQPage',mainEntity:faqMatches.map(m=>({'@type':'Question',name:m[1],acceptedAnswer:{'@type':'Answer',text:m[2]}}))}
]};
const values={PERSONAL_CONTENT:renderPersonal(personal),PERSONAL_COUNT:personal.length,CORPORATE_COUNT:corporate.length,REFERENCE_COUNT:reference.length,REFERENCE_ISSUER_COUNT:referenceIssuers.size,REFERENCE_ROWS:reference.map(c=>renderCard(c,true)).join('\n'),CORPORATE_ROWS:corporate.map(c=>renderCard(c)).join('\n'),REFERENCE_SOURCE_NOTES:renderNotes(reference),CORPORATE_SOURCE_NOTES:renderNotes(corporate),ISSUER_OPTIONS:'<option value="all">전체</option>'+[...referenceIssuers].map(([key,label])=>'<option value="'+esc(key)+'">'+esc(label)+'</option>').join(''),TRACKING_HEAD:head,TRACKING_BODY:body,TRACKING_FOOT:foot,JSON_LD:'<script type="application/ld+json">'+JSON.stringify(structured).replaceAll('<','\\u003c')+'</script>'};
html=html.replace(/\{\{([A-Z_]+)\}\}/g,(_,key)=>{if(!(key in values))throw Error('Unknown template token '+key);return values[key]});
html=html.replaceAll('2026.10.29',data.updated.replaceAll('-','.')).replaceAll('2026-10-29',data.updated);
html=html.replace('id="issuer"','id="issuer" disabled').replace('id="condition-filter"','id="condition-filter" disabled').replace('id="issuance-filter"','id="issuance-filter" disabled').replace('id="card-search"','id="card-search" disabled').replace('id="filter-reset"','id="filter-reset" disabled');
html=applyNavigation(html);
if(!html)throw Error('Shared navigation could not be applied');
if(/\{\{[A-Z_]+\}\}/.test(html)||/noindex|디자인 검토용|샘플 2종/.test(html))throw Error('Unfinished production page');
fs.mkdirSync(path.join(ROOT,'payment'),{recursive:true});
fs.writeFileSync(path.join(ROOT,'payment/index.html'),html);
console.log(`Payment page built: ${data.cards.length} cards / ${issuers.size} issuers / ${faqMatches.length} FAQ entries`);
