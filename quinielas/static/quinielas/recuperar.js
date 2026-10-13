(() => {
  const params = new URLSearchParams(location.hash.slice(1));
  const uid = params.get('uid');
  const token = params.get('token');
  history.replaceState(null, '', location.pathname);
  const status = document.getElementById('estado');
  const reset = document.getElementById('restablecer');
  const request = document.getElementById('solicitar');
  if (uid && token) {
    reset.hidden = false;
    request.hidden = true;
    const appUrl = document.querySelector('main').dataset.appUrl;
    if (appUrl && appUrl.startsWith('streak://')) {
      const app = document.getElementById('abrir-app');
      const destination = new URL(appUrl);
      destination.searchParams.set('uid', uid);
      destination.searchParams.set('token', token);
      app.href = destination.href;
      app.hidden = false;
    }
  }
  async function submit(form, endpoint, payload) {
    const button = form.querySelector('button');
    button.disabled = true;
    status.textContent = '';
    status.className = '';
    try {
      const response = await fetch(endpoint, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload), credentials: 'same-origin', cache: 'no-store'
      });
      const data = await response.json();
      if (!response.ok) {
        status.className = 'error';
        const details = data.error?.detalles;
        status.textContent = details ? Object.values(details).flat().join(' ') : (data.error?.mensaje || 'No se pudo completar la solicitud.');
        return;
      }
      status.textContent = data.detail || 'Solicitud completada.';
      form.reset();
      if (form === reset) {
        form.hidden = true;
        document.getElementById('abrir-app').hidden = true;
      }
    } catch (_) {
      status.className = 'error';
      status.textContent = 'No se pudo conectar. Intenta nuevamente.';
    } finally { button.disabled = false; }
  }
  request.addEventListener('submit', event => {
    event.preventDefault();
    submit(request, '/api/auth/recuperar/', {email: document.getElementById('email').value});
  });
  reset.addEventListener('submit', event => {
    event.preventDefault();
    const password = document.getElementById('password').value;
    if (password !== document.getElementById('confirmacion').value) {
      status.className = 'error';
      status.textContent = 'Las contrasenas no coinciden.';
      return;
    }
    submit(reset, '/api/auth/restablecer/', {uid, token, new_password: password});
  });
})();
