/* ==========================================================
   Sayangin — validasi form Login & Register (sisi klien)
   Integrasi backend (mis. mockapi.io) dipasang di onSubmit.
   ========================================================== */
(() => {
  /* ---------- Tampilkan / sembunyikan kata sandi ---------- */
  document.querySelectorAll('[data-toggle-password]').forEach(btn => {
    const input = document.getElementById(btn.dataset.togglePassword);
    if (!input) return;
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(show));
      if (!btn.querySelector('svg')) {
        btn.textContent = show ? 'Sembunyikan' : 'Tampilkan';
      }
      if (btn.hasAttribute('aria-label')) {
        btn.setAttribute('aria-label', (show ? 'Sembunyikan' : 'Tampilkan') + btn.getAttribute('aria-label').replace(/^(Tampilkan|Sembunyikan)/, ''));
      }
    });
  });

  /* ---------- Aturan validasi ---------- */
  const rules = {
    identity: v => !v.trim() ? 'Isi email atau username kamu.' : '',
    username: v => {
      if (!v.trim()) return 'Isi nama pengguna.';
      if (v.length < 3) return 'Nama pengguna minimal 3 karakter.';
      if (!/^[A-Za-z0-9._]+$/.test(v)) return 'Gunakan huruf, angka, titik, atau garis bawah saja.';
      return '';
    },
    email: v => {
      if (!v.trim()) return 'Isi alamat email.';
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return 'Format email belum benar.';
      return '';
    },
    password: (v, form) => {
      if (!v) return 'Isi kata sandi.';
      if (form.id === 'register-form') {
        if (v.length < 8) return 'Kata sandi minimal 8 karakter.';
      }
      return '';
    },
    confirm: (v, form) => {
      if (!v) return 'Ulangi kata sandi.';
      if (v !== form.elements.password.value) return 'Kata sandi belum sama.';
      return '';
    },
  };

  const renderFieldError = (err, msg) => {
    if (!err) return;
    if (msg) {
      err.innerHTML = `<span class="alert-icon alert-icon--sm" aria-hidden="true">!</span><span></span>`;
      err.querySelector('span:last-child').textContent = msg;
      err.hidden = false;
    } else {
      err.innerHTML = '';
      err.hidden = true;
    }
  };

  const validateField = (input, form) => {
    const rule = rules[input.name];
    if (!rule) return true;
    const msg = rule(input.value, form);
    const field = input.closest('.field');
    const err = document.getElementById(`${input.id}-error`);
    if (field) {
      field.classList.toggle('is-invalid', !!msg);
      field.classList.toggle('is-valid', !msg && input.value !== '');
    }
    if (msg) {
      input.setAttribute('aria-invalid', 'true');
    } else {
      input.removeAttribute('aria-invalid');
    }
    if (err) {
      renderFieldError(err, msg);
      const describedBy = new Set((input.getAttribute('aria-describedby') || '').split(' ').filter(Boolean));
      msg ? describedBy.add(err.id) : describedBy.delete(err.id);
      describedBy.size ? input.setAttribute('aria-describedby', [...describedBy].join(' ')) : input.removeAttribute('aria-describedby');
    }
    return !msg;
  };

  document.querySelectorAll('.auth-form').forEach(form => {
    const inputs = [...form.querySelectorAll('.input, .field__input')];
    const alertBox = form.querySelector('[data-form-alert]');

    inputs.forEach(input => {
      input.addEventListener('blur', () => { if (input.value) validateField(input, form); });
      input.addEventListener('input', () => {
        if (input.getAttribute('aria-invalid') === 'true' || input.closest('.field')?.classList.contains('is-invalid')) {
          validateField(input, form);
        }
        if (input.name === 'password' && form.elements.confirm?.value) validateField(form.elements.confirm, form);
      });
    });

    form.addEventListener('submit', (e) => {
      if (alertBox) alertBox.hidden = true;

      // Run validation checks
      const results = inputs.map(i => validateField(i, form));
      const firstInvalid = inputs[results.indexOf(false)];

      // If there are errors, STOP submission
      if (firstInvalid) {
        e.preventDefault();
        firstInvalid.focus();
        return;
      }

      // IF VALID: Do NOT prevent default.
      // Let the browser send the POST request to Django.
      const btn = form.querySelector('[type="submit"]');
      if (btn) {
        btn.setAttribute('aria-busy', 'true');
        btn.textContent = 'Memproses…';
      }
    });
  });

  /* ---------- Umpan balik unggah dokumen (.dropzone) ---------- */
  document.querySelectorAll('[data-file-input]').forEach(fileInput => {
    const labelSpan = fileInput.closest('.dropzone')?.querySelector('[data-file-label]');
    if (!labelSpan) return;
    fileInput.addEventListener('change', () => {
      const file = fileInput.files?.[0];
      if (file) {
        labelSpan.textContent = `Terpilih: ${file.name}`;
      }
    });
  });
})();