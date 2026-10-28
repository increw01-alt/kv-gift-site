/* Regenerate crawlable website cards from data/businesses.json. No network calls. */
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '..');
const cards = require('../js/business-cards.js');
const data = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/businesses.json'), 'utf8'));
const all = cards.uniqueSites(data.businesses);
if (all.length !== data.businesses.length) throw new Error('등록 사이트의 잘못된 주소 또는 중복 도메인을 확인하세요.');
const managed = cards.featured(all);
if (managed.length < 10) throw new Error('메인 노출 후보는 최소 10개가 필요합니다.');
for (const b of all) {
  const image = path.resolve(ROOT, '.' + b.image);
  if (!image.startsWith(ROOT + path.sep) || !fs.existsSync(image)) throw new Error('대표 이미지 누락: ' + b.image);
}
function section(text, id, content) {
  const start = '<!-- ' + id + '_START -->', end = '<!-- ' + id + '_END -->';
  const begin = text.indexOf(start), finish = text.indexOf(end);
  if (begin < 0 || finish < begin) throw new Error('정적 카드 생성 위치 누락: ' + id);
  return text.slice(0, begin + start.length) + '\n' + content + '\n' + text.slice(finish);
}
const mainFile = path.join(ROOT, 'index.html');
let main = fs.readFileSync(mainFile, 'utf8');
main = section(main, 'MAIN_BUSINESSES', cards.render(managed.slice(0, 10)));
fs.writeFileSync(mainFile, main);
const listFile = path.join(ROOT, 'business.html');
let list = fs.readFileSync(listFile, 'utf8');
list = section(list, 'ALL_BUSINESSES', cards.render(all));
list = list.replace(/(<p class="biz_count">전체 <em>).*?(<\/em>개 사이트<\/p>)/, (_m,a,z)=>a+all.length+z);
const itemList = {
  '@context': 'https://schema.org', '@type': 'ItemList', name: '상품권·결제 관련 등록 사이트', numberOfItems: all.length,
  itemListElement: all.map((b, i) => ({ '@type': 'ListItem', position: i + 1, item: { '@type': 'WebSite', name: b.name, url: b.homepage, description: b.desc } }))
};
list = list.replace(/(<script type="application\/ld\+json" id="biz_itemlist">)[\s\S]*?(<\/script>)/, (_m, a, z) => a + JSON.stringify(itemList).replaceAll('<', '\\u003c') + z);
list = list.replace(/(<script type="application\/json" id="business-directory-data">)[\s\S]*?(<\/script>)/, (_m, a, z) => a + JSON.stringify(all).replaceAll('<', '\\u003c') + z);
fs.writeFileSync(listFile, list);
console.log(JSON.stringify({ mainCandidates: managed.length, mainCards: 10, directorySites: all.length, preservedPartners: all.length - managed.length }));
