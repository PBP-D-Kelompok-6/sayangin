/* ==========================================================
   Sayangin — validasi form Login & Register (sisi klien)
   Integrasi backend (mis. mockapi.io) dipasang di onSubmit.
   ========================================================== */
(() => {
  /* ---------- Tampilkan / sembunyikan kata sandi ---------- */
  document.querySelectorAll('[data-toggle-password]').forEach(btn => {
    const input = document.getElementById(btn.dataset.togglePassword);
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(show));
      btn.setAttribute('aria-label', (show ? 'Sembunyikan' : 'Tampilkan') + btn.getAttribute('aria-label').replace(/^(Tampilkan|Sembunyikan)/, ''));
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
        if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) return 'Gunakan kombinasi huruf dan angka.';
      }
      return '';
    },
    confirm: (v, form) => {
      if (!v) return 'Ulangi kata sandi.';
      if (v !== form.elements.password.value) return 'Kata sandi belum sama.';
      return '';
    },
  };

  const validateField = (input, form) => {
    const rule = rules[input.name];
    if (!rule) return true;
    const msg = rule(input.value, form);
    const field = input.closest('.field');
    const err = document.getElementById(`${input.id}-error`);
    field.classList.toggle('is-invalid', !!msg);
    field.classList.toggle('is-valid', !msg && input.value !== '');
    input.setAttribute('aria-invalid', String(!!msg));
    if (err) {
      err.textContent = msg;
      const describedBy = new Set((input.getAttribute('aria-describedby') || '').split(' ').filter(Boolean));
      msg ? describedBy.add(err.id) : describedBy.delete(err.id);
      describedBy.size ? input.setAttribute('aria-describedby', [...describedBy].join(' ')) : input.removeAttribute('aria-describedby');
    }
    return !msg;
  };

  document.querySelectorAll('.auth-form').forEach(form => {
    const inputs = [...form.querySelectorAll('.field__input')];
    const alertBox = form.querySelector('[data-form-alert]');

    inputs.forEach(input => {
      input.addEventListener('blur', () => { if (input.value) validateField(input, form); });
      input.addEventListener('input', () => {
        if (input.closest('.field').classList.contains('is-invalid')) validateField(input, form);
        if (input.name === 'password' && form.elements.confirm?.value) validateField(form.elements.confirm, form);
      });
    });

    form.addEventListener('submit', (e) => {
      alertBox.hidden = true;
      
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
      const label = btn.textContent;
      btn.setAttribute('aria-busy', 'true');
      btn.textContent = 'Memproses…';
    });
  });
})();
