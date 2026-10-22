(() => {
    'use strict';
    document.addEventListener('DOMContentLoaded', () => {
        const torneo = document.getElementById('id_torneo');
        if (!torneo) return;
        const fields = ['fase', 'equipo_local', 'equipo_visita', 'equipo']
            .map(name => document.getElementById(`id_${name}`)).filter(Boolean);
        const form = torneo.closest('form');
        const status = document.createElement('p');
        status.setAttribute('role', 'status');
        torneo.parentElement.append(status);
        let controller;
        const base = window.location.pathname.replace(/(?:add\/|\d+\/change\/)$/, '');
        torneo.addEventListener('change', async () => {
            if (controller) controller.abort();
            controller = new AbortController();
            const current = controller;
            fields.forEach(field => {
                field.replaceChildren(new Option('---------', ''));
                field.disabled = true;
                field.dispatchEvent(new Event('change', {bubbles: true}));
            });
            status.textContent = '';
            if (!torneo.value) return;
            status.textContent = 'Cargando opciones del torneo…';
            try {
                const response = await fetch(`${base}opciones-torneo/?torneo=${encodeURIComponent(torneo.value)}`, {
                    signal: current.signal, credentials: 'same-origin', headers: {'Accept': 'application/json'}
                });
                if (!response.ok) throw new Error('No se pudieron cargar las opciones. Vuelve a seleccionar el torneo.');
                const data = await response.json();
                if (controller !== current) return;
                fields.forEach(field => {
                    const options = field.id === 'id_fase' ? data.fases : data.equipos;
                    options.forEach(item => field.add(new Option(item.nombre, item.id)));
                    field.disabled = false;
                });
                status.textContent = data.equipos.length ? '' : 'Este torneo no tiene equipos disponibles. Revisa los equipos por torneo y su país.';
            } catch (error) {
                if (error.name !== 'AbortError') status.textContent = error.message;
            }
        });
        form.addEventListener('submit', event => {
            if (fields.some(field => field.disabled)) {
                event.preventDefault();
                status.textContent = 'Selecciona el torneo y espera a que carguen sus opciones.';
            }
        });
    });
})();
