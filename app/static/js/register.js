(() => {
  const page = document.querySelector('[data-register-page]');
  if (!page) return;

  const checkUrl = page.dataset.checkUrl;
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  function paneFor(jenis) {
    return page.querySelector(`[data-pane="${jenis}"]`);
  }

  function activateTab(jenis) {
    page.querySelectorAll('[data-tab]').forEach((tab) => {
      const active = tab.dataset.jenis === jenis;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    page.querySelectorAll('[data-pane]').forEach((pane) => {
      pane.hidden = pane.dataset.jenis !== jenis;
    });
  }

  page.querySelectorAll('[data-tab]').forEach((tab) => {
    tab.addEventListener('click', (event) => {
      event.preventDefault();
      const jenis = tab.dataset.jenis;
      activateTab(jenis);
      history.replaceState(null, '', `${window.location.pathname}?jenis=${jenis}`);
    });
  });

  page.querySelectorAll('[data-pane]').forEach((pane) => {
    const form = pane.querySelector('[data-check-form]');
    const slot = pane.querySelector('[data-identity-slot]');
    const accountForm = pane.querySelector('[data-account-form]');
    const button = pane.querySelector('[data-check-button]');
    const input = form.querySelector('input:not([type="hidden"])');

    input.addEventListener('input', () => {
      button.disabled = input.value.trim().length === 0;
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      button.disabled = true;
      const originalLabel = button.textContent;
      button.textContent = 'Memeriksa...';
      slot.innerHTML = '';
      accountForm.hidden = true;

      try {
        const response = await fetch(checkUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          },
          body: new URLSearchParams(new FormData(form)),
        });
        const html = await response.text();
        slot.innerHTML = html;

        const identifierField = accountForm.querySelector('input[type="hidden"][name="npm"], input[type="hidden"][name="nik"]');
        if (identifierField) identifierField.value = input.value.trim();

        const state = slot.querySelector('[data-identity-state]')?.dataset.identityState;
        if (response.ok && state === 'ok') {
          accountForm.hidden = false;
          const email = accountForm.querySelector('input[name="email"]');
          if (email) email.focus();
        }
      } catch (error) {
        slot.innerHTML = '<div class="alert alert-danger identity-error">Periksa koneksi internet Anda lalu coba lagi.</div>';
      } finally {
        button.textContent = originalLabel;
        button.disabled = input.value.trim().length === 0;
      }
    });
  });
})();
