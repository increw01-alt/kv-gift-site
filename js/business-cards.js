/* Registered website cards: shared browser renderer and static build source. */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.KVBusinessCards = api;
})(typeof window !== 'undefined' ? window : this, function () {
  'use strict';
  var pending;
  var HOME_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 11 12 2l10 9-3 2v9h-5v-7h-4v7H5v-9Z" fill="currentColor"/></svg>';

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function address(value) {
    try {
      var url = new URL(value);
      return /^(https?:)$/.test(url.protocol) ? url : null;
    } catch (_) { return null; }
  }

  function uniqueSites(items) {
    var seen = Object.create(null);
    return (Array.isArray(items) ? items : []).filter(function (b) {
      if (!b || b.enabled === false || !b.name) return false;
      var url = address(b.homepage);
      if (!url) return false;
      var host = url.hostname.toLowerCase().replace(/^www\./, '');
      if (seen[host]) return false;
      seen[host] = true;
      return true;
    });
  }

  function featured(items) {
    return uniqueSites(items).filter(function (b) { return b.featured === true; });
  }

  function select(items, limit, random) {
    var result = featured(items).slice();
    var rng = random || Math.random;
    for (var i = result.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var swap = result[i]; result[i] = result[j]; result[j] = swap;
    }
    return result.slice(0, typeof limit === 'number' ? Math.max(0, limit) : 10);
  }

  function renderCard(b) {
    var url = address(b.homepage);
    if (!url) return '';
    var host = url.hostname.toLowerCase().replace(/^www\./, '');
    var image = /^\/img\/[a-zA-Z0-9_./-]+$/.test(b.image || '') ? b.image : '/img/kv_random8.jpg';
    var rel = b.mine ? 'noopener' : 'noopener nofollow';
    return '<li class="business-card" data-business-id="' + esc(b.id || host) + '" data-host="' + esc(host) + '"><article>' +
      '<a class="photo-link" href="' + esc(url.href) + '" target="_blank" rel="' + rel + '" aria-label="' + esc(b.name) + ' 홈페이지 새 창으로 열기">' +
      '<img src="' + esc(image) + '" alt="' + esc(b.imageAlt || (b.name + ' 안내 이미지')) + '" width="640" height="400" loading="lazy">' +
      '<h3>' + esc(b.name) + '</h3></a>' +
      '<div class="description"><p title="' + esc(b.desc) + '">' + esc(b.desc) + '</p></div>' +
      '<div class="actions"><a class="homepage" href="' + esc(url.href) + '" target="_blank" rel="' + rel + '" aria-label="' + esc(b.name) + ' 홈페이지 바로가기 새 창으로 열기">' +
      HOME_ICON + '<span>홈페이지 바로가기</span></a></div></article></li>';
  }

  function render(items) { return uniqueSites(items).map(renderCard).join(''); }

  function load() {
    if (!pending) pending = fetch('/data/businesses.json?v=20261028-sites1', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('등록 사이트 정보 요청 실패'); return r.json(); })
      .then(function (data) { return uniqueSites(data.businesses); });
    return pending;
  }

  return { esc: esc, address: address, uniqueSites: uniqueSites, featured: featured, select: select, renderCard: renderCard, render: render, load: load };
});
