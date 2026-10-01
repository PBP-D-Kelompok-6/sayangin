/* ==========================================================
   Sayangin — interaksi homepage
   ========================================================== */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Drawer menu (mobile) ---------- */
  const drawer = document.getElementById('drawer');
  const openBtn = document.querySelector('[data-drawer-open]');
  const closeBtn = document.querySelector('[data-drawer-close]');

  const setDrawer = (open) => {
    if (!drawer) return;
    if (open) {
      drawer.hidden = false;
      requestAnimationFrame(() => drawer.classList.add('is-open'));
      closeBtn?.focus();
    } else {
      drawer.classList.remove('is-open');
      setTimeout(() => { drawer.hidden = true; }, reduceMotion ? 0 : 250);
      openBtn?.focus();
    }
    openBtn?.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('no-scroll', open);
  };
  openBtn?.addEventListener('click', () => setDrawer(true));
  closeBtn?.addEventListener('click', () => setDrawer(false));
  drawer?.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setDrawer(false)));

  /* ---------- Dropdown kategori ---------- */
  document.querySelectorAll('[data-dropdown]').forEach(btn => {
    const menu = document.getElementById(btn.getAttribute('aria-controls'));
    const toggle = (open) => {
      btn.setAttribute('aria-expanded', String(open));
      menu.classList.toggle('is-open', open);
    };
    btn.addEventListener('click', (e) => { e.stopPropagation(); toggle(btn.getAttribute('aria-expanded') !== 'true'); });
    document.addEventListener('click', (e) => { if (!menu.contains(e.target)) toggle(false); });
    menu.addEventListener('click', () => toggle(false));
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (drawer && !drawer.hidden) setDrawer(false);
    document.querySelectorAll('[data-dropdown][aria-expanded="true"]').forEach(b => b.click());
  });

  /* ---------- Hero slider ---------- */
  const slides = [...document.querySelectorAll('.hero__slide')];
  const dots = [...document.querySelectorAll('.hero__dots button')];
  let current = 0;
  let timer;

  const show = (i) => {
    current = (i + slides.length) % slides.length;
    slides.forEach((s, n) => {
      const active = n === current;
      s.classList.toggle('is-active', active);
      s.setAttribute('aria-hidden', String(!active));
      s.querySelectorAll('a, button').forEach(el => active ? el.removeAttribute('tabindex') : el.setAttribute('tabindex', '-1'));
    });
    dots.forEach((d, n) => d.setAttribute('aria-selected', String(n === current)));
  };
  const play = () => {
    if (reduceMotion || slides.length < 2) return;
    clearInterval(timer);
    timer = setInterval(() => show(current + 1), 6500);
  };
  dots.forEach((d, n) => d.addEventListener('click', () => { show(n); play(); }));
  const hero = document.querySelector('.hero');
  hero?.addEventListener('mouseenter', () => clearInterval(timer));
  hero?.addEventListener('mouseleave', play);
  hero?.addEventListener('focusin', () => clearInterval(timer));
  play();

  /* ---------- Favorit (♥) ---------- */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.fav-btn');
    if (!btn) return;
    e.preventDefault();
    const on = btn.getAttribute('aria-pressed') !== 'true';
    btn.setAttribute('aria-pressed', String(on));
    btn.classList.remove('pop');
    void btn.offsetWidth; // restart animasi
    if (!reduceMotion) btn.classList.add('pop');
  });

  /* ---------- (Opsional) isi etalase dari DummyJSON ----------
     Tambahkan atribut data-source="dummyjson" pada <ul data-product-grid>
     untuk mengganti kartu statis dengan data API. */
  const grid = document.querySelector('[data-product-grid][data-source="dummyjson"]');
  if (grid) loadProducts(grid);

  async function loadProducts(target) {
    const tints = ['wheat', 'blush', 'straw', 'stone', 'mint', 'sage'];
    const cities = ['Jakarta Selatan', 'Bandung', 'Yogyakarta', 'Surabaya', 'Depok', 'Bekasi', 'Bogor', 'Malang'];
    const conditions = ['Seperti baru', 'Jarang dipakai', 'Bekas pakai'];
    const rupiah = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 });
    try {
      const res = await fetch('https://dummyjson.com/products?limit=12&select=title,price,category,thumbnail');
      const { products } = await res.json();
      target.innerHTML = products.map((p, i) => `
        <li class="product-card">
          <div class="product-card__media" style="--tint: var(--tint-${tints[i % tints.length]})">
            <span class="badge">${escapeHtml(p.category)}</span>
            <img src="${p.thumbnail}" alt="${escapeHtml(p.title)}" loading="lazy">
            <button class="fav-btn" type="button" aria-pressed="false" aria-label="Simpan ${escapeHtml(p.title)}"><svg class="icon"><use href="#i-heart"/></svg></button>
          </div>
          <h3 class="product-card__title"><a href="#">${escapeHtml(p.title)}</a></h3>
          <p class="product-card__price">${rupiah.format(Math.round(p.price * 16000 / 1000) * 1000)}</p>
          <p class="product-card__meta">
            <span class="product-card__loc"><svg class="icon icon--xs"><use href="#i-pin"/></svg>${cities[i % cities.length]}</span>
            <span class="product-card__cond">${conditions[i % conditions.length]}</span>
          </p>
        </li>`).join('');
    } catch (err) {
      console.warn('Gagal memuat produk, kartu statis tetap dipakai.', err);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
})();
