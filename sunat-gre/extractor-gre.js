/* =====================================================================
 * EXTRACTOR GRE – Guías de Remisión Electrónica (SUNAT, uso autorizado)
 * Versión 1.1.0
 *
 * Dónde ejecutarlo:
 *   Microsoft Edge > DevTools > Console > contexto
 *   "iframeApplication (resultado) – intranet.sunat.peru"
 *
 * Qué hace:
 *   0. (Opcional) Toma el token y los filtros de una búsqueda hecha en la
 *      propia pantalla de SUNAT ("Capturar desde SUNAT"), sin copiar nada a mano.
 *   1. Consulta el listado paginado de GRE del rango indicado.
 *   2. Elimina duplicados.
 *   3. Consulta el detalle de cada guía, de una en una, con pausas.
 *   4. Exporta CSV (UTF-8 con BOM, separador ;) y JSON completo.
 *   5. Si se detiene (token vencido, cancelación), al volver a iniciar continúa
 *      donde quedó sin repetir las guías ya obtenidas en esta sesión.
 *
 * Seguridad:
 *   - El token solo vive en memoria durante la ejecución y se descarta al final.
 *   - Se revisa localmente su vencimiento (si es JWT); no se muestra ni exporta.
 *   - No usa localStorage, sessionStorage, cookies ni servidores externos.
 *   - credentials: "omit" y mode: "cors" (nunca "no-cors").
 *   - Ante HTTP 401/403 el proceso se detiene.
 *
 * Única variable global: window.GREExtractor
 * ===================================================================== */
(() => {
  'use strict';

  const VERSION = '1.1.0';
  const API_LISTADO = 'https://api-intranet.sunat.peru/v1/contribuyente/gre/comprobantes';
  const PANEL_ID = 'gre-extractor-host';

  /* ---------------------------------------------------------------
   * 0. Evitar dos ejecuciones simultáneas
   * ------------------------------------------------------------- */
  const instanciaPrevia = window.GREExtractor;
  if (instanciaPrevia && instanciaPrevia.ejecutando) {
    console.warn('[GRE] Ya hay una extracción en curso. Use GREExtractor.cancelar() y espere a que termine antes de volver a pegar el script.');
    try { instanciaPrevia.mostrarPanel(); } catch (_) { /* sin panel */ }
    return;
  }
  if (instanciaPrevia && typeof instanciaPrevia.cerrarPanel === 'function') {
    try { instanciaPrevia.cerrarPanel(); } catch (_) { /* ignorar */ }
  }

  /* ---------------------------------------------------------------
   * 1. Configuración predeterminada
   * ------------------------------------------------------------- */
  const CONFIG_PREDETERMINADA = Object.freeze({
    fechaInicio: '',
    fechaFin: '',
    rucEmisor: '',
    rucReceptor: '',
    codCpe: '09',
    numSerie: '',
    numCpe: '',
    codEstado: '',
    codSubEstado: '',
    rangoHoras: '',
    tipBusqueda: '2',
    perPage: 100,
    pausaMinMs: 600,
    pausaMaxMs: 900,
    maxReintentos: 2,
    maxDiasRango: 0,            // 0 = sin límite. Ajuste si SUNAT impone un rango máximo.
    maxPaginas: 1000,           // Tope de seguridad de páginas del listado.
    timeoutMs: 45000,           // Tiempo máximo por solicitud.
    maxErroresConsecutivos: 8   // Detiene el lote si fallan muchas guías seguidas (red caída, sesión perdida).
  });

  const ESTADOS_REINTENTABLES = new Set([429, 500, 502, 503, 504]);

  // Explicación que se muestra cuando el navegador no puede leer la respuesta ("Failed to fetch").
  const AYUDA_FALLO_CONEXION = [
    'El navegador no pudo leer la respuesta de la API. Causas más comunes:',
    '1) Token vencido, incompleto o copiado de otra solicitud.',
    '2) Filtros que la API rechaza (por ejemplo, el RUC en un campo que no corresponde al "Tipo de búsqueda").',
    '3) La consola no está en el contexto "iframeApplication (intranet.sunat.peru)".',
    'Solución recomendada: pulse "Capturar desde SUNAT", haga la búsqueda en la pantalla de SUNAT y vuelva a pulsar Iniciar.',
    'La causa exacta aparece en el mensaje rojo de la consola y en la pestaña Network (columna Estado).'
  ];

  /* ---------------------------------------------------------------
   * 2. Estado interno (no contiene el token)
   * ------------------------------------------------------------- */
  const estado = {
    ejecutando: false,
    pausado: false,
    controller: null,
    config: null,
    motivoFin: '',
    tiempos: { inicio: 0, inicioDetalle: 0, fin: 0 },
    listado: null,
    unicos: [],
    duplicados: [],
    resultados: new Map(),   // clave -> registro
    previos: new Map(),      // clave -> { detalle, consultadoEn } (cargado desde JSON anterior)
    memoria: new Map(),      // clave -> { detalle, consultadoEn } (obtenidas en una ejecución anterior de esta sesión)
    errores: [],
    controlDetalle: [],
    control: [],
    progreso: null,
    resumen: null
  };

  function listadoVacio() {
    return { totalApi: null, perPageApi: null, totalPaginas: 0, registros: 0, paginas: [] };
  }
  function progresoVacio() {
    return { total: 0, actual: '', procesadas: 0, ok: 0, error: 0, omitidas: 0, consultadas: 0, pendientesReales: 0 };
  }
  estado.listado = listadoVacio();
  estado.progreso = progresoVacio();

  let ui = null; // referencias del panel (si existe)

  // Captura desde la aplicación SUNAT. Solo en memoria (nunca global ni persistente).
  let tokenCapturado = null;     // se consume al iniciar y se descarta al terminar
  let filtrosCapturados = null;  // filtros de la última búsqueda hecha en la pantalla de SUNAT (sin token)
  const captura = { activa: false, temporizador: null, restaurar: null };

  /* ---------------------------------------------------------------
   * 3. Utilidades generales
   * ------------------------------------------------------------- */
  class ErrorValidacion extends Error { constructor(m) { super(m); this.name = 'ErrorValidacion'; } }
  class ErrorAutenticacion extends Error {
    constructor(status, url, mensaje, codigo) {
      super(mensaje || `HTTP ${status}: acceso no autorizado o sesión/token vencido.`);
      this.name = 'ErrorAutenticacion'; this.status = status; this.url = url;
      this.codigo = codigo || `DETENIDO_HTTP_${status}`;
    }
  }
  class ErrorDetencion extends Error {
    constructor(m, ayuda = []) { super(m); this.name = 'ErrorDetencion'; this.ayuda = ayuda; }
  }

  const esVacio = (v) => v === null || v === undefined || (typeof v === 'string' && v.trim() === '');
  const esObjetoPlano = (v) => v !== null && typeof v === 'object' && !Array.isArray(v) && !(v instanceof Date);
  const esPrimitivo = (v) => v === null || v === undefined || v instanceof Date ||
    ['string', 'number', 'boolean', 'bigint'].includes(typeof v);

  /** Convierte cualquier valor a texto sin producir "null"/"undefined". */
  function texto(v) {
    if (v === null || v === undefined) return '';
    if (v instanceof Date) return isNaN(v.getTime()) ? '' : v.toISOString();
    if (typeof v === 'number') return Number.isFinite(v) ? String(v) : '';
    if (typeof v === 'object') { try { return JSON.stringify(v); } catch (_) { return ''; } }
    return String(v);
  }

  /** Lee una ruta "a.b.c" de forma segura. */
  function obtener(obj, ruta) {
    let actual = obj;
    for (const parte of ruta.split('.')) {
      if (actual === null || actual === undefined || typeof actual !== 'object') return undefined;
      actual = actual[parte];
    }
    return actual;
  }

  /** Devuelve el primer valor primitivo no vacío. */
  function primero(...valores) {
    for (const v of valores) if (!esVacio(v) && esPrimitivo(v)) return v;
    return '';
  }

  /**
   * Busca, dentro de uno o varios objetos (solo primer nivel), la primera
   * propiedad cuyo NOMBRE coincida con alguna expresión regular y cuyo valor
   * sea primitivo y no vacío. No inventa datos: solo lee lo que existe.
   */
  function buscarClave(nodos, expresiones) {
    const lista = (Array.isArray(nodos) ? nodos : [nodos]).filter(esObjetoPlano);
    for (const re of expresiones) {
      for (const nodo of lista) {
        for (const k of Object.keys(nodo)) {
          const v = nodo[k];
          if (re.test(k) && esPrimitivo(v) && !esVacio(v)) return v;
        }
      }
    }
    return '';
  }

  /** Busca en profundidad la primera propiedad con un nombre exacto. */
  function buscarProfundo(obj, nombre, profundidad = 0) {
    if (profundidad > 8 || obj === null || typeof obj !== 'object') return undefined;
    if (!Array.isArray(obj) && Object.prototype.hasOwnProperty.call(obj, nombre)) return obj[nombre];
    for (const v of Object.values(obj)) {
      if (v && typeof v === 'object') {
        const r = buscarProfundo(v, nombre, profundidad + 1);
        if (r !== undefined) return r;
      }
    }
    return undefined;
  }

  const dos = (n) => String(n).padStart(2, '0');
  function marcaTiempo(d = new Date()) {
    return `${d.getFullYear()}${dos(d.getMonth() + 1)}${dos(d.getDate())}_${dos(d.getHours())}${dos(d.getMinutes())}${dos(d.getSeconds())}`;
  }
  function fechaHoraLocal(d = new Date()) {
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ${dos(d.getHours())}:${dos(d.getMinutes())}:${dos(d.getSeconds())}`;
  }
  function hoyISO() {
    const d = new Date();
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
  }
  function duracion(ms) {
    if (!Number.isFinite(ms) || ms < 0) return '--:--:--';
    const s = Math.round(ms / 1000);
    return `${dos(Math.floor(s / 3600))}:${dos(Math.floor((s % 3600) / 60))}:${dos(s % 60)}`;
  }

  const horaDe = (ms) => fechaHoraLocal(new Date(ms)).slice(11);

  /** Número de comprobante con 8 dígitos solo para mostrar/CSV. */
  function numero8(num) {
    const s = texto(num).trim();
    return /^\d+$/.test(s) ? s.padStart(8, '0') : s;
  }
  function guiaLegible(serie, num) {
    const s = texto(serie).trim();
    const n = numero8(num);
    return s || n ? `${s}-${n}` : '';
  }
  function claveGuia(ruc, cod, serie, num) {
    return [ruc, cod, serie, num].map((v) => texto(v).trim()).join('-');
  }
  function claveDesdeDetalle(det) {
    if (!esObjetoPlano(det)) return '';
    const partes = [det.numRuc, det.codCpe, det.numSerie, det.numCpe];
    if (partes.some(esVacio)) return '';
    return claveGuia(...partes);
  }

  function crearAbortError() {
    try { return new DOMException('Proceso cancelado por el usuario', 'AbortError'); }
    catch (_) { const e = new Error('Proceso cancelado por el usuario'); e.name = 'AbortError'; return e; }
  }
  const esAbort = (e) => !!e && e.name === 'AbortError';

  /** Espera cancelable. */
  function dormir(ms, signal) {
    return new Promise((resolve, reject) => {
      if (signal && signal.aborted) { reject(crearAbortError()); return; }
      const alAbortar = () => { clearTimeout(t); reject(crearAbortError()); };
      const t = setTimeout(() => {
        if (signal) signal.removeEventListener('abort', alAbortar);
        resolve();
      }, Math.max(0, ms));
      if (signal) signal.addEventListener('abort', alAbortar, { once: true });
    });
  }

  /** Mientras esté en pausa, espera (cancelable). */
  async function esperarSiPausado(signal) {
    let avisado = false;
    while (estado.pausado) {
      if (!avisado) { log('En pausa. Pulse "Reanudar" o ejecute GREExtractor.reanudar().', 'warn'); avisado = true; actualizarUI(); }
      await dormir(300, signal);
    }
  }

  function pausaAleatoria(cfg) {
    const min = cfg.pausaMinMs, max = cfg.pausaMaxMs;
    return min + Math.floor(Math.random() * (max - min + 1));
  }

  /* ---------------------------------------------------------------
   * 4. Mensajes (consola + panel). Sin datos personales.
   * ------------------------------------------------------------- */
  function log(mensaje, nivel = 'info') {
    const fn = { info: console.log, ok: console.log, warn: console.warn, error: console.error }[nivel] || console.log;
    fn.call(console, '%c[GRE]', 'color:#0a7d55;font-weight:bold', mensaje);
    if (ui && ui.log) {
      const linea = h('div', { class: 'l-' + nivel, text: `[${fechaHoraLocal().slice(11)}] ${mensaje}` });
      ui.log.append(linea);
      while (ui.log.childElementCount > 300) ui.log.firstChild.remove();
      ui.log.scrollTop = ui.log.scrollHeight;
    }
  }

  function registrarError({ guia = '', clave = '', url = '', estadoHttp = '', mensaje = '', intento = '', accion = '' }) {
    estado.errores.push({
      guia, clave, url, estadoHttp: texto(estadoHttp), mensaje: texto(mensaje),
      intento: texto(intento), fechaHora: fechaHoraLocal(), accion
    });
  }

  /* ---------------------------------------------------------------
   * 5. Validación y normalización de la configuración
   * ------------------------------------------------------------- */
  const RE_FECHA = /^\d{4}-\d{2}-\d{2}$/;
  function parsearFecha(s) {
    if (typeof s !== 'string' || !RE_FECHA.test(s)) return null;
    const [y, m, d] = s.split('-').map(Number);
    const f = new Date(Date.UTC(y, m - 1, d));
    if (f.getUTCFullYear() !== y || f.getUTCMonth() !== m - 1 || f.getUTCDate() !== d) return null;
    return f;
  }

  function entero(valor, nombre, min, max, predeterminado) {
    if (esVacio(valor)) return predeterminado;
    const n = Number(valor);
    if (!Number.isInteger(n) || n < min || n > max) {
      throw new ErrorValidacion(`"${nombre}" debe ser un número entero entre ${min} y ${max}.`);
    }
    return n;
  }

  function normalizarConfig(op = {}) {
    if (!esObjetoPlano(op)) throw new ErrorValidacion('Las opciones deben ser un objeto.');
    const D = CONFIG_PREDETERMINADA;
    const t = (v, def = '') => (esVacio(v) ? def : String(v).trim());

    const cfg = {
      fechaInicio: t(op.fechaInicio ?? op.fecEmisionIni),
      fechaFin: t(op.fechaFin ?? op.fecEmisionFin),
      rucEmisor: t(op.rucEmisor ?? op.numRucEmisor),
      rucReceptor: t(op.rucReceptor ?? op.numRucReceptor),
      codCpe: t(op.codCpe, D.codCpe),
      numSerie: t(op.numSerie ?? op.serie).toUpperCase(),
      numCpe: t(op.numCpe ?? op.numero),
      codEstado: t(op.codEstado),
      codSubEstado: t(op.codSubEstado),
      rangoHoras: t(op.rangoHoras),
      tipBusqueda: t(op.tipBusqueda, D.tipBusqueda),
      perPage: entero(op.perPage ?? op.per_page, 'Cantidad por página', 1, 1000, D.perPage),
      pausaMinMs: D.pausaMinMs,
      pausaMaxMs: D.pausaMaxMs,
      maxReintentos: entero(op.maxReintentos, 'Máximo de reintentos', 0, 10, D.maxReintentos),
      maxDiasRango: entero(op.maxDiasRango, 'Máximo de días del rango', 0, 3660, D.maxDiasRango),
      maxPaginas: entero(op.maxPaginas, 'Máximo de páginas', 1, 100000, D.maxPaginas),
      timeoutMs: entero(op.timeoutMs, 'Tiempo máximo por solicitud', 5000, 300000, D.timeoutMs),
      maxErroresConsecutivos: entero(op.maxErroresConsecutivos, 'Máximo de errores consecutivos', 1, 1000, D.maxErroresConsecutivos)
    };

    // Pausa: "pausaMs" fija, o rango mínimo/máximo.
    if (!esVacio(op.pausaMs)) {
      const p = entero(op.pausaMs, 'Pausa', 0, 60000, D.pausaMinMs);
      cfg.pausaMinMs = p; cfg.pausaMaxMs = p;
    } else {
      cfg.pausaMinMs = entero(op.pausaMinMs, 'Pausa mínima', 0, 60000, D.pausaMinMs);
      cfg.pausaMaxMs = entero(op.pausaMaxMs, 'Pausa máxima', 0, 60000, D.pausaMaxMs);
      if (cfg.pausaMinMs > cfg.pausaMaxMs) [cfg.pausaMinMs, cfg.pausaMaxMs] = [cfg.pausaMaxMs, cfg.pausaMinMs];
    }

    // Fechas obligatorias
    if (!cfg.fechaInicio || !cfg.fechaFin) throw new ErrorValidacion('La fecha inicial y la fecha final son obligatorias.');
    const fi = parsearFecha(cfg.fechaInicio), ff = parsearFecha(cfg.fechaFin);
    if (!fi) throw new ErrorValidacion(`Fecha inicial inválida "${cfg.fechaInicio}". Use el formato YYYY-MM-DD.`);
    if (!ff) throw new ErrorValidacion(`Fecha final inválida "${cfg.fechaFin}". Use el formato YYYY-MM-DD.`);
    if (fi.getTime() > ff.getTime()) throw new ErrorValidacion('La fecha inicial no puede ser mayor que la fecha final.');
    const dias = Math.round((ff - fi) / 86400000) + 1;
    if (cfg.maxDiasRango > 0 && dias > cfg.maxDiasRango) {
      throw new ErrorValidacion(`El rango tiene ${dias} días y el máximo configurado es ${cfg.maxDiasRango}. Divida la consulta.`);
    }

    // RUC opcionales, pero si se indican deben tener 11 dígitos
    for (const [campo, etiqueta] of [['rucEmisor', 'RUC emisor'], ['rucReceptor', 'RUC receptor']]) {
      if (cfg[campo] && !/^\d{11}$/.test(cfg[campo])) throw new ErrorValidacion(`${etiqueta} debe tener 11 dígitos.`);
    }
    if (!cfg.codCpe) throw new ErrorValidacion('El código CPE es obligatorio (por ejemplo "09").');
    if (!/^[0-9A-Za-z]{1,4}$/.test(cfg.codCpe)) throw new ErrorValidacion('Código CPE inválido.');
    if (cfg.numCpe && !/^\d+$/.test(cfg.numCpe)) throw new ErrorValidacion('El número de comprobante debe contener solo dígitos.');
    if (!cfg.rucEmisor && !cfg.rucReceptor) log('Aviso: no indicó RUC emisor ni receptor. La API podría exigir uno de ellos.', 'warn');

    cfg.diasRango = dias;
    return Object.freeze(cfg);
  }

  /**
   * Obtiene el token, en este orden: opciones/campo del panel, token capturado
   * de la aplicación SUNAT, o prompt(). Nunca lo guarda de forma permanente.
   */
  function obtenerToken(op) {
    let t = op && typeof op.token === 'string' ? op.token : '';
    let origen = 'ingresado';
    if (!t.trim() && tokenCapturado) { t = tokenCapturado; origen = 'capturado de la aplicación'; }
    tokenCapturado = null; // se consume una sola vez
    if (!t.trim()) t = window.prompt('Pegue el token Bearer (solo se usa en memoria y se descarta al terminar):', '') || '';
    t = t.trim().replace(/^bearer\s+/i, '').trim();
    if (!t) throw new ErrorValidacion('No se ingresó el token Bearer. Pulse "Capturar desde SUNAT" o péguelo en el campo del token.');
    if (/\s/.test(t)) throw new ErrorValidacion('El token contiene espacios o saltos de línea. Cópielo nuevamente.');
    return { token: t, origen };
  }

  /**
   * Lee, solo localmente, la fecha de vencimiento de un token JWT.
   * No registra ni exporta ningún otro dato del token.
   */
  function analizarToken(token) {
    const partes = String(token || '').split('.');
    if (partes.length !== 3) return { tipo: 'opaco', exp: null };
    try {
      let b64 = partes[1].replace(/-/g, '+').replace(/_/g, '/');
      b64 += '='.repeat((4 - (b64.length % 4)) % 4);
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const carga = JSON.parse(new TextDecoder().decode(bytes));
      const exp = Number(carga && carga.exp);
      return { tipo: 'jwt', exp: Number.isFinite(exp) && exp > 0 ? exp * 1000 : null, sinFirma: !partes[2] };
    } catch (_) {
      return { tipo: 'ilegible', exp: null };
    }
  }

  /** Revisa el vencimiento antes de empezar. Devuelve el vencimiento (ms) o null si no se conoce. */
  function validarVencimientoToken(token, origen) {
    const info = analizarToken(token);
    if (info.tipo === 'ilegible' || info.sinFirma) {
      log('Aviso: el token no se pudo leer completo; puede estar cortado. Si falla, use "Capturar desde SUNAT" o cópielo de nuevo.', 'warn');
      return null;
    }
    if (!info.exp) {
      log(`Token ${origen}. No indica su vencimiento; se usará igual.`);
      return null;
    }
    const restante = info.exp - Date.now();
    if (restante <= 0) {
      throw new ErrorValidacion(`El token venció a las ${horaDe(info.exp)} (hace ${Math.max(1, Math.round(-restante / 60000))} min). ` +
        'Obtenga uno nuevo: pulse "Capturar desde SUNAT" y haga una búsqueda o abra una guía con "Ver".');
    }
    log(`Token ${origen}, válido hasta las ${horaDe(info.exp)} (quedan ${Math.floor(restante / 60000)} min).`, restante < 3 * 60000 ? 'warn' : 'ok');
    return info.exp;
  }

  /** Avisa si, por la cantidad de guías, el token podría vencer antes de terminar. */
  function avisarSiTokenNoAlcanza(ctx, unicos) {
    if (!ctx.tokenExp) return;
    const pendientes = unicos.filter((u) => !estado.previos.has(u.clave) && !estado.memoria.has(u.clave)).length;
    const estimadoMs = pendientes * ((ctx.cfg.pausaMinMs + ctx.cfg.pausaMaxMs) / 2 + 500);
    const restanteMs = ctx.tokenExp - Date.now();
    if (estimadoMs > restanteMs) {
      log(`Aviso: procesar ${pendientes} guía(s) tomaría unos ${Math.ceil(estimadoMs / 60000)} min, pero el token vence en ${Math.max(0, Math.floor(restanteMs / 60000))} min.`, 'warn');
      log('Si se detiene por token vencido: pulse "Capturar desde SUNAT", abra una guía con "Ver" y pulse Iniciar. Continuará donde quedó.', 'warn');
    }
  }

  /** Parámetros que sí pueden exportarse (nunca el token). */
  function parametrosExportables(cfg) {
    if (!cfg) return {};
    const claves = ['fechaInicio', 'fechaFin', 'rucEmisor', 'rucReceptor', 'codCpe', 'numSerie', 'numCpe',
      'codEstado', 'codSubEstado', 'rangoHoras', 'tipBusqueda', 'perPage', 'pausaMinMs', 'pausaMaxMs', 'maxReintentos'];
    const r = {};
    for (const k of claves) r[k] = cfg[k];
    return r;
  }

  /* ---------------------------------------------------------------
   * 6. Solicitud HTTP con reintentos
   * ------------------------------------------------------------- */
  function calcularEspera(intento, retryAfter) {
    if (retryAfter) {
      const seg = Number(retryAfter);
      if (Number.isFinite(seg) && seg >= 0) return Math.min(seg * 1000, 120000);
      const fecha = Date.parse(retryAfter);
      if (Number.isFinite(fecha)) return Math.min(Math.max(fecha - Date.now(), 1000), 120000);
    }
    return 1000 * Math.pow(2, intento - 1) + Math.floor(Math.random() * 250); // 1 s, 2 s, 4 s...
  }

  /** Extrae un mensaje corto del cuerpo de error, sin volcar datos completos. */
  function mensajeDeCuerpo(cuerpo) {
    if (!cuerpo) return '';
    try {
      const j = JSON.parse(cuerpo);
      const m = primero(j && j.msg, j && j.message, j && j.mensaje, j && j.error_description, j && j.error, j && j.cod);
      return m ? ` – ${texto(m).slice(0, 150)}` : '';
    } catch (_) { return ''; }
  }

  function errorTokenVencido(ctx, url, etiqueta, clave, intento) {
    const msg = `El token venció a las ${horaDe(ctx.tokenExp)}`;
    registrarError({ guia: etiqueta, clave, url, estadoHttp: '', mensaje: msg, intento, accion: 'PROCESO DETENIDO' });
    return new ErrorAutenticacion(0, url, `${msg}.`, 'DETENIDO_TOKEN_VENCIDO');
  }

  /**
   * GET con: credentials "omit", mode "cors", timeout, cancelación,
   * reintentos para 429/5xx/red, parada ante 401/403 y registro de errores.
   * Devuelve { ok, status, data, mensaje, intentos }.
   */
  async function pedirJSON(url, ctx, etiqueta, clave = '') {
    const { signal, cfg } = ctx;
    const totalIntentos = cfg.maxReintentos + 1;
    let ultimo = { ok: false, status: 0, mensaje: 'Sin respuesta', intentos: 0 };

    const fallar = (status, mensaje, intento, puedeReintentar, retryAfter) => {
      ultimo = { ok: false, status, mensaje, intentos: intento };
      if (puedeReintentar && intento < totalIntentos) {
        const espera = calcularEspera(intento, retryAfter);
        registrarError({ guia: etiqueta, clave, url, estadoHttp: status, mensaje, intento, accion: `REINTENTO en ${(espera / 1000).toFixed(1)} s` });
        log(`${etiqueta}: ${mensaje}. Reintento ${intento}/${totalIntentos - 1} en ${(espera / 1000).toFixed(1)} s.`, 'warn');
        return espera;
      }
      registrarError({ guia: etiqueta, clave, url, estadoHttp: status, mensaje, intento, accion: status === 404 ? 'OMITIDA (no encontrada)' : 'OMITIDA (sin más reintentos)' });
      return null;
    };

    for (let intento = 1; intento <= totalIntentos; intento++) {
      await esperarSiPausado(signal);
      if (signal.aborted) throw crearAbortError();
      // Si el token ya venció, no tiene sentido enviar más solicitudes.
      if (ctx.tokenExp && Date.now() >= ctx.tokenExp) throw errorTokenVencido(ctx, url, etiqueta, clave, intento);

      // Controlador por solicitud: se aborta por cancelación general o por timeout.
      const ctrl = new AbortController();
      let porTimeout = false;
      const alCancelar = () => ctrl.abort();
      signal.addEventListener('abort', alCancelar, { once: true });
      const temporizador = setTimeout(() => { porTimeout = true; ctrl.abort(); }, cfg.timeoutMs);

      let resp = null, cuerpo = '';
      try {
        // Misma forma que la solicitud que funciona en la aplicación (sin opciones adicionales).
        resp = await fetch(url, {
          method: 'GET',
          mode: 'cors',
          credentials: 'omit',
          headers: {
            accept: 'application/json, text/plain, */*',
            authorization: 'Bearer ' + ctx.token
          },
          signal: ctrl.signal
        });
        cuerpo = await resp.text();
      } catch (e) {
        clearTimeout(temporizador);
        signal.removeEventListener('abort', alCancelar);
        if (signal.aborted) throw crearAbortError();
        // Un token vencido suele verse como "Failed to fetch" (la API responde sin cabeceras CORS).
        if (ctx.tokenExp && Date.now() >= ctx.tokenExp) throw errorTokenVencido(ctx, url, etiqueta, clave, intento);
        const msg = porTimeout
          ? `Tiempo de espera agotado (${cfg.timeoutMs} ms)`
          : `La API no respondió o el navegador bloqueó la respuesta (${(e && e.message) || e})`;
        const espera = fallar(0, msg, intento, true);
        if (espera !== null) { await dormir(espera, signal); continue; }
        return ultimo;
      }
      clearTimeout(temporizador);
      signal.removeEventListener('abort', alCancelar);

      const status = resp.status;

      // 401 / 403: detener todo
      if (status === 401 || status === 403) {
        registrarError({ guia: etiqueta, clave, url, estadoHttp: status, mensaje: 'Sesión o token no autorizado/vencido', intento, accion: 'PROCESO DETENIDO' });
        throw new ErrorAutenticacion(status, url);
      }
      // 404: guía no encontrada, continuar
      if (status === 404) {
        fallar(404, 'Guía no encontrada (HTTP 404)' + mensajeDeCuerpo(cuerpo), intento, false);
        return ultimo;
      }
      // 429 y 5xx temporales: reintentar
      if (ESTADOS_REINTENTABLES.has(status)) {
        const espera = fallar(status, `HTTP ${status} temporal${mensajeDeCuerpo(cuerpo)}`, intento, true, resp.headers.get('retry-after'));
        if (espera !== null) { await dormir(espera, signal); continue; }
        return ultimo;
      }
      // Otros códigos no exitosos: no reintentar
      if (!resp.ok) {
        fallar(status, `HTTP ${status} ${resp.statusText || ''}`.trim() + mensajeDeCuerpo(cuerpo), intento, false);
        return ultimo;
      }
      // 2xx: validar cuerpo
      if (!cuerpo || !cuerpo.trim()) {
        const espera = fallar(status, 'Respuesta vacía', intento, true);
        if (espera !== null) { await dormir(espera, signal); continue; }
        return ultimo;
      }
      let data;
      try {
        data = JSON.parse(cuerpo);
      } catch (e) {
        const tipo = resp.headers.get('content-type') || '';
        const msg = (/html/i.test(tipo) || /^\s*</.test(cuerpo))
          ? 'Se recibió HTML en lugar de JSON (posible sesión vencida o redirección al login)'
          : `JSON inválido (${e.message})`;
        fallar(status, msg, intento, false);
        return ultimo;
      }
      return { ok: true, status, data, mensaje: '', intentos: intento };
    }
    return ultimo;
  }

  /* ---------------------------------------------------------------
   * 7. Listado paginado
   * ------------------------------------------------------------- */
  function construirUrlListado(cfg, page) {
    const p = new URLSearchParams();
    p.set('numRucEmisor', cfg.rucEmisor);
    p.set('numRucReceptor', cfg.rucReceptor);
    p.set('codCpe', cfg.codCpe);
    p.set('numSerie', cfg.numSerie);
    p.set('numCpe', cfg.numCpe);
    p.set('fecEmisionIni', cfg.fechaInicio);
    p.set('fecEmisionFin', cfg.fechaFin);
    p.set('codEstado', cfg.codEstado);
    p.set('codSubEstado', cfg.codSubEstado);
    p.set('rangoHoras', cfg.rangoHoras);
    p.set('page', String(page));
    p.set('per_page', String(cfg.perPage));
    p.set('tipBusqueda', cfg.tipBusqueda);
    return `${API_LISTADO}?${p.toString()}`;
  }

  async function obtenerListado(ctx) {
    const { cfg, signal } = ctx;
    const L = estado.listado;
    const todos = [];
    let page = 1;

    while (true) {
      if (signal.aborted) throw crearAbortError();
      log(`Consultando listado, página ${page}${L.totalPaginas ? ' de ' + L.totalPaginas : ''}...`);
      const url = construirUrlListado(cfg, page);
      const r = await pedirJSON(url, ctx, `LISTADO página ${page}`);

      if (!r.ok) {
        if (page === 1) {
          throw new ErrorDetencion(`No se pudo obtener la primera página del listado: ${r.mensaje}.`,
            r.status === 0 ? AYUDA_FALLO_CONEXION : []);
        }
        L.paginas.push({ page, esperados: esperadosEnPagina(L, page), recibidos: 0, ok: false, mensaje: r.mensaje, pageApi: '' });
        log(`Página ${page} del listado falló: ${r.mensaje}. Se continúa con la siguiente.`, 'error');
      } else {
        const data = r.data;
        if (!esObjetoPlano(data)) throw new ErrorDetencion('La respuesta del listado no es un objeto JSON.');
        const pag = esObjetoPlano(data.paginacion) ? data.paginacion : {};
        const items = Array.isArray(data.items) ? data.items : [];
        if (!Array.isArray(data.items)) log(`Advertencia: la página ${page} no contiene el arreglo "items".`, 'warn');

        if (page === 1) {
          const total = Number(pag.totalRegistros);
          const perPageApi = Number(pag.per_page);
          L.totalApi = Number.isFinite(total) && !esVacio(pag.totalRegistros) ? total : null;
          L.perPageApi = Number.isInteger(perPageApi) && perPageApi > 0 ? perPageApi : cfg.perPage;
          if (L.perPageApi !== cfg.perPage) log(`La API usa ${L.perPageApi} registros por página (se pidió ${cfg.perPage}).`, 'warn');
          if (L.totalApi !== null) {
            L.totalPaginas = L.totalApi === 0 ? 0 : Math.ceil(L.totalApi / L.perPageApi);
            log(`La API informa ${L.totalApi} registros en ${L.totalPaginas} página(s).`, 'ok');
          } else {
            log('La API no informó paginacion.totalRegistros; se paginará hasta recibir una página incompleta.', 'warn');
          }
          if (L.totalPaginas > cfg.maxPaginas) {
            log(`Se limitará a ${cfg.maxPaginas} páginas (tope de seguridad). Reduzca el rango de fechas.`, 'warn');
            L.totalPaginas = cfg.maxPaginas;
          }
        }
        L.paginas.push({
          page, esperados: esperadosEnPagina(L, page), recibidos: items.length, ok: true, mensaje: '',
          pageApi: texto(pag.page)
        });
        todos.push(...items);
      }

      const ultimaPagina = L.paginas[L.paginas.length - 1];
      const continuar = L.totalApi !== null
        ? page < L.totalPaginas
        : (ultimaPagina.ok && ultimaPagina.recibidos >= L.perPageApi && page < cfg.maxPaginas);
      if (!continuar) break;
      page++;
      await dormir(pausaAleatoria(cfg), signal);
    }

    L.registros = todos.length;
    log(`Listado completo: ${todos.length} registro(s) recibido(s).`, 'ok');
    return todos;
  }

  function esperadosEnPagina(L, page) {
    if (L.totalApi === null || !L.perPageApi) return '';
    return Math.max(0, Math.min(L.perPageApi, L.totalApi - (page - 1) * L.perPageApi));
  }

  /** Elimina duplicados por rucEmisor + codCpe + numSerie + numCpe. */
  function deduplicar(items) {
    const mapa = new Map();
    const duplicados = [];
    for (const it of items) {
      if (!esObjetoPlano(it)) continue;
      const clave = claveGuia(it.rucEmisor, it.codCpe, it.numSerie, it.numCpe);
      if (mapa.has(clave)) duplicados.push(clave);
      else mapa.set(clave, it);
    }
    return { unicos: [...mapa.entries()].map(([clave, item]) => ({ clave, item })), duplicados };
  }

  /* ---------------------------------------------------------------
   * 8. Detalle de cada guía
   * ------------------------------------------------------------- */
  function construirUrlDetalle(item) {
    const segmentos = [item.rucEmisor, item.codCpe, item.numSerie, item.numCpe]
      .map((v) => encodeURIComponent(texto(v).trim())); // numCpe sin ceros a la izquierda
    return `${API_LISTADO}/${segmentos.join('-')}`;
  }

  function crearRegistro(clave, item, extra = {}) {
    return {
      clave, listado: item || null, detalle: null, ok: false, procesada: false,
      http: '', intentos: 0, error: '', consultadoEn: '', origen: 'actual', ...extra
    };
  }

  function agregarControl(lista, tipo, guia, campo, valorListado, valorDetalle, detalle) {
    lista.push({ tipo, guia, campo, valorListado: texto(valorListado), valorDetalle: texto(valorDetalle), detalle });
  }

  /** Compara campos clave del listado con el detalle. */
  function compararListadoDetalle(clave, item, det) {
    if (!esObjetoPlano(item) || !esObjetoPlano(det)) return;
    const norm = (v) => { const s = texto(v).trim().toUpperCase(); return /^\d+$/.test(s) ? String(Number(s)) : s; };
    const pares = [['rucEmisor', 'numRuc'], ['codCpe', 'codCpe'], ['numSerie', 'numSerie'], ['numCpe', 'numCpe']];
    for (const [a, b] of pares) {
      const vl = item[a], vd = det[b];
      if (esVacio(vd)) {
        agregarControl(estado.controlDetalle, 'CAMPO_AUSENTE_EN_DETALLE', clave, `listado.${a} / detalle.${b}`, vl, '', 'El detalle no trae este campo');
      } else if (norm(vl) !== norm(vd)) {
        agregarControl(estado.controlDetalle, 'DIFERENCIA_LISTADO_DETALLE', clave, `listado.${a} / detalle.${b}`, vl, vd, 'Valores distintos');
      }
    }
  }

  async function obtenerDetalles(ctx) {
    const { cfg, signal } = ctx;
    const P = estado.progreso;
    P.total = estado.unicos.length;
    const yaObtenida = (clave) => estado.previos.get(clave) || estado.memoria.get(clave);
    P.pendientesReales = estado.unicos.filter((u) => !yaObtenida(u.clave)).length;
    estado.tiempos.inicioDetalle = Date.now();
    if (P.total > P.pendientesReales) {
      log(`Continuación: ${P.total - P.pendientesReales} guía(s) ya obtenidas antes no se volverán a consultar; quedan ${P.pendientesReales}.`, 'ok');
    }

    let consecutivos = 0;
    let primeraSolicitud = true;

    for (const { clave, item } of estado.unicos) {
      if (signal.aborted) throw crearAbortError();
      const reg = estado.resultados.get(clave);
      const etiqueta = guiaLegible(item.numSerie, item.numCpe) || clave;
      P.actual = etiqueta;

      // Ya recuperada antes (JSON anterior o ejecución anterior de esta sesión)
      const pv = yaObtenida(clave);
      if (pv) {
        const deArchivo = estado.previos.has(clave);
        Object.assign(reg, {
          detalle: pv.detalle, ok: true, procesada: true, http: 'REUTILIZADA',
          consultadoEn: pv.consultadoEn, origen: deArchivo ? 'previo' : 'memoria'
        });
        compararListadoDetalle(clave, item, pv.detalle);
        P.omitidas++; P.ok++; P.procesadas++;
        actualizarUI();
        continue;
      }

      await esperarSiPausado(signal);
      if (!primeraSolicitud) await dormir(pausaAleatoria(cfg), signal);
      primeraSolicitud = false;

      // Datos mínimos para construir la URL
      const faltan = ['rucEmisor', 'codCpe', 'numSerie', 'numCpe'].filter((k) => esVacio(item[k]));
      if (faltan.length) {
        const msg = `Datos incompletos en el listado: falta ${faltan.join(', ')}`;
        registrarError({ guia: etiqueta, clave, url: '', estadoHttp: '', mensaje: msg, intento: 0, accion: 'OMITIDA' });
        Object.assign(reg, { procesada: true, error: msg });
        P.error++; P.procesadas++;
        log(`${etiqueta}: ${msg}`, 'error');
        actualizarUI();
        continue;
      }

      const url = construirUrlDetalle(item);
      const r = await pedirJSON(url, ctx, etiqueta, clave);
      P.consultadas++;
      reg.procesada = true;
      reg.intentos = r.intentos;
      reg.http = r.status;
      reg.consultadoEn = fechaHoraLocal();

      if (r.ok && esObjetoPlano(r.data)) {
        reg.ok = true;
        reg.detalle = r.data;
        P.ok++;
        consecutivos = 0;
        compararListadoDetalle(clave, item, r.data);
        log(`${P.procesadas + 1}/${P.total} ${etiqueta} OK (${obtenerBienes(r.data).length} bien(es))`, 'ok');
      } else {
        reg.error = r.ok ? 'La respuesta no contiene un objeto de detalle' : r.mensaje;
        if (r.ok) registrarError({ guia: etiqueta, clave, url, estadoHttp: r.status, mensaje: reg.error, intento: r.intentos, accion: 'OMITIDA' });
        P.error++;
        if (r.status !== 404) consecutivos++;
        log(`${P.procesadas + 1}/${P.total} ${etiqueta} ERROR: ${reg.error}`, 'error');
      }
      P.procesadas++;
      actualizarUI();

      if (consecutivos >= cfg.maxErroresConsecutivos) {
        throw new ErrorDetencion(`Se detuvo el proceso tras ${consecutivos} errores consecutivos (posible caída de red o sesión). Los datos recuperados se conservan.`);
      }
    }
  }

  /* ---------------------------------------------------------------
   * 9. Proceso principal
   * ------------------------------------------------------------- */
  function reiniciarEstado(cfg) {
    estado.config = cfg;
    estado.motivoFin = 'EN_CURSO';
    estado.tiempos = { inicio: Date.now(), inicioDetalle: 0, fin: 0 };
    estado.listado = listadoVacio();
    estado.unicos = [];
    estado.duplicados = [];
    estado.resultados = new Map();
    estado.errores = [];
    estado.controlDetalle = [];
    estado.control = [];
    estado.progreso = progresoVacio();
    estado.resumen = null;
    estado.pausado = false;
    estado.controller = new AbortController();
  }

  /**
   * Función principal. Ejemplo:
   *   await GREExtractor.iniciarExtraccionGRE({ fechaInicio: '2026-11-01', fechaFin: '2026-11-03',
   *     rucReceptor: '20103913340', codCpe: '09', perPage: 100, pausaMs: 700 });
   * Si no se pasa "token", se pedirá con prompt().
   */
  async function iniciarExtraccionGRE(opciones = {}) {
    if (estado.ejecutando) {
      log('Ya existe una extracción en curso. Cancélela o espere a que termine.', 'warn');
      return null;
    }
    estado.ejecutando = true;
    let iniciado = false;
    const ctx = { token: null, tokenExp: null, signal: null, cfg: null };

    try {
      const cfg = normalizarConfig(opciones);
      detenerCaptura('inicio'); // no interceptar solicitudes durante la extracción
      const datosToken = obtenerToken(opciones);
      ctx.token = datosToken.token;
      datosToken.token = null;
      // Borrar el token del objeto recibido para que no quede referenciado.
      if (opciones && typeof opciones === 'object' && 'token' in opciones) { try { opciones.token = ''; } catch (_) { /* objeto congelado */ } }
      ctx.tokenExp = validarVencimientoToken(ctx.token, datosToken.origen);

      // Guías ya obtenidas en una ejecución anterior de esta sesión: permiten continuar donde quedó.
      const memoria = new Map();
      for (const r of estado.resultados.values()) {
        if (r.ok && esObjetoPlano(r.detalle)) memoria.set(r.clave, { detalle: r.detalle, consultadoEn: r.consultadoEn });
      }

      reiniciarEstado(cfg);
      estado.memoria = memoria;
      iniciado = true;
      ctx.cfg = cfg;
      ctx.signal = estado.controller.signal;
      actualizarUI();

      if (!/(^|\.)intranet\.sunat\.peru$/i.test(location.hostname)) {
        log(`Aviso: el contexto actual es ${location.origin}. Se esperaba intranet.sunat.peru (iframeApplication).`, 'warn');
      }
      log(`Inicio: ${cfg.fechaInicio} a ${cfg.fechaFin} (${cfg.diasRango} día(s)), CPE ${cfg.codCpe}.`);

      // 1) Listado
      const items = await obtenerListado(ctx);

      // 2) Duplicados
      const { unicos, duplicados } = deduplicar(items);
      estado.unicos = unicos;
      estado.duplicados = duplicados;
      if (duplicados.length) log(`Se eliminaron ${duplicados.length} registro(s) duplicado(s) del listado.`, 'warn');
      for (const { clave, item } of unicos) estado.resultados.set(clave, crearRegistro(clave, item));
      log(`Guías únicas a procesar: ${unicos.length}.`, 'ok');
      avisarSiTokenNoAlcanza(ctx, unicos);

      // 3) Detalles
      await obtenerDetalles(ctx);
      estado.motivoFin = 'COMPLETADO';
      log('Extracción completada.', 'ok');
    } catch (e) {
      if (esAbort(e)) {
        estado.motivoFin = 'CANCELADO';
        log('Proceso cancelado. Se conservan los resultados ya recuperados; puede descargarlos.', 'warn');
      } else if (e instanceof ErrorAutenticacion) {
        estado.motivoFin = e.codigo;
        log(`${e.message} Proceso detenido; lo ya obtenido se conserva.`, 'error');
        log('Para continuar: pulse "Capturar desde SUNAT", abra una guía con "Ver" y pulse Iniciar con los mismos filtros. Solo se consultarán las guías que faltan.', 'warn');
      } else if (e instanceof ErrorValidacion) {
        log(`Validación: ${e.message}`, 'error');
      } else if (e instanceof ErrorDetencion) {
        estado.motivoFin = 'DETENIDO';
        log(e.message, 'error');
        for (const linea of e.ayuda) log(linea, 'warn');
      } else {
        estado.motivoFin = 'ERROR';
        log(`Error inesperado: ${(e && e.message) || e}`, 'error');
        console.error(e);
      }
    } finally {
      // Descartar el token
      ctx.token = null;
      ctx.tokenExp = null;
      tokenCapturado = null;
      estado.ejecutando = false;
      estado.pausado = false;
      estado.controller = null;
      if (iniciado) {
        estado.tiempos.fin = Date.now();
        try { finalizar(); } catch (e) { log(`Error al generar el resumen: ${e.message}`, 'error'); }
      }
      actualizarUI();
    }
    return iniciado ? estado.resumen : null;
  }

  function pausar() {
    if (!estado.ejecutando) { log('No hay un proceso en curso.', 'warn'); return; }
    estado.pausado = true; log('Pausa solicitada (se aplica antes de la siguiente solicitud).', 'warn'); actualizarUI();
  }
  function reanudar() {
    if (!estado.ejecutando) { log('No hay un proceso en curso.', 'warn'); return; }
    if (!estado.pausado) return;
    estado.pausado = false; log('Proceso reanudado.', 'ok'); actualizarUI();
  }
  function cancelar() {
    if (!estado.ejecutando || !estado.controller) { log('No hay un proceso en curso.', 'warn'); return; }
    estado.pausado = false;
    estado.controller.abort();
    log('Cancelación solicitada...', 'warn');
  }

  /* ---------------------------------------------------------------
   * 10. Control de calidad y resumen
   * ------------------------------------------------------------- */
  function obtenerBienes(det) {
    const b = obtener(det, 'traslado.bien');
    if (Array.isArray(b)) return b.filter(esObjetoPlano);
    return esObjetoPlano(b) ? [b] : [];
  }

  function construirControl() {
    const C = [...estado.controlDetalle];
    const L = estado.listado;

    if (L.totalApi !== null && L.totalApi !== L.registros) {
      agregarControl(C, 'TOTAL_NO_COINCIDE', '', 'paginacion.totalRegistros vs registros recuperados', L.totalApi, L.registros,
        'La cantidad informada por la API no coincide con la recuperada');
    }
    for (const p of L.paginas) {
      if (!p.ok) agregarControl(C, 'PAGINA_FALLIDA', `página ${p.page}`, 'items', p.esperados, 0, p.mensaje);
      else if (p.esperados !== '' && p.recibidos < p.esperados) agregarControl(C, 'PAGINA_INCOMPLETA', `página ${p.page}`, 'items.length', p.esperados, p.recibidos, 'La página trajo menos registros de los esperados');
      if (p.ok && p.pageApi !== '' && Number(p.pageApi) !== p.page) agregarControl(C, 'PAGINA_NO_COINCIDE', `página ${p.page}`, 'paginacion.page', p.page, p.pageApi, 'La API devolvió otro número de página');
    }
    if (L.totalApi !== null && estado.motivoFin === 'COMPLETADO' && L.paginas.length < L.totalPaginas) {
      agregarControl(C, 'PAGINAS_FALTANTES', '', 'páginas', L.totalPaginas, L.paginas.length, 'No se consultaron todas las páginas');
    }
    for (const d of estado.duplicados) agregarControl(C, 'GUIA_REPETIDA_EN_LISTADO', d, 'clave', d, '', 'Registro duplicado eliminado');

    for (const r of estado.resultados.values()) {
      if (!r.procesada) agregarControl(C, 'GUIA_NO_PROCESADA', r.clave, '', '', '', `Proceso finalizado como ${estado.motivoFin}`);
      else if (!r.ok) agregarControl(C, 'GUIA_SIN_DETALLE', r.clave, 'HTTP', '', r.http, r.error);
      else if (obtenerBienes(r.detalle).length === 0) agregarControl(C, 'GUIA_SIN_BIENES', r.clave, 'traslado.bien', '', '0', 'La guía no tiene bienes');
      if (r.origen === 'previo_fuera_del_listado') agregarControl(C, 'PREVIO_FUERA_DEL_LISTADO', r.clave, '', '', '', 'Guía del JSON anterior que no aparece en el listado actual');
    }
    estado.control = C;
  }

  function calcularResumen() {
    const regs = [...estado.resultados.values()];
    const ok = regs.filter((r) => r.ok);
    const L = estado.listado, P = estado.progreso, T = estado.tiempos;
    const totalBienes = ok.reduce((s, r) => s + obtenerBienes(r.detalle).length, 0);
    const tiempoTotal = (T.fin || Date.now()) - T.inicio;
    const tiempoDetalle = T.inicioDetalle ? (T.fin || Date.now()) - T.inicioDetalle : 0;
    return {
      'Estado final': estado.motivoFin,
      'Rango': estado.config ? `${estado.config.fechaInicio} a ${estado.config.fechaFin}` : '',
      'Total informado por la API': L.totalApi === null ? '' : L.totalApi,
      'Registros obtenidos del listado': L.registros,
      'Páginas esperadas / consultadas': `${L.totalPaginas} / ${L.paginas.length}`,
      'Guías únicas': estado.unicos.length,
      'Duplicados eliminados': estado.duplicados.length,
      'Detalles correctos': ok.length,
      '  de ellos reutilizados (JSON previo o esta sesión)': regs.filter((r) => r.ok && r.origen !== 'actual').length,
      'Guías con error': regs.filter((r) => r.procesada && !r.ok).length,
      'Guías no procesadas': regs.filter((r) => !r.procesada).length,
      'Entradas en registro de errores': estado.errores.length,
      'Total de bienes': totalBienes,
      'Guías sin bienes': ok.filter((r) => obtenerBienes(r.detalle).length === 0).length,
      'Observaciones de control': estado.control.length,
      'Tiempo total': duracion(tiempoTotal),
      'Promedio por guía consultada': P.consultadas ? `${(tiempoDetalle / P.consultadas / 1000).toFixed(2)} s` : ''
    };
  }

  function finalizar() {
    // Incluir guías del JSON previo que no aparecieron en el listado actual
    for (const [clave, pv] of estado.previos) {
      if (!estado.resultados.has(clave)) {
        estado.resultados.set(clave, crearRegistro(clave, null, {
          detalle: pv.detalle, ok: true, procesada: true, http: 'PREVIO',
          consultadoEn: pv.consultadoEn, origen: 'previo_fuera_del_listado'
        }));
      }
    }
    estado.memoria = new Map();
    construirControl();
    estado.resumen = calcularResumen();

    console.log('%c[GRE] RESUMEN', 'color:#0a7d55;font-weight:bold;font-size:13px');
    console.table(estado.resumen);
    if (estado.control.length) {
      const porTipo = {};
      for (const c of estado.control) porTipo[c.tipo] = (porTipo[c.tipo] || 0) + 1;
      console.log('%c[GRE] Control de calidad (cantidad por tipo)', 'color:#b36b00;font-weight:bold');
      console.table(porTipo);
    }
    for (const [k, v] of Object.entries(estado.resumen)) log(`${k.trim()}: ${v}`, 'info');
    log('Use los botones de descarga o GREExtractor.descargarTodo().', 'ok');
  }

  /* ---------------------------------------------------------------
   * 11. Aplanamiento genérico
   * ------------------------------------------------------------- */
  /**
   * Convierte un objeto anidado en { "ruta.a.b": valorPrimitivo }.
   * - Arreglos de primitivos: se unen con " | ".
   * - Arreglos de objetos (o vacíos): solo se registra "<ruta>[cantidad]";
   *   su contenido se exporta en archivos separados.
   */
  function flattenObject(valor, prefijo = '', salida = {}) {
    if (esPrimitivo(valor)) {
      if (prefijo) salida[prefijo] = valor instanceof Date ? texto(valor) : valor;
      return salida;
    }
    if (Array.isArray(valor)) {
      if (valor.length > 0 && valor.every(esPrimitivo)) salida[prefijo] = valor.map(texto).filter((s) => s !== '').join(' | ');
      else salida[`${prefijo}[cantidad]`] = valor.length;
      return salida;
    }
    if (esObjetoPlano(valor)) {
      const claves = Object.keys(valor);
      if (!claves.length && prefijo) salida[prefijo] = '';
      for (const k of claves) flattenObject(valor[k], prefijo ? `${prefijo}.${k}` : k, salida);
    }
    return salida;
  }

  /* ---------------------------------------------------------------
   * 12. Extracción de datos legibles (sin inventar propiedades)
   * ------------------------------------------------------------- */
  function subnodos(n) {
    return esObjetoPlano(n) ? [n, ...Object.values(n).filter(esObjetoPlano)] : [];
  }

  function datosPersona(nodo) {
    const lista = Array.isArray(nodo) ? nodo.filter(esObjetoPlano) : (esObjetoPlano(nodo) ? [nodo] : []);
    const una = (n) => {
      const nodos = subnodos(n);
      return {
        tipoDoc: texto(buscarClave(nodos, [/^codTip.*Doc/i, /tip.*doc/i])),
        numDoc: texto(buscarClave(nodos, [/^numDocIdentidad$/i, /^numDoc/i, /^numRuc$/i, /doc.*ident/i, /ruc/i])),
        nombre: texto(buscarClave(nodos, [/raz[oó]n/i, /^desNombre/i, /^nomb/i, /^nom[A-Z_]/, /nombre/i, /apellido/i]))
      };
    };
    const datos = lista.map(una);
    const unir = (campo) => datos.map((d) => d[campo]).filter(Boolean).join(' | ');
    return { tipoDoc: unir('tipoDoc'), numDoc: unir('numDoc'), nombre: unir('nombre') };
  }

  function datosDireccion(nodo) {
    if (!esObjetoPlano(nodo)) return { direccion: '', ubigeo: '', departamento: '', provincia: '', distrito: '', ruc: '', establecimiento: '' };
    const nodos = [nodo.direccion, ...subnodos(nodo)].filter(esObjetoPlano);
    return {
      direccion: texto(buscarClave(nodos, [/^desDireccion/i, /direcci[oó]n/i, /^desDir/i])),
      ubigeo: texto(buscarClave(nodos, [/ubigeo/i])),
      departamento: texto(buscarClave(nodos, [/^desDepartamento/i, /departamento|dpto/i])),
      provincia: texto(buscarClave(nodos, [/^desProvincia/i, /provincia/i])),
      distrito: texto(buscarClave(nodos, [/^desDistrito/i, /distrito/i])),
      ruc: texto(buscarClave(nodos, [/^numRuc$/i, /ruc/i])),
      establecimiento: texto(buscarClave(nodos, [/^(des|nom).*establec/i, /establec/i, /local/i]))
    };
  }

  function textoDeArreglo(valor) {
    if (valor === undefined || valor === null) return '';
    const lista = Array.isArray(valor) ? valor : [valor];
    return lista.map((v) => {
      if (esPrimitivo(v)) return texto(v);
      if (esObjetoPlano(v)) return Object.values(flattenObject(v)).map(texto).filter(Boolean).join(' ');
      return '';
    }).filter(Boolean).join(' | ');
  }

  const COLUMNAS_GUIAS = [
    'Clave', 'ID interno', 'RUC emisor', 'Nombre emisor', 'Código CPE', 'Tipo CPE', 'Serie', 'Número', 'Guía completa',
    'Código estado', 'Estado', 'Fecha emisión', 'Fecha generación CDR', 'Observaciones guía', 'Observaciones receptor',
    'Código motivo traslado', 'Motivo traslado', 'Fecha inicio traslado', 'Fecha entrega', 'Modalidad traslado',
    'Bultos/Pallets', 'Unidad peso', 'Peso bruto', 'Placa',
    'Partida dirección', 'Partida ubigeo', 'Partida departamento', 'Partida provincia', 'Partida distrito', 'Partida RUC establecimiento', 'Partida establecimiento',
    'Llegada dirección', 'Llegada ubigeo', 'Llegada departamento', 'Llegada provincia', 'Llegada distrito', 'Llegada RUC establecimiento', 'Llegada establecimiento',
    'Receptor tipo doc.', 'Receptor documento', 'Receptor nombre',
    'Proveedor documento', 'Proveedor nombre', 'Comprador documento', 'Comprador nombre',
    'Transportista documento', 'Transportista nombre', 'Registro MTC',
    'Cantidad bienes', 'Usuario registro', 'Fecha registro', 'Usuario modificación', 'Fecha modificación',
    'Origen', 'Consulta correcta', 'HTTP', 'Intentos', 'Consultado en', 'Mensaje error'
  ];

  /** Datos de identificación comunes (de detalle o, si falta, del listado). */
  function datosBase(reg) {
    const d = reg.detalle || {}, it = reg.listado || {};
    const ruc = primero(d.numRuc, obtener(d, 'emisor.numRuc'), it.rucEmisor);
    const serie = primero(d.numSerie, it.numSerie);
    const num = primero(d.numCpe, it.numCpe);
    const emisor = d.emisor;
    const traslado = esObjetoPlano(d.traslado) ? d.traslado : {};
    const partida = datosDireccion(traslado.partida);
    const llegada = datosDireccion(traslado.llegada);
    const transp = datosPersona(traslado.transportista);
    return {
      d, it, traslado, partida, llegada, transp,
      ruc: texto(ruc),
      nombreEmisor: texto(buscarClave(subnodos(emisor), [/raz[oó]n/i, /^desNombre/i, /^nomb/i, /^nom[A-Z_]/, /nombre/i])),
      serie: texto(serie),
      num: texto(num),
      guia: guiaLegible(serie, num),
      fecEmision: texto(primero(obtener(d, 'emision.fecEmision'), d.fecEmision, it.fecEmision)),
      estado: texto(primero(d.desEstado, it.desEstado)),
      motivo: [texto(traslado.codMotivoTraslado), texto(traslado.desMotivoTraslado)].filter(Boolean).join(' - ')
    };
  }

  function filaGuia(reg) {
    const b = datosBase(reg);
    const { d, it, traslado } = b;
    const receptor = datosPersona(d.receptor);
    const proveedor = datosPersona(traslado.proveedor);
    const comprador = datosPersona(traslado.comprador);
    const aud = subnodos(d.auditoria);
    const fila = {
      'Clave': reg.clave,
      'ID interno': texto(d.id),
      'RUC emisor': b.ruc,
      'Nombre emisor': b.nombreEmisor,
      'Código CPE': texto(primero(d.codCpe, it.codCpe)),
      'Tipo CPE': texto(primero(d.desTipoCpe, it.desCpe)),
      'Serie': b.serie,
      'Número': b.num,
      'Guía completa': b.guia,
      'Código estado': texto(primero(d.codEstado, it.codEstado)),
      'Estado': b.estado,
      'Fecha emisión': b.fecEmision,
      'Fecha generación CDR': texto(primero(it.fecGenCdr, d.fecGenCdr, obtener(d, 'emision.fecGenCdr'))),
      'Observaciones guía': texto(primero(obtener(d, 'emision.desObservacion'), buscarClave(subnodos(d.emision), [/observ/i, /^desObs/i]))),
      'Observaciones receptor': textoDeArreglo(buscarProfundo(d, 'receptorObs')),
      'Código motivo traslado': texto(traslado.codMotivoTraslado),
      'Motivo traslado': texto(traslado.desMotivoTraslado),
      'Fecha inicio traslado': texto(traslado.fecInicioTraslado),
      'Fecha entrega': texto(traslado.fecEntrega),
      'Modalidad traslado': texto(primero(traslado.desModalidadTraslado, traslado.codModalidadTraslado)),
      'Bultos/Pallets': texto(traslado.numBultosPallets),
      'Unidad peso': texto(traslado.codUnidadMedidaPb),
      'Peso bruto': texto(traslado.numPesoBruto),
      'Placa': texto(primero(traslado.numPlacaVehiculo, buscarClave(subnodos(Array.isArray(traslado.vehiculo) ? traslado.vehiculo[0] : traslado.vehiculo), [/placa/i]))),
      'Partida dirección': b.partida.direccion,
      'Partida ubigeo': b.partida.ubigeo,
      'Partida departamento': b.partida.departamento,
      'Partida provincia': b.partida.provincia,
      'Partida distrito': b.partida.distrito,
      'Partida RUC establecimiento': b.partida.ruc,
      'Partida establecimiento': b.partida.establecimiento,
      'Llegada dirección': b.llegada.direccion,
      'Llegada ubigeo': b.llegada.ubigeo,
      'Llegada departamento': b.llegada.departamento,
      'Llegada provincia': b.llegada.provincia,
      'Llegada distrito': b.llegada.distrito,
      'Llegada RUC establecimiento': b.llegada.ruc,
      'Llegada establecimiento': b.llegada.establecimiento,
      'Receptor tipo doc.': receptor.tipoDoc,
      'Receptor documento': primero(receptor.numDoc, it.rucReceptor),
      'Receptor nombre': receptor.nombre,
      'Proveedor documento': proveedor.numDoc,
      'Proveedor nombre': proveedor.nombre,
      'Comprador documento': comprador.numDoc,
      'Comprador nombre': comprador.nombre,
      'Transportista documento': b.transp.numDoc,
      'Transportista nombre': b.transp.nombre,
      'Registro MTC': texto(buscarClave(subnodos(Array.isArray(traslado.transportista) ? traslado.transportista[0] : traslado.transportista), [/mtc/i])),
      'Cantidad bienes': reg.ok ? obtenerBienes(d).length : '',
      'Usuario registro': texto(buscarClave(aud, [/usu.*reg/i])),
      'Fecha registro': texto(buscarClave(aud, [/fec.*reg/i])),
      'Usuario modificación': texto(buscarClave(aud, [/usu.*mod/i])),
      'Fecha modificación': texto(buscarClave(aud, [/fec.*mod/i])),
      'Origen': reg.origen,
      'Consulta correcta': reg.ok ? 'SI' : (reg.procesada ? 'NO' : 'NO_PROCESADA'),
      'HTTP': texto(reg.http),
      'Intentos': texto(reg.intentos),
      'Consultado en': reg.consultadoEn,
      'Mensaje error': reg.error
    };
    // Columnas dinámicas: todas las propiedades primitivas del detalle.
    if (reg.detalle) Object.assign(fila, flattenObject(reg.detalle));
    return fila;
  }

  const CAMPOS_BIEN_MAPEADOS = new Set(['numOrden', 'codBien', 'codProductoSunat', 'codSubPartida', 'codGtin', 'desBien',
    'codUniMedida', 'desUniMedida', 'numCantidad', 'indBienRegulado', 'numContenedor', 'numPrecinto']);

  function filasBienes(reg) {
    const b = datosBase(reg);
    const base = {
      'Clave': reg.clave, 'RUC emisor': b.ruc, 'Nombre emisor': b.nombreEmisor, 'Serie': b.serie, 'Número': b.num,
      'Guía completa': b.guia, 'Fecha emisión': b.fecEmision, 'Estado': b.estado, 'Motivo traslado': b.motivo,
      'Partida': [b.partida.direccion, b.partida.ubigeo].filter(Boolean).join(' - '),
      'Llegada': [b.llegada.direccion, b.llegada.ubigeo].filter(Boolean).join(' - '),
      'Transportista': [b.transp.numDoc, b.transp.nombre].filter(Boolean).join(' - ')
    };
    if (!reg.ok) return [{ ...base, 'Indicador bienes': reg.procesada ? 'SIN_DETALLE' : 'NO_PROCESADA' }];
    const bienes = obtenerBienes(reg.detalle);
    if (!bienes.length) return [{ ...base, 'Indicador bienes': 'SIN_BIENES' }];

    return bienes.map((bien) => {
      const extra = {};
      for (const [k, v] of Object.entries(flattenObject(bien))) {
        const raiz = k.split(/[.[]/)[0];
        if (!CAMPOS_BIEN_MAPEADOS.has(raiz)) extra['bien.' + k] = v;
      }
      return {
        ...base,
        'Indicador bienes': 'CON_BIENES',
        'N° orden': texto(bien.numOrden),
        'Código bien': texto(bien.codBien),
        'Código producto SUNAT': texto(bien.codProductoSunat),
        'Subpartida': texto(bien.codSubPartida),
        'GTIN': texto(bien.codGtin),
        'Descripción bien': texto(bien.desBien),
        'Unidad medida': texto(bien.codUniMedida),
        'Descripción unidad': texto(bien.desUniMedida),
        'Cantidad': texto(bien.numCantidad),
        'Bien regulado': texto(bien.indBienRegulado),
        'Documento relacionado': textoDeArreglo(bien.docRelacionado),
        'Contenedor': texto(bien.numContenedor),
        'Precinto': texto(bien.numPrecinto),
        'Contenedor vacío': texto(primero(
          buscarClave([bien], [/contenedor.*vac|vac.*contenedor|^indVacio$/i]),
          buscarClave([b.traslado], [/contenedor.*vac|vac.*contenedor/i])
        )),
        ...extra
      };
    });
  }

  const COLUMNAS_BIENES = ['Clave', 'RUC emisor', 'Nombre emisor', 'Serie', 'Número', 'Guía completa', 'Fecha emisión', 'Estado',
    'Motivo traslado', 'Partida', 'Llegada', 'Transportista', 'Indicador bienes', 'N° orden', 'Código bien', 'Código producto SUNAT',
    'Subpartida', 'GTIN', 'Descripción bien', 'Unidad medida', 'Descripción unidad', 'Cantidad', 'Bien regulado',
    'Documento relacionado', 'Contenedor', 'Precinto', 'Contenedor vacío'];

  /* ---------------------------------------------------------------
   * 13. Colecciones (arreglos) en archivos adicionales
   * ------------------------------------------------------------- */
  const ARCHIVO_POR_COLECCION = {
    proveedor: 'GRE_PROVEEDORES', conductor: 'GRE_CONDUCTORES', vehiculo: 'GRE_VEHICULOS',
    contenedores: 'GRE_CONTENEDORES', contenedor: 'GRE_CONTENEDORES', receptorObs: 'GRE_OBSERVACIONES',
    docRelacionado: 'GRE_DOCUMENTOS_RELACIONADOS', docGrePorEvento: 'GRE_DOC_GRE_POR_EVENTO'
  };
  // Si estas propiedades vienen como objeto (no arreglo), también se exportan como una fila.
  const OBJETOS_COMO_COLECCION = new Set(['proveedor', 'conductor', 'vehiculo', 'contenedores']);
  const COLUMNAS_COLECCION = ['Clave', 'RUC emisor', 'Serie', 'Número', 'Guía completa', 'Fecha emisión', 'Colección', 'Índice', 'Índice padre'];

  function nombreArchivoColeccion(clave, ruta) {
    return ARCHIVO_POR_COLECCION[clave] || ('GRE_ARR_' + ruta.replace(/\[\]/g, '').replace(/[^A-Za-z0-9]+/g, '_').toUpperCase());
  }

  function recolectarColecciones(reg, salida) {
    const b = datosBase(reg);
    const base = { 'Clave': reg.clave, 'RUC emisor': b.ruc, 'Serie': b.serie, 'Número': b.num, 'Guía completa': b.guia, 'Fecha emisión': b.fecEmision };

    const agregar = (archivo, fila) => {
      if (!salida.has(archivo)) salida.set(archivo, []);
      salida.get(archivo).push(fila);
    };

    const recorrer = (nodo, ruta, indicePadre) => {
      if (!esObjetoPlano(nodo)) return;
      for (const [k, v] of Object.entries(nodo)) {
        const r = ruta ? `${ruta}.${k}` : k;
        if (Array.isArray(v)) {
          const esBien = r === 'traslado.bien';
          v.forEach((elem, i) => {
            const indice = indicePadre ? `${indicePadre}/${i + 1}` : String(i + 1);
            if (!esBien) {
              const fila = { ...base, 'Colección': r, 'Índice': i + 1, 'Índice padre': indicePadre };
              if (esObjetoPlano(elem)) Object.assign(fila, flattenObject(elem));
              else if (esPrimitivo(elem)) fila['valor'] = elem;
              agregar(nombreArchivoColeccion(k, r), fila);
            }
            if (esObjetoPlano(elem)) recorrer(elem, `${r}[]`, indice); // arreglos anidados
          });
        } else if (esObjetoPlano(v)) {
          if (OBJETOS_COMO_COLECCION.has(k)) {
            agregar(nombreArchivoColeccion(k, r), { ...base, 'Colección': r, 'Índice': 1, 'Índice padre': indicePadre, ...flattenObject(v) });
          }
          recorrer(v, r, indicePadre);
        }
      }
    };
    recorrer(reg.detalle, '', '');
  }

  /* ---------------------------------------------------------------
   * 14. CSV y descargas
   * ------------------------------------------------------------- */
  /** Sanitiza una celda: sin null/undefined, sin saltos de línea, comillas escapadas y protección anti-fórmulas. */
  function celdaCSV(v) {
    let s;
    if (v === null || v === undefined) s = '';
    else if (typeof v === 'number') s = Number.isFinite(v) ? String(v) : '';
    else if (typeof v === 'boolean') s = v ? 'true' : 'false';
    else if (v instanceof Date) s = isNaN(v.getTime()) ? '' : v.toISOString();
    else if (typeof v === 'object') { try { s = JSON.stringify(v); } catch (_) { s = ''; } }
    else {
      s = String(v).replace(/\r\n|\r|\n|\u2028|\u2029|\t/g, ' ');
      if (/^[=+\-@]/.test(s)) s = "'" + s; // evita fórmulas inyectadas en Excel
    }
    s = s.replace(/\r\n|\r|\n|\u2028|\u2029|\t/g, ' ');
    return '"' + s.replace(/"/g, '""') + '"';
  }

  function unirColumnas(base, filas) {
    const cols = [...base];
    const vistas = new Set(cols);
    for (const f of filas) for (const k of Object.keys(f)) if (!vistas.has(k)) { vistas.add(k); cols.push(k); }
    return cols;
  }

  function generarCSV(columnas, filas) {
    const lineas = [columnas.map(celdaCSV).join(';')];
    for (const f of filas) lineas.push(columnas.map((c) => celdaCSV(f[c])).join(';'));
    return '﻿' + lineas.join('\r\n') + '\r\n';
  }

  /** Construye todos los archivos con los datos reales en memoria. */
  function construirArchivos() {
    const cfg = estado.config;
    const marca = marcaTiempo();
    const sufijo = cfg ? `${cfg.fechaInicio}_a_${cfg.fechaFin}_${marca}` : `sin_rango_${marca}`;
    const regs = [...estado.resultados.values()];
    const archivos = [];
    const csv = 'text/csv;charset=utf-8';

    // A. Guías
    const fGuias = regs.map(filaGuia);
    archivos.push({ tipo: 'guias', nombre: `GRE_GUIAS_${sufijo}.csv`, tipoMime: csv, filas: fGuias.length,
      contenido: generarCSV(unirColumnas(COLUMNAS_GUIAS, fGuias), fGuias) });

    // B. Bienes
    const fBienes = regs.flatMap(filasBienes);
    archivos.push({ tipo: 'bienes', nombre: `GRE_BIENES_${sufijo}.csv`, tipoMime: csv, filas: fBienes.length,
      contenido: generarCSV(unirColumnas(COLUMNAS_BIENES, fBienes), fBienes) });

    // C. Errores
    const colsErr = ['Guía', 'Clave', 'URL', 'Estado HTTP', 'Mensaje', 'Número de intento', 'Fecha y hora', 'Acción tomada'];
    const fErr = estado.errores.map((e) => ({
      'Guía': e.guia, 'Clave': e.clave, 'URL': e.url, 'Estado HTTP': e.estadoHttp, 'Mensaje': e.mensaje,
      'Número de intento': e.intento, 'Fecha y hora': e.fechaHora, 'Acción tomada': e.accion
    }));
    archivos.push({ tipo: 'errores', nombre: `GRE_ERRORES_${sufijo}.csv`, tipoMime: csv, filas: fErr.length, contenido: generarCSV(colsErr, fErr) });

    // D. JSON completo (solo detalles correctos, estructura original intacta, sin token)
    const detalles = regs.filter((r) => r.ok && r.detalle).map((r) => ({
      clave: r.clave, consultadoEn: r.consultadoEn, origen: r.origen, detalle: r.detalle
    }));
    const json = {
      formato: 'GRE_EXTRACTOR_JSON', version: VERSION, generadoEn: fechaHoraLocal(),
      estadoFinal: estado.motivoFin, parametros: parametrosExportables(cfg),
      totales: { detalles: detalles.length, errores: estado.errores.length }, detalles
    };
    archivos.push({ tipo: 'json', nombre: `GRE_JSON_COMPLETO_${sufijo}.json`, tipoMime: 'application/json;charset=utf-8',
      filas: detalles.length, contenido: JSON.stringify(json, null, 2) });

    // E. Control de calidad + resumen
    const colsCtl = ['Tipo', 'Guía', 'Campo', 'Valor listado', 'Valor detalle', 'Detalle'];
    const fCtl = [];
    for (const [k, v] of Object.entries(estado.resumen || calcularResumen())) {
      fCtl.push({ 'Tipo': 'RESUMEN', 'Guía': '', 'Campo': k.trim(), 'Valor listado': texto(v), 'Valor detalle': '', 'Detalle': '' });
    }
    for (const c of estado.control) {
      fCtl.push({ 'Tipo': c.tipo, 'Guía': c.guia, 'Campo': c.campo, 'Valor listado': c.valorListado, 'Valor detalle': c.valorDetalle, 'Detalle': c.detalle });
    }
    archivos.push({ tipo: 'control', nombre: `GRE_CONTROL_${sufijo}.csv`, tipoMime: csv, filas: fCtl.length, contenido: generarCSV(colsCtl, fCtl) });

    // F. Archivos adicionales por arreglo
    const colecciones = new Map();
    for (const r of regs) if (r.ok && r.detalle) recolectarColecciones(r, colecciones);
    for (const [nombre, filas] of colecciones) {
      archivos.push({ tipo: 'adicionales', nombre: `${nombre}_${sufijo}.csv`, tipoMime: csv, filas: filas.length,
        contenido: generarCSV(unirColumnas(COLUMNAS_COLECCION, filas), filas) });
    }
    return archivos;
  }

  function descargarArchivo(nombre, contenido, tipoMime) {
    const blob = new Blob([contenido], { type: tipoMime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = nombre; a.style.display = 'none';
    (document.body || document.documentElement).appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  /** tipos: 'todo' | 'guias' | 'bienes' | 'errores' | 'json' | 'control' | 'adicionales' */
  async function descargar(tipo = 'todo') {
    if (!estado.resultados.size && !estado.errores.length) { log('Todavía no hay datos para descargar.', 'warn'); return []; }
    let archivos;
    try { archivos = construirArchivos(); } catch (e) { log(`No se pudieron generar los archivos: ${e.message}`, 'error'); console.error(e); return []; }
    const elegidos = tipo === 'todo' ? archivos : archivos.filter((a) => a.tipo === tipo);
    if (!elegidos.length) { log(`No hay archivos del tipo "${tipo}".`, 'warn'); return []; }
    for (const a of elegidos) {
      try { descargarArchivo(a.nombre, a.contenido, a.tipoMime); log(`Descargado: ${a.nombre} (${a.filas} fila(s))`, 'ok'); }
      catch (e) { log(`Descarga bloqueada de ${a.nombre}: ${e.message}`, 'error'); }
      await dormir(450); // pausa para que el navegador no bloquee descargas múltiples
    }
    return elegidos.map((a) => a.nombre);
  }
  const descargarTodo = () => descargar('todo');

  /** Devuelve el contenido de los archivos (alternativa si las descargas están bloqueadas). */
  function exportar() {
    const r = {};
    for (const a of construirArchivos()) r[a.nombre] = a.contenido;
    return r;
  }

  /* ---------------------------------------------------------------
   * 15. Reanudación desde GRE_JSON_COMPLETO.json
   * ------------------------------------------------------------- */
  async function cargarJSONPrevio(fuente) {
    if (estado.ejecutando) { log('No se puede cargar un JSON mientras hay una extracción en curso.', 'warn'); return null; }
    try {
      let obj;
      if (typeof Blob !== 'undefined' && fuente instanceof Blob) obj = JSON.parse(await fuente.text());
      else if (typeof fuente === 'string') obj = JSON.parse(fuente);
      else if (fuente && typeof fuente === 'object') obj = fuente;
      else throw new Error('Indique un archivo, texto JSON u objeto.');

      const lista = Array.isArray(obj) ? obj : (obj && Array.isArray(obj.detalles) ? obj.detalles : null);
      if (!lista) throw new Error('Formato no reconocido: se esperaba GRE_JSON_COMPLETO (propiedad "detalles").');

      let cargadas = 0, invalidas = 0;
      for (const e of lista) {
        const det = esObjetoPlano(e) && esObjetoPlano(e.detalle) ? e.detalle : (esObjetoPlano(e) ? e : null);
        const clave = esObjetoPlano(e) && typeof e.clave === 'string' && e.clave.trim() ? e.clave.trim() : claveDesdeDetalle(det);
        if (!det || !clave) { invalidas++; continue; }
        estado.previos.set(clave, { detalle: det, consultadoEn: esObjetoPlano(e) ? texto(e.consultadoEn) : '' });
        cargadas++;
      }
      log(`JSON previo cargado: ${cargadas} guía(s) válidas${invalidas ? `, ${invalidas} entrada(s) ignorada(s)` : ''}. Total en memoria: ${estado.previos.size}.`, 'ok');
      actualizarUI();
      return { cargadas, invalidas, total: estado.previos.size };
    } catch (e) {
      log(`No se pudo leer el JSON previo: ${e.message}`, 'error');
      return null;
    }
  }

  /** Abre el selector de archivos (útil sin panel). */
  function seleccionarJSONPrevio() {
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = '.json,application/json';
      input.addEventListener('change', async () => {
        const f = input.files && input.files[0];
        resolve(f ? await cargarJSONPrevio(f) : null);
      }, { once: true });
      input.click();
    });
  }

  function limpiarPrevios() {
    if (estado.ejecutando) { log('No se puede limpiar durante una extracción.', 'warn'); return; }
    estado.previos.clear(); log('Se descartó el JSON previo cargado.', 'ok'); actualizarUI();
  }

  /** Olvida todo lo obtenido (resultados, errores y JSON previo) para que la próxima ejecución consulte todo de nuevo. */
  function olvidarResultados() {
    if (estado.ejecutando) { log('No se puede limpiar durante una extracción.', 'warn'); return; }
    estado.resultados = new Map();
    estado.previos.clear();
    estado.memoria = new Map();
    estado.errores = []; estado.control = []; estado.controlDetalle = [];
    estado.unicos = []; estado.duplicados = [];
    estado.listado = listadoVacio(); estado.progreso = progresoVacio();
    estado.resumen = null; estado.motivoFin = ''; estado.tiempos = { inicio: 0, inicioDetalle: 0, fin: 0 };
    log('Se olvidaron los resultados anteriores. La próxima ejecución consultará todas las guías.', 'ok');
    actualizarUI();
  }

  /* ---------------------------------------------------------------
   * 16. Captura del token y de los filtros desde la propia aplicación SUNAT
   *     Escucha temporalmente (máx. 5 min) las solicitudes que la pantalla de
   *     SUNAT hace a la API de GRE en esta misma pestaña, y toma su token y,
   *     si es una búsqueda, sus filtros. No envía nada a ningún lado y al
   *     terminar deja la página como estaba.
   * ------------------------------------------------------------- */
  const HOST_API = 'api-intranet.sunat.peru';
  const RUTA_API_GRE = '/v1/contribuyente/gre/';
  const RUTA_LISTADO = '/v1/contribuyente/gre/comprobantes';
  const CAPTURA_MAX_MS = 5 * 60 * 1000;
  const PARAMETROS_A_CAMPOS = {
    numRucEmisor: 'rucEmisor', numRucReceptor: 'rucReceptor', codCpe: 'codCpe', numSerie: 'numSerie',
    numCpe: 'numCpe', fecEmisionIni: 'fechaInicio', fecEmisionFin: 'fechaFin', codEstado: 'codEstado',
    codSubEstado: 'codSubEstado', rangoHoras: 'rangoHoras', tipBusqueda: 'tipBusqueda'
  };

  /** Convierte dd/mm/aaaa a aaaa-mm-dd si la aplicación usara ese formato. */
  function normalizarFechaCapturada(valor) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(valor || '');
    return m ? `${m[3]}-${m[2]}-${m[1]}` : valor;
  }

  /** Lee la cabecera Authorization de una llamada fetch(input, init). */
  function autorizacionDeFetch(input, init) {
    const fuentes = [];
    if (init && init.headers) fuentes.push(init.headers);
    if (typeof Request !== 'undefined' && input instanceof Request) fuentes.push(input.headers);
    for (const cabeceras of fuentes) {
      try { const v = new Headers(cabeceras).get('authorization'); if (v) return v; } catch (_) { /* formato no estándar */ }
    }
    return '';
  }

  function textoVence(token) {
    const info = analizarToken(token);
    return info.exp ? ` (vence a las ${horaDe(info.exp)})` : '';
  }

  /** Revisa una solicitud de la aplicación: si va a la API de GRE, toma el token y, si es el listado, los filtros. */
  function procesarSolicitudApp(url, autorizacion) {
    if (!captura.activa || !url) return;
    let u;
    try { u = new URL(String(url), location.href); } catch (_) { return; }
    if (u.hostname !== HOST_API || !u.pathname.startsWith(RUTA_API_GRE)) return;
    const m = /^bearer\s+(\S+)$/i.exec(String(autorizacion || '').trim());
    if (!m || /^(null|undefined)$/i.test(m[1])) return;

    if (m[1] !== tokenCapturado) {
      tokenCapturado = m[1];
      log(`Token capturado de la aplicación${textoVence(tokenCapturado)}.`, 'ok');
    }

    if (u.pathname.replace(/\/+$/, '') === RUTA_LISTADO) {
      const filtros = {};
      for (const [param, campo] of Object.entries(PARAMETROS_A_CAMPOS)) {
        if (u.searchParams.has(param)) filtros[campo] = normalizarFechaCapturada(u.searchParams.get(param).trim());
      }
      filtrosCapturados = filtros;
      if (ui) for (const [campo, v] of Object.entries(filtros)) if (ui.inputs[campo]) ui.inputs[campo].value = v;
      const descripcion = [
        `fechas ${filtros.fechaInicio || '?'} a ${filtros.fechaFin || '?'}`,
        filtros.rucEmisor && `RUC emisor ${filtros.rucEmisor}`,
        filtros.rucReceptor && `RUC receptor ${filtros.rucReceptor}`,
        filtros.tipBusqueda && `tipo de búsqueda ${filtros.tipBusqueda}`
      ].filter(Boolean).join(', ');
      log(`Filtros copiados de su búsqueda: ${descripcion}. Puede cambiar las fechas y pulsar Iniciar.`, 'ok');
      detenerCaptura('listo');
    } else {
      actualizarUI();
    }
  }

  /** Empieza a escuchar (temporalmente) las solicitudes de la aplicación SUNAT. */
  function iniciarCaptura() {
    if (estado.ejecutando) { log('No se puede capturar durante una extracción.', 'warn'); return; }
    if (captura.activa) return;
    const restauradores = [];

    // Solicitudes XMLHttpRequest (las que usa normalmente la aplicación)
    const protoXHR = window.XMLHttpRequest && window.XMLHttpRequest.prototype;
    if (protoXHR) {
      const urls = new WeakMap();
      const openOriginal = protoXHR.open;
      const cabeceraOriginal = protoXHR.setRequestHeader;
      const openEnvuelto = function (metodo, url) {
        try { urls.set(this, String(url)); } catch (_) { /* ignorar */ }
        return openOriginal.apply(this, arguments);
      };
      const cabeceraEnvuelta = function (nombre, valor) {
        try { if (/^authorization$/i.test(String(nombre))) procesarSolicitudApp(urls.get(this), valor); } catch (_) { /* nunca romper la aplicación */ }
        return cabeceraOriginal.apply(this, arguments);
      };
      protoXHR.open = openEnvuelto;
      protoXHR.setRequestHeader = cabeceraEnvuelta;
      restauradores.push(() => {
        if (protoXHR.open === openEnvuelto) protoXHR.open = openOriginal;
        if (protoXHR.setRequestHeader === cabeceraEnvuelta) protoXHR.setRequestHeader = cabeceraOriginal;
      });
    }

    // Solicitudes fetch (por si la aplicación las usa)
    const fetchOriginal = window.fetch;
    if (typeof fetchOriginal === 'function') {
      const fetchEnvuelto = function (input, init) {
        try {
          const url = (typeof Request !== 'undefined' && input instanceof Request) ? input.url : String(input);
          procesarSolicitudApp(url, autorizacionDeFetch(input, init));
        } catch (_) { /* nunca romper la aplicación */ }
        return fetchOriginal.apply(window, arguments);
      };
      window.fetch = fetchEnvuelto;
      restauradores.push(() => { if (window.fetch === fetchEnvuelto) window.fetch = fetchOriginal; });
    }

    captura.activa = true;
    captura.restaurar = () => restauradores.forEach((f) => { try { f(); } catch (_) { /* ignorar */ } });
    captura.temporizador = setTimeout(() => detenerCaptura('tiempo'), CAPTURA_MAX_MS);
    log('Captura activa (5 min). En la pantalla de SUNAT pulse "Buscar" con los filtros que desea (copia token y filtros) o abra una guía con "Ver" (solo token). Si el panel tapa la pantalla, minimícelo con "–".', 'ok');
    actualizarUI();
  }

  /** Deja de escuchar y restaura la página. */
  function detenerCaptura(motivo) {
    if (!captura.activa) return;
    captura.activa = false;
    clearTimeout(captura.temporizador);
    captura.temporizador = null;
    if (captura.restaurar) captura.restaurar();
    captura.restaurar = null;
    if (motivo === 'usuario') log('Captura detenida.');
    if (motivo === 'tiempo') {
      if (tokenCapturado) log('Captura finalizada por tiempo; el token capturado sigue disponible.');
      else log('No se detectó ninguna búsqueda en 5 minutos. Revise que la consola esté en "iframeApplication" y vuelva a intentarlo, o pegue el token manualmente.', 'warn');
    }
    actualizarUI();
  }

  function textoEstadoToken() {
    if (captura.activa) {
      return tokenCapturado
        ? `Token capturado${textoVence(tokenCapturado)}. Si quiere copiar también los filtros, pulse "Buscar" en SUNAT; si no, pulse Iniciar.`
        : 'Esperando… En la pantalla de SUNAT pulse "Buscar" (copia token y filtros) o abra una guía con "Ver" (solo token).';
    }
    if (tokenCapturado) return `Token capturado de la aplicación${textoVence(tokenCapturado)}. Listo para Iniciar.`;
    return 'Sin token capturado. Pulse el botón, o pegue el token abajo (si no, se pedirá al iniciar).';
  }

  /* ---------------------------------------------------------------
   * 17. Panel flotante (HTML/CSS nativo, Shadow DOM, removible)
   * ------------------------------------------------------------- */
  function h(tag, props = {}, ...hijos) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, String(v));
    }
    for (const c of hijos.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c));
    return el;
  }

  const CSS = `
    :host{all:initial}
    *{box-sizing:border-box}
    .p{position:fixed;top:10px;right:10px;width:420px;max-height:92vh;display:flex;flex-direction:column;background:#fff;color:#1d2433;
      font:12px/1.35 "Segoe UI",system-ui,sans-serif;border:1px solid #c9d1dc;border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.25);z-index:2147483647}
    .hd{display:flex;align-items:center;gap:6px;padding:7px 10px;background:#12355b;color:#fff;border-radius:8px 8px 0 0;cursor:move;user-select:none}
    .hd b{flex:1;font-size:13px}
    .hd button{background:transparent;color:#fff;border:1px solid rgba(255,255,255,.4);border-radius:4px;width:24px;height:22px;cursor:pointer;padding:0}
    .bd{overflow:auto;padding:8px 10px}
    .g{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:5px 8px}
    label{display:flex;flex-direction:column;min-width:0;font-size:11px;color:#4a5568}
    input{font:12px "Segoe UI",system-ui,sans-serif;padding:3px 5px;border:1px solid #b8c2cf;border-radius:4px;color:#1d2433;background:#fff;min-width:0;width:100%}
    .full{grid-column:1/-1}
    .row{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
    button.b{font:12px "Segoe UI",system-ui,sans-serif;padding:4px 9px;border-radius:4px;border:1px solid #12355b;background:#12355b;color:#fff;cursor:pointer}
    button.s{background:#fff;color:#12355b}
    button.r{background:#a12b2b;border-color:#a12b2b}
    button:disabled{opacity:.45;cursor:not-allowed}
    .bar{height:10px;background:#e6ebf1;border-radius:5px;overflow:hidden;margin-top:8px}
    .bar>div{height:100%;width:0;background:#1f8a5b;transition:width .2s}
    .st{margin-top:5px;display:grid;grid-template-columns:1fr 1fr;gap:2px 8px;font-size:11.5px}
    .st span b{color:#12355b}
    .log{margin-top:7px;height:150px;overflow:auto;background:#0f1724;color:#d6dde8;font:11px Consolas,monospace;padding:5px;border-radius:4px}
    .l-ok{color:#7ee2a8}.l-warn{color:#ffd479}.l-error{color:#ff8c8c}
    .nota{font-size:10.5px;color:#6b7686;margin-top:4px}
    h4{margin:9px 0 3px;font-size:12px;color:#12355b}
  `;

  const CAMPOS_FORM = [
    ['fechaInicio', 'Fecha inicial *', 'date'], ['fechaFin', 'Fecha final *', 'date'],
    ['rucEmisor', 'RUC emisor', 'text'], ['rucReceptor', 'RUC receptor', 'text'],
    ['codCpe', 'Código CPE', 'text'], ['tipBusqueda', 'Tipo de búsqueda', 'text'],
    ['numSerie', 'Serie', 'text'], ['numCpe', 'Número', 'text'],
    ['codEstado', 'Código estado', 'text'], ['codSubEstado', 'Código subestado', 'text'],
    ['rangoHoras', 'Rango de horas', 'text'], ['perPage', 'Registros por página', 'number'],
    ['maxReintentos', 'Máx. reintentos', 'number'], ['timeoutMs', 'Tiempo máx. por solicitud (ms)', 'number'],
    ['pausaMinMs', 'Pausa mínima (ms)', 'number'], ['pausaMaxMs', 'Pausa máxima (ms)', 'number'],
    ['maxDiasRango', 'Máx. días de rango (0 = sin límite)', 'number']
  ];

  function crearPanel() {
    if (typeof document === 'undefined') return;
    cerrarPanel();
    const D = CONFIG_PREDETERMINADA;
    const valoresIniciales = {
      ...D, fechaInicio: hoyISO(), fechaFin: hoyISO(),
      ...(estado.config ? parametrosExportables(estado.config) : (filtrosCapturados || {}))
    };

    const host = h('div', { id: PANEL_ID });
    const root = host.attachShadow({ mode: 'open' });
    try { const hoja = new CSSStyleSheet(); hoja.replaceSync(CSS); root.adoptedStyleSheets = [hoja]; }
    catch (_) { root.append(h('style', { text: CSS })); }

    const inputs = {};
    const campos = CAMPOS_FORM.map(([nombre, etiqueta, tipo]) => {
      inputs[nombre] = h('input', { type: tipo, value: texto(valoresIniciales[nombre]), autocomplete: 'off', spellcheck: 'false' });
      return h('label', {}, etiqueta, inputs[nombre]);
    });
    inputs.token = h('input', { type: 'password', autocomplete: 'off', placeholder: 'Déjelo vacío si usó "Capturar desde SUNAT"' });
    const estadoToken = h('div', { class: 'nota' });

    const btn = {
      capturar: h('button', { class: 'b', onclick: () => (captura.activa ? detenerCaptura('usuario') : iniciarCaptura()) }, '🎯 Capturar desde SUNAT'),
      iniciar: h('button', { class: 'b', onclick: () => alIniciar() }, '▶ Iniciar'),
      pausar: h('button', { class: 'b s', onclick: () => pausar() }, '⏸ Pausar'),
      reanudar: h('button', { class: 'b s', onclick: () => reanudar() }, '⏵ Reanudar'),
      cancelar: h('button', { class: 'b r', onclick: () => cancelar() }, '■ Cancelar'),
      cargar: h('button', { class: 'b s', onclick: () => fileInput.click() }, '📂 Cargar JSON anterior'),
      limpiar: h('button', { class: 'b s', onclick: () => limpiarPrevios() }, 'Quitar JSON anterior'),
      olvidar: h('button', {
        class: 'b s', onclick: () => {
          const n = [...estado.resultados.values()].filter((r) => r.ok).length;
          if (!n || window.confirm(`Se olvidarán ${n} guía(s) ya obtenidas (descárguelas antes si las necesita). ¿Continuar?`)) olvidarResultados();
        }
      }, 'Empezar de cero'),
      todo: h('button', { class: 'b', onclick: () => descargar('todo') }, '⬇ Descargar todo'),
      guias: h('button', { class: 'b s', onclick: () => descargar('guias') }, 'Guías'),
      bienes: h('button', { class: 'b s', onclick: () => descargar('bienes') }, 'Bienes'),
      errores: h('button', { class: 'b s', onclick: () => descargar('errores') }, 'Errores'),
      json: h('button', { class: 'b s', onclick: () => descargar('json') }, 'JSON'),
      control: h('button', { class: 'b s', onclick: () => descargar('control') }, 'Control'),
      adicionales: h('button', { class: 'b s', onclick: () => descargar('adicionales') }, 'Adicionales')
    };
    const fileInput = h('input', { type: 'file', accept: '.json,application/json', style: 'display:none' });
    fileInput.addEventListener('change', async () => {
      const f = fileInput.files && fileInput.files[0];
      if (f) await cargarJSONPrevio(f);
      fileInput.value = '';
    });

    const barra = h('div');
    const stats = {};
    const stat = (k, etiqueta) => { stats[k] = h('b', { text: '0' }); return h('span', {}, `${etiqueta}: `, stats[k]); };
    const cuerpo = h('div', { class: 'bd' },
      h('h4', { text: '1. Token y filtros' }),
      h('div', { class: 'row' }, btn.capturar),
      estadoToken,
      h('h4', { text: '2. Revise los filtros' }),
      h('div', { class: 'g' }, ...campos,
        h('label', { class: 'full' }, 'Token Bearer manual (opcional; solo memoria, se borra al iniciar)', inputs.token)),
      h('h4', { text: '3. Ejecutar' }),
      h('div', { class: 'row' }, btn.iniciar, btn.pausar, btn.reanudar, btn.cancelar),
      h('div', { class: 'bar' }, barra),
      h('div', { class: 'st' },
        stat('total', 'Total guías'), stat('actual', 'Guía actual'),
        stat('ok', 'Correctas'), stat('error', 'Con error'),
        stat('pct', 'Avance'), stat('omitidas', 'Reutilizadas'),
        stat('trans', 'Transcurrido'), stat('eta', 'Restante estimado'),
        stat('previos', 'Guías en JSON previo'), stat('estado', 'Estado')),
      h('h4', { text: 'Reanudación' }),
      h('div', { class: 'row' }, btn.cargar, btn.limpiar, btn.olvidar, fileInput),
      h('div', { class: 'nota', text: 'Si el proceso se detiene, al pulsar Iniciar de nuevo continúa donde quedó (mientras no recargue la página).' }),
      h('h4', { text: 'Descargas' }),
      h('div', { class: 'row' }, btn.todo, btn.guias, btn.bienes, btn.errores, btn.json, btn.control, btn.adicionales),
      h('div', { class: 'nota', text: 'Si el navegador pregunta, permita "descargar varios archivos".' }),
      h('div', { class: 'log' })
    );
    const btnMin = h('button', { title: 'Minimizar', onclick: () => { cuerpo.style.display = cuerpo.style.display === 'none' ? '' : 'none'; } }, '–');
    const btnCerrar = h('button', { title: 'Cerrar panel', onclick: () => {
      if (estado.ejecutando) log('El panel se cerró; el proceso sigue en la consola. Reábralo con GREExtractor.mostrarPanel().', 'warn');
      cerrarPanel();
    } }, '×');
    const cabecera = h('div', { class: 'hd' }, h('b', { text: `Extractor GRE v${VERSION}` }), btnMin, btnCerrar);
    const panel = h('div', { class: 'p' }, cabecera, cuerpo);
    root.append(panel);
    (document.body || document.documentElement).appendChild(host);

    habilitarArrastre(cabecera, panel);
    ui = { host, inputs, btn, barra, stats, estadoToken, log: cuerpo.querySelector('.log') };
    actualizarUI();

    function alIniciar() {
      const op = {};
      for (const [nombre] of CAMPOS_FORM) op[nombre] = inputs[nombre].value;
      op.token = inputs.token.value;
      inputs.token.value = ''; // borrar el token del campo de inmediato
      iniciarExtraccionGRE(op).catch((e) => log(`Error: ${e.message}`, 'error'));
    }
  }

  function habilitarArrastre(asa, panel) {
    let x0 = 0, y0 = 0, arrastrando = false;
    asa.addEventListener('mousedown', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      arrastrando = true;
      const r = panel.getBoundingClientRect();
      x0 = e.clientX - r.left; y0 = e.clientY - r.top;
      e.preventDefault();
    });
    const mover = (e) => {
      if (!arrastrando) return;
      panel.style.left = Math.max(0, e.clientX - x0) + 'px';
      panel.style.top = Math.max(0, e.clientY - y0) + 'px';
      panel.style.right = 'auto';
    };
    const soltar = () => { arrastrando = false; };
    document.addEventListener('mousemove', mover);
    document.addEventListener('mouseup', soltar);
    asa._limpiarArrastre = () => { document.removeEventListener('mousemove', mover); document.removeEventListener('mouseup', soltar); };
  }

  function cerrarPanel() {
    if (typeof document === 'undefined') return;
    if (ui && ui.host) {
      const asa = ui.host.shadowRoot && ui.host.shadowRoot.querySelector('.hd');
      if (asa && asa._limpiarArrastre) asa._limpiarArrastre();
    }
    const existente = document.getElementById(PANEL_ID);
    if (existente) existente.remove();
    ui = null;
  }

  function actualizarUI() {
    if (!ui) return;
    const P = estado.progreso, E = estado;
    const hay = E.resultados.size > 0 || E.errores.length > 0;
    const b = ui.btn;
    b.capturar.disabled = E.ejecutando;
    b.capturar.textContent = captura.activa ? '⏹ Detener captura' : '🎯 Capturar desde SUNAT';
    ui.estadoToken.textContent = textoEstadoToken();
    b.iniciar.disabled = E.ejecutando;
    b.pausar.disabled = !E.ejecutando || E.pausado;
    b.reanudar.disabled = !E.ejecutando || !E.pausado;
    b.cancelar.disabled = !E.ejecutando;
    b.cargar.disabled = E.ejecutando;
    b.limpiar.disabled = E.ejecutando || E.previos.size === 0;
    b.olvidar.disabled = E.ejecutando || (E.resultados.size === 0 && E.previos.size === 0);
    for (const k of ['todo', 'guias', 'bienes', 'errores', 'json', 'control', 'adicionales']) b[k].disabled = !hay;
    for (const inp of Object.values(ui.inputs)) inp.disabled = E.ejecutando;

    const pct = P.total ? (P.procesadas / P.total) * 100 : 0;
    ui.barra.style.width = pct.toFixed(1) + '%';
    const ahora = E.tiempos.fin && !E.ejecutando ? E.tiempos.fin : Date.now();
    const trans = E.tiempos.inicio ? ahora - E.tiempos.inicio : 0;
    let eta = '';
    if (E.ejecutando && P.consultadas > 0 && E.tiempos.inicioDetalle) {
      const porGuia = (Date.now() - E.tiempos.inicioDetalle) / P.consultadas;
      eta = duracion(porGuia * Math.max(0, P.pendientesReales - P.consultadas));
    }
    const s = ui.stats;
    s.total.textContent = String(P.total);
    s.actual.textContent = P.actual || '-';
    s.ok.textContent = String(P.ok);
    s.error.textContent = String(P.error);
    s.pct.textContent = pct.toFixed(1) + '%';
    s.omitidas.textContent = String(P.omitidas);
    s.trans.textContent = E.tiempos.inicio ? duracion(trans) : '-';
    s.eta.textContent = eta || '-';
    s.previos.textContent = String(E.previos.size);
    s.estado.textContent = E.ejecutando ? (E.pausado ? 'PAUSADO' : 'EN CURSO') : (E.motivoFin || 'LISTO');
  }

  // Refresco periódico del tiempo transcurrido mientras hay ejecución.
  const refresco = setInterval(() => { if (estado.ejecutando) actualizarUI(); }, 1000);

  /** Elimina completamente el panel, los datos en memoria y el objeto global. */
  function destruir() {
    if (estado.ejecutando && estado.controller) estado.controller.abort();
    detenerCaptura('destruir');
    tokenCapturado = null;
    filtrosCapturados = null;
    clearInterval(refresco);
    cerrarPanel();
    estado.resultados.clear(); estado.previos.clear(); estado.memoria.clear();
    estado.errores = []; estado.control = []; estado.controlDetalle = [];
    try { delete window.GREExtractor; } catch (_) { window.GREExtractor = undefined; }
    console.log('[GRE] Extractor eliminado de la página.');
  }

  /* ---------------------------------------------------------------
   * 18. Objeto de control global (único)
   * ------------------------------------------------------------- */
  window.GREExtractor = {
    version: VERSION,
    iniciarExtraccionGRE,
    iniciar: iniciarExtraccionGRE,
    pausar, reanudar, cancelar,
    capturarDesdeSUNAT: iniciarCaptura,
    detenerCaptura: () => detenerCaptura('usuario'),
    get hayTokenCapturado() { return !!tokenCapturado; },
    get filtrosCapturados() { return filtrosCapturados ? { ...filtrosCapturados } : null; },
    cargarJSONPrevio, seleccionarJSONPrevio, limpiarPrevios, olvidarResultados,
    descargar, descargarTodo, exportar,
    flattenObject,
    mostrarPanel: crearPanel, cerrarPanel, destruir,
    get ejecutando() { return estado.ejecutando; },
    get resumen() { return estado.resumen; },
    get errores() { return estado.errores.slice(); },
    get control() { return estado.control.slice(); },
    get progreso() { return { ...estado.progreso, pausado: estado.pausado, estado: estado.motivoFin }; },
    detallesCorrectos() { return [...estado.resultados.values()].filter((r) => r.ok).map((r) => r.detalle); }
  };

  crearPanel();
  log(`Extractor GRE v${VERSION} listo en ${location.origin}.`, 'ok');
  log('Paso 1: pulse "Capturar desde SUNAT" y haga su búsqueda en la pantalla de SUNAT.');
  if (!/(^|\.)intranet\.sunat\.peru$/i.test(location.hostname)) {
    log('Aviso: este no parece el contexto "iframeApplication (intranet.sunat.peru)". Cámbielo en el selector de contexto de la consola.', 'warn');
  }
})();
