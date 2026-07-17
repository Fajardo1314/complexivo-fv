import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue, update, remove, set, get, push } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

// --- CONFIGURACION FIREBASE ---
const OUR_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/";
const ourApp = initializeApp({ databaseURL: OUR_DB_URL });
const db = getDatabase(ourApp);

// --- GLOBAL STATE ---
let usuarioActivo = null;
let permanenciaInterval = null;

// Initialize Admin if not exists
async function inicializarAdmin() {
    try {
        const adminRef = ref(db, 'usuarios/admin');
        const snapshot = await get(adminRef);
        if (!snapshot.exists()) {
            await set(adminRef, {
                nombre: "admin",
                password: "admin123",
                email: "smartstock97@gmail.com",
                rol: "SuperAdmin"
            });
        }
    } catch (e) {
        console.error("Error al inicializar admin:", e);
    }
}
inicializarAdmin();

// --- AUDIT TRAIL ---
async function registrarAuditoria(accion, detalles) {
    if (!usuarioActivo) return;
    try {
        await push(ref(db, 'auditoria'), {
            timestamp: new Date().toLocaleString('es-ES'),
            usuario: usuarioActivo.nombre || "Sistema",
            rol: usuarioActivo.rol,
            accion: accion,
            detalles: detalles
        });
    } catch (e) {
        console.error("Error al registrar auditoria:", e);
    }
}

// --- UI ELEMENTS ---
const navBtns = document.querySelectorAll('.nav-btn');
const panels = document.querySelectorAll('.panel');

// --- TAB NAVIGATION ---
navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.target;
        if (!target) return;
        panels.forEach(p => p.classList.remove('active'));
        const targetPanel = document.getElementById(target);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }
        navBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

const estadoPir = document.getElementById('estadoPir');
const subAlerta = document.getElementById('subAlerta');
const cardAlerta = document.getElementById('cardAlerta');

const estadoChapa = document.getElementById('estadoChapa');
const cardChapa = document.getElementById('cardChapa');

const estadoFoco = document.getElementById('estadoFoco');
const cardFoco = document.getElementById('cardFoco');
const subFoco = document.getElementById('subFoco');

const listaInventario = document.getElementById('listaInventario');
const listaAccesos = document.getElementById('listaAccesos');
const listaRetiros = document.getElementById('listaRetiros');
const listaUsuarios = document.getElementById('listaUsuarios');
const listaUsuariosWeb = document.getElementById('listaUsuariosWeb');

// Forms & Configs
const btnGuardarUsuario = document.getElementById('btnGuardarUsuario');
const userUid = document.getElementById('userUid');
const userNombre = document.getElementById('userNombre');
const userRol = document.getElementById('userRol');
const userCorreo = document.getElementById('userCorreo');

const btnGuardarWebUsuario = document.getElementById('btnGuardarWebUsuario');
const webUserOperatorId = document.getElementById('webUserOperatorId');
const webUserUsername = document.getElementById('webUserUsername');
const webUserPassword = document.getElementById('webUserPassword');
const webUserCorreo = document.getElementById('webUserCorreo');
const webUserRol = document.getElementById('webUserRol');

// --- TOAST FUNCTION ---
function crearToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.borderLeftColor = type === 'success' ? 'var(--success)' : type === 'danger' ? 'var(--danger)' : 'var(--primary)';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4000);
}

// --- TAB NAVIGATION ---
const btnIrAjustes = document.getElementById('btnIrAjustes');
if (btnIrAjustes) {
    btnIrAjustes.addEventListener('click', () => {
        panels.forEach(p => p.classList.remove('active'));
        document.getElementById('panel-ajustes-inventario').classList.add('active');
    });
}

const btnVolverInventario = document.getElementById('btnVolverInventario');
if (btnVolverInventario) {
    btnVolverInventario.addEventListener('click', () => {
        panels.forEach(p => p.classList.remove('active'));
        document.getElementById('panel-inventario').classList.add('active');
    });
}

// --- TIME DISPLAY ---
setInterval(() => {
    const ahora = new Date();
    const el = document.getElementById('system-time');
    if (el) el.innerText = ahora.toLocaleTimeString('es-ES');
}, 1000);

// --- LOGIN MANAGER ---
const loginOverlay = document.getElementById('loginOverlay');
const btnIngresar = document.getElementById('btnIngresar');
const loginUser = document.getElementById('loginUser');
const loginPass = document.getElementById('loginPass');
const dashboardContainer = document.querySelector('.dashboard-container');

function mapRol(rol) {
    if (!rol) return '';
    const r = rol.toLowerCase();
    if (r === 'superadmin') return 'SuperAdmin';
    if (r === 'docente') return 'Docente';
    if (r === 'estudiante') return 'Estudiante';
    return rol;
}

btnIngresar.addEventListener('click', async () => {
    const u = loginUser.value.trim();
    const p = loginPass.value.trim();
    if (!u || !p) {
        crearToast("Completa todos los campos", "danger");
        return;
    }
    try {
        const snap = await get(ref(db, `usuarios/${u}`));
        if (snap.exists()) {
            const user = snap.val();
            if (user.password === p) {
                user.rol = mapRol(user.rol);
                usuarioActivo = user;
                crearToast(`Bienvenido ${user.nombre}`, "success");
                loginOverlay.style.display = 'none';
                dashboardContainer.style.display = 'flex';

                document.getElementById('profileNombre').innerText = user.nombre;
                document.getElementById('profileRol').innerText = user.rol;
                document.getElementById('profileUsuario').innerText = user.nombre;
                document.getElementById('profileCorreo').innerText = user.email || "---";

                navBtns.forEach(btn => {
                    btn.style.display = 'flex';
                });

                const serverTab = document.querySelector('[data-target="panel-servidor"]');
                if (serverTab) {
                    if (user.rol === "SuperAdmin" || user.rol === "Docente") {
                        serverTab.style.display = 'flex';
                    } else {
                        serverTab.style.display = 'none';
                    }
                }

                await registrarAuditoria('Login', 'Usuario ingreso a la plataforma');
                cargarAuditoria();
            } else {
                crearToast("Contrasena incorrecta", "danger");
            }
        } else {
            crearToast("Usuario no encontrado", "danger");
        }
    } catch (e) {
        console.error(e);
        crearToast("Error de conexion", "danger");
    }
});

document.getElementById('btnCerrarSesion').addEventListener('click', async () => {
    await registrarAuditoria('Logout', 'Usuario cerro sesion');
    usuarioActivo = null;
    dashboardContainer.style.display = 'none';
    loginOverlay.style.display = 'flex';
    loginUser.value = '';
    loginPass.value = '';
});

// --- AUDIT TRAIL RENDER ---
async function cargarAuditoria() {
    const list = document.getElementById('profileAuditoria');
    if (!list) return;
    onValue(ref(db, 'auditoria'), (snap) => {
        list.innerHTML = '';
        const data = snap.val();
        if (data) {
            Object.values(data).reverse().forEach(log => {
                if (log.usuario === usuarioActivo.nombre) {
                    const p = document.createElement('div');
                    p.style.cssText = 'padding:10px; border-bottom:1px solid var(--glass-border); font-size:0.85rem;';
                    p.innerHTML = `<span style="color:var(--primary); font-weight:700;">[${log.timestamp}]</span> <strong>${log.accion}</strong>: ${log.detalles}`;
                    list.appendChild(p);
                }
            });
        } else {
            list.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:20px;">No hay registros de actividad.</p>';
        }
    });
}

// --- REAL-TIME MONITORING LISTENERS ---
onValue(ref(db, 'monitoreo/permanencia'), (snapshot) => {
    const data = snapshot.val();
    const clock = document.getElementById('permanenciaReloj');
    const userLabel = document.getElementById('permanenciaUsuario');
    if (permanenciaInterval) clearInterval(permanenciaInterval);
    if (data && data.activo) {
        const start = new Date(data.inicio).getTime();
        userLabel.innerText = data.usuario || "Usuario desconocido";
        permanenciaInterval = setInterval(() => {
            const diff = Date.now() - start;
            const hrs = Math.floor(diff / 3600000).toString().padStart(2, '0');
            const mins = Math.floor((diff % 3600000) / 60000).toString().padStart(2, '0');
            const secs = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0');
            clock.innerText = `${hrs}:${mins}:${secs}`;
        }, 1000);
    } else {
        clock.innerText = "00:00:00";
        userLabel.innerText = "Nadie adentro";
    }
});

onValue(ref(db, 'monitoreo/movimiento_pir'), (snapshot) => {
    const val = snapshot.val();
    if (val) { estadoPir.innerText = "MOVIMIENTO"; subAlerta.innerText = "Se detecto movimiento"; cardAlerta.classList.add('alert-danger'); }
    else { estadoPir.innerText = "Seguro"; subAlerta.innerText = "Sin movimiento"; cardAlerta.classList.remove('alert-danger'); }
});

onValue(ref(db, 'monitoreo/estado_chapa'), (snapshot) => {
    const val = snapshot.val();
    estadoChapa.innerText = val || "CERRADA";
    if (val === "ABIERTA") { cardChapa.style.borderColor = 'var(--success)'; cardChapa.style.boxShadow = '0 10px 30px var(--success-glow)'; }
    else { cardChapa.style.borderColor = ''; cardChapa.style.boxShadow = ''; }
});

onValue(ref(db, 'estado_foco'), (snapshot) => {
    const val = snapshot.val();
    estadoFoco.innerText = val || "Apagado";
    if (val === "ENCENDIDO") { cardFoco.style.borderColor = 'var(--warning)'; cardFoco.style.boxShadow = '0 10px 30px var(--warning-glow)'; subFoco.innerText = "Luz artificial encendida"; }
    else { cardFoco.style.borderColor = ''; cardFoco.style.boxShadow = ''; subFoco.innerText = "Luz artificial apagada"; }
});

document.getElementById('btnToggleFoco').addEventListener('click', async () => {
    const stateRef = ref(db, 'estado_foco');
    const snap = await get(stateRef);
    const curr = snap.val();
    const target = curr === "ENCENDIDO" ? "APAGADO" : "ENCENDIDO";
    await set(stateRef, target);
    crearToast(`Comando de luz cambiado a ${target}`, "success");
});

document.getElementById('btnAbrirPuertaRemota').addEventListener('click', async () => {
    try {
        await update(ref(db, 'puerta'), {
            estado: "abierta", metodo: "WEB", timestamp: Date.now() / 1000,
            ultimo_acceso: new Date().toLocaleString('es-ES'),
            usuario_responsable: (usuarioActivo && usuarioActivo.nombre) || "Dashboard Web"
        });
        crearToast("Comando de apertura enviado con exito", "success");
        setTimeout(async () => { await set(ref(db, 'puerta/estado'), "cerrada"); }, 5000);
    } catch (e) { crearToast("Error al enviar comando", "danger"); }
});

const modalConfirmacionPresencia = document.getElementById('modalConfirmacionPresencia');
const btnDesactivarAlarma = document.getElementById('btnDesactivarAlarma');
onValue(ref(db, 'monitoreo/alerta_pir_nocturna'), (snapshot) => {
    if (snapshot.val() === true) {
        modalConfirmacionPresencia.style.display = 'flex';
        if (btnDesactivarAlarma) btnDesactivarAlarma.style.display = 'block';
    } else {
        modalConfirmacionPresencia.style.display = 'none';
        if (btnDesactivarAlarma) btnDesactivarAlarma.style.display = 'none';
    }
});
if (btnDesactivarAlarma) {
    btnDesactivarAlarma.addEventListener('click', async () => {
        await set(ref(db, 'monitoreo/alerta_pir_nocturna'), false);
        crearToast('Alarma PIR desactivada', 'success');
    });
}

document.getElementById('btnPresenciaSi').addEventListener('click', async () => {
    await set(ref(db, 'monitoreo/alerta_pir_nocturna'), false);
    await set(ref(db, 'estado_foco'), "ENCENDIDO");
    crearToast("Se encendieron las luces por confirmacion de presencia", "success");
});

document.getElementById('btnPresenciaNo').addEventListener('click', async () => {
    await set(ref(db, 'monitoreo/alerta_pir_nocturna'), false);
    await set(ref(db, 'estado_foco'), "APAGADO");
    crearToast("Luces permanecen apagadas", "info");
});

const umbralSlider = document.getElementById('umbralLuxSlider');
const umbralLabel = document.getElementById('umbralLuxLabel');
onValue(ref(db, 'configuracion/umbral_luxes'), (snap) => { const val = snap.val() || 100; umbralSlider.value = val; umbralLabel.innerText = `${val} lux`; });
umbralSlider.addEventListener('input', (e) => { umbralLabel.innerText = `${e.target.value} lux`; });
umbralSlider.addEventListener('change', async (e) => { await set(ref(db, 'configuracion/umbral_luxes'), parseInt(e.target.value)); crearToast("Umbral de luxes guardado", "success"); });

document.getElementById('btnGuardarTiempoFoco').addEventListener('click', async () => {
    const val = parseFloat(document.getElementById('inputTiempoFoco').value) || 10;
    const unidad = document.getElementById('selectUnidadFoco').value;
    await set(ref(db, 'configuracion/tiempo_encendido_luces'), { valor: val, unidad: unidad });
    crearToast(`Temporizador de luces fijado en ${val} ${unidad}`, "success");
});
onValue(ref(db, 'configuracion/tiempo_encendido_luces'), (snap) => { const data = snap.val(); if (data) { document.getElementById('inputTiempoFoco').value = data.valor || 10; document.getElementById('selectUnidadFoco').value = data.unidad || "minutos"; } });

document.getElementById('btnGuardarHorario').addEventListener('click', async () => {
    if (usuarioActivo.rol !== "SuperAdmin" && usuarioActivo.rol !== "Docente") { crearToast("Acceso denegado", "danger"); return; }
    const ini = document.getElementById('inputHoraInicio').value;
    const fin = document.getElementById('inputHoraFin').value;
    await set(ref(db, 'configuracion/horario_iluminacion'), { inicio: ini, fin: fin });
    crearToast("Horario de iluminacion guardado con exito", "success");
});
onValue(ref(db, 'configuracion/horario_iluminacion'), (snap) => { const data = snap.val(); if (data) { document.getElementById('inputHoraInicio').value = data.inicio || "06:30"; document.getElementById('inputHoraFin').value = data.fin || "22:00"; } });

// --- ESTANTE SECURITY ---
const widgetCas1 = document.getElementById('widgetCasillero1');
const widgetCas2 = document.getElementById('widgetCasillero2');
const valCas1 = document.getElementById('valCasillero1');
const valCas2 = document.getElementById('valCasillero2');
const checkModoSeguro = document.getElementById('checkModoSeguro');
const bannerEstante = document.getElementById('alertaEstanteBanner');

onValue(ref(db, 'monitoreo/casillero1'), (snap) => { const val = snap.val() || "SEGURO"; valCas1.innerText = val; if (val === "ALERTA") { widgetCas1.style.borderColor = "var(--danger)"; widgetCas1.style.background = "rgba(192, 57, 43, 0.08)"; } else { widgetCas1.style.borderColor = "var(--success)"; widgetCas1.style.background = ""; } });
onValue(ref(db, 'monitoreo/casillero2'), (snap) => { const val = snap.val() || "SEGURO"; valCas2.innerText = val; if (val === "ALERTA") { widgetCas2.style.borderColor = "var(--danger)"; widgetCas2.style.background = "rgba(192, 57, 43, 0.08)"; } else { widgetCas2.style.borderColor = "var(--success)"; widgetCas2.style.background = ""; } });
onValue(ref(db, 'monitoreo/modo_seguro_estante'), (snap) => { checkModoSeguro.checked = snap.val() || false; });
checkModoSeguro.addEventListener('change', async () => {
    if (usuarioActivo.rol !== "SuperAdmin" && usuarioActivo.rol !== "Docente") { crearToast("Acceso denegado", "danger"); checkModoSeguro.checked = !checkModoSeguro.checked; return; }
    await set(ref(db, 'monitoreo/modo_seguro_estante'), checkModoSeguro.checked);
    if (checkModoSeguro.checked) { await set(ref(db, 'monitoreo/alerta_estante'), ""); }
    crearToast(`Modo retiro seguro ${checkModoSeguro.checked ? "activado" : "desactivado"}`, "success");
});
onValue(ref(db, 'monitoreo/alerta_estante'), (snap) => { const val = snap.val() || ""; if (val) { bannerEstante.innerText = `ALERTA: ${val}`; bannerEstante.style.display = "block"; } else { bannerEstante.style.display = "none"; } });

// --- INVENTARIO MANAGER ---
let listCarreras = ["TAIPT", "TIRE", "TAI"];
let listCategorias = ["Hardware", "Herramientas", "Accesorios", "Otros"];
onValue(ref(db, 'configuracion/carreras'), (snap) => { const data = snap.val(); if (data) { listCarreras = Object.values(data); } actualizarDropdownsYListas(); });
onValue(ref(db, 'configuracion/categorias'), (snap) => { const data = snap.val(); if (data) { listCategorias = Object.values(data); } actualizarDropdownsYListas(); });

function actualizarDropdownsYListas() {
    const comboCar = document.getElementById('invCarrera');
    const comboCat = document.getElementById('invCategoria');
    const uiCar = document.getElementById('listaAjustesCarreras');
    const uiCat = document.getElementById('listaAjustesCategorias');
    if (comboCar) comboCar.innerHTML = listCarreras.map(c => `<option value="${c}">${c}</option>`).join('');
    if (comboCat) comboCat.innerHTML = listCategorias.map(c => `<option value="${c}">${c}</option>`).join('');
    if (uiCar) uiCar.innerHTML = listCarreras.map(c => `<li style="display:flex; justify-content:space-between; padding:8px; border-bottom:1px solid var(--glass-border);"><span>${c}</span><button class="delete-btn" style="padding:2px 8px;" onclick="eliminarCarrera('${c}')">Eliminar</button></li>`).join('');
    if (uiCat) uiCat.innerHTML = listCategorias.map(c => `<li style="display:flex; justify-content:space-between; padding:8px; border-bottom:1px solid var(--glass-border);"><span>${c}</span><button class="delete-btn" style="padding:2px 8px;" onclick="eliminarCategoria('${c}')">Eliminar</button></li>`).join('');
}

document.getElementById('btnAgregarCarrera').addEventListener('click', async () => { const val = document.getElementById('inputNuevaCarrera').value.trim().toUpperCase(); if (val && !listCarreras.includes(val)) { await push(ref(db, 'configuracion/carreras'), val); document.getElementById('inputNuevaCarrera').value = ''; crearToast("Carrera anyadida", "success"); } });
document.getElementById('btnAgregarCategoria').addEventListener('click', async () => { const val = document.getElementById('inputNuevaCategoria').value.trim(); if (val && !listCategorias.includes(val)) { await push(ref(db, 'configuracion/categorias'), val); document.getElementById('inputNuevaCategoria').value = ''; crearToast("Categoria anyadida", "success"); } });
window.eliminarCarrera = async function (car) { const snap = await get(ref(db, 'configuracion/carreras')); if (snap.exists()) { const data = snap.val(); const key = Object.keys(data).find(k => data[k] === car); if (key) { await remove(ref(db, `configuracion/carreras/${key}`)); crearToast("Carrera eliminada", "success"); } } };
window.eliminarCategoria = async function (cat) { const snap = await get(ref(db, 'configuracion/categorias')); if (snap.exists()) { const data = snap.val(); const key = Object.keys(data).find(k => data[k] === cat); if (key) { await remove(ref(db, `configuracion/categorias/${key}`)); crearToast("Categoria eliminada", "success"); } } };

let todosLosProductos = {};
const invSearchInput = document.getElementById('invSearchInput');
function renderInventario() {
    listaInventario.innerHTML = '';
    const query = invSearchInput.value.toLowerCase().trim();
    Object.keys(todosLosProductos).forEach(key => {
        const prod = todosLosProductos[key];
        const nombre = prod.nombre_producto || '---';
        if (query && !key.toLowerCase().includes(query) && !nombre.toLowerCase().includes(query)) return;
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><span style="font-family:monospace; color:var(--primary); font-weight:700;">${key}</span></td><td><strong>${nombre}</strong></td><td>${prod.carrera || '---'}</td><td>${prod.categoria || 'Otros'}</td><td>${prod.ubicacion || '---'}</td><td><span class="badge ${prod.stock > 0 ? 'badge-green' : 'badge-red'}">${prod.stock || 0} und</span></td><td><span class="badge ${(prod.estado || 'Funcional') === 'Funcional' ? 'badge-green' : (prod.estado || '') === 'Regular' ? 'badge-orange' : 'badge-red'}">${prod.estado || 'Funcional'}</span></td><td style="display:flex; gap:6px;"><button class="edit-btn" onclick="editarProducto('${key}')">Editar</button><button class="delete-btn" onclick="eliminarProducto('${key}')">Eliminar</button></td>`;
        listaInventario.appendChild(tr);
    });
}
invSearchInput.addEventListener('input', renderInventario);
onValue(ref(db, 'inventario'), (snapshot) => { todosLosProductos = snapshot.val() || {}; renderInventario(); renderQRAltaPanel(); });

document.getElementById('btnAgregarInventario').addEventListener('click', async () => {
    const id = document.getElementById('invId').value || 'PRD_' + Math.random().toString(36).substr(2, 6).toUpperCase();
    const nombre = document.getElementById('invNombre').value.trim();
    if (!nombre) { crearToast("Ingresa el nombre del producto", "danger"); return; }
    await set(ref(db, `inventario/${id}`), { nombre_producto: nombre, ubicacion: document.getElementById('invUbicacion').value.trim(), stock: parseInt(document.getElementById('invStock').value) || 0, carrera: document.getElementById('invCarrera').value, categoria: document.getElementById('invCategoria').value, estado: document.getElementById('invEstado').value });
    crearToast("Producto registrado", "success");
    document.getElementById('invId').value = ''; document.getElementById('invNombre').value = ''; document.getElementById('invUbicacion').value = ''; document.getElementById('invStock').value = '';
});
window.editarProducto = function (id) { const prod = todosLosProductos[id]; if (prod) { document.getElementById('invId').value = id; document.getElementById('invNombre').value = prod.nombre_producto || ''; document.getElementById('invUbicacion').value = prod.ubicacion || ''; document.getElementById('invStock').value = prod.stock || 0; document.getElementById('invCarrera').value = prod.carrera || ''; document.getElementById('invCategoria').value = prod.categoria || ''; document.getElementById('invEstado').value = prod.estado || 'Funcional'; crearToast("Cargado en formulario", "info"); } };
window.eliminarProducto = async function (id) { if (confirm("Eliminar este producto?")) { await remove(ref(db, `inventario/${id}`)); crearToast("Producto eliminado", "success"); } };

// --- QR Alta Panel ---
const qrSearch = document.getElementById('qrSearchInput');
function renderQRAltaPanel() {
    const grid = document.getElementById('labelsPrintGrid');
    if (!grid) return; grid.innerHTML = '';
    const query = qrSearch.value.toLowerCase().trim();
    Object.keys(todosLosProductos).forEach(key => {
        const prod = todosLosProductos[key]; const nombre = prod.nombre_producto || '---';
        if (query && !key.toLowerCase().includes(query) && !nombre.toLowerCase().includes(query)) return;
        const div = document.createElement('div'); div.className = "printable-badge"; div.style.position = "relative";
        div.innerHTML = `<input type="checkbox" class="qr-print-check" data-id="${key}" style="position:absolute; top:10px; right:10px; width:20px; height:20px; cursor:pointer;"><div class="badge-header">UCUENCA - SMART STOCK</div><div class="qr-preview-img" id="qr-container-${key}" style="padding:10px; background:white;"></div><div class="badge-footer">${key}</div>`;
        grid.appendChild(div);
        setTimeout(() => { const container = document.getElementById(`qr-container-${key}`); if (container) { new QRCode(container, { text: `https://smartstock.eu1.netbird.services/retiro.html?id=${key}`, width: 100, height: 100 }); } }, 100);
    });
}
qrSearch.addEventListener('input', renderQRAltaPanel);

document.getElementById('btnExportarPdfLabels').addEventListener('click', async () => {
    const checks = document.querySelectorAll('.qr-print-check:checked');
    if (checks.length === 0) { crearToast("Selecciona al menos un codigo QR", "danger"); return; }
    try {
        crearToast("Generando PDF...", "info");
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ unit: 'mm', format: 'a4' });
        const pageW = 210, margin = 12, cols = 3, labelW = (pageW - 2 * margin) / cols, labelH = 65, qrSize = 38;
        let col = 0, row = 0;
        const items = []; for (const chk of checks) { const key = chk.dataset.id; const container = document.getElementById(`qr-container-${key}`); if (!container) continue; const imgEl = container.querySelector('img'); if (imgEl && imgEl.src) items.push({ key, src: imgEl.src }); }
        items.forEach((item, idx) => { const x = margin + col * labelW; const y = margin + row * labelH; if (y + labelH > 297 - margin && idx > 0) { doc.addPage(); col = 0; row = 0; } const fX = margin + col * labelW; const fY = margin + row * labelH; doc.setFontSize(7); doc.setFont("helvetica", "bold"); doc.text("UCUENCA - SMART STOCK", fX + labelW / 2, fY + 8, { align: 'center' }); doc.addImage(item.src, 'PNG', fX + (labelW - qrSize) / 2, fY + 10, qrSize, qrSize); doc.setFontSize(8); doc.setFont("courier", "bold"); doc.text(item.key, fX + labelW / 2, fY + labelH - 4, { align: 'center' }); col++; if (col >= cols) { col = 0; row++; } });
        doc.save('etiquetas_qr_inventario.pdf');
        crearToast("PDF descargado correctamente", "success");
    } catch (e) { crearToast("Error al generar PDF: " + e.message, "danger"); }
});

// --- HISTORIAL DE MOVIMIENTOS ---
let todosLosAccesos = [];
let todosLosRetiros = [];
const filtroFechaInput = document.getElementById('filtroFechaMovimientos');
const btnLimpiarFiltro = document.getElementById('btnLimpiarFiltroFecha');

function filtrarYRenderizarMovimientos() {
    const fechaFiltro = filtroFechaInput.value;
    listaAccesos.innerHTML = '';
    const accesosFiltrados = todosLosAccesos.filter(acc => { if (!fechaFiltro) return true; return (acc.fecha_hora || "").includes(fechaFiltro); });
    if (accesosFiltrados.length > 0) {
        accesosFiltrados.forEach(acc => {
            const tr = document.createElement('tr');
            const nombre = (acc.perfil && acc.perfil.nombre) || acc.identificador_usuario || "---";
            const rol = (acc.perfil && acc.perfil.rol) || "---";
            const badgeClass = acc.exitoso ? "badge-green" : "badge-red";
            tr.innerHTML = `<td><strong>${nombre}</strong></td><td><span class="badge ${badgeClass}">${acc.metodo || "---"}</span></td><td>${rol}</td><td>${acc.fecha_hora || "---"}</td><td>${acc.motivo || "---"}</td>`;
            listaAccesos.appendChild(tr);
        });
    } else { listaAccesos.innerHTML = '<tr><td colspan="5">Sin accesos registrados para esta fecha.</td></tr>'; }

    listaRetiros.innerHTML = '';
    const retirosFiltrados = todosLosRetiros.filter(ret => { if (!fechaFiltro) return true; const parts = fechaFiltro.split("-"); const formatEs = `${parts[2]}/${parts[1]}/${parts[0]}`; return ret.fecha && ret.fecha.includes(formatEs); });
    if (retirosFiltrados.length > 0) {
        retirosFiltrados.forEach(ret => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><strong>${ret.nombre_producto}</strong></td><td>${ret.producto_id}</td><td>${ret.cantidad_retirada}</td><td>${ret.stock_anterior}</td><td>${ret.stock_nuevo}</td><td>${ret.usuario}</td><td>${ret.fecha}</td>`;
            listaRetiros.appendChild(tr);
        });
    } else { listaRetiros.innerHTML = '<tr><td colspan="7">Sin retiros registrados para esta fecha.</td></tr>'; }
}
if (filtroFechaInput) filtroFechaInput.addEventListener('change', filtrarYRenderizarMovimientos);
if (btnLimpiarFiltro) btnLimpiarFiltro.addEventListener('click', () => { filtroFechaInput.value = ''; filtrarYRenderizarMovimientos(); });

onValue(ref(db, 'accesos'), (snapshot) => { todosLosAccesos = []; const data = snapshot.val(); if (data) { todosLosAccesos = Object.values(data).reverse(); } filtrarYRenderizarMovimientos(); });
onValue(ref(db, 'retiros'), (snapshot) => { todosLosRetiros = []; const data = snapshot.val(); if (data) { todosLosRetiros = Object.values(data).reverse(); } filtrarYRenderizarMovimientos(); });

// --- GESTION DE TARJETAS RFID ---
onValue(ref(db, 'tarjetas'), (snapshot) => {
    listaUsuarios.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const tar = data[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><span style="font-family:monospace; font-weight:700;">${key}</span></td><td><strong>${tar.nombre}</strong></td><td>${tar.rol}</td><td>${tar.propietario || "---"}</td><td><button class="delete-btn" onclick="eliminarUsuarioRFID('${key}')">Eliminar</button></td>`;
            listaUsuarios.appendChild(tr);
        });
    }
});

btnGuardarUsuario.addEventListener('click', async () => {
    const uid = userUid.value.trim();
    const nom = userNombre.value.trim();
    const rol = userRol.value;
    if (!uid || !nom) { crearToast("UID y Nombre son obligatorios", "danger"); return; }
    await set(ref(db, `tarjetas/${uid}`), { activa: true, nombre: nom, propietario: "", rol: rol });
    crearToast("Tarjeta RFID autorizada", "success");
    userUid.value = ''; userNombre.value = ''; userCorreo.value = '';
});

window.eliminarUsuarioRFID = async function (uid) {
    if (confirm("Eliminar tarjeta RFID?")) { await remove(ref(db, `tarjetas/${uid}`)); crearToast("Tarjeta eliminada", "success"); }
};

// --- USUARIOS PLATAFORMA ---
onValue(ref(db, 'usuarios'), (snapshot) => {
    listaUsuariosWeb.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const usr = data[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><span style="font-family:monospace; font-weight:700;">${key}</span></td><td><strong>${usr.nombre || key}</strong></td><td>${usr.email || "---"}</td><td><span class="badge badge-green">${usr.rol || "---"}</span></td><td><button class="delete-btn" onclick="eliminarUsuarioWeb('${key}')">Eliminar</button></td>`;
            listaUsuariosWeb.appendChild(tr);
        });
    }
});

btnGuardarWebUsuario.addEventListener('click', async () => {
    const usr = webUserUsername.value.trim();
    const pass = webUserPassword.value.trim();
    const nom = webUserOperatorId.value.trim() || usr;
    const corr = webUserCorreo.value.trim();
    const rol = webUserRol.value;
    if (!usr || !pass) { crearToast("Usuario y contrasena son requeridos", "danger"); return; }
    await set(ref(db, `usuarios/${usr}`), { nombre: nom || usr, password: pass, email: corr, rol: rol });
    crearToast("Usuario registrado con exito", "success");
    webUserOperatorId.value = ''; webUserUsername.value = ''; webUserPassword.value = ''; webUserCorreo.value = '';
});

window.eliminarUsuarioWeb = async function (username) {
    if (username === "admin") { crearToast("No se puede eliminar al administrador principal", "danger"); return; }
    if (confirm(`Eliminar cuenta de ${username}?`)) { await remove(ref(db, `usuarios/${username}`)); crearToast("Cuenta eliminada", "success"); }
};

// --- SERVIDOR REMOTE ACTIONS ---
const serverCmdStatus = document.getElementById('serverCmdStatus');
document.getElementById('btnRestartServices').addEventListener('click', async () => { serverCmdStatus.innerText = "Reiniciando servicios..."; try { await set(ref(db, 'sistema/comandos_servidor'), "restart_services"); crearToast("Senal de reinicio enviada", "success"); setTimeout(() => { serverCmdStatus.innerText = ""; }, 3000); } catch { serverCmdStatus.innerText = "Error al enviar comando"; } });
document.getElementById('btnRebootPi').addEventListener('click', async () => { if (confirm("Reiniciar Raspberry Pi?")) { serverCmdStatus.innerText = "Reiniciando servidor..."; try { await set(ref(db, 'sistema/comandos_servidor'), "reboot"); crearToast("Reinicio de Raspberry enviado", "success"); } catch { serverCmdStatus.innerText = "Error"; } } });
document.getElementById('btnShutdownPi').addEventListener('click', async () => { if (confirm("Apagar Raspberry Pi?")) { serverCmdStatus.innerText = "Apagando servidor..."; try { await set(ref(db, 'sistema/comandos_servidor'), "shutdown"); crearToast("Apagado de Raspberry enviado", "success"); } catch { serverCmdStatus.innerText = "Error"; } } });