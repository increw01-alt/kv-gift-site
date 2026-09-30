/* kv-gift.co.kr 한국상품권거래소 — 정적 사이트 메인 스크립트 (원본 인라인 스크립트 정리·통합) */
(function () {
  'use strict';

  /* ---------- 팝업 레이어 (24시간 다시 보지 않기) ---------- */
  function getCookie(n) {
    var m = document.cookie.match(new RegExp('(?:^|; )' + n + '=([^;]*)'));
    return m ? m[1] : null;
  }
  function setCookie(n, v, hours) {
    var d = new Date(); d.setTime(d.getTime() + hours * 3600 * 1000);
    document.cookie = n + '=' + v + '; expires=' + d.toUTCString() + '; path=/';
  }
  $('.hd_pops').each(function () {
    if (getCookie(this.id)) $(this).hide();
  });
  $('.hd_pops_reject').on('click', function () {
    var c = $(this).attr('class').split(' ');
    setCookie(c[1], 1, parseInt(c[2], 10) || 24);
    $('#' + c[1]).hide();
  });
  $('.hd_pops_close').on('click', function () {
    var c = $(this).attr('class').split(' ');
    $('#' + c[1]).hide();
  });

  /* ---------- 모바일 헤더 ---------- */
  $('#general_toggle').on('click', function () {
    $('.mo_wrap').css('display', 'block').removeClass('close').addClass('open');
    $('.nav_content').removeClass('close').addClass('open');
  });
  $('.menu_close').on('click', function () {
    $('.mo_wrap').removeClass('open').addClass('close');
    $('.nav_content').removeClass('open').addClass('close');
    $('.nav_inner').slideUp(100);
    $('.nav_list').removeClass('atv');
    setTimeout(function () { $('.mo_wrap').css('display', 'none'); }, 500);
  });
  $('.nav_list').on('click', function () {
    var inner = $(this).children('.nav_inner');
    $('.nav_inner').not(inner).slideUp(100);
    inner.is(':visible') ? inner.slideUp(100) : inner.slideDown(100);
    var wasActive = $(this).hasClass('atv');
    $('.nav_list').removeClass('atv');
    if (!wasActive) $(this).addClass('atv');
  });
  $(window).on('pageshow', function () {
    $('.mo_wrap').removeClass('open').addClass('close');
    $('.nav_content').removeClass('open').addClass('close');
    $('.nav_inner').slideUp(100);
    $('.nav_list').removeClass('atv');
  });

  /* ---------- 헤더 고정 여부 (브라우저 폭) ---------- */
  function applyHeadMode() {
    if (window.innerWidth > 1200) {
      $('#general_head').css({ position: 'relative', background: '', 'border-bottom': '' });
    } else {
      $('#general_head').css('position', 'fixed');
      applyHeadScroll();
    }
  }
  function applyHeadScroll() {
    if (window.innerWidth > 1200) return;
    if (window.scrollY > 1) $('#general_head').css({ background: '#fff', 'border-bottom': '1px solid #ddd' });
    else $('#general_head').css({ background: 'unset', 'border-bottom': 'unset' });
  }
  applyHeadMode();
  $(window).on('resize', applyHeadMode);

  /* ---------- 스크롤: TOP 버튼 / 플로팅 ---------- */
  $(window).on('scroll', function () {
    var y = window.scrollY;
    applyHeadScroll();
    $('#top_btn').toggleClass('fixation', y > 509);
    $('.floating_left, .floating_right').toggleClass('atv', y > 730);
  });
  $('#top_btn').on('click', function () {
    $('html, body').animate({ scrollTop: 0 }, 500);
    return false;
  });

  /* ---------- 현재 페이지 메뉴 활성화 ---------- */
  var path = location.pathname;
  var menuActive = {
    '/intro.html': ['menu_6', 'menu_6-4'], '/guide.html': ['menu_6', 'menu_6-1'],
    '/faq.html': ['menu_7', 'menu_7-2'], '/business.html': ['menu_2']
  };
  if (menuActive[path]) menuActive[path].forEach(function (c) { $('.' + c).addClass('atv'); });

  /* ---------- 등록업체 빠른검색 탭 ---------- */
  function resetSearch() {
    $('.search_btn1, .search_btn2, .search_con1, .search_con2').removeClass('atv');
    $('.search_content').hide();
    $('.content3').removeClass('bt');
    $('.search_btn1, .search_btn2').css('border-bottom', 'none');
  }
  resetSearch();
  $('.search_con_close').on('click', resetSearch);
  $('.search_btn1').on('click', function () {
    $('.search_content').show(); $('.content3').addClass('bt'); $(this).addClass('atv');
    if (window.innerWidth > 800) { $('.search_btn2, .search_con1, .search_con2').addClass('atv'); }
    else { $('.search_btn2, .search_con2').removeClass('atv'); $('.search_con1').addClass('atv'); $('.search_btn2').css('border-bottom', '1px solid #ddd'); }
  });
  $('.search_btn2').on('click', function () {
    $('.search_content').show(); $('.content3').addClass('bt'); $(this).addClass('atv');
    if (window.innerWidth > 800) { $('.search_btn1, .search_con1, .search_con2').addClass('atv'); }
    else { $('.search_btn1, .search_con1').removeClass('atv'); $('.search_con2').addClass('atv'); $('.search_btn1').css('border-bottom', '1px solid #ddd'); }
  });

  /* ---------- 시세표: data/prices.json 렌더링 ---------- */
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function renderPrices(data) {
    if (data.updated) {
      var d = data.updated.split('-');
      $('.price-updated').text(d.length === 3 ? d[0].slice(2) + '. ' + d[1] + '. ' + d[2] : data.updated);
    }
    $('[data-price-table]').each(function () {
      var rows = data[$(this).data('price-table')] || [];
      var html = rows.map(function (r) {
        var click = r._slug ? ' onclick="location.href=\'/price/' + r._slug + '.html\'" style="cursor:pointer"' : '';
        var liveDot = r._live ? ' <i style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#2ecc71;vertical-align:2px" title="실시간 반영"></i>' : '';
        var arrow = r._slug ? ' <span style="color:var(--color-orange);font-size:11px">시세보기 ›</span>' : '';
        return '<div class="swiper-slide"' + click + '><div class="wrap flex">' +
          '<p>' + esc(r.name) + liveDot + arrow + '</p><p>' + esc(r.face) + '</p>' +
          '<p>' + esc(r.buy) + '<span>' + esc(r.buy_rate) + '</span></p>' +
          '<p>' + esc(r.sell) + '<span>' + esc(r.sell_rate) + '</span></p>' +
          '</div></div>';
      }).join('');
      $(this).find('.swiper-wrapper').html(html);
    });
    initPriceSliders();
  }
  function initPriceSliders() {
    $('.market_price_slide').each(function () {
      if (this.swiper) this.swiper.destroy(true, true);
      var sw = new Swiper(this, {
        direction: 'vertical', slidesPerView: 5, mousewheel: true, spaceBetween: 3,
        autoplay: { delay: 2500, disableOnInteraction: false }
      });
      $(this).hover(function () { sw.autoplay.stop(); }, function () { sw.autoplay.start(); });
    });
  }
  /* 협회(koreagiftcard.co.kr) 실시간 집계를 받아 백화점 10만원권 행에 반영 */
  var LIVE_BRANDS = {
    '신세계 상품권': 'shinsegae', '롯데 상품권': 'lotte', '현대 상품권': 'hyundai',
    '갤러리아 상품권': null, 'AK 상품권': null
  };
  function mergeLive(prices, live) {
    if (!live || !live.summary) return prices;
    var byBrand = {};
    live.summary.forEach(function (s) { byBrand[s.brand + ' 상품권'] = s; });
    (prices.paper || []).forEach(function (row) {
      var s = byBrand[row.name];
      if (s && row.face === '100,000') {
        row.buy = s.bestBuy.price.toLocaleString('ko-KR');
        row.buy_rate = s.bestBuy.rate + '%';
        row.sell = s.bestSell.price.toLocaleString('ko-KR');
        row.sell_rate = s.bestSell.rate + '%';
        row._live = true;
      }
      if (row.name in LIVE_BRANDS && LIVE_BRANDS[row.name]) row._slug = LIVE_BRANDS[row.name];
    });
    if (live.updated_at) prices._live_at = live.updated_at;
    return prices;
  }
  if ($('[data-price-table]').length) {
    var pPrices = $.ajax({ url: '/data/prices.json', dataType: 'json', timeout: 8000 });
    var pLive = fetch('https://koreagiftcard.co.kr/rates.json', { cache: 'no-store' })
      .then(function (r) { return r.json(); }).catch(function () { return null; });
    pPrices.done(function (prices) {
      pLive.then(function (live) {
        renderPrices(mergeLive(prices, live));
        if (prices._live_at) {
          $('.price-updated').each(function () {
            $(this).text($(this).text() + ' · 실시간 ' + prices._live_at.slice(11));
          });
        }
      });
    }).fail(function () { console.error('시세 데이터(data/prices.json) 로드 실패'); });
  }

  /* ---------- 등록업체: data/businesses.json 렌더링 (메인 섹션 + 최근등록업체 플로팅) ---------- */
  if ($('#main_business_list').length || $('#recent_business_list').length) {
    $.ajax({ url: '/data/businesses.json', dataType: 'json', timeout: 8000 })
      .done(function (data) {
        var all = (data.businesses || []).slice();
        /* 원본과 동일: 메인 카드는 랜덤 순서로 10곳 노출 */
        for (var i = all.length - 1; i > 0; i--) {
          var j = Math.floor(Math.random() * (i + 1));
          var t = all[i]; all[i] = all[j]; all[j] = t;
        }
        var random10 = all.slice(0, 10);
        $('#main_business_list').html(random10.map(function (b, i) {
          var btns = '';
          if (b.phone) {
            btns += '<p onclick="event.stopPropagation();location.href=\'tel:' + esc(b.phone) + '\'" title="' + esc(b.phone) + '">' +
              '<img src="/img/phone-solid.svg" alt="">전화번호</p>';
          }
          if (b.homepage) {
            btns += '<p onclick="event.stopPropagation();window.open(\'' + esc(b.homepage) + '\')">' +
              '<img src="/img/internet-explorer.svg" alt="">홈페이지</p>';
          }
          return '<li class="kv" onclick="location.href=\'/business.html\'">' +
            '<span></span><span></span><span></span><span></span>' +
            '<div class="name" style="background-image:url(&quot;/img/kv_random' + ((i % 32) + 1) + '.jpg&quot;)"><p>' + esc(b.name) + '</p></div>' +
            '<div class="text"><p>' + esc(b.desc) + '</p></div>' +
            (btns ? '<div class="btn_wrap flex">' + btns + '</div>' : '') +
            '</li>';
        }).join(''));
        /* 최근등록업체 플로팅: 최신 등록순 10곳 */
        $('#recent_business_list').html((data.businesses || []).slice(0, 10).map(function (b) {
          return '<li class="new_busi" onclick="location.href=\'/business.html\'"><span>N</span>' + esc(b.name) + '</li>';
        }).join(''));
      })
      .fail(function () { console.error('등록업체 데이터(data/businesses.json) 로드 실패'); });
  }

  /* ---------- 메인 게시판 요약: data/latest_posts.json 렌더링 ---------- */
  if ($('.board1').length) {
    var postUrl = function (bo, id) { return '/board/' + bo + '/' + id + '.html'; };
    $.ajax({ url: '/data/latest_posts.json', dataType: 'json', timeout: 8000 })
      .done(function (d) {
        function fill4(sel, bo, items) {
          var $ul = $(sel);
          if (!$ul.length || !items) return;
          $ul.find('li').not('.board_title').remove();
          items.forEach(function (r) {
            $ul.append('<li class="flex" onclick="location.href=\'' + postUrl(bo, r.id) + '\'">' +
              '<p>' + esc(r.cat || '-') + '</p><p>' + esc(r.title) + '</p>' +
              '<p>' + esc(r.author) + '</p><p>' + esc(r.date) + '</p></li>');
          });
        }
        fill4('.board1 .left ul', 'purchase', d.purchase);
        fill4('.board1 .right ul', 'sale', d.sale);
        var $f = $('.board2 .free_board ul');
        if ($f.length && d.free) {
          $f.empty();
          d.free.forEach(function (r) {
            $f.append('<li class="flex" onclick="location.href=\'' + postUrl('free', r.id) + '\'">' +
              '<p>' + esc(r.title) + '</p><span>' + esc(r.date) + '</span></li>');
          });
        }
        var $t = $('.board2 .tip_board ul');
        if ($t.length && d.gc_tip) {
          $t.empty();
          d.gc_tip.forEach(function (r) {
            $t.append('<li onclick="location.href=\'' + postUrl('gc_tip', r.id) + '\'">' +
              '<p>' + esc(r.title) + '</p></li>');
          });
        }
        var $n = $('.board2 .add_board > ul');
        if ($n.length && d.general_notice) {
          $n.empty();
          d.general_notice.forEach(function (r) {
            $n.append('<li class="flex" onclick="location.href=\'' + postUrl('general_notice', r.id) + '\'">' +
              '<p>' + esc(r.title) + '</p><span>' + esc(r.date) + '</span></li>');
          });
        }
        if (d.general_notice && d.general_notice[0]) {
          $('.content2 .notice p').text(d.general_notice[0].title);
          $('.content2 .notice span').text(d.general_notice[0].date);
        }
      })
      .fail(function () { console.error('최근 글 데이터(data/latest_posts.json) 로드 실패'); });
  }

  /* ---------- 슬라이더 ---------- */
  try {
    if ($('.goto_slider').length) {
      var goto = new Swiper('.goto_slider', {
        breakpoints: {
          0: { slidesPerView: 1.5, spaceBetween: 15 }, 600: { slidesPerView: 2.5, spaceBetween: 20 },
          801: { slidesPerView: 3.5, spaceBetween: 20 }, 1000: { slidesPerView: 4.5, spaceBetween: 20 },
          1201: { slidesPerView: 2.5, spaceBetween: 30 }
        },
        autoplay: { delay: 2500, disableOnInteraction: false }, loop: true, loopAdditionalSlides: 1,
        pagination: { el: '.goto_slider .swiper-pagination', type: 'fraction' },
        navigation: { nextEl: '.goto_slider .swiper-button-next', prevEl: '.goto_slider .swiper-button-prev' }
      });
      $('.goto_slider').hover(function () { goto.autoplay.stop(); }, function () { goto.autoplay.start(); });
    }
    if ($('.premium_slide').length) {
      var prem = new Swiper('.premium_slide', {
        breakpoints: { 0: { slidesPerView: 2 }, 600: { slidesPerView: 3 }, 801: { slidesPerView: 4 }, 1001: { slidesPerView: 5 } },
        pagination: { el: '.premium_slide .swiper-pagination', clickable: true },
        autoplay: { delay: 2500, disableOnInteraction: false }
      });
      $('.premium_slide').hover(function () { prem.autoplay.stop(); }, function () { prem.autoplay.start(); });
    }
  } catch (e) { console.error('Swiper init error:', e); }

  /* ---------- 회사소개: 약속 3가지 토글 ---------- */
  $('.promise_btn').on('click', function () {
    $('.promise_btn').removeClass('atv');
    $(this).addClass('atv');
  });
  $('.promise_btn.trigger').trigger('click');

  /* ---------- 이용안내: 게시물 규제정책 펼치기 ---------- */
  $('.add_btn').on('click', function () {
    $('.add_content').slideToggle();
    $(this).toggleClass('atv');
  });
})();
