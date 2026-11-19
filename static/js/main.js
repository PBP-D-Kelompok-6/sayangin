/* ==========================================================
   Sayangin — interaksi halaman utama, profil AJAX & komponen global
   ========================================================== */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Utilitas Toast & CSRF ---------- */
  const toastRegion = document.querySelector('[data-toast-region]');
  const showToast = (message) => {
    if (!toastRegion || !message) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'status');
    const span = document.createElement('span');
    span.className = 'toast__text';
    span.textContent = message;
    toast.appendChild(span);
    toastRegion.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3200);
  };

  const getCsrfToken = () => {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  };

  const escapeHtml = (str) => {
    return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
  };

  const ensureCityOption = (selectEl, cityName) => {
    if (!selectEl || !cityName) return;
    const existing = [...selectEl.options].find(
      (o) => o.value.toLowerCase() === cityName.toLowerCase()
    );
    if (existing) {
      selectEl.value = existing.value;
    } else {
      const opt = new Option(cityName, cityName, true, true);
      selectEl.add(opt);
      selectEl.value = cityName;
    }
  };

  /* ---------- RajaOngkir Destination Autocomplete (Profil & Edit Profil) ---------- */
  document.querySelectorAll('[data-ro-lookup]').forEach((lookup) => {
    const form = lookup.closest('form');
    if (!form) return;
    const apiUrl = lookup.getAttribute('data-ro-url') || '/api/rajaongkir/destinations/';
    const qInput = lookup.querySelector('[data-ro-query]');
    const resultsBox = lookup.querySelector('[data-ro-results]');
    const statusEl = lookup.querySelector('[data-ro-status]');
    const provInput = lookup.querySelector('[data-ro-province]');
    const distInput = lookup.querySelector('[data-ro-district]');
    const subInput = lookup.querySelector('[data-ro-subdistrict]');
    const destIdInput = lookup.querySelector('[data-ro-dest-id]');
    const citySelect = form.querySelector('[data-ro-city]');
    const postalInput = form.querySelector('[data-ro-postal]');
    let roTimer = null;

    const initialCity = citySelect?.getAttribute('data-initial-city');
    if (initialCity) {
      ensureCityOption(citySelect, initialCity);
    }

    qInput?.addEventListener('input', () => {
      const q = (qInput.value || '').trim();
      clearTimeout(roTimer);
      if (q.length < 2) {
        if (resultsBox) {
          resultsBox.hidden = true;
          resultsBox.innerHTML = '';
        }
        return;
      }
      roTimer = setTimeout(async () => {
        try {
          const res = await fetch(`${apiUrl}?q=${encodeURIComponent(q)}`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await res.json();
          const items = data.results || [];
          if (!resultsBox) return;
          if (!items.length) {
            resultsBox.innerHTML = '<div class="ro-empty">Lokasi tidak ditemukan. Coba nama kota atau kode pos lain.</div>';
            resultsBox.hidden = false;
            return;
          }
          resultsBox.innerHTML = '';
          items.forEach((item) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ro-item';
            const srcLabel = item.source === 'rajaongkir' ? 'RajaOngkir' : 'Katalog';
            btn.innerHTML = `<span>${escapeHtml(item.label)}</span><small>${srcLabel}</small>`;
            btn.addEventListener('click', () => {
              ensureCityOption(citySelect, item.city);
              if (postalInput && item.postal_code) postalInput.value = item.postal_code;
              if (provInput) provInput.value = item.province || '';
              if (distInput) distInput.value = item.district || '';
              if (subInput) subInput.value = item.subdistrict || '';
              if (destIdInput) destIdInput.value = item.destination_id || '';
              qInput.value = item.label;
              if (statusEl) {
                statusEl.textContent = `Terpilih: ${item.city}${item.province ? ', ' + item.province : ''}${item.postal_code ? ' · ' + item.postal_code : ''}`;
              }
              resultsBox.hidden = true;
            });
            resultsBox.appendChild(btn);
          });
          resultsBox.hidden = false;
        } catch {
          if (resultsBox) resultsBox.hidden = true;
        }
      }, 250);
    });

    citySelect?.addEventListener('change', () => {
      const opt = citySelect.selectedOptions?.[0];
      if (opt && opt.dataset.postal && postalInput && !postalInput.value) {
        postalInput.placeholder = `Contoh: ${opt.dataset.postal}`;
      }
      if (destIdInput) destIdInput.value = '';
      if (distInput) distInput.value = '';
      if (subInput) subInput.value = '';
      if (provInput) provInput.value = '';
      if (statusEl && citySelect.value) {
        statusEl.textContent = `Kota terpilih: ${citySelect.value}${opt?.dataset.postal ? ' (contoh kode pos ' + opt.dataset.postal + ')' : ''}`;
      }
    });
  });

  /* ---------- Landing: Tiga pilihan (JUAL / DONASI / SIMPAN) ---------- */
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

  /* ---------- Landing: Fase cara kerja ---------- */
  const phaseTabs = [...document.querySelectorAll('[data-phase-tab]')];
  const phasePhoto = document.querySelector('[data-phase-photo]');
  const phaseText = document.querySelector('[data-phase-text]');
  const phaseData = [
    { img: '/static/img/jaket-kulit.jpg', text: 'Foto barangmu dan masukkan ke Lemari Digital. Satu menit per barang.' },
    { img: '/static/img/heels-chrome.jpg', text: 'Saat lama tak dipakai, sistem memberi pengingat: jual, donasi, atau simpan.' },
    { img: '/static/img/tas-kulit.jpg', text: 'Salurkan ke pembeli baru atau lembaga mitra yang benar-benar membutuhkan.' },
  ];
  if (phaseTabs.length) {
    const PHASE_MS = 2500;
    const PHASE_FADE_MS = 200; // sama dengan transition di umum.css
    const phaseSection = phaseTabs[0].closest('.phases');
    let phaseNow = 0;
    let phaseTimer = null;
    let phaseFade = null;
    // Gambar dimuat lebih dulu supaya tidak berkedip saat pertama kali berganti.
    phaseData.forEach(({ img }) => { new Image().src = img; });
    const showPhase = (idx) => {
      phaseNow = idx;
      phaseTabs.forEach((t, i) => {
        const active = i === idx;
        t.setAttribute('aria-selected', String(active));
        t.classList.toggle('btn--dark', active);
        t.classList.toggle('btn--outline', !active);
      });
      // Pudar keluar dulu, ganti isinya, lalu pudar masuk.
      phaseSection.classList.add('is-switching');
      clearTimeout(phaseFade);
      phaseFade = setTimeout(() => {
        const item = phaseData[idx];
        if (item && phasePhoto) {
          phasePhoto.style.setProperty('--img', `url(${item.img})`);
        }
        if (item && phaseText) {
          phaseText.textContent = item.text;
        }
        phaseSection.classList.remove('is-switching');
      }, PHASE_FADE_MS);
    };
    // Berganti sendiri, kecuali pengguna meminta gerakan dikurangi di pengaturan perangkatnya.
    const startPhaseTimer = () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      clearInterval(phaseTimer);
      phaseTimer = setInterval(() => showPhase((phaseNow + 1) % phaseTabs.length), PHASE_MS);
    };
    phaseTabs.forEach((tab, idx) => {
      tab.addEventListener('click', (e) => {
        e.preventDefault();
        showPhase(idx);
        startPhaseTimer(); // dipencet tetap bisa; hitungannya mulai lagi dari langkah itu
      });
    });
    startPhaseTimer();
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

  /* ---------- Konfirmasi keluar (#keluar overlay / <dialog>) ---------- */
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

  /* ---------- Profil & Alamat AJAX (fetch + JSON) ---------- */
  const profileRoot = document.querySelector('[data-api-profile-url]');
  const modalProfil = document.getElementById('modal-profil');
  const modalAlamat = document.getElementById('modal-alamat');
  const modalPassword = document.getElementById('modal-password');
  const modalDeleteAccount = document.getElementById('hapus-akun');

  const openModal = (modalEl) => {
    if (!modalEl) return;
    modalEl.classList.add('is-open');
    const firstInput = modalEl.querySelector('input:not([type="hidden"]):not(.visually-hidden), textarea, select');
    firstInput?.focus();
  };

  const closeModal = (modalEl) => {
    if (!modalEl) return;
    modalEl.classList.remove('is-open');
    if (window.location.hash === `#${modalEl.id}`) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  };

  document.querySelectorAll('[data-modal-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-modal-close');
      const targetModal = document.getElementById(targetId);
      closeModal(targetModal);
    });
  });

  [modalProfil, modalAlamat, modalPassword, modalDeleteAccount].forEach((modalEl) => {
    modalEl?.addEventListener('click', (e) => {
      if (e.target === modalEl) {
        closeModal(modalEl);
      }
    });
  });

  if (profileRoot) {
    const editProfileFallbackUrl = profileRoot.getAttribute('data-edit-profile-url') || '/profil/edit/';
    const addressListEl = document.querySelector('[data-address-list]');
    const addressCountEl = document.querySelector('[data-address-count]');
    const formProfil = document.getElementById('form-ajax-profil');
    const formAlamat = document.getElementById('form-ajax-alamat');
    const addressModalTitle = document.querySelector('[data-address-modal-title]');
    const profileErrorBox = document.querySelector('[data-profile-modal-error]');
    const profileErrorText = document.querySelector('[data-profile-modal-error-text]');
    const addressErrorBox = document.querySelector('[data-address-modal-error]');
    const addressErrorText = document.querySelector('[data-address-modal-error-text]');
    const addressFiltersWrap = document.querySelector('[data-address-filters]');
    const addressSearchInput = document.querySelector('[data-address-search]');

    let currentAddressFilter = 'ALL';
    let currentAddressQuery = '';

    const renderAddresses = (addresses) => {
      if (!addressListEl) return;
      if (addressCountEl) {
        addressCountEl.textContent = addresses.length ? `${addresses.length} alamat` : '0 alamat';
      }
      if (!addresses.length) {
        const isFiltered = (currentAddressFilter && currentAddressFilter !== 'ALL') || Boolean(currentAddressQuery);
        const emptyMsg = isFiltered
          ? 'Tidak ada alamat yang cocok dengan filter saat ini.'
          : 'Alamat belum diisi';
        addressListEl.innerHTML = `
          <div class="list-row" data-address-empty>
            <span class="profile__key text-muted">-</span>
            <span class="spacer">${escapeHtml(emptyMsg)}</span>
            <a class="text-sm" href="${escapeHtml(editProfileFallbackUrl)}?mode=add" data-address-add>Tambah alamat</a>
          </div>
        `;
        return;
      }

      addressListEl.innerHTML = addresses.map((addr) => {
        const keyLabel = `${escapeHtml(addr.label_display)}${addr.is_primary ? ' · utama' : ''}`;
        const ongkirBadge = addr.rajaongkir_city_id
          ? `<span class="mono" title="ID Kota RajaOngkir"> · #${escapeHtml(addr.rajaongkir_city_id)}</span>`
          : '';
        const primaryBtn = !addr.is_primary
          ? `<button class="link-btn text-sm text-soft" type="button" data-address-set-primary="${addr.id}">Utama</button>`
          : '';

        return `
          <div class="list-row" data-address-row="${addr.id}">
            <span class="profile__key">${keyLabel}</span>
            <span class="spacer">
              <span data-address-text>${escapeHtml(addr.formatted_address)}</span>${ongkirBadge}
            </span>
            <span class="row">
              ${primaryBtn}
              <a class="text-sm"
                 href="${escapeHtml(editProfileFallbackUrl)}?address_id=${addr.id}"
                 data-address-edit="${addr.id}"
                 data-label="${escapeHtml(addr.label)}"
                 data-recipient-name="${escapeHtml(addr.recipient_name)}"
                 data-phone-number="${escapeHtml(addr.phone_number)}"
                 data-address="${escapeHtml(addr.address)}"
                 data-subdistrict="${escapeHtml(addr.subdistrict || '')}"
                 data-district="${escapeHtml(addr.district || '')}"
                 data-city="${escapeHtml(addr.city)}"
                 data-province="${escapeHtml(addr.province || '')}"
                 data-rajaongkir-destination-id="${escapeHtml(addr.rajaongkir_destination_id || '')}"
                 data-postal-code="${escapeHtml(addr.postal_code)}"
                 data-is-primary="${addr.is_primary ? 'true' : 'false'}">Ubah</a>
              <button class="link-btn text-sm text-muted" type="button" data-address-delete="${addr.id}">Hapus</button>
            </span>
          </div>
        `;
      }).join('');
    };

    const resetRajaOngkirModalFields = () => {
      if (!formAlamat) return;
      const qEl = formAlamat.querySelector('[data-ro-query]');
      const rEl = formAlamat.querySelector('[data-ro-results]');
      const sEl = formAlamat.querySelector('[data-ro-status]');
      if (qEl) qEl.value = '';
      if (rEl) {
        rEl.hidden = true;
        rEl.innerHTML = '';
      }
      if (sEl) sEl.textContent = 'Ketik nama daerah atau kode pos 5 digit untuk mengisi kota & kode pos otomatis.';
    };

    const openAddressModalForAdd = (e) => {
      if (e) e.preventDefault();
      if (!formAlamat || !modalAlamat) return;
      if (addressErrorBox) addressErrorBox.hidden = true;
      if (addressModalTitle) addressModalTitle.innerHTML = 'Tambah <em>alamat</em>';
      formAlamat.querySelector('input[name="address_id"]').value = '';
      const defaultRadio = formAlamat.querySelector('input[name="label"][value="RUMAH"]');
      if (defaultRadio) defaultRadio.checked = true;
      const recipEl = formAlamat.querySelector('input[name="recipient_name"]');
      if (recipEl) recipEl.value = recipEl.defaultValue;
      const phoneEl = formAlamat.querySelector('input[name="phone_number"]');
      if (phoneEl) phoneEl.value = phoneEl.defaultValue;
      formAlamat.querySelector('textarea[name="address"]').value = '';
      formAlamat.querySelector('select[name="city"]').value = '';
      formAlamat.querySelector('input[name="postal_code"]').value = '';
      ['province', 'district', 'subdistrict', 'rajaongkir_destination_id'].forEach((name) => {
        const el = formAlamat.querySelector(`input[name="${name}"]`);
        if (el) el.value = '';
      });
      formAlamat.querySelector('input[name="is_primary"]').checked = true;
      resetRajaOngkirModalFields();
      openModal(modalAlamat);
    };

    const openAddressModalForEdit = (triggerEl, e) => {
      if (e) e.preventDefault();
      if (!formAlamat || !modalAlamat || !triggerEl) return;
      if (addressErrorBox) addressErrorBox.hidden = true;
      if (addressModalTitle) addressModalTitle.innerHTML = 'Ubah <em>alamat</em>';

      const id = triggerEl.getAttribute('data-address-edit') || '';
      const label = triggerEl.getAttribute('data-label') || 'RUMAH';
      const recipientName = triggerEl.getAttribute('data-recipient-name') || '';
      const phoneNumber = triggerEl.getAttribute('data-phone-number') || '';
      const addressText = triggerEl.getAttribute('data-address') || '';
      const city = triggerEl.getAttribute('data-city') || '';
      const province = triggerEl.getAttribute('data-province') || '';
      const district = triggerEl.getAttribute('data-district') || '';
      const subdistrict = triggerEl.getAttribute('data-subdistrict') || '';
      const roDestId = triggerEl.getAttribute('data-rajaongkir-destination-id') || '';
      const postalCode = triggerEl.getAttribute('data-postal-code') || '';
      const isPrimary = triggerEl.getAttribute('data-is-primary') === 'true';

      formAlamat.querySelector('input[name="address_id"]').value = id;
      const radio = formAlamat.querySelector(`input[name="label"][value="${label}"]`);
      if (radio) radio.checked = true;
      formAlamat.querySelector('input[name="recipient_name"]').value = recipientName;
      formAlamat.querySelector('input[name="phone_number"]').value = phoneNumber;
      formAlamat.querySelector('textarea[name="address"]').value = addressText;
      ensureCityOption(formAlamat.querySelector('select[name="city"]'), city);
      formAlamat.querySelector('input[name="postal_code"]').value = postalCode;
      const setHidden = (name, val) => {
        const el = formAlamat.querySelector(`input[name="${name}"]`);
        if (el) el.value = val;
      };
      setHidden('province', province);
      setHidden('district', district);
      setHidden('subdistrict', subdistrict);
      setHidden('rajaongkir_destination_id', roDestId);
      formAlamat.querySelector('input[name="is_primary"]').checked = isPrimary;
      resetRajaOngkirModalFields();
      openModal(modalAlamat);
    };

    document.querySelectorAll('[data-profile-edit]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        if (!modalProfil) return;
        e.preventDefault();
        if (profileErrorBox) profileErrorBox.hidden = true;
        openModal(modalProfil);
      });
    });

    const fetchAndRenderFilteredAddresses = async () => {
      const apiUrl = profileRoot.getAttribute('data-api-profile-url') || '/api/profile/';
      const params = new URLSearchParams();
      if (currentAddressFilter && currentAddressFilter !== 'ALL') {
        params.set('label', currentAddressFilter);
      }
      if (currentAddressQuery) {
        params.set('q', currentAddressQuery);
      }
      const queryStr = params.toString() ? `?${params.toString()}` : '';
      try {
        const res = await fetch(`${apiUrl}${queryStr}`, {
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
        });
        const data = await res.json();
        if (data.status === 'ok') {
          renderAddresses(data.addresses);
        }
      } catch {
        showToast('Gagal memuat filter alamat.');
      }
    };

    addressFiltersWrap?.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-address-filter]');
      if (!btn) return;
      e.preventDefault();
      currentAddressFilter = (btn.getAttribute('data-address-filter') || 'ALL').toUpperCase();
      addressFiltersWrap.querySelectorAll('[data-address-filter]').forEach((b) => {
        b.setAttribute('aria-pressed', String(b === btn));
      });
      fetchAndRenderFilteredAddresses();
    });

    let addressSearchDebounceTimer = null;
    addressSearchInput?.addEventListener('input', (e) => {
      currentAddressQuery = (e.target.value || '').trim();
      clearTimeout(addressSearchDebounceTimer);
      addressSearchDebounceTimer = setTimeout(() => {
        fetchAndRenderFilteredAddresses();
      }, 250);
    });

    document.querySelectorAll('[data-address-add]').forEach((btn) => {
      btn.addEventListener('click', openAddressModalForAdd);
    });

    addressListEl?.addEventListener('click', async (e) => {
      const addTrigger = e.target.closest('[data-address-add]');
      if (addTrigger) {
        openAddressModalForAdd(e);
        return;
      }

      const editTrigger = e.target.closest('[data-address-edit]');
      if (editTrigger) {
        openAddressModalForEdit(editTrigger, e);
        return;
      }

      const setPrimaryBtn = e.target.closest('[data-address-set-primary]');
      if (setPrimaryBtn) {
        e.preventDefault();
        const addrId = setPrimaryBtn.getAttribute('data-address-set-primary');
        try {
          const res = await fetch(`/api/addresses/${addrId}/set-primary/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCsrfToken(),
              'X-Requested-With': 'XMLHttpRequest',
            },
          });
          const data = await res.json();
          if (data.status === 'ok') {
            await fetchAndRenderFilteredAddresses();
            showToast(data.message || 'Alamat utama diperbarui.');
          }
        } catch {
          showToast('Gagal mengubah alamat utama.');
        }
        return;
      }

      const deleteBtn = e.target.closest('[data-address-delete]');
      if (deleteBtn) {
        e.preventDefault();
        const addrId = deleteBtn.getAttribute('data-address-delete');
        try {
          const res = await fetch(`/api/addresses/${addrId}/delete/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCsrfToken(),
              'X-Requested-With': 'XMLHttpRequest',
            },
          });
          const data = await res.json();
          if (data.status === 'ok') {
            await fetchAndRenderFilteredAddresses();
            showToast(data.message || 'Alamat dihapus.');
          }
        } catch {
          showToast('Gagal menghapus alamat.');
        }
      }
    });

    formProfil?.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (profileErrorBox) profileErrorBox.hidden = true;
      const updateUrl = profileRoot.getAttribute('data-api-profile-update-url');
      const formData = new FormData(formProfil);
      try {
        const res = await fetch(updateUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: formData,
        });
        const data = await res.json();
        if (!res.ok || data.status !== 'ok') {
          const firstErr = data.errors
            ? Object.values(data.errors).flat()[0]
            : 'Periksa kembali data yang dimasukkan.';
          if (profileErrorBox && profileErrorText) {
            profileErrorText.textContent = firstErr;
            profileErrorBox.hidden = false;
          }
          return;
        }
        document.querySelectorAll('[data-user-fullname]').forEach((el) => {
          el.textContent = data.user.full_name;
        });
        document.querySelectorAll('[data-user-firstname]').forEach((el) => {
          el.textContent = data.user.first_name;
        });
        document.querySelectorAll('[data-user-email]').forEach((el) => {
          el.textContent = data.user.email || 'Belum diisi';
        });
        document.querySelectorAll('[data-user-phone]').forEach((el) => {
          el.textContent = data.user.phone_number || 'Belum diisi';
        });
        closeModal(modalProfil);
        showToast(data.message || 'Data diri berhasil diperbarui.');
      } catch {
        if (profileErrorBox && profileErrorText) {
          profileErrorText.textContent = 'Terjadi kesalahan jaringan. Coba lagi.';
          profileErrorBox.hidden = false;
        }
      }
    });

    formAlamat?.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (addressErrorBox) addressErrorBox.hidden = true;
      const addrId = formAlamat.querySelector('input[name="address_id"]').value;
      const targetUrl = addrId
        ? `/api/addresses/${addrId}/edit/`
        : profileRoot.getAttribute('data-api-address-add-url');
      const formData = new FormData(formAlamat);

      try {
        const res = await fetch(targetUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: formData,
        });
        const data = await res.json();
        if (!res.ok || data.status !== 'ok') {
          const firstErr = data.errors
            ? Object.values(data.errors).flat()[0]
            : 'Periksa kembali alamat yang dimasukkan.';
          if (addressErrorBox && addressErrorText) {
            addressErrorText.textContent = firstErr;
            addressErrorBox.hidden = false;
          }
          return;
        }
        closeModal(modalAlamat);
        const nextUrl = profileRoot.getAttribute('data-next-url') || '';
        if (nextUrl) {
          showToast('Alamat disimpan. Kembali ke checkout…');
          const savedId = data.address?.id;
          const sep = nextUrl.includes('?') ? '&' : '?';
          window.location.href = savedId ? `${nextUrl}${sep}address_id=${encodeURIComponent(savedId)}` : nextUrl;
          return;
        }
        showToast(data.message || 'Alamat berhasil disimpan.');
        await fetchAndRenderFilteredAddresses();
      } catch {
        if (addressErrorBox && addressErrorText) {
          addressErrorText.textContent = 'Terjadi kesalahan jaringan. Coba lagi.';
          addressErrorBox.hidden = false;
        }
      }
    });

    // Buka otomatis modal Tambah/Ubah Alamat bila datang dari Checkout (+ Tambah alamat / Ubah).
    const shouldOpenAddAddress = profileRoot.getAttribute('data-open-add-address') === 'true';
    const editAddrIdParam = profileRoot.getAttribute('data-edit-address-id') || '';
    if (shouldOpenAddAddress) {
      openAddressModalForAdd();
    } else if (editAddrIdParam) {
      const editTrigger = document.querySelector(`[data-address-edit="${editAddrIdParam}"]`);
      if (editTrigger) {
        openAddressModalForEdit(editTrigger);
      }
    }

    /* ---------- Auto-save Preferensi via AJAX ---------- */
    const prefUrl = profileRoot.getAttribute('data-api-preferences-url');
    const prefSummaryEl = document.querySelector('[data-pref-summary]');
    const savePreferences = async (sourceToggle) => {
      if (!prefUrl) return;
      const sizes = [...document.querySelectorAll('[data-pref-size]:checked')].map(el => el.value);
      const categories = [...document.querySelectorAll('[data-pref-category]:checked')].map(el => el.value);
      const reminderDesktop = document.querySelector('[data-pref-reminder]');
      const reminderMobile = document.querySelector('[data-pref-reminder-mobile]');
      const emailDesktop = document.querySelector('[data-pref-email]');
      const emailMobile = document.querySelector('[data-pref-email-mobile]');

      let reminder = reminderDesktop ? reminderDesktop.checked : true;
      let emailNewsletter = emailDesktop ? emailDesktop.checked : false;

      if (sourceToggle === reminderMobile && reminderDesktop) {
        reminder = reminderMobile.checked;
        reminderDesktop.checked = reminder;
      } else if (sourceToggle === reminderDesktop && reminderMobile) {
        reminderMobile.checked = reminder;
      }

      if (sourceToggle === emailMobile && emailDesktop) {
        emailNewsletter = emailMobile.checked;
        emailDesktop.checked = emailNewsletter;
      } else if (sourceToggle === emailDesktop && emailMobile) {
        emailMobile.checked = emailNewsletter;
      }

      try {
        const res = await fetch(prefUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            sizes,
            categories,
            reminder,
            email_newsletter: emailNewsletter,
          }),
        });
        const data = await res.json();
        if (data.status === 'ok') {
          if (prefSummaryEl) {
            const sizeStr = data.preferences.sizes.length ? data.preferences.sizes.join(', ') : '-';
            const catStr = data.preferences.categories.length ? data.preferences.categories.join(', ') : '-';
            prefSummaryEl.textContent = `${sizeStr} · ${catStr}`;
          }
          showToast(data.message || 'Preferensi disimpan.');
        }
      } catch {
        showToast('Gagal menyimpan preferensi.');
      }
    };

    document.querySelectorAll('[data-pref-size], [data-pref-category], [data-pref-reminder], [data-pref-email], [data-pref-reminder-mobile], [data-pref-email-mobile]').forEach((input) => {
      input.addEventListener('change', () => savePreferences(input));
    });
  }

  /* ---------- Keamanan: Kata Sandi, Google OAuth & Hapus Akun via AJAX ---------- */
  const formPassword = document.getElementById('form-ajax-password');
  const passwordErrorBox = document.querySelector('[data-password-modal-error]');
  const passwordErrorText = document.querySelector('[data-password-modal-error-text]');
  const passwordStatusEl = document.querySelector('[data-password-status]');
  const oldPasswordField = document.querySelector('[data-old-password-field]');

  document.querySelectorAll('[data-password-edit]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      if (!modalPassword) return;
      e.preventDefault();
      if (passwordErrorBox) passwordErrorBox.hidden = true;
      formPassword?.reset();
      openModal(modalPassword);
    });
  });

  formPassword?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (passwordErrorBox) passwordErrorBox.hidden = true;
    const passwordUrl = profileRoot?.getAttribute('data-api-password-url') || '/api/security/password/';
    const formData = new FormData(formPassword);

    try {
      const res = await fetch(passwordUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'ok') {
        if (passwordErrorBox && passwordErrorText) {
          passwordErrorText.textContent = data.message || 'Gagal memperbarui kata sandi.';
          passwordErrorBox.hidden = false;
        }
        return;
      }
      if (passwordStatusEl && data.password_status) {
        passwordStatusEl.textContent = data.password_status;
      }
      if (oldPasswordField) {
        oldPasswordField.hidden = false;
      }
      formPassword.reset();
      closeModal(modalPassword);
      showToast(data.message || 'Kata sandi berhasil diperbarui.');
    } catch {
      if (passwordErrorBox && passwordErrorText) {
        passwordErrorText.textContent = 'Terjadi kesalahan jaringan. Coba lagi.';
        passwordErrorBox.hidden = false;
      }
    }
  });

  const googleActionWrap = document.querySelector('[data-google-action-wrap]');
  const googleStatusEl = document.querySelector('[data-google-status]');
  const googleStatusMobileEl = document.querySelector('[data-google-status-mobile]');

  googleActionWrap?.addEventListener('click', async (e) => {
    const disconnectBtn = e.target.closest('[data-google-disconnect]');
    if (!disconnectBtn) return;
    e.preventDefault();
    const disconnectUrl = profileRoot?.getAttribute('data-api-google-disconnect-url') || '/api/security/google/disconnect/';
    try {
      const res = await fetch(disconnectUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'ok') {
        showToast(data.message || 'Gagal memutuskan akun Google.');
        return;
      }
      if (googleStatusEl) {
        googleStatusEl.textContent = 'Belum terhubung';
      }
      if (googleStatusMobileEl) {
        googleStatusMobileEl.textContent = 'Kata sandi';
      }
      const connectUrl = data.connect_url || '/auth/google/?action=connect';
      googleActionWrap.innerHTML = `<a class="text-sm" href="${escapeHtml(connectUrl)}">Hubungkan</a>`;
      showToast(data.message || 'Akun Google berhasil diputuskan.');
    } catch {
      showToast('Gagal memutuskan akun Google.');
    }
  });

  const formDeleteAccount = document.getElementById('form-ajax-delete-account');
  const deleteErrorBox = document.querySelector('[data-delete-modal-error]');
  const deleteErrorText = document.querySelector('[data-delete-modal-error-text]');

  document.querySelectorAll('[data-delete-account-open]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      if (!modalDeleteAccount) return;
      e.preventDefault();
      if (deleteErrorBox) deleteErrorBox.hidden = true;
      formDeleteAccount?.reset();
      openModal(modalDeleteAccount);
    });
  });

  formDeleteAccount?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (deleteErrorBox) deleteErrorBox.hidden = true;
    const deleteUrl = profileRoot?.getAttribute('data-api-delete-account-url') || '/api/security/delete-account/';
    const formData = new FormData(formDeleteAccount);

    try {
      const res = await fetch(deleteUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'ok') {
        if (deleteErrorBox && deleteErrorText) {
          deleteErrorText.textContent = data.message || 'Gagal menghapus akun.';
          deleteErrorBox.hidden = false;
        }
        return;
      }
      window.location.href = data.redirect_url || '/';
    } catch {
      if (deleteErrorBox && deleteErrorText) {
        deleteErrorText.textContent = 'Terjadi kesalahan jaringan. Coba lagi.';
        deleteErrorBox.hidden = false;
      }
    }
  });

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
      [modalProfil, modalAlamat, modalPassword, modalDeleteAccount].forEach((modalEl) => {
        if (modalEl && (modalEl.classList.contains('is-open') || window.location.hash === `#${modalEl.id}`)) {
          closeModal(modalEl);
        }
      });
    }
  });
})();
