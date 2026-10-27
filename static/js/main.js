/* ==========================================================
   Sayangin — interaksi halaman utama & komponen global
   ========================================================== */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Landing: Empat pilihan (JUAL / DONASI / SIMPAN / TUNDA BELI) ---------- */
  const choiceWords = [...document.querySelectorAll('[data-choice-word]')];
  const choicePreview = document.querySelector('[data-choice-preview]');
  const choiceCaption = document.querySelector('[data-choice-caption]');
  if (choiceWords.length && choicePreview) {
    choiceWords.forEach(word => {
      word.style.cursor = 'pointer';
      word.setAttribute('tabindex', '0');
      const activate = () => {
        choiceWords.forEach(w => w.classList.toggle('is-active', w === word));
        if (word.dataset.choiceImg) {
          choicePreview.style.backgroundImage = `url(${word.dataset.choiceImg})`;
        }
        if (choiceCaption && word.dataset.choiceDesc) {
          choiceCaption.textContent = word.dataset.choiceDesc;
        }
      };
      word.addEventListener('click', activate);
      word.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          activate();
        }
      });
    });
  }

  /* ---------- Landing (mobile): Fase cara kerja ---------- */
  const phaseTabs = [...document.querySelectorAll('[data-phase-tab]')];
  const phasePhoto = document.querySelector('[data-phase-photo]');
  const phaseText = document.querySelector('[data-phase-text]');
  const phaseData = [
    { img: '/static/img/jaket-kulit.jpg', text: 'Foto barangmu dan masukkan ke Lemari Digital. Satu menit per barang.' },
    { img: '/static/img/heels-chrome.jpg', text: 'Saat lama tak dipakai, sistem memberi pengingat: jual, donasi, atau simpan.' },
    { img: '/static/img/tas-kulit.jpg', text: 'Salurkan ke pembeli baru atau lembaga mitra yang benar-benar membutuhkan.' },
  ];
  if (phaseTabs.length) {
    phaseTabs.forEach((tab, idx) => {
      tab.addEventListener('click', (e) => {
        e.preventDefault();
        phaseTabs.forEach((t, i) => {
          const active = i === idx;
          t.setAttribute('aria-selected', String(active));
          t.classList.toggle('btn--dark', active);
          t.classList.toggle('btn--outline', !active);
        });
        const item = phaseData[idx];
        if (item && phasePhoto) {
          phasePhoto.style.setProperty('--img', `url(${item.img})`);
        }
        if (item && phaseText) {
          phaseText.textContent = item.text;
        }
      });
    });
  }

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

  /* ---------- A7 · Konfirmasi keluar (#keluar overlay / <dialog>) ---------- */
  const keluarOverlay = document.getElementById('keluar');
  const closeKeluar = () => {
    if (!keluarOverlay) return;
    keluarOverlay.classList.remove('is-open');
    if (window.location.hash === '#keluar') {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  };
  const openKeluar = (e) => {
    if (!keluarOverlay) return;
    if (e) e.preventDefault();
    if (drawer && !drawer.hidden) {
      setDrawer(false);
    }
    keluarOverlay.classList.add('is-open');
    const closeBtnEl = keluarOverlay.querySelector('[data-dialog-close]');
    closeBtnEl?.focus();
  };

  if (keluarOverlay) {
    const logoutTriggers = document.querySelectorAll('[href="#keluar"], [data-dialog-open="keluar"], [data-dialog-open="logout-dialog"]');
    logoutTriggers.forEach((trigger) => {
      trigger.addEventListener('click', openKeluar);
    });

    const closeButtons = keluarOverlay.querySelectorAll('[data-dialog-close]');
    closeButtons.forEach((button) => {
      button.addEventListener('click', (e) => {
        e.preventDefault();
        closeKeluar();
      });
    });

    keluarOverlay.addEventListener('click', (event) => {
      if (event.target === keluarOverlay) {
        closeKeluar();
      }
    });
  }

  /* ---------- Keyboard shortcut "/" untuk fokus ke kolom pencarian & Escape ---------- */
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
      const searchInput = document.querySelector('.search input[type="search"]');
      if (searchInput) {
        e.preventDefault();
        searchInput.focus();
      }
    }
    if (e.key === 'Escape') {
      if (drawer && !drawer.hidden) {
        setDrawer(false);
      }
      if (keluarOverlay && (keluarOverlay.classList.contains('is-open') || window.location.hash === '#keluar')) {
        closeKeluar();
      }
    }
  });
})();
