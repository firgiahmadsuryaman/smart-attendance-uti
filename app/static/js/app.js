(function () {
  const toggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.addEventListener('click', (event) => {
      if (window.innerWidth <= 900 && sidebar.classList.contains('open') &&
          !sidebar.contains(event.target) && !toggle.contains(event.target)) {
        sidebar.classList.remove('open');
      }
    });
  }
  document.querySelectorAll('.toggle-password').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.target);
      if (!input) return;
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      button.innerHTML = showing ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
    });
  });
  document.querySelectorAll('[data-confirm]').forEach((button) => {
    button.addEventListener('click', (event) => {
      if (!window.confirm(button.dataset.confirm || 'Lanjutkan tindakan ini?')) event.preventDefault();
    });
  });
})();
