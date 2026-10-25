'use strict';
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const main = $('#contenido'), modal = $('#modal');
  const state = {user: null, admin: false, csrf: '', tournaments: [], countries: [], pools: [], matches: [], version: 0};
  let toastTimer;
  const paths = {
    home: '<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
    trophy: '<path d="M7 3h10v6a5 5 0 0 1-10 0zM12 14v6M8 21h8M7 5H3v3a4 4 0 0 0 4 4M17 5h4v3a4 4 0 0 1-4 4"/>',
    group: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v2"/>',
    ball: '<circle cx="12" cy="12" r="9"/><path d="m12 8 4 3-1 5H9l-1-5zM12 3v5M21 10l-5 1M18 19l-3-3M6 19l3-3M3 10l5 1"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    star: '<path d="m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z"/>',
    shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    plus: '<path d="M12 4v16M4 12h16"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    chart: '<path d="M4 20V10m8 10V4m8 16v-7"/>',
    logout: '<path d="M9 4H4v16h5m5-13 5 5-5 5m-5-5h10"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v12h5"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
  };
  const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.ball}</svg>`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const initials = name => esc(String(name || 'ST').split(/\s+/).map(word => word[0]).slice(0, 2).join('').toUpperCase());
  const pretty = value => ({ACTIVO: 'Activo', FINALIZADO: 'Finalizado', BORRADOR: 'Borrador', PROGRAMADO: 'Por jugar', EN_JUEGO: 'En juego', SUSPENDIDO: 'Suspendido', CANCELADO: 'Cancelado', LIGA: 'Liga', COPA: 'Copa', GRUPOS: 'Grupos', ELIMINATORIA: 'Eliminatoria', COMPLETADO: 'Completado', PENDIENTE: 'Pendiente', FALLIDO: 'Fallido', REEMBOLSADO: 'Reembolsado'}[value] || value || '—');
  const date = value => value ? new Intl.DateTimeFormat('es-GT', {day: 'numeric', month: 'short'}).format(new Date(value)) : 'Por definir';
  const time = value => value ? new Intl.DateTimeFormat('es-GT', {hour: '2-digit', minute: '2-digit'}).format(new Date(value)) : '—';
  const badge = value => `<span class="badge ${esc(value)}">${esc(pretty(value))}</span>`;
  function imageURL(value) {
    if (!value) return '';
    try { const url = new URL(value, location.origin); return url.origin === location.origin && url.pathname.startsWith('/media/') ? esc(url.href) : ''; } catch { return ''; }
  }
  function avatar(user, large = false) {
    const url = imageURL(user?.foto);
    return url ? `<img class="avatar${large ? ' large' : ''}" src="${url}" alt="">` : `<span class="avatar${large ? ' large' : ''}">${initials(user?.username)}</span>`;
  }
  function team(item, away = false) {
    const url = imageURL(item?.escudo);
    return `<span class="team${away ? ' away' : ''}">${url ? `<img src="${url}" alt="" loading="lazy">` : `<span class="team-mark">${initials(item?.nombre)}</span>`}<span>${esc(item?.nombre || 'Equipo por definir')}</span></span>`;
  }
  function flatten(value) {
    if (!value) return '';
    if (Array.isArray(value)) return value.map(flatten).join('\n');
    if (typeof value === 'object') return Object.entries(value).map(([key, val]) => `${key === 'non_field_errors' ? '' : `${key}: `}${flatten(val)}`).join('\n');
    return String(value);
  }
  async function api(path, {method = 'GET', data, signal} = {}) {
    const headers = {Accept: 'application/json'};
    if (method !== 'GET') headers['X-CSRFToken'] = state.csrf;
    if (data && !(data instanceof FormData)) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {method, headers, credentials: 'same-origin', signal,
      body: data instanceof FormData ? data : data ? JSON.stringify(data) : undefined});
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error([body?.error?.mensaje || body?.detail || 'No pudimos completar la solicitud. Inténtalo de nuevo.', flatten(body?.error?.detalles)].filter(Boolean).join('\n'));
      error.status = response.status; error.code = body?.error?.codigo; error.details = body?.error?.detalles;
      if (response.status === 401 && state.user) { state.user = null; state.admin = false; state.pools = []; shell(); }
      throw error;
    }
    return body;
  }
  function toast(message) {
    const target = $('#toast'); target.textContent = message; target.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { target.hidden = true; }, 5000);
  }
  function title(heading, subtitle, actions = '') {
    return `<div class="page-heading"><div><h1>${esc(heading)}</h1><p>${esc(subtitle)}</p></div>${actions ? `<div class="actions">${actions}</div>` : ''}</div>`;
  }
  const btn = (label, action, type = '', symbol = '') => `<button type="button" class="btn ${type}" data-action="${action}">${symbol ? icon(symbol) : ''}${label}</button>`;
  const link = (label, href, type = '') => `<a class="btn ${type}" href="${href}">${label}</a>`;
  const empty = (heading, text, actions = '', symbol = 'trophy') => `<div class="empty">${icon(symbol)}<h3>${esc(heading)}</h3><p>${esc(text)}</p>${actions ? `<div class="actions">${actions}</div>` : ''}</div>`;
  const rules = () => `<div class="panel"><div class="panel-head"><h3>Cada acierto suma</h3>${icon('chart')}</div><div class="rule-row"><span>Marcador exacto</span><b>+5 pts</b></div><div class="rule-row"><span>Resultado + diferencia</span><b>+4 pts</b></div><div class="rule-row"><span>Resultado correcto</span><b>+3 pts</b></div><p class="note">El pronóstico cierra 5 minutos antes del partido. Cuenta el tiempo reglamentario.</p></div>`;
  function shell() {
    const route = location.hash.slice(1).split('/')[0] || 'inicio';
    const nav = [['inicio', 'home', 'Inicio'], ['quinielas', 'group', 'Mis quinielas'], ['torneos', 'trophy', 'Torneos'], ['equipos', 'ball', 'Equipos'], ['perfil', 'user', 'Mi perfil'], ['planes', 'star', 'Plan y pagos']];
    if (state.admin) nav.push(['administracion', 'shield', 'Administración']);
    $('#navigation').innerHTML = nav.map(([name, symbol, label], i) => `${i === 4 ? '<div class="nav-divider"></div>' : ''}<a href="#${name}" class="nav-link${route === name || (route === 'quiniela' && name === 'quinielas') || (route === 'torneo' && name === 'torneos') ? ' active' : ''}" aria-label="${label}" ${route === name ? 'aria-current="page"' : ''}>${icon(symbol)}<span>${label}</span>${name === 'quinielas' && state.pools.length ? `<span class="nav-badge">${state.pools.length}</span>` : ''}</a>`).join('');
    $('#page-label').textContent = nav.find(([name]) => name === route)?.[2] || 'Centro de juego';
    $('#today').textContent = new Intl.DateTimeFormat('es-GT', {weekday: 'long', day: 'numeric', month: 'long'}).format(new Date());
    $('#account-actions').innerHTML = state.user ? `<div class="account"><a class="account" href="#perfil">${avatar(state.user)}<span class="account-name">${esc(state.user.first_name || state.user.username)}<small>${state.user.es_pro ? 'Jugador PRO' : 'Jugador STREAK'}</small></span></a><button class="icon-button" data-action="logout" aria-label="Cerrar sesión">${icon('logout')}</button></div>` : `<div class="actions">${btn('Iniciar sesión', 'login', 'secondary')}${btn('Crear cuenta', 'register')}</div>`;
  }
  function openDialog(content) { $('#modal-body').innerHTML = content; if (!modal.open) modal.showModal(); }
  function requireUser() {
    if (!state.user) { authDialog('login'); return false; }
    if (state.user.pass_temporal_flag) { modal.close(); location.hash = 'perfil'; toast('Primero cambia tu contraseña temporal.'); return false; }
    return true;
  }
  const field = (name, label, type = 'text', attrs = '') => `<label>${label}<input name="${name}" type="${type}" ${attrs}></label>`;
  function authDialog(mode) {
    const login = mode === 'login', recover = mode === 'recover';
    openDialog(`<span class="eyebrow">TU COMUNIDAD EMPIEZA AQUÍ</span><h2 id="modal-title">${login ? 'De vuelta al juego.' : recover ? 'Recupera tu acceso.' : 'El próximo acierto es tuyo.'}</h2><p class="intro">${login ? 'Entra con la misma cuenta que usas en la app.' : recover ? 'Te enviaremos una contraseña temporal al correo registrado. Vence en 24 horas.' : 'Crea una cuenta gratuita y comparte el fútbol con tus amigos.'}</p><form data-form="${mode}">${!recover ? field('username', 'Nombre de usuario', 'text', 'required maxlength="150" autocomplete="username" autocapitalize="none"') : ''}${!login ? field('email', 'Correo electrónico', 'email', 'required autocomplete="email"') : ''}${!recover ? field('password', 'Contraseña', 'password', `required autocomplete="${login ? 'current' : 'new'}-password" ${!login ? 'minlength="8"' : ''}`) : ''}${!login && !recover ? `<div class="form-grid">${field('first_name', 'Nombre (opcional)', 'text', 'autocomplete="given-name" maxlength="150"')}${field('fecha_nacimiento', 'Fecha de nacimiento (opcional)', 'date')}</div><p class="form-help">Usa al menos 8 caracteres. Evita contraseñas comunes o similares a tu usuario.</p>` : ''}<div class="form-error" role="alert"></div><button class="btn wide" type="submit">${login ? 'Entrar a STREAK' : recover ? 'Enviar contraseña temporal' : 'Crear mi cuenta gratuita'} ${icon('arrow')}</button></form><div class="modal-foot">${login ? '<button class="link-button" data-action="recover">Olvidé mi contraseña</button><p>¿Aún no tienes cuenta? <button class="link-button" data-action="register">Regístrate</button></p>' : '<button class="link-button" data-action="login">Volver a iniciar sesión</button>'}</div>`);
  }
  function fixture(match, {pool = null, tournament = ''} = {}) {
    const own = match.mi_pronostico;
    const open = match.pronosticos_abiertos && new Date(match.cierre_pronosticos) > new Date();
    const score = match.goles_local != null && match.goles_visita != null ? `${esc(match.goles_local)} : ${esc(match.goles_visita)}` : time(match.fecha_hora);
    return `<article class="fixture${own ? ' predicted' : ''}" data-fixture="${match.id}"><div class="fixture-top"><span>${esc(tournament || state.tournaments.find(t => t.id === match.torneo)?.nombre || 'Partido')} · ${date(match.fecha_hora)}</span>${badge(match.estado)}</div><div class="fixture-teams">${team(match.equipo_local_detalle)}<span class="score${match.goles_local == null ? ' time' : ''}">${score}</span>${team(match.equipo_visita_detalle, true)}</div>${pool && open ? `<form class="predict-form" data-form="prediction" data-pool="${pool}" data-match="${match.id}" data-closes="${esc(match.cierre_pronosticos)}"><span class="score-label">${own ? 'Tu pronóstico' : 'Tu próximo acierto'}</span><div class="score-inputs"><label><span class="sr-only">Goles de ${esc(match.equipo_local_detalle?.nombre)}</span><input type="number" name="goles_local_pred" min="0" max="32767" inputmode="numeric" required value="${own ? esc(own.goles_local_pred) : ''}"></label><span>:</span><label><span class="sr-only">Goles de ${esc(match.equipo_visita_detalle?.nombre)}</span><input type="number" name="goles_visita_pred" min="0" max="32767" inputmode="numeric" required value="${own ? esc(own.goles_visita_pred) : ''}"></label></div><button class="btn small" type="submit">${own ? 'Actualizar' : 'Guardar'}</button><div class="form-error" role="alert"></div></form>` : ''}<div class="fixture-foot"><span>${pool ? own ? `Pronóstico: <strong>${esc(own.goles_local_pred)} – ${esc(own.goles_visita_pred)}</strong> · ${match.mis_puntos ?? 0} pts` : open ? 'Aún no has pronosticado' : 'Pronóstico cerrado' : `${time(match.fecha_hora)} · Hora de tu dispositivo`}</span>${pool ? `<button class="link-button small" data-action="match-detail" data-pool="${pool}" data-match="${match.id}">Ver pronósticos ↗</button>` : `<a class="text-link" href="#torneo/${match.torneo}">Ver torneo ${icon('arrow')}</a>`}</div></article>`;
  }
  function poolCard(pool) {
    return `<article class="card"><div class="card-top"><span class="stat-icon">${icon('group')}</span><span class="badge">${pool.cantidad_inscritos}/${pool.max_participantes} jugadores</span></div><div><h3>${esc(pool.nombre)}</h3><p>${esc(pool.torneo_nombre)}</p></div><div class="card-footer"><span>Tu posición <b>${pool.mi_posicion ? `#${pool.mi_posicion}` : '—'}</b></span><span><b>${pool.mis_puntos ?? 0}</b> puntos</span></div><a class="btn secondary" href="#quiniela/${pool.id}">Abrir quiniela ${icon('arrow')}</a></article>`;
  }
  function tournamentCard(t) {
    return `<article class="card"><div class="card-top"><span class="stat-icon">${icon('trophy')}</span>${badge(t.estado)}</div><div><h3>${esc(t.nombre)}</h3><p>${esc(t.pais_detalle?.nombre || 'Sin país asignado')} · ${esc(t.temporada || 'Temporada actual')}</p></div><div class="card-footer"><span>${esc(pretty(t.formato))}</span>${t.demo_clave ? '<span class="badge demo-tag">DEMOSTRACIÓN</span>' : ''}</div><a class="btn secondary" href="#torneo/${t.id}">Explorar torneo ${icon('arrow')}</a></article>`;
  }
  function rankRows(rows, pool, compact = false) {
    return rows.map(row => compact ? `<div class="rank-row"><span class="rank-pos">${row.posicion}</span>${avatar(row)}<a class="rank-name" href="#quiniela/${pool}">${esc(row.username)}${row.usuario === state.user?.id ? ' (tú)' : ''}</a><strong>${row.puntos_totales} <small>pts</small></strong></div>` : `<tr class="${row.usuario === state.user?.id ? 'own-row' : ''}"><td>${row.posicion}</td><td><button class="row-button" data-action="player-detail" data-pool="${pool}" data-user="${row.usuario}">${esc(row.username)}${row.usuario === state.user?.id ? ' (tú)' : ''}</button></td><td>${row.es_pro ? '<span class="badge pro">PRO</span>' : 'Gratis'}</td><td><b>${row.puntos_totales}</b></td></tr>`).join('');
  }
  async function dashboard() {
    const upcoming = state.matches.filter(m => m.estado === 'PROGRAMADO' && new Date(m.fecha_hora) > new Date()).sort((a,b) => new Date(a.fecha_hora) - new Date(b.fecha_hora));
    const active = state.tournaments.filter(t => t.estado === 'ACTIVO');
    const ranking = state.pools.length ? await api(`/api/quinielas/${state.pools[0].id}/tabla/`) : [];
    return `${title(state.user ? `Vamos al juego, ${state.user.first_name || state.user.username}.` : 'Tu fútbol. Tu gente. Tu juego.', 'Cada jornada es una nueva oportunidad para subir en la tabla.', `${btn('Unirme con código', 'join', 'secondary')}${btn('Crear quiniela', 'create', '', 'plus')}`)}<section class="hero"><div class="hero-copy"><span class="eyebrow"><span class="live-dot"></span> LA EMOCIÓN SE JUEGA EN EQUIPO</span><h2>El partido empieza<br>con tu <span>pronóstico.</span></h2><p>Arma tu quiniela, reúne a tu gente y demuestra cuánto sabes de fútbol.</p>${state.user ? link('Explorar mis quinielas &nbsp; ↗', '#quinielas', 'lime') : btn('Empieza gratis &nbsp; ↗', 'register', 'lime')}</div><div class="pitch" aria-hidden="true"><svg viewBox="0 0 300 260" fill="none"><rect x="30" y="10" width="245" height="240" rx="4" stroke="#91b791" stroke-width="1.3"/><path d="M30 130h245M95 10v40h115V10M95 250v-40h115v40" stroke="#91b791" stroke-width="1.3"/><circle cx="152" cy="130" r="47" stroke="#91b791" stroke-width="1.3"/><circle cx="152" cy="130" r="3" fill="#c5ee72"/><svg x="108" y="80" width="95" height="100" viewBox="180 220 792 830"><image href="${esc(document.getElementById('streak-logo-image').getAttribute('src'))}" width="1080" height="1350"/></svg></svg></div><span class="hero-tag">EL SIGUIENTE ACIERTO ES TUYO.</span></section><section class="stats"><div class="stat"><div class="stat-icon">${icon('group')}</div><div><strong>${state.user ? state.pools.length : state.tournaments.length}</strong><span>${state.user ? 'Mis quinielas' : 'Torneos disponibles'}</span></div></div><div class="stat"><div class="stat-icon">${icon('chart')}</div><div><strong>${state.user ? state.pools.reduce((sum,p) => sum + (p.mis_puntos || 0),0) : active.length}</strong><span>${state.user ? 'Puntos acumulados' : 'Torneos activos'}</span></div></div><div class="stat"><div class="stat-icon">${icon('clock')}</div><div><strong>${upcoming.length}</strong><span>Próximos partidos</span></div></div></section><div class="dashboard-grid"><div><div class="section-heading"><div><h2>La próxima jornada</h2><p>Elige tu partido. Confía en tu intuición.</p></div><a class="text-link" href="#torneos">Ver torneos ${icon('arrow')}</a></div><div class="fixture-list">${upcoming.slice(0,5).map(m => fixture(m)).join('') || empty('A la espera del próximo silbatazo', 'Los próximos partidos aparecerán aquí cuando se programe una nueva jornada.', link('Explorar torneos', '#torneos', 'secondary'), 'clock')}</div>${state.pools.length ? `<div class="section-heading section-spacer"><h2>Tus quinielas</h2><a class="text-link" href="#quinielas">Ver todas ${icon('arrow')}</a></div><div class="cards">${state.pools.slice(0,2).map(poolCard).join('')}</div>` : ''}</div><aside class="dashboard-side"><div class="panel"><div class="panel-head"><h3>${state.pools.length ? 'La tabla se mueve' : 'Mejor con tu gente'}</h3>${icon('trophy')}</div>${ranking.length ? `<p class="small muted">${esc(state.pools[0].nombre)}</p>${rankRows(ranking.slice(0,5),state.pools[0].id,true)}<a class="text-link section-spacer" href="#quiniela/${state.pools[0].id}">Ver clasificación ${icon('arrow')}</a>` : `<p class="small muted">Un código, tus amigos y una jornada por delante. Crea tu primera quiniela o únete a una.</p><div class="section-spacer">${btn('Unirme a una quiniela', 'join', 'secondary small')}</div>`}</div>${rules()}<div class="panel"><div class="panel-head"><h3>En la cancha</h3><span class="badge">${active.length} ACTIVOS</span></div>${active.slice(0,3).map(t => `<div class="mini-tournament"><div class="stat-icon">${icon('trophy')}</div><div><strong>${esc(t.nombre)}</strong><p>${esc(t.temporada)}</p></div><a class="text-link" href="#torneo/${t.id}" aria-label="Ver ${esc(t.nombre)}">${icon('arrow')}</a></div>`).join('') || '<p class="small muted">Todavía no hay torneos activos.</p>'}</div></aside></div>`;
  }
  function poolsPage() {
    if (!state.user) return loginPage();
    return `${title('Mis quinielas', 'El fútbol se disfruta más cuando hay algo que compartir.', `${btn('Unirme con código', 'join', 'secondary')}${btn('Crear quiniela', 'create', '', 'plus')}`)}<div class="toolbar"><label class="input-search"><span class="sr-only">Buscar quiniela</span><input type="search" id="pool-search" placeholder="Buscar entre tus quinielas…"></label><div class="tabs" role="group" aria-label="Estado de quinielas"><button class="tab active" data-pools="all">Todas</button><button class="tab" data-pools="ACTIVO">En juego</button><button class="tab" data-pools="FINALIZADO">Historial</button></div></div><div id="pool-list" class="cards">${state.pools.map(poolCard).join('')}</div>${!state.pools.length ? empty('Tu primera quiniela te espera', 'Crea una para tu grupo o entra con el código que te compartieron.', btn('Crear mi quiniela', 'create') + btn('Tengo un código', 'join', 'secondary'), 'group') : ''}`;
  }
  function countriesOptions() { return '<option value="">Todos los países</option>' + state.countries.map(p => `<option value="${p.id}">${esc(p.nombre)}</option>`).join(''); }
  function tournamentsPage() {
    return `${title('Explora los torneos', 'Elige la competición y sigue cada partido de principio a fin.')}<div class="toolbar"><label class="input-search"><span class="sr-only">Buscar torneo</span><input id="tournament-search" type="search" placeholder="Buscar torneo…"></label><select id="country-filter" aria-label="Filtrar torneos por país">${countriesOptions()}</select><select id="status-filter" aria-label="Filtrar torneos por estado"><option value="">Todos los estados</option><option value="ACTIVO">Activos</option><option value="FINALIZADO">Finalizados</option></select></div><div class="cards" id="tournament-list">${state.tournaments.map(tournamentCard).join('')}</div>${!state.tournaments.length ? empty('Pronto habrá más fútbol', 'Los torneos publicados aparecerán aquí.') : ''}`;
  }
  async function tournamentPage(id, version) {
    const [t, matches, teams, phases] = await Promise.all([api(`/api/torneos/${id}/`), api(`/api/torneos/${id}/partidos/`), api(`/api/torneos/${id}/equipos/`), api(`/api/torneos/${id}/fases/`)]);
    if (version === state.version) { state.detailMatches = matches; state.detailPool = null; }
    return `<a class="text-link back-link" href="#torneos">← Todos los torneos</a>${title(t.nombre, `${t.temporada} · ${pretty(t.formato)} · ${t.pais_detalle?.nombre || 'Sin país asignado'}`, t.estado === 'ACTIVO' ? `<button class="btn" data-action="create" data-tournament="${id}">${icon('plus')} Crear quiniela</button>` : badge(t.estado))}${t.demo_clave ? '<div class="warning">Torneo de demostración: estos partidos son ejemplos para explorar STREAK.</div>' : ''}<div class="detail-banner"><div><strong>${matches.length}</strong><p>partidos en este torneo</p></div><div><strong>${teams.length}</strong><p>equipos inscritos</p></div><div><strong>${phases.length}</strong><p>fases de competición</p></div>${badge(t.estado)}</div><div class="section-heading"><h2>Calendario y resultados</h2></div>${matchFilters(phases)}<div class="fixture-list" id="match-list">${matches.map(m => fixture(m)).join('') || empty('Calendario por confirmar', 'Los partidos aparecerán aquí cuando estén programados.')}</div><div class="section-heading section-spacer"><h2>Los protagonistas</h2></div><div class="tournament-teams">${teams.map(t => `<div>${team(t)}${t.grupo ? `<p class="small muted">Grupo ${esc(t.grupo)}</p>` : ''}</div>`).join('') || '<p class="muted small">Aún no hay equipos inscritos.</p>'}</div>`;
  }
  const matchFilters = phases => `<div class="toolbar"><select id="match-phase" aria-label="Filtrar partidos por fase"><option value="">Todas las fases</option>${phases.map(f => `<option value="${f.id}">${esc(f.nombre)}</option>`).join('')}</select><select id="match-state" aria-label="Filtrar partidos por estado"><option value="">Todos los partidos</option><option value="PROGRAMADO">Por jugar</option><option value="EN_JUEGO">En juego</option><option value="FINALIZADO">Finalizados</option><option value="SUSPENDIDO">Suspendidos</option><option value="CANCELADO">Cancelados</option></select></div>`;
  async function poolPage(id, version) {
    if (!state.user) return loginPage();
    const [pool, matches, ranking] = await Promise.all([api(`/api/quinielas/${id}/`), api(`/api/quinielas/${id}/partidos/`), api(`/api/quinielas/${id}/tabla/`)]);
    const phases = await api(`/api/torneos/${pool.torneo}/fases/`);
    if (version === state.version) { state.detailMatches = matches; state.detailPool = id; }
    return `<a class="text-link back-link" href="#quinielas">← Mis quinielas</a>${title(pool.nombre, `${pool.torneo_nombre} · ${pool.cantidad_inscritos} de ${pool.max_participantes} jugadores`, `<button class="btn secondary" data-action="copy-code" data-code="${esc(pool.codigo_unico)}">${icon('copy')} Invitar amigos</button>`)}<div class="detail-banner"><div><p>CÓDIGO DE INVITACIÓN</p><strong class="invite-code">${esc(pool.codigo_unico)}</strong></div><div><strong>${pool.mis_puntos ?? 0} <small>pts</small></strong><p>tus puntos</p></div><div><strong>${pool.mi_posicion ? `#${pool.mi_posicion}` : '—'}</strong><p>tu posición</p></div></div><div class="detail-layout"><section><div class="section-heading"><div><h2>Tus pronósticos</h2><p>Guarda cada marcador antes del cierre.</p></div></div>${matchFilters(phases)}<div id="match-list" class="fixture-list">${matches.map(m => fixture(m,{pool:id})).join('') || empty('Esperando el calendario', 'Cuando haya partidos podrás registrar tus pronósticos.')}</div></section><aside><div class="panel"><div class="panel-head"><h3>La clasificación</h3>${icon('trophy')}</div><div class="table-wrap"><table><thead><tr><th>#</th><th>Jugador</th><th>Plan</th><th>PTS</th></tr></thead><tbody>${rankRows(ranking,id)}</tbody></table></div><p class="note">Toca un jugador para ver sus resultados. Los pronósticos rivales se muestran al iniciar cada partido.</p></div>${rules()}</aside></div>`;
  }
  async function teamsPage() {
    state.teams = await api('/api/equipos/');
    return `${title('Un equipo. Muchas historias.', 'Los mismos equipos, en todas sus competiciones.')}<div class="toolbar"><label class="input-search"><span class="sr-only">Buscar equipo</span><input id="team-search" type="search" placeholder="Buscar un equipo…"></label><select id="team-country" aria-label="Filtrar equipos por país">${countriesOptions()}</select></div><div class="cards" id="team-list">${teamCards(state.teams)}</div>`;
  }
  const teamCards = teams => teams.map(t => `<article class="card"><div class="card-top">${team(t)}${t.pais_detalle ? `<span class="badge">${esc(t.pais_detalle.codigo)}</span>` : ''}</div><p>${esc(t.pais_detalle?.nombre || 'Sin país asignado')}</p></article>`).join('') || empty('No encontramos equipos', 'Prueba con otro nombre o país.', '', 'ball');
  function loginPage() { return `${title('Tu lugar en la cancha', 'Una cuenta para la app y la web de STREAK.')}${empty('Entra y juega con tu comunidad', 'Inicia sesión para acceder a tus quinielas, pronósticos y clasificación.', btn('Iniciar sesión', 'login') + btn('Crear cuenta gratis', 'register', 'secondary'), 'user')}`; }
  function profilePage() {
    const u = state.user; if (!u) return loginPage();
    return `${title('Mi perfil', 'Tu cuenta, tus datos y tu forma de jugar.')}<div class="profile-layout"><section class="panel"><div class="profile-heading">${avatar(u,true)}<div><h2>${esc(u.username)}</h2><p>${esc(u.email)}</p><span class="badge${u.es_pro ? ' pro' : ''}">${u.es_pro ? 'PRO' : 'PLAN GRATUITO'}</span></div></div>${u.pass_temporal_flag ? '<div class="warning">Estás usando una contraseña temporal. Cámbiala para volver a jugar.</div>' : `<form data-form="profile"><div class="form-grid">${field('first_name','Nombre','text',`value="${esc(u.first_name)}" maxlength="150" autocomplete="given-name"`)}${field('last_name','Apellido','text',`value="${esc(u.last_name)}" maxlength="150" autocomplete="family-name"`)}${field('telefono','Teléfono','tel',`value="${esc(u.telefono)}" autocomplete="tel" maxlength="20"`)}${field('fecha_nacimiento','Fecha de nacimiento','date',`value="${esc(u.fecha_nacimiento || '')}"`)}<label class="full">Foto de perfil<input type="file" name="foto" accept="image/png,image/jpeg,image/webp"><span class="form-help">Selecciona una foto nueva para reemplazar la actual.</span></label></div><div class="form-error" role="alert"></div><button class="btn" type="submit">Guardar cambios</button></form>`}</section><aside><div class="panel"><div class="panel-head"><h3>${u.pass_temporal_flag ? 'Crea tu contraseña nueva' : 'Cambiar contraseña'}</h3>${icon('shield')}</div><form data-form="password">${field('old_password',u.pass_temporal_flag ? 'Contraseña temporal del correo' : 'Contraseña actual','password','required autocomplete="current-password"')}${field('new_password','Nueva contraseña','password','required minlength="8" autocomplete="new-password"')}${field('confirm_password','Repite la nueva contraseña','password','required minlength="8" autocomplete="new-password"')}<p class="form-help">Al guardar se cerrará la sesión en tus dispositivos.</p><div class="form-error" role="alert"></div><button class="btn secondary" type="submit">Actualizar contraseña</button></form></div><div class="panel"><h3>Control de tu cuenta</h3><p class="note">Puedes eliminar tu cuenta desde la página de confirmación. Esta acción es permanente.</p><a href="/eliminar-cuenta/" class="text-link">Ir a eliminar cuenta ↗</a></div></aside></div>`;
  }
  async function plansPage() {
    if (!state.user) return loginPage();
    const [status, payments] = await Promise.all([api('/api/pro/estado/'),api('/api/pro/pagos/')]);
    const p = status.plan;
    const amount = new Intl.NumberFormat('es-GT',{style:'currency',currency:p.moneda}).format(p.monto_centavos/100);
    return `${title('Más amigos. La misma pasión.', 'Consulta tu plan actual y el historial de tu cuenta.')}<div class="cards"><article class="card plan"><div class="card-top"><h3>STREAK Gratis</h3>${!status.es_pro ? '<span class="badge">TU PLAN</span>' : ''}</div><div class="price">$0 <small>para empezar</small></div><p>Todo lo que necesitas para jugar con tu gente.</p><ul><li>Crea y comparte quinielas</li><li>Hasta ${p.max_participantes_gratis} participantes por quiniela</li><li>Pronósticos, resultados y clasificación</li><li>Acceso desde la app y la web</li></ul>${link('Ir a mis quinielas','#quinielas','secondary')}</article><article class="card plan featured"><div class="card-top"><h3>STREAK PRO</h3>${status.es_pro ? '<span class="badge pro">TU PLAN</span>' : icon('star')}</div><div class="price">${esc(amount)} <small>pago único</small></div><p>Haz espacio para una comunidad más grande.</p><ul><li>Todas las funciones del plan gratuito</li><li>Hasta ${p.max_participantes} participantes por quiniela</li><li>Distintivo PRO en la clasificación</li></ul><div class="card-footer">${status.es_pro ? 'Tu acceso PRO está activo.' : 'La compra se gestiona desde la app móvil.'}</div>${p.modo_prueba ? '<p class="small">Los pagos están en modo de prueba. No se realizan cobros reales.</p>' : ''}</article></div><section class="panel payment-history"><div class="panel-head"><h3>Historial de pagos</h3>${icon('clock')}</div>${payments.length ? `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Importe</th><th>Estado</th></tr></thead><tbody>${payments.map(p => `<tr><td>${date(p.fecha)}</td><td>${esc(p.monto)} ${esc(p.moneda.toUpperCase())}</td><td>${esc(pretty(p.estado))}</td></tr>`).join('')}</tbody></table></div>` : '<p class="small muted">Todavía no hay pagos registrados en tu cuenta.</p>'}</section>`;
  }
  async function adminPage() {
    if (!state.user) return loginPage();
    if (!state.admin) return empty('Esta zona es para administradores', 'Tu cuenta puede jugar quinielas. Para administrar el sistema necesitas los permisos correspondientes.', link('Volver a mis quinielas','#quinielas'), 'shield');
    const result = await api('/web/administracion/');
    const descriptions = {Pais:'Organiza las competiciones por país.',Equipo:'Crea cada equipo una vez y reutilízalo.',EquipoTorneo:'Inscribe equipos existentes en sus torneos.',Torneo:'Define temporadas, países y fases.',Fase:'Ordena las etapas de cada competición.',Partido:'Programa encuentros y registra resultados.',Usuario:'Gestiona cuentas y permisos.',Quiniela:'Consulta las comunidades de jugadores.',Participante:'Consulta las inscripciones y puntuaciones.',Pronostico:'Revisa marcadores y puntos obtenidos.',Pago:'Consulta el estado de los pagos.',Group:'Agrupa permisos de administración.'};
    return `${title('Todo listo para la jornada.', 'Gestiona STREAK con los permisos de tu cuenta.', link('Panel completo ↗','/admin/','secondary'))}<div class="detail-banner"><div><h2>Un equipo se crea una sola vez.</h2><p>Países → equipos → torneos y fases → equipos por torneo → partidos.</p></div>${icon('shield')}</div><div class="cards">${result.modulos.map(m => `<article class="card admin-card"><div class="card-top"><span class="stat-icon">${icon(['Usuario','Participante','Group'].includes(m.modelo) ? 'group' : m.modelo === 'Partido' ? 'ball' : 'trophy')}</span><span class="badge">GESTIÓN</span></div><div><h3>${esc(m.nombre)}</h3><p>${esc(descriptions[m.modelo] || 'Gestiona los registros de este módulo.')}</p></div><div class="actions">${m.url ? link('Ver registros ↗', esc(m.url), 'secondary small') : ''}${m.crear_url ? link('+ Crear',esc(m.crear_url),'small') : ''}</div></article>`).join('') || empty('Sin módulos asignados','Tu cuenta es de personal, pero todavía no tiene permisos de administración.')}</div>`;
  }
  function rulesPage() {
    return `${title('Cada acierto tiene su recompensa.', 'Estas son las reglas que utiliza STREAK para calcular tu puntuación.')}<div class="rules-grid"><article class="rule-card"><strong>5</strong><p>Marcador exacto</p><small>Predices 2–1. Termina 2–1.</small></article><article class="rule-card"><strong>4</strong><p>Resultado y diferencia</p><small>Predices 2–1. Termina 3–2.</small></article><article class="rule-card"><strong>3</strong><p>Resultado correcto</p><small>Predices 2–0. Termina 1–0.</small></article><article class="rule-card"><strong>0</strong><p>Resultado incorrecto</p><small>Predices 2–0. Termina 0–1.</small></article></div><div class="panel section-spacer"><h2>Antes del silbatazo</h2><p class="note">Puedes guardar o actualizar tu pronóstico hasta cinco minutos antes del inicio. Los marcadores de prórroga y penales son informativos; se puntúa el tiempo reglamentario. Los pronósticos de tus rivales se revelan al comenzar el partido.</p><p class="note">Si entras a una quiniela con la jornada iniciada, solo podrás pronosticar partidos que sigan abiertos. Comienzas con 0 puntos, sin penalización adicional. En los empates de puntos, los jugadores comparten posición.</p><p class="note">La clasificación se recalcula al registrar o corregir un resultado. Los partidos suspendidos o cancelados no suman puntos.</p></div>`;
  }
  async function render() {
    const version = ++state.version;
    shell();
    const [route='inicio', id] = (location.hash.slice(1) || 'inicio').split('/');
    main.setAttribute('aria-busy','true');
    main.innerHTML = '<div class="loading"><span class="spinner"></span>Preparando la jugada…</div>';
    try {
      if (state.user && !state.user.pass_temporal_flag && ['inicio','quinielas'].includes(route)) {
        const pools = await api('/api/quinielas/mias/');
        if (version !== state.version) return;
        state.pools = pools; shell();
      }
      if (['torneo','quiniela'].includes(route) && !/^\d+$/.test(id || '')) throw new Error('No encontramos esta página.');
      let content;
      if (state.user?.pass_temporal_flag && !['inicio','perfil','torneos','torneo','equipos','reglas'].includes(route)) content = profilePage();
      else content = await ({inicio:dashboard,quinielas:poolsPage,torneos:tournamentsPage,torneo:()=>tournamentPage(id,version),quiniela:()=>poolPage(id,version),equipos:teamsPage,perfil:profilePage,planes:plansPage,administracion:adminPage,reglas:rulesPage}[route] || (() => empty('Esta página no existe','Vuelve al inicio para seguir jugando.',link('Volver al inicio','#inicio'))))();
      if (version !== state.version) return;
      main.innerHTML = `${state.user?.pass_temporal_flag && route !== 'perfil' ? '<div class="warning">Para volver a jugar debes <a class="text-link" href="#perfil">cambiar tu contraseña temporal</a>.</div>' : ''}${content}`;
      document.title = `${$('#page-label').textContent} · STREAK`;
    } catch (error) {
      if (version !== state.version) return;
      main.innerHTML = `<div class="error-box" role="alert">${esc(error.message)}</div><div class="actions">${btn('Reintentar','retry','secondary')}${link('Volver al inicio','#inicio','ghost')}</div>`;
    } finally { if (version === state.version) main.removeAttribute('aria-busy'); }
  }
  async function refreshSession() {
    const data = await api('/web/sesion/'); state.csrf = data.csrf; state.user = data.usuario; state.admin = data.administrador;
    state.pools = state.user && !state.user.pass_temporal_flag ? await api('/api/quinielas/mias/') : [];
  }
  async function load() {
    try {
      await refreshSession();
      [state.tournaments,state.countries] = await Promise.all([api('/api/torneos/'),api('/api/paises/')]);
      const schedules = await Promise.all(state.tournaments.map(t => api(`/api/torneos/${t.id}/partidos/`)));
      state.matches = schedules.flat();
      await render();
    } catch(error) { main.innerHTML = `<div class="error-box" role="alert">${esc(error.message)}</div>${btn('Volver a intentar','reload','secondary')}`; }
  }
  function createDialog(selected = '') {
    if (!requireUser()) return;
    const active = state.tournaments.filter(t => t.estado === 'ACTIVO');
    if (!active.length) { toast('Necesitas un torneo activo para crear una quiniela.'); return; }
    openDialog(`<span class="eyebrow">TU GRUPO, TUS REGLAS DE JUEGO</span><h2 id="modal-title">Crea tu quiniela.</h2><p class="intro">Invita a tus amigos con un código único.</p><form data-form="create">${field('nombre','Nombre de la quiniela','text','required maxlength="100" placeholder="Ej. La peña del domingo"')}<label>Torneo<select name="torneo" required>${active.map(t => `<option value="${t.id}" ${String(t.id) === String(selected) ? 'selected' : ''}>${esc(t.nombre)}</option>`).join('')}</select></label>${field('max_participantes','Máximo de participantes','number',`required min="2" max="${state.user.es_pro ? 100 : 50}" value="20"`)}<p class="form-help">Tu plan permite hasta ${state.user.es_pro ? 100 : 50} participantes, incluyéndote.</p><div class="form-error" role="alert"></div><button class="btn wide" type="submit">Crear quiniela ${icon('arrow')}</button></form>`);
  }
  function joinDialog() {
    if (!requireUser()) return;
    openDialog(`<span class="eyebrow">EL GRUPO TE ESTÁ ESPERANDO</span><h2 id="modal-title">Entra a la quiniela.</h2><p class="intro">Pide a un amigo el código de seis caracteres.</p><form data-form="join-preview">${field('codigo','Código de invitación','text','required minlength="6" maxlength="6" placeholder="ABC234" autocomplete="off" autocapitalize="characters"')}<div class="form-error" role="alert"></div><button class="btn wide" type="submit">Buscar quiniela ${icon('arrow')}</button></form>`);
  }
  function displayJoinPreview(data, code) {
    openDialog(`<h2 id="modal-title">${esc(data.nombre)}</h2><p class="intro">${esc(data.torneo_nombre)} · ${data.cantidad_inscritos}/${data.max_participantes} jugadores</p>${data.requiere_confirmacion ? `<div class="warning">${esc(data.advertencia)} Hay ${data.partidos_cerrados} partidos con plazo cerrado. Empezarás con 0 puntos, sin penalización adicional.</div>` : '<div class="success">Todavía puedes sumarte a la competición.</div>'}<form data-form="join-confirm" data-code="${esc(code)}">${data.requiere_confirmacion ? '<label><input type="checkbox" name="accept" required> Entiendo que solo podré pronosticar partidos abiertos.</label>' : ''}<div class="form-error" role="alert"></div><button class="btn wide" type="submit">Unirme a esta quiniela</button></form>`);
  }
  async function detailDialog(action, button) {
    if (!requireUser()) return;
    openDialog('<h2 id="modal-title">Cargando detalle…</h2><div class="loading"><span class="spinner"></span></div>');
    try {
      if (action === 'match-detail') {
        const data = await api(`/api/quinielas/${button.dataset.pool}/partidos/${button.dataset.match}/detalle/`);
        openDialog(`<h2 id="modal-title">Las jugadas del grupo</h2><p class="intro">${esc(data.partido.equipo_local_detalle?.nombre)} vs. ${esc(data.partido.equipo_visita_detalle?.nombre)}</p><div class="table-wrap"><table><thead><tr><th>Jugador</th><th>Pronóstico</th><th>PTS</th></tr></thead><tbody>${data.participantes.map(p => `<tr><td>${esc(p.username)}</td><td>${p.pronostico ? `${p.pronostico.goles_local_pred} – ${p.pronostico.goles_visita_pred}` : p.estado_pronostico === 'OCULTO' ? 'Oculto hasta el inicio' : 'Sin pronóstico'}</td><td>${p.puntos_obtenidos}</td></tr>`).join('')}</tbody></table></div>`);
      } else {
        const data = await api(`/api/quinielas/${button.dataset.pool}/participantes/${button.dataset.user}/detalle/`);
        openDialog(`<h2 id="modal-title">${esc(data.participante.username)}</h2><p class="intro">${data.participante.puntos_totales} puntos · Resultados por partido</p><div class="list-stack">${data.partidos.map(p => `<div><p class="small"><b>${esc(p.equipo_local_detalle?.nombre)} – ${esc(p.equipo_visita_detalle?.nombre)}</b></p><p class="small muted">${p.pronostico ? `Pronóstico: ${p.pronostico.goles_local_pred} – ${p.pronostico.goles_visita_pred} · ${p.puntos_obtenidos} pts` : p.estado_pronostico === 'OCULTO' ? 'Oculto hasta el inicio' : 'Sin pronóstico'}</p></div>`).join('') || '<p class="small muted">Todavía no hay partidos.</p>'}</div>`);
      }
    } catch(error) { openDialog(`<h2 id="modal-title">No pudimos abrir el detalle</h2><div class="error-box" role="alert">${esc(error.message)}</div>`); }
  }
  document.addEventListener('click', async event => {
    if (event.target.closest('.skip-link')) { event.preventDefault(); main.focus(); return; }
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    try {
      if (['login','register','recover'].includes(action)) authDialog(action);
      if (action === 'close-modal') modal.close();
      if (action === 'create') createDialog(button.dataset.tournament);
      if (action === 'join') joinDialog();
      if (action === 'retry') render();
      if (action === 'reload') load();
      if (action === 'logout') { button.disabled = true; await api('/web/salir/',{method:'POST'}); await refreshSession(); location.hash='inicio'; await render(); toast('Sesión cerrada. ¡Nos vemos en la próxima jornada!'); }
      if (action === 'copy-code') {
        try { await navigator.clipboard.writeText(button.dataset.code); toast('Código copiado. Compártelo con tus amigos.'); }
        catch { openDialog(`<h2 id="modal-title">Invita a tu gente</h2><p class="intro">Comparte este código de invitación:</p><p class="invite-code">${esc(button.dataset.code)}</p>`); }
      }
      if (['match-detail','player-detail'].includes(action)) await detailDialog(action,button);
    } catch(error) { toast(error.message); button.disabled = false; }
  });
  document.addEventListener('submit', async event => {
    const form = event.target.closest('form[data-form]'); if (!form) return; event.preventDefault();
    const submit = $('button[type=submit]',form); if (submit.disabled) return;
    const err = $('.form-error',form); err.textContent=''; submit.disabled = true;
    const values = Object.fromEntries(new FormData(form));
    try {
      switch (form.dataset.form) {
        case 'login': {
          const session = await api('/web/entrar/',{method:'POST',data:values}); state.csrf=session.csrf;
          await refreshSession(); modal.close(); if(state.user.pass_temporal_flag) location.hash='perfil'; await render(); toast('¡Bienvenido a STREAK!'); break;
        }
        case 'register':
          if (!values.fecha_nacimiento) delete values.fecha_nacimiento;
          await api('/api/auth/register/',{method:'POST',data:values}); authDialog('login'); toast('Cuenta creada. Ya puedes iniciar sesión.'); break;
        case 'recover': {
          const result=await api('/api/auth/recuperar/',{method:'POST',data:values});
          openDialog(`<h2 id="modal-title">Revisa tu correo.</h2><div class="success">${esc(result.detail)}</div><p class="intro">Revisa también spam. Inicia sesión con la contraseña temporal y después crea una nueva.</p>${btn('Volver a iniciar sesión','login')}`); break;
        }
        case 'create': {
          const pool=await api('/api/quinielas/',{method:'POST',data:{...values,torneo:Number(values.torneo),max_participantes:Number(values.max_participantes)}});
          await refreshSession(); modal.close(); location.hash=`quiniela/${pool.id}`; toast('Tu quiniela está lista. Invita a tus amigos.'); break;
        }
        case 'join-preview': {
          const code=values.codigo.trim().toUpperCase(); const result=await api('/api/quinielas/validar-codigo/',{method:'POST',data:{codigo:code}}); displayJoinPreview(result,code); break;
        }
        case 'join-confirm': {
          const code=form.dataset.code;
          try { const result=await api('/api/quinielas/unirse/',{method:'POST',data:{codigo:code,aceptar_ingreso_tardio:values.accept === 'on'}}); await refreshSession(); modal.close(); location.hash=`quiniela/${result.quiniela_id}`; toast('Ya estás dentro. ¡A jugar!'); }
          catch(error) { if(error.code === 'CONFIRMACION_INGRESO_TARDIO') displayJoinPreview(error.details,code); else throw error; } break;
        }
        case 'prediction': {
          if(new Date(form.dataset.closes) <= new Date()) throw new Error('El plazo acaba de cerrar. Actualiza la página para ver el estado.');
          await api(`/api/quinielas/${form.dataset.pool}/pronosticos/`,{method:'POST',data:{partido:Number(form.dataset.match),goles_local_pred:Number(values.goles_local_pred),goles_visita_pred:Number(values.goles_visita_pred)}});
          const saved=await api(`/api/quinielas/${form.dataset.pool}/partidos/`);
          state.detailMatches=saved; filterMatches(); toast('Pronóstico guardado. ¡Que ruede el balón!'); break;
        }
        case 'profile': {
          let data;
          if (values.foto?.size) data=new FormData(form);
          else { const {foto, ...fields}=values; data={...fields,fecha_nacimiento:values.fecha_nacimiento || null}; }
          await api('/api/usuarios/me/',{method:'PATCH',data}); await refreshSession(); await render(); toast('Tu perfil está actualizado.'); break;
        }
        case 'password':
          if(values.new_password !== values.confirm_password) throw new Error('Las contraseñas nuevas no coinciden.');
          await api('/api/auth/cambiar-password/',{method:'POST',data:{old_password:values.old_password,new_password:values.new_password}});
          await api('/web/salir/',{method:'POST'}); await refreshSession(); await render(); authDialog('login'); toast('Contraseña actualizada. Inicia sesión nuevamente.'); break;
      }
    } catch(error) { err.textContent = error.message; }
    finally { submit.disabled = false; }
  });
  function filterMatches() {
    const container=$('#match-list'); if(!container) return;
    const phase=$('#match-phase')?.value, status=$('#match-state')?.value;
    const matches=(state.detailMatches || []).filter(m => (!phase || String(m.fase) === phase) && (!status || m.estado === status));
    container.innerHTML=matches.map(m => fixture(m,{pool:state.detailPool})).join('') || empty('No hay partidos con estos filtros','Prueba con otra fase o estado.');
  }
  function filterPools(status) {
    const container=$('#pool-list'); if(!container) return;
    const activeStatus=status || $('[data-pools].active')?.dataset.pools || 'all', query=$('#pool-search')?.value.toLowerCase() || '';
    const pools=state.pools.filter(p => p.nombre.toLowerCase().includes(query) && (activeStatus === 'all' || state.tournaments.find(t => t.id === p.torneo)?.estado === activeStatus));
    container.innerHTML=pools.map(poolCard).join('') || empty('Sin quinielas para mostrar','Prueba con otros filtros o crea una nueva.');
  }
  document.addEventListener('click',event => {
    const tab=event.target.closest('[data-pools]'); if(!tab) return;
    document.querySelectorAll('[data-pools]').forEach(t => t.classList.toggle('active',t === tab)); filterPools(tab.dataset.pools);
  });
  function filterLists(event) {
    if(['tournament-search','country-filter','status-filter'].includes(event.target.id)) {
      const q=$('#tournament-search').value.toLowerCase(), c=$('#country-filter').value, s=$('#status-filter').value;
      const list=state.tournaments.filter(t => t.nombre.toLowerCase().includes(q) && (!c || String(t.pais) === c) && (!s || t.estado === s));
      $('#tournament-list').innerHTML=list.map(tournamentCard).join('') || empty('No encontramos torneos','Prueba con otro nombre, país o estado.');
    }
    if(['team-search','team-country'].includes(event.target.id)) {
      const q=$('#team-search').value.toLowerCase(), c=$('#team-country').value;
      $('#team-list').innerHTML=teamCards(state.teams.filter(t => t.nombre.toLowerCase().includes(q) && (!c || String(t.pais) === c)));
    }
    if(['match-phase','match-state'].includes(event.target.id)) filterMatches();
    if(event.target.id === 'pool-search') filterPools();
  }
  document.addEventListener('input',filterLists);
  document.addEventListener('change',filterLists);
  window.addEventListener('hashchange',() => { if(modal.open) modal.close(); render(); window.scrollTo({top:0,behavior:'instant'}); });
  // Disable a score form as soon as its deadline passes; the API is authoritative.
  setInterval(() => document.querySelectorAll('form[data-closes]').forEach(form => {
    if(new Date(form.dataset.closes) <= new Date()) { form.querySelectorAll('input,button').forEach(el => {el.disabled=true;}); $('.form-error',form).textContent='El plazo para pronosticar ha cerrado.'; }
  }),1000);
  load();
})();
