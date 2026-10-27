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
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  };

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

  const openModal = (modalEl) => {
    if (!modalEl) return;
    modalEl.classList.add('is-open');
    const firstInput = modalEl.querySelector('input:not([type="hidden"]):not(.visually-hidden), textarea, select');
    firstInput?.focus();
  };

  const closeModal = (modalEl) => {
    if (!modalEl) return;
    modalEl.classList.remove('is-open');
  };

  document.querySelectorAll('[data-modal-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-modal-close');
      const targetModal = document.getElementById(targetId);
      closeModal(targetModal);
    });
  });

  [modalProfil, modalAlamat].forEach((modalEl) => {
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

    const renderAddresses = (addresses) => {
      if (!addressListEl) return;
      if (addressCountEl) {
        addressCountEl.textContent = addresses.length ? `${addresses.length} alamat` : 'Belum diisi';
      }
      if (!addresses.length) {
        addressListEl.innerHTML = `
          <div class="list-row" data-address-empty>
            <span class="profile__key">Rumah · utama</span>
            <span class="spacer">Alamat belum diisi</span>
            <a class="text-sm" href="${escapeHtml(editProfileFallbackUrl)}" data-address-add>Isi</a>
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
                 data-city="${escapeHtml(addr.city)}"
                 data-postal-code="${escapeHtml(addr.postal_code)}"
                 data-is-primary="${addr.is_primary ? 'true' : 'false'}">Ubah</a>
              <button class="link-btn text-sm text-muted" type="button" data-address-delete="${addr.id}">Hapus</button>
            </span>
          </div>
        `;
      }).join('');
    };

    const openAddressModalForAdd = (e) => {
      if (e) e.preventDefault();
      if (!formAlamat || !modalAlamat) return;
      if (addressErrorBox) addressErrorBox.hidden = true;
      if (addressModalTitle) addressModalTitle.innerHTML = 'Tambah <em>alamat</em>';
      formAlamat.querySelector('input[name="address_id"]').value = '';
      const defaultRadio = formAlamat.querySelector('input[name="label"][value="RUMAH"]');
      if (defaultRadio) defaultRadio.checked = true;
      formAlamat.querySelector('textarea[name="address"]').value = '';
      formAlamat.querySelector('select[name="city"]').value = '';
      formAlamat.querySelector('input[name="postal_code"]').value = '';
      formAlamat.querySelector('input[name="is_primary"]').checked = true;
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
      const postalCode = triggerEl.getAttribute('data-postal-code') || '';
      const isPrimary = triggerEl.getAttribute('data-is-primary') === 'true';

      formAlamat.querySelector('input[name="address_id"]').value = id;
      const radio = formAlamat.querySelector(`input[name="label"][value="${label}"]`);
      if (radio) radio.checked = true;
      formAlamat.querySelector('input[name="recipient_name"]').value = recipientName;
      formAlamat.querySelector('input[name="phone_number"]').value = phoneNumber;
      formAlamat.querySelector('textarea[name="address"]').value = addressText;
      formAlamat.querySelector('select[name="city"]').value = city;
      formAlamat.querySelector('input[name="postal_code"]').value = postalCode;
      formAlamat.querySelector('input[name="is_primary"]').checked = isPrimary;
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
            renderAddresses(data.addresses);
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
            renderAddresses(data.addresses);
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
        renderAddresses(data.addresses);
        closeModal(modalAlamat);
        showToast(data.message || 'Alamat berhasil disimpan.');
      } catch {
        if (addressErrorBox && addressErrorText) {
          addressErrorText.textContent = 'Terjadi kesalahan jaringan. Coba lagi.';
          addressErrorBox.hidden = false;
        }
      }
    });

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
      if (modalProfil && modalProfil.classList.contains('is-open')) {
        closeModal(modalProfil);
      }
      if (modalAlamat && modalAlamat.classList.contains('is-open')) {
        closeModal(modalAlamat);
      }
    }
  });
})();
