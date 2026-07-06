import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue, update, remove, set, get, push } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

// --- CONFIGURACIÓN FIREBASE ---
const OUR_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/";
const ourApp = initializeApp({ databaseURL: OUR_DB_URL }, 'ours');
const db = getDatabase(ourApp);

const NEW_CONEXION_DB_URL = "https://new-conexion-default-rtdb.firebaseio.com/";
const companionApp = initializeApp({ databaseURL: NEW_CONEXION_DB_URL }, 'companion');
const companionDb = getDatabase(companionApp);

// --- GLOBAL STATE ---
let usuarioActivo = null;
let permanenciaInterval = null;

// Initialize Admin if not exists
async function inicializarAdmin() {
    try {
        const adminRef = ref(db, 'usuarios_sistema/admin');
        const snapshot = await get(adminRef);
        if (!snapshot.exists()) {
            await set(adminRef, {
                usuario: "admin",
                passwordWeb: "admin123",
                correo: "smartstock97@gmail.com",
                rol: "SuperAdmin",
                id_operador: "ADM_001"
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
            id_operador: usuarioActivo.id_operador || "ADM_001",
            usuario: usuarioActivo.usuario,
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
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

// --- TAB NAVIGATION ---
navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        navBtns.forEach(b => b.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active');
    });
});

// Ir a Ajustes de Inventario desde el panel de Inventario
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

btnIngresar.addEventListener('click', async () => {
    const u = loginUser.value.trim();
    const p = loginPass.value.trim();
    if (!u || !p) {
        crearToast("Completa todos los campos", "danger");
        return;
    }
    try {
        const snap = await get(ref(db, `usuarios_sistema/${u}`));
        if (snap.exists()) {
            const user = snap.val();
            if (user.passwordWeb === p) {
                usuarioActivo = user;
                crearToast(`Bienvenido ${user.usuario}`, "success");
                loginOverlay.style.display = 'none';
                dashboardContainer.style.display = 'flex';
                
                // Set Profile Details
                document.getElementById('profileNombre').innerText = user.usuario;
                document.getElementById('profileRol').innerText = user.rol;
                document.getElementById('profileUsuario').innerText = user.usuario;
                document.getElementById('profileCorreo').innerText = user.correo || "—";
                document.getElementById('profileIdOperador').innerText = user.id_operador || "—";
                
                // Restrict UI tabs based on roles
                navBtns.forEach(btn => {
                    const roles = btn.dataset.roles ? btn.dataset.roles.split(',') : [];
                    if (roles.length > 0 && !roles.includes(user.rol)) {
                        btn.style.display = 'none';
                    } else {
                        btn.style.display = 'flex';
                    }
                });

                // Server tab restriction
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
                crearToast("Contraseña incorrecta", "danger");
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
                if (log.usuario === usuarioActivo.usuario) {
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
// Stay Counter (Permanencia)
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

// PIR Motion
onValue(ref(db, 'monitoreo/movimiento_pir'), (snapshot) => {
    const val = snapshot.val();
    if (val) {
        estadoPir.innerText = "MOVIMIENTO";
        subAlerta.innerText = "Se detecto movimiento";
        cardAlerta.classList.add('alert-danger');
    } else {
        estadoPir.innerText = "Seguro";
        subAlerta.innerText = "Sin movimiento";
        cardAlerta.classList.remove('alert-danger');
    }
});

// Chapa/Door Strike
onValue(ref(db, 'monitoreo/estado_chapa'), (snapshot) => {
    const val = snapshot.val();
    estadoChapa.innerText = val || "CERRADA";
    if (val === "ABIERTA") {
        cardChapa.style.borderColor = 'var(--success)';
        cardChapa.style.boxShadow = '0 10px 30px var(--success-glow)';
    } else {
        cardChapa.style.borderColor = '';
        cardChapa.style.boxShadow = '';
    }
});

// Foco Switch
onValue(ref(db, 'estado_foco'), (snapshot) => {
    const val = snapshot.val();
    estadoFoco.innerText = val || "Apagado";
    if (val === "ENCENDIDO") {
        cardFoco.style.borderColor = 'var(--warning)';
        cardFoco.style.boxShadow = '0 10px 30px var(--warning-glow)';
        subFoco.innerText = "Luz artificial encendida";
    } else {
        cardFoco.style.borderColor = '';
        cardFoco.style.boxShadow = '';
        subFoco.innerText = "Luz artificial apagada";
    }
});

// Toggle Foco Manually
document.getElementById('btnToggleFoco').addEventListener('click', async () => {
    const stateRef = ref(db, 'estado_foco');
    const snap = await get(stateRef);
    const curr = snap.val();
    const target = curr === "ENCENDIDO" ? "APAGADO" : "ENCENDIDO";
    await set(stateRef, target);
    crearToast(`Comando de luz cambiado a ${target}`, "success");
});

// Door Open Companion command
document.getElementById('btnAbrirPuertaRemota').addEventListener('click', async () => {
    try {
        await set(ref(companionDb, 'puerta/estado'), "ABIERTA");
        await set(ref(companionDb, 'puerta/ultimo_cambio'), new Date().toLocaleString());
        crearToast("Comando de apertura remota enviado a new-conexion", "success");
        setTimeout(async () => {
            await set(ref(companionDb, 'puerta/estado'), "CERRADA");
        }, 5000);
    } catch (e) {
        crearToast("Error al enviar comando companion", "danger");
    }
});

// Nocturnal Alarm Dialog (Forbidden hours motion)
const modalConfirmacionPresencia = document.getElementById('modalConfirmacionPresencia');
onValue(ref(db, 'monitoreo/alerta_pir_nocturna'), (snapshot) => {
    if (snapshot.val() === true) {
        modalConfirmacionPresencia.style.display = 'flex';
    } else {
        modalConfirmacionPresencia.style.display = 'none';
    }
});

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

// BH1750 Lux Threshold Slider
const umbralSlider = document.getElementById('umbralLuxSlider');
const umbralLabel = document.getElementById('umbralLuxLabel');

onValue(ref(db, 'configuracion/umbral_luxes'), (snap) => {
    const val = snap.val() || 100;
    umbralSlider.value = val;
    umbralLabel.innerText = `${val} lux`;
});

umbralSlider.addEventListener('input', (e) => {
    umbralLabel.innerText = `${e.target.value} lux`;
});

umbralSlider.addEventListener('change', async (e) => {
    await set(ref(db, 'configuracion/umbral_luxes'), parseInt(e.target.value));
    crearToast("Umbral de luxes guardado", "success");
});

// Save Time Foco Limit
document.getElementById('btnGuardarTiempoFoco').addEventListener('click', async () => {
    const val = parseFloat(document.getElementById('inputTiempoFoco').value) || 10;
    const unidad = document.getElementById('selectUnidadFoco').value;
    await set(ref(db, 'configuracion/tiempo_encendido_luces'), { valor: val, unidad: unidad });
    crearToast(`Temporizador de luces fijado en ${val} ${unidad}`, "success");
});

onValue(ref(db, 'configuracion/tiempo_encendido_luces'), (snap) => {
    const data = snap.val();
    if (data) {
        document.getElementById('inputTiempoFoco').value = data.valor || 10;
        document.getElementById('selectUnidadFoco').value = data.unidad || "minutos";
    }
});

// Horario Permitted Edits (Docente / SuperAdmin Only)
document.getElementById('btnGuardarHorario').addEventListener('click', async () => {
    if (usuarioActivo.rol !== "SuperAdmin" && usuarioActivo.rol !== "Docente") {
        crearToast("Acceso denegado: Solo Docente y Administrador pueden cambiar horarios", "danger");
        return;
    }
    const ini = document.getElementById('inputHoraInicio').value;
    const fin = document.getElementById('inputHoraFin').value;
    await set(ref(db, 'configuracion/horario_iluminacion'), { inicio: ini, fin: fin });
    crearToast("Horario de iluminacion guardado con exito", "success");
});

onValue(ref(db, 'configuracion/horario_iluminacion'), (snap) => {
    const data = snap.val();
    if (data) {
        document.getElementById('inputHoraInicio').value = data.inicio || "06:30";
        document.getElementById('inputHoraFin').value = data.fin || "22:00";
    }
});

// --- ESTANTE SECURITY (FC-51 IR) ---
const widgetCas1 = document.getElementById('widgetCasillero1');
const widgetCas2 = document.getElementById('widgetCasillero2');
const valCas1 = document.getElementById('valCasillero1');
const valCas2 = document.getElementById('valCasillero2');
const checkModoSeguro = document.getElementById('checkModoSeguro');
const bannerEstante = document.getElementById('alertaEstanteBanner');

onValue(ref(db, 'monitoreo/casillero1'), (snap) => {
    const val = snap.val() || "SEGURO";
    valCas1.innerText = val;
    if (val === "ALERTA") {
        widgetCas1.style.borderColor = "var(--danger)";
        widgetCas1.style.background = "rgba(192, 57, 43, 0.08)";
    } else {
        widgetCas1.style.borderColor = "var(--success)";
        widgetCas1.style.background = "";
    }
});

onValue(ref(db, 'monitoreo/casillero2'), (snap) => {
    const val = snap.val() || "SEGURO";
    valCas2.innerText = val;
    if (val === "ALERTA") {
        widgetCas2.style.borderColor = "var(--danger)";
        widgetCas2.style.background = "rgba(192, 57, 43, 0.08)";
    } else {
        widgetCas2.style.borderColor = "var(--success)";
        widgetCas2.style.background = "";
    }
});

onValue(ref(db, 'monitoreo/modo_seguro_estante'), (snap) => {
    checkModoSeguro.checked = snap.val() || false;
});

checkModoSeguro.addEventListener('change', async () => {
    if (usuarioActivo.rol !== "SuperAdmin" && usuarioActivo.rol !== "Docente") {
        crearToast("Acceso denegado: Solo Docente y Administrador pueden modificar este modo", "danger");
        checkModoSeguro.checked = !checkModoSeguro.checked;
        return;
    }
    await set(ref(db, 'monitoreo/modo_seguro_estante'), checkModoSeguro.checked);
    if (checkModoSeguro.checked) {
        await set(ref(db, 'monitoreo/alerta_estante'), "");
    }
    crearToast(`Modo retiro seguro ${checkModoSeguro.checked ? "activado" : "desactivado"}`, "success");
});

onValue(ref(db, 'monitoreo/alerta_estante'), (snap) => {
    const val = snap.val() || "";
    if (val) {
        bannerEstante.innerText = `ALERTA: ${val}`;
        bannerEstante.style.display = "block";
    } else {
        bannerEstante.style.display = "none";
    }
});

// --- INVENTARIO MANAGER ---
let listCarreras = ["TAIPT", "TIRE", "TAI"];
let listCategorias = ["Hardware", "Herramientas", "Accesorios", "Otros"];

onValue(ref(db, 'configuracion/carreras'), (snap) => {
    const data = snap.val();
    if (data) {
        listCarreras = Object.values(data);
    }
    actualizarDropdownsYListas();
});

onValue(ref(db, 'configuracion/categorias'), (snap) => {
    const data = snap.val();
    if (data) {
        listCategorias = Object.values(data);
    }
    actualizarDropdownsYListas();
});

function actualizarDropdownsYListas() {
    const comboCar = document.getElementById('invCarrera');
    const comboCat = document.getElementById('invCategoria');
    const uiCar = document.getElementById('listaAjustesCarreras');
    const uiCat = document.getElementById('listaAjustesCategorias');

    if (comboCar) {
        comboCar.innerHTML = listCarreras.map(c => `<option value="${c}">${c}</option>`).join('');
    }
    if (comboCat) {
        comboCat.innerHTML = listCategorias.map(c => `<option value="${c}">${c}</option>`).join('');
    }

    if (uiCar) {
        uiCar.innerHTML = listCarreras.map(c => `
            <li style="display:flex; justify-content:space-between; padding:8px; border-bottom:1px solid var(--glass-border);">
                <span>${c}</span>
                <button class="delete-btn" style="padding:2px 8px;" onclick="eliminarCarrera('${c}')">Eliminar</button>
            </li>
        `).join('');
    }

    if (uiCat) {
        uiCat.innerHTML = listCategorias.map(c => `
            <li style="display:flex; justify-content:space-between; padding:8px; border-bottom:1px solid var(--glass-border);">
                <span>${c}</span>
                <button class="delete-btn" style="padding:2px 8px;" onclick="eliminarCategoria('${c}')">Eliminar</button>
            </li>
        `).join('');
    }
}

// Add Career & Category
document.getElementById('btnAgregarCarrera').addEventListener('click', async () => {
    const val = document.getElementById('inputNuevaCarrera').value.trim().toUpperCase();
    if (val && !listCarreras.includes(val)) {
        await push(ref(db, 'configuracion/carreras'), val);
        document.getElementById('inputNuevaCarrera').value = '';
        crearToast("Carrera añadida", "success");
    }
});

document.getElementById('btnAgregarCategoria').addEventListener('click', async () => {
    const val = document.getElementById('inputNuevaCategoria').value.trim();
    if (val && !listCategorias.includes(val)) {
        await push(ref(db, 'configuracion/categorias'), val);
        document.getElementById('inputNuevaCategoria').value = '';
        crearToast("Categoria añadida", "success");
    }
});

window.eliminarCarrera = async function(car) {
    const snap = await get(ref(db, 'configuracion/carreras'));
    if (snap.exists()) {
        const data = snap.val();
        const key = Object.keys(data).find(k => data[k] === car);
        if (key) {
            await remove(ref(db, `configuracion/carreras/${key}`));
            crearToast("Carrera eliminada", "success");
        }
    }
};

window.eliminarCategoria = async function(cat) {
    const snap = await get(ref(db, 'configuracion/categorias'));
    if (snap.exists()) {
        const data = snap.val();
        const key = Object.keys(data).find(k => data[k] === cat);
        if (key) {
            await remove(ref(db, `configuracion/categorias/${key}`));
            crearToast("Categoria eliminada", "success");
        }
    }
};

// Inventario Render
let todosLosProductos = {};
const invSearchInput = document.getElementById('invSearchInput');

function renderInventario() {
    listaInventario.innerHTML = '';
    const query = invSearchInput.value.toLowerCase().trim();
    
    Object.keys(todosLosProductos).forEach(key => {
        const prod = todosLosProductos[key];
        const nombre = prod.nombre_producto || '—';
        const carrera = prod.carrera || '—';
        const categoria = prod.categoria || 'Otros';
        const ubicacion = prod.ubicacion || '—';
        const stock = prod.stock || 0;
        const estado = prod.estado || 'Funcional';

        if (query && !key.toLowerCase().includes(query) && !nombre.toLowerCase().includes(query)) {
            return;
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><span style="font-family:monospace; color:var(--primary); font-weight:700;">${key}</span></td>
            <td><strong>${nombre}</strong></td>
            <td>${carrera}</td>
            <td>${categoria}</td>
            <td>${ubicacion}</td>
            <td><span class="badge ${stock > 0 ? 'badge-green' : 'badge-red'}">${stock} und</span></td>
            <td><span class="badge ${estado === 'Funcional' ? 'badge-green' : estado === 'Regular' ? 'badge-orange' : 'badge-red'}">${estado}</span></td>
            <td style="display:flex; gap:6px;">
                <button class="edit-btn" onclick="editarProducto('${key}')">Editar</button>
                <button class="delete-btn" onclick="eliminarProducto('${key}')">Eliminar</button>
            </td>
        `;
        listaInventario.appendChild(tr);
    });
}

invSearchInput.addEventListener('input', renderInventario);

onValue(ref(db, 'inventario'), (snapshot) => {
    todosLosProductos = snapshot.val() || {};
    renderInventario();
    renderQRAltaPanel();
});

// Add / Edit Product
document.getElementById('btnAgregarInventario').addEventListener('click', async () => {
    const id = document.getElementById('invId').value || 'PRD_' + Math.random().toString(36).substr(2, 6).toUpperCase();
    const nombre = document.getElementById('invNombre').value.trim();
    const ubic = document.getElementById('invUbicacion').value.trim();
    const stock = parseInt(document.getElementById('invStock').value) || 0;
    const carrera = document.getElementById('invCarrera').value;
    const categoria = document.getElementById('invCategoria').value;
    const estado = document.getElementById('invEstado').value;

    if (!nombre) {
        crearToast("Ingresa el nombre del producto", "danger");
        return;
    }

    await set(ref(db, `inventario/${id}`), {
        nombre_producto: nombre,
        ubicacion: ubic,
        stock: stock,
        carrera: carrera,
        categoria: categoria,
        estado: estado
    });

    crearToast("Producto registrado", "success");
    
    // Clear Form
    document.getElementById('invId').value = '';
    document.getElementById('invNombre').value = '';
    document.getElementById('invUbicacion').value = '';
    document.getElementById('invStock').value = '';
});

window.editarProducto = function(id) {
    const prod = todosLosProductos[id];
    if (prod) {
        document.getElementById('invId').value = id;
        document.getElementById('invNombre').value = prod.nombre_producto || '';
        document.getElementById('invUbicacion').value = prod.ubicacion || '';
        document.getElementById('invStock').value = prod.stock || 0;
        document.getElementById('invCarrera').value = prod.carrera || '';
        document.getElementById('invCategoria').value = prod.categoria || '';
        document.getElementById('invEstado').value = prod.estado || 'Funcional';
        crearToast("Cargado en formulario", "info");
    }
};

window.eliminarProducto = async function(id) {
    if (confirm("¿Estás seguro de eliminar este producto?")) {
        await remove(ref(db, `inventario/${id}`));
        crearToast("Producto eliminado", "success");
    }
};

// --- QR Alta Panel ---
const qrSearch = document.getElementById('qrSearchInput');
function renderQRAltaPanel() {
    const grid = document.getElementById('labelsPrintGrid');
    if (!grid) return;
    grid.innerHTML = '';
    const query = qrSearch.value.toLowerCase().trim();

    Object.keys(todosLosProductos).forEach(key => {
        const prod = todosLosProductos[key];
        const nombre = prod.nombre_producto || '—';

        if (query && !key.toLowerCase().includes(query) && !nombre.toLowerCase().includes(query)) {
            return;
        }

        const div = document.createElement('div');
        div.className = "printable-badge";
        div.style.position = "relative";
        div.innerHTML = `
            <input type="checkbox" class="qr-print-check" data-id="${key}" style="position:absolute; top:10px; right:10px; width:20px; height:20px; cursor:pointer;">
            <div class="badge-header">UCUENCA - SMART STOCK</div>
            <div class="qr-preview-img" id="qr-container-${key}" style="padding:10px; background:white;"></div>
            <div class="badge-footer">${key}</div>
        `;
        grid.appendChild(div);

        // Generate QR code (CORRECT URL points to web domain)
        setTimeout(() => {
            const container = document.getElementById(`qr-container-${key}`);
            if (container) {
                new QRCode(container, {
                    text: `https://smartstock.eu1.netbird.services/retiro.html?id=${key}`,
                    width: 100,
                    height: 100
                });
            }
        }, 100);
    });
}

qrSearch.addEventListener('input', renderQRAltaPanel);

// Export QRs Selected to PDF (3x4 cm)
document.getElementById('btnExportarPdfLabels').addEventListener('click', () => {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({
        unit: 'mm',
        format: [30, 40]
    });

    const checks = document.querySelectorAll('.qr-print-check:checked');
    if (checks.length === 0) {
        crearToast("Selecciona al menos un código QR para exportar", "danger");
        return;
    }

    checks.forEach((chk, index) => {
        const key = chk.dataset.id;
        const container = document.getElementById(`qr-container-${key}`);
        if (!container) return;
        const imgEl = container.querySelector('img');
        if (imgEl && imgEl.src) {
            if (index > 0) doc.addPage([30, 40]);
            doc.addImage(imgEl.src, 'PNG', 3, 2, 24, 24);
            doc.setFontSize(6);
            doc.setFont("courier", "bold");
            doc.text(key, 15, 34, { align: 'center' });
        }
    });

    doc.save(`etiquetas_seleccionadas.pdf`);
    crearToast("PDF de etiquetas generado", "success");
});

// --- HISTORIAL DE MOVIMIENTOS ---
let todosLosAccesos = [];
let todosLosRetiros = [];
const filtroFechaInput = document.getElementById('filtroFechaMovimientos');
const btnLimpiarFiltro = document.getElementById('btnLimpiarFiltroFecha');

function filtrarYRenderizarMovimientos() {
    const fechaFiltro = filtroFechaInput.value; // YYYY-MM-DD
    
    // Render Accesos
    listaAccesos.innerHTML = '';
    const accesosFiltrados = todosLosAccesos.filter(acc => {
        if (!fechaFiltro) return true;
        // Parse acc.hora_ingreso (YYYY-MM-DD HH:MM:SS or DD/MM/YYYY)
        const fechaAcc = acc.hora_ingreso || "";
        if (fechaAcc.includes(fechaFiltro)) return true;
        
        // standard format check
        try {
            const dateParts = fechaAcc.split(" ")[0]; // YYYY-MM-DD
            return dateParts === fechaFiltro;
        } catch {
            return false;
        }
    });

    if (accesosFiltrados.length > 0) {
        accesosFiltrados.forEach(acc => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${acc.docente}</strong></td>
                <td><span class="badge badge-green">${acc.metodo_acceso}</span></td>
                <td>${acc.rol || "Docente"}</td>
                <td>${acc.hora_ingress || acc.hora_ingreso || "—"}</td>
                <td>${acc.hora_salida || "—"}</td>
                <td>${acc.tiempo_permanencia_min || 0} min</td>
                <td>${acc.acompanantes_al_ingresar || 0}</td>
                <td>${acc.saca_producto ? 'Sí' : 'No'}</td>
            `;
            listaAccesos.appendChild(tr);
        });
    } else {
        listaAccesos.innerHTML = '<tr><td colspan="8">Sin accesos registrados para esta fecha.</td></tr>';
    }

    // Render Retiros
    listaRetiros.innerHTML = '';
    const retirosFiltrados = todosLosRetiros.filter(ret => {
        if (!fechaFiltro) return true;
        // ret.fecha is DD/MM/YYYY HH:MM:SS or similar.
        // Let's convert YYYY-MM-DD to DD/MM/YYYY to compare
        const parts = fechaFiltro.split("-");
        const formatEs = `${parts[2]}/${parts[1]}/${parts[0]}`; // DD/MM/YYYY
        return ret.fecha && ret.fecha.includes(formatEs);
    });

    if (retirosFiltrados.length > 0) {
        retirosFiltrados.forEach(ret => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${ret.nombre_producto}</strong></td>
                <td>${ret.producto_id}</td>
                <td>${ret.cantidad_retirada}</td>
                <td>${ret.stock_anterior}</td>
                <td>${ret.stock_nuevo}</td>
                <td>${ret.usuario}</td>
                <td>${ret.fecha}</td>
            `;
            listaRetiros.appendChild(tr);
        });
    } else {
        listaRetiros.innerHTML = '<tr><td colspan="7">Sin retiros registrados para esta fecha.</td></tr>';
    }
}

if (filtroFechaInput) {
    filtroFechaInput.addEventListener('change', filtrarYRenderizarMovimientos);
}
if (btnLimpiarFiltro) {
    btnLimpiarFiltro.addEventListener('click', () => {
        filtroFechaInput.value = '';
        filtrarYRenderizarMovimientos();
    });
}

onValue(ref(db, 'accesos'), (snapshot) => {
    todosLosAccesos = [];
    const data = snapshot.val();
    if (data) {
        todosLosAccesos = Object.values(data).reverse();
    }
    filtrarYRenderizarMovimientos();
});

onValue(ref(db, 'retiros'), (snapshot) => {
    todosLosRetiros = [];
    const data = snapshot.val();
    if (data) {
        todosLosRetiros = Object.values(data).reverse();
    }
    filtrarYRenderizarMovimientos();
});

// --- PERSONAL RFID AND WEB PLATAFORMA ---
onValue(ref(db, 'usuarios'), (snapshot) => {
    listaUsuarios.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const usr = data[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span style="font-family:monospace; font-weight:700;">${key}</span></td>
                <td><strong>${usr.nombre}</strong></td>
                <td>${usr.rol}</td>
                <td>${usr.correo}</td>
                <td>
                    <button class="delete-btn" onclick="eliminarUsuarioRFID('${key}')">Eliminar</button>
                </td>
            `;
            listaUsuarios.appendChild(tr);
        });
    }
});

btnGuardarUsuario.addEventListener('click', async () => {
    const uid = userUid.value.trim();
    const nom = userNombre.value.trim();
    const rol = userRol.value;
    const corr = userCorreo.value.trim();
    if (!uid || !nom) {
        crearToast("UID y Nombre son obligatorios", "danger");
        return;
    }
    await set(ref(db, `usuarios/${uid}`), { nombre: nom, rol: rol, correo: corr });
    crearToast("Tarjeta RFID autorizada", "success");
    userUid.value = '';
    userNombre.value = '';
    userCorreo.value = '';
});

window.eliminarUsuarioRFID = async function(uid) {
    if (confirm("¿Eliminar acceso a este docente?")) {
        await remove(ref(db, `usuarios/${uid}`));
        crearToast("Acceso revocado", "success");
    }
};

// Web Users
onValue(ref(db, 'usuarios_sistema'), (snapshot) => {
    listaUsuariosWeb.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const usr = data[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span style="font-family:monospace; font-weight:700;">${usr.id_operador || "—"}</span></td>
                <td><strong>${usr.usuario}</strong></td>
                <td>${usr.correo}</td>
                <td><span class="badge badge-green">${usr.rol}</span></td>
                <td>
                    <button class="delete-btn" onclick="eliminarUsuarioWeb('${key}')">Eliminar</button>
                </td>
            `;
            listaUsuariosWeb.appendChild(tr);
        });
    }
});

btnGuardarWebUsuario.addEventListener('click', async () => {
    const op = webUserOperatorId.value.trim();
    const usr = webUserUsername.value.trim();
    const pass = webUserPassword.value.trim();
    const corr = webUserCorreo.value.trim();
    const rol = webUserRol.value;

    if (!op || !usr || !pass) {
        crearToast("ID, usuario y contraseña son requeridos", "danger");
        return;
    }
    await set(ref(db, `usuarios_sistema/${usr}`), {
        id_operador: op,
        usuario: usr,
        passwordWeb: pass,
        correo: corr,
        rol: rol
    });
    crearToast("Usuario registrado con éxito", "success");
    webUserOperatorId.value = '';
    webUserUsername.value = '';
    webUserPassword.value = '';
    webUserCorreo.value = '';
});

window.eliminarUsuarioWeb = async function(username) {
    if (username === "admin") {
        crearToast("No se puede eliminar al administrador principal", "danger");
        return;
    }
    if (confirm(`¿Eliminar cuenta web de ${username}?`)) {
        await remove(ref(db, `usuarios_sistema/${username}`));
        crearToast("Cuenta web eliminada", "success");
    }
};

// --- SERVIDOR REMOTE ACTIONS ---
const serverCmdStatus = document.getElementById('serverCmdStatus');

document.getElementById('btnRestartServices').addEventListener('click', async () => {
    serverCmdStatus.innerText = "Reiniciando servicios...";
    try {
        await set(ref(db, 'sistema/comandos_servidor'), "restart_services");
        crearToast("Señal de reinicio de servicios enviada", "success");
        setTimeout(() => { serverCmdStatus.innerText = ""; }, 3000);
    } catch {
        serverCmdStatus.innerText = "Error al enviar comando";
    }
});

document.getElementById('btnRebootPi').addEventListener('click', async () => {
    if (confirm("¿Rebotar la Raspberry Pi de forma remota?")) {
        serverCmdStatus.innerText = "Reiniciando servidor...";
        try {
            await set(ref(db, 'sistema/comandos_servidor'), "reboot");
            crearToast("Señal de reinicio de Raspberry enviada", "success");
        } catch {
            serverCmdStatus.innerText = "Error al enviar comando";
        }
    }
});

document.getElementById('btnShutdownPi').addEventListener('click', async () => {
    if (confirm("¿Apagar la Raspberry Pi de forma remota?")) {
        serverCmdStatus.innerText = "Apagando servidor...";
        try {
            await set(ref(db, 'sistema/comandos_servidor'), "shutdown");
            crearToast("Señal de apagado de Raspberry enviada", "success");
        } catch {
            serverCmdStatus.innerText = "Error al enviar comando";
        }
    }
});
