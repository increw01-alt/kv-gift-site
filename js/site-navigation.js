'use strict';
(() => {
  const root=document.querySelector('.kv-global-header');if(!root)return;
  function setCurrent(){
    const p=location.pathname;
    let href='';
    if(p.startsWith('/payment'))href='/payment/';
    else if(p.startsWith('/price'))href='/price/';
    else if(p.startsWith('/business'))href='/business.html';
    else if(/\/(gc_information|gc_tip|gc_word)\//.test(p))href='/board/gc_information/';
    else if(p.includes('/general_notice/')||p.startsWith('/faq'))href='/faq.html';
    else if(p.startsWith('/board/'))href='/board/free/';
    else if(/^\/(guide|intro)/.test(p))href='/guide.html';
    else if(location.hash==='#shop')href='/#shop';
    root.querySelectorAll('.kv-header-link').forEach(link=>{
      link.removeAttribute('aria-current');
      if(link.getAttribute('href')===href)link.setAttribute('aria-current','page');
    });
    root.querySelectorAll('.kv-mobile-menu-list details').forEach(details=>{
      details.open=Boolean(href)&&details.querySelector('a').getAttribute('href')===href;
    });
  }
  setCurrent();
  addEventListener('hashchange',setCurrent);
  const items=[...root.querySelectorAll('.kv-header-nav-item')];
  function closeAll(){items.forEach(item=>{item.classList.remove('is-open');item.querySelector('button').setAttribute('aria-expanded','false');item.querySelector('.kv-header-submenu').hidden=true;});}
  function open(item){closeAll();item.classList.add('is-open');item.querySelector('button').setAttribute('aria-expanded','true');item.querySelector('.kv-header-submenu').hidden=false;}
  items.forEach(item=>{
    item.querySelector('button').addEventListener('click',()=>item.classList.contains('is-open')?closeAll():open(item));
    item.addEventListener('mouseenter',()=>{if(matchMedia('(min-width:1101px)').matches)open(item)});
    item.addEventListener('mouseleave',closeAll);
    item.addEventListener('focusout',event=>{if(!item.contains(event.relatedTarget))closeAll()});
  });
  document.addEventListener('pointerdown',event=>{if(!root.contains(event.target))closeAll()});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){const focused=root.querySelector('.kv-header-nav-item.is-open button');closeAll();if(focused)focused.focus()}});
  const dialog=root.querySelector('dialog'),toggle=root.querySelector('.kv-menu-toggle');
  toggle.addEventListener('click',()=>{closeAll();dialog.showModal();toggle.setAttribute('aria-expanded','true');document.documentElement.classList.add('kv-menu-is-open')});
  dialog.querySelector('[data-menu-close]').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{toggle.setAttribute('aria-expanded','false');document.documentElement.classList.remove('kv-menu-is-open');toggle.focus()});
  dialog.addEventListener('click',event=>{if(event.target===dialog){const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right)dialog.close()}});
  dialog.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>dialog.close()));
  const active=root.querySelector('.kv-header-link[aria-current]');
  if(active&&matchMedia('(max-width:1100px)').matches){const scroller=root.querySelector('.kv-header-nav>.kv-header-inner');scroller.scrollLeft=Math.max(0,active.offsetLeft-(scroller.clientWidth-active.offsetWidth)/2)}
  addEventListener('resize',()=>{closeAll();if(matchMedia('(min-width:1101px)').matches&&dialog.open)dialog.close()});
})();
