import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue, update, remove, set, get, push } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

// --- CONFIGURACIÓN FIREBASE ---
const firebaseConfig = {
    databaseURL: "https://aula-4587b-default-rtdb.firebaseio.com/"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

// --- GLOBAL STATE ---
let usuarioActivo = null;

// Audio alarm state (declared globally to avoid TDZ with Firebase listeners)
let audioCtx = null;
let beepInterval = null;

// Inicializar el admin en Firebase si no existe
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
            console.log("[Firebase] Admin de sistema inicializado correctamente.");
        }
    } catch (e) {
        console.error("Error al inicializar admin en Firebase:", e);
    }
}
inicializarAdmin();

// --- AUDIT TRAIL LOGGING ---
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
        console.error("Error al registrar auditoría:", e);
    }
}

// --- UI VARIABLES ---
const navBtns = document.querySelectorAll('.nav-btn');
const panels = document.querySelectorAll('.panel');

const countPersonas = document.getElementById('countPersonas');
const estadoPir = document.getElementById('estadoPir');
const subAlerta = document.getElementById('subAlerta');
const cardAlerta = document.getElementById('cardAlerta');
const iconAlerta = document.getElementById('iconAlerta');

const estadoChapa = document.getElementById('estadoChapa');
const cardChapa = document.getElementById('cardChapa');
const iconChapa = document.getElementById('iconChapa');

const estadoFoco = document.getElementById('estadoFoco');
const cardFoco = document.getElementById('cardFoco');
const subFoco = document.getElementById('subFoco');

const estadoPuerta = document.getElementById('estadoPuerta');
const cardPuerta = document.getElementById('cardPuerta');
const subPuerta = document.getElementById('subPuerta');
const iconPuerta = document.getElementById('iconPuerta');

const estadoInfrarrojo = document.getElementById('estadoInfrarrojo');
const cardInfrarrojo = document.getElementById('cardInfrarrojo');
const subInfrarrojo = document.getElementById('subInfrarrojo');
const iconInfrarrojo = document.getElementById('iconInfrarrojo');

const listaInventario = document.getElementById('listaInventario');
const listaAccesos = document.getElementById('listaAccesos');
const listaUsuarios = document.getElementById('listaUsuarios');
const listaUsuariosWeb = document.getElementById('listaUsuariosWeb');

// Formulario Usuarios RFID
const btnGuardarUsuario = document.getElementById('btnGuardarUsuario');
const userUid = document.getElementById('userUid');
const userNombre = document.getElementById('userNombre');
const userRol = document.getElementById('userRol');

// Formulario Usuarios Web Plataforma
const btnGuardarWebUsuario = document.getElementById('btnGuardarWebUsuario');
const webUserOperatorId = document.getElementById('webUserOperatorId');
const webUserUsername = document.getElementById('webUserUsername');
const webUserPassword = document.getElementById('webUserPassword');
const webUserCorreo = document.getElementById('webUserCorreo');
const webUserRol = document.getElementById('webUserRol');
const webUserFormTitle = document.getElementById('webUserFormTitle');

// Botón Datos Semilla
const btnSeedData = document.getElementById('btnSeedData');

// QR Labels panel
const qrSearchInput = document.getElementById('qrSearchInput');
const labelsPrintGrid = document.getElementById('labelsPrintGrid');
const btnExportarPdfLabels = document.getElementById('btnExportarPdfLabels');

// --- NAVEGACIÓN ---
navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        navBtns.forEach(b => b.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active');
    });
});

// --- HAMBURGER MENU (MOBILE) ---
const hamburgerBtn = document.getElementById('hamburgerBtn');
const sidebar = document.getElementById('sidebar');
if (hamburgerBtn && sidebar) {
    hamburgerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.toggle('active');
    });

    // Close sidebar when clicking a nav button on mobile
    sidebar.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('active');
            }
        });
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && sidebar.classList.contains('active')) {
            if (!sidebar.contains(e.target) && e.target !== hamburgerBtn && !hamburgerBtn.contains(e.target)) {
                sidebar.classList.remove('active');
            }
        }
    });

    // Show hamburger on mobile
    function checkMobile() {
        if (window.innerWidth <= 768) {
            hamburgerBtn.style.display = 'flex';
        } else {
            hamburgerBtn.style.display = 'none';
            sidebar.classList.remove('active');
        }
    }
    window.addEventListener('resize', checkMobile);
    checkMobile();
}

// --- SISTEMA TIME & DATE ---
setInterval(() => {
    const ahora = new Date();
    document.getElementById('system-time').innerText = ahora.toLocaleTimeString('es-ES');
}, 1000);

// --- CHART.JS CONFIG ---
let traficoChart = null;
try {
    if (typeof Chart !== 'undefined') {
        const ctx = document.getElementById('traficoChart').getContext('2d');
        traficoChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Personas en el Aula (Historial)',
                    data: [],
                    borderColor: '#c8956c',
                    backgroundColor: 'rgba(200, 149, 108, 0.08)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#d4a574',
                    pointBorderColor: '#fff',
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.03)' },
                        ticks: { color: '#94a3b8', stepSize: 1 }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    } else {
        console.warn("Chart.js no está cargado. Se omitirá el gráfico de afluencia.");
    }
} catch (e) {
    console.error("Error al inicializar Chart.js: ", e);
}

// Función para actualizar gráfico limitando a 12 puntos
function updateChart(timeLabel, personas) {
    if (!traficoChart) return;
    if (traficoChart.data.labels.length > 12) {
        traficoChart.data.labels.shift();
        traficoChart.data.datasets[0].data.shift();
    }
    // Evitar añadir duplicados si el último punto de tiempo es el mismo
    if (traficoChart.data.labels.length > 0 && traficoChart.data.labels[traficoChart.data.labels.length - 1] === timeLabel) {
        traficoChart.data.datasets[0].data[traficoChart.data.datasets[0].data.length - 1] = personas;
    } else {
        traficoChart.data.labels.push(timeLabel);
        traficoChart.data.datasets[0].data.push(personas);
    }
    traficoChart.update();
}

// --- FIREBASE: MONITOREO TIEMPO REAL ---
let currentPuertaState = 'CERRADA';
let currentPirState = false;

function verificarIntrusion() {
    if (currentPuertaState === 'CERRADA' && currentPirState) {
        estadoPir.innerText = "[!] INTRUSIÓN";
        subAlerta.innerText = "¡Movimiento con puerta cerrada!";
        cardAlerta.classList.add('alert-danger');
        cardAlerta.classList.remove('card-secure');
        iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;
        mostrarAlertaCritica("¡Movimiento detectado con el cerrojo de la puerta CERRADO!");
    } else if (currentPirState) {
        estadoPir.innerText = "[!] ALERTA";
        subAlerta.innerText = "¡Movimiento detectado!";
        cardAlerta.classList.add('alert-danger');
        cardAlerta.classList.remove('card-secure');
        iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;
        detenerAlertaCritica();
    } else {
        estadoPir.innerText = "Seguro";
        subAlerta.innerText = "No se detecta movimiento";
        cardAlerta.classList.remove('alert-danger');
        cardAlerta.classList.add('card-secure');
        iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12,12A5,5 0 1,1 17,7A5,5 0 0,1 12,12M12,14C17.07,14 21,16.24 21,19v2H3V19C3,16.24 6.93,14 12,14Z"/></svg>`;
        detenerAlertaCritica();
    }
}

// Sensor PIR
onValue(ref(db, 'movimiento_pir'), (snapshot) => {
    const val = snapshot.val();
    currentPirState = (val === true || val === "true" || val === "Movimiento Detectado" || val === 1 || val === "1");
    verificarIntrusion();
});

// Sensor Puerta (Cerrojo Eléctrico / Estado de la Puerta)
onValue(ref(db, 'puerta_fisica/estado'), (snapshot) => {
    const val = snapshot.val();
    const isOpen = (val === true || val === "true" || val === "ABIERTA" || val === "abierta" || val === 1 || val === "1");
    currentPuertaState = isOpen ? 'ABIERTA' : 'CERRADA';

    estadoChapa.innerText = currentPuertaState;
    if (isOpen) {
        cardChapa.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        cardChapa.style.boxShadow = '0 10px 30px rgba(16, 185, 129, 0.15)';
        iconChapa.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" class="lock-open"><path fill="currentColor" d="M18,8H16V6A4,4 0 0,0 8,6V8H6A2,2 0 0,0 4,10V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V10A2,2 0 0,0 18,8M9,6A2,2 0 0,1 13,4A2,2 0 0,1 15,6V8H9V6M18,20H6V10H18V20M12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17A2,2 0 0,0 14,15A2,2 0 0,0 12,13Z"/></svg>`;
        cardChapa.querySelector('.metric-sub').innerText = "Acceso liberado";
    } else {
        cardChapa.style.borderColor = '';
        cardChapa.style.boxShadow = '';
        iconChapa.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" class="lock-closed"><path fill="currentColor" d="M18,8H17V6A5,5 0 0,0 7,6V8H6A2,2 0 0,0 4,10V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V10A2,2 0 0,0 18,8M9,6A3,3 0 0,1 15,6V8H9V6M18,20H6V10H18V20M12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17A2,2 0 0,0 14,15A2,2 0 0,0 12,13Z"/></svg>`;
        cardChapa.querySelector('.metric-sub').innerText = "Puerta asegurada";
    }
    verificarIntrusion();
});

// Sensor Infrarrojo (Cantidad de Personas / Aforo)
onValue(ref(db, 'aforo'), (snapshot) => {
    const val = snapshot.val();
    const personas = (val !== null && val !== undefined) ? parseInt(val) || 0 : 0;
    countPersonas.innerText = personas;

    const timeStr = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    updateChart(timeStr, personas);
});

// --- FIREBASE: CONTROL FOCO INTELIGENTE MERCURY ---
onValue(ref(db, 'movimiento_pir'), (snapshot) => {
    const raw = snapshot.val();
    const val = (raw || "").toString().trim().toUpperCase();
    const isEncendido = (val === "ENCENDIDO" || val === "ON" || val === "TRUE" || val === "1");
    if (isEncendido) {
        estadoFoco.innerHTML = '<span class="badge badge-green" style="box-shadow: 0 0 10px rgba(16,185,129,0.5);">[Luz] Encendido</span>';
        cardFoco.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        cardFoco.style.boxShadow = '0 10px 30px rgba(16, 185, 129, 0.15)';
        subFoco.innerText = "Luz artificial activada";
    } else {
        estadoFoco.innerHTML = '<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-muted); border: 1px solid rgba(148, 163, 184, 0.3);">[Off] Apagado</span>';
        cardFoco.style.borderColor = '';
        cardFoco.style.boxShadow = '';
        subFoco.innerText = "Luz artificial desactivada";
    }
});

// --- FIREBASE: INVENTARIO ---
let todosLosProductos = {};
onValue(ref(db, 'inventario'), (snapshot) => {
    listaInventario.innerHTML = '';
    const data = snapshot.val();
    todosLosProductos = data || {};
    actualizarEtiquetasQR();
    if (data) {
        Object.keys(data).forEach(key => {
            const prod = data[key];
            const ubicacion = prod.ubicacion || 'No asignada';
            const categoria = prod.categoria || 'General';
            const estado = prod.estado || 'Funcional';
            const estadoBadge = estado === 'Funcional'
                ? '<span class="badge badge-green">Funcional</span>'
                : '<span class="badge badge-red">No Funcional</span>';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span style="font-family:monospace; color:var(--primary); font-weight:700;">${key}</span></td>
                <td>${prod.nombre_producto}</td>
                <td><span class="badge ${prod.stock > 0 ? 'badge-green' : 'badge-red'}">${prod.stock} unidades</span></td>
                <td>${ubicacion}</td>
                <td>${categoria}</td>
                <td>${estadoBadge}</td>
                <td>
                    <button class="edit-btn" data-id="${key}">Editar</button>
                    <button class="delete-btn" data-id="${key}">Eliminar</button>
                    <button class="qr-btn" data-id="${key}" data-nombre="${prod.nombre_producto}" style="padding:6px 12px; background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.4); color:var(--primary); border-radius:8px; font-weight:600; cursor:pointer; transition:all 0.2s;">QR</button>
                </td>
            `;
            tr.querySelector('.qr-btn').addEventListener('click', (e) => {
                const id = e.currentTarget.dataset.id;
                const nombre = e.currentTarget.dataset.nombre;
                mostrarModalQR(id, nombre);
            });
            tr.querySelector('.edit-btn').addEventListener('click', (e) => {
                const id = e.currentTarget.dataset.id;
                cargarFormularioProducto(id, prod);
            });
            tr.querySelector('.delete-btn').addEventListener('click', (e) => {
                const id = e.currentTarget.dataset.id;
                eliminarProducto(id);
            });
            listaInventario.appendChild(tr);
        });
    } else {
        listaInventario.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No hay productos registrados.</td></tr>';
    }
});

// --- FIREBASE: ACCESOS HISTÓRICOS ---
onValue(ref(db, 'accesos'), (snapshot) => {
    listaAccesos.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        // Ordenar por más recientes primero
        const keys = Object.keys(data).reverse();
        keys.forEach(key => {
            const acc = data[key];

            const tIngreso = acc.hora_ingreso ? acc.hora_ingreso : '--';
            const tSalida = acc.hora_salida ? acc.hora_salida : 'Activo';
            const permanencia = acc.hora_salida ? acc.tiempo_permanencia_min + ' min' : '<span class="badge badge-green">En Aula</span>';
            const sacaProd = acc.saca_producto ? `<span class="badge badge-orange">Extracción (${acc.producto_extraido_id})</span>` : 'Ninguna';

            // Método de acceso (RFID o Teclado)
            const metodo = acc.metodo_acceso || 'rfid';
            const metodoBadge = metodo === 'teclado'
                ? '<span class="badge badge-blue">[Teclado] Teclado</span>'
                : '<span class="badge badge-purple">[RFID] RFID</span>';
            const codigoRef = acc.codigo_usado ? `<br><span style="color:var(--text-muted); font-size:0.75rem; font-family:monospace;">${acc.codigo_usado}</span>` : '';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${acc.docente}</strong>${codigoRef}</td>
                <td>${metodoBadge}</td>
                <td><span style="color:var(--text-muted); font-size:0.85rem;">${acc.rol || ''}</span></td>
                <td>${tIngreso}</td>
                <td>${tSalida}</td>
                <td>${permanencia}</td>
                <td><span style="font-weight:700;">${acc.acompanantes_al_ingresar}</span></td>
                <td>${sacaProd}</td>
            `;
            listaAccesos.appendChild(tr);
        });
    } else {
        listaAccesos.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No hay registros de acceso.</td></tr>';
    }
});

// --- FIREBASE: GESTIÓN DE USUARIOS RFID ---
onValue(ref(db, 'usuarios'), (snapshot) => {
    listaUsuarios.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const user = data[key];
            const tr = document.createElement('tr');
            const nombreDocente = user.nombre || '';
            tr.innerHTML = `
                <td><span style="font-family:monospace; color:var(--accent); font-weight:700;">${key}</span></td>
                <td><strong>${nombreDocente}</strong></td>
                <td>${user.rol}</td>
                <td><span style="font-size:0.8rem; color:var(--text-muted);">${user.correo || '---'}</span></td>
                <td><button class="qr-btn" data-nombre="${nombreDocente}" style="padding:5px 10px; background:rgba(109,184,122,0.15); border:1px solid rgba(109,184,122,0.3); color:var(--success); border-radius:8px; font-weight:600; cursor:pointer; font-size:0.75rem;">Ver</button></td>
                <td style="display:flex; gap:6px; flex-wrap:wrap;">
                    <button class="edit-btn" data-uid="${key}">Editar</button>
                    <button class="delete-btn" data-uid="${key}">Eliminar</button>
                </td>
            `;
            tr.querySelector('.qr-btn').addEventListener('click', () => mostrarActividadDocente(nombreDocente));
            tr.querySelector('.delete-btn').addEventListener('click', (e) => {
                const uid = e.currentTarget.dataset.uid;
                if (confirm(`¿Estás seguro de revocar el acceso a ${user.nombre}?`)) {
                    remove(ref(db, `usuarios/${uid}`))
                        .then(() => {
                            registrarAuditoria('Eliminación Docente', `Docente eliminado: ${user.nombre} (UID: ${uid})`);
                            crearToast('Usuario eliminado correctamente.', 'success');
                        })
                        .catch(err => alert('Error al eliminar: ' + err));
                }
            });
            tr.querySelector('.edit-btn').addEventListener('click', () => {
                cargarFormularioDocente(key, user);
            });
            listaUsuarios.appendChild(tr);
        });
    } else {
        listaUsuarios.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No hay docentes registrados en la base de datos.</td></tr>';
    }
});

// --- FIREBASE: GESTIÓN DE USUARIOS DE PLATAFORMA ---
let editingWebUserId = null;

onValue(ref(db, 'usuarios_sistema'), (snapshot) => {
    if (!listaUsuariosWeb) return;
    listaUsuariosWeb.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const user = data[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span style="font-family:monospace; color:var(--primary); font-weight:700;">${user.id_operador || '---'}</span></td>
                <td><strong>${user.usuario}</strong></td>
                <td><span style="font-size:0.8rem; color:var(--text-muted);">${user.correo || '---'}</span></td>
                <td><span class="badge badge-purple">${user.rol}</span></td>
                <td style="display:flex; gap:6px; flex-wrap:wrap;">
                    <button class="edit-btn" data-key="${key}">Editar</button>
                    <button class="delete-btn" data-key="${key}">Eliminar</button>
                </td>
            `;
            tr.querySelector('.delete-btn').addEventListener('click', (e) => {
                const k = e.currentTarget.dataset.key;
                if (usuarioActivo && usuarioActivo.usuario === user.usuario) {
                    alert("No puedes eliminar el usuario con el que has iniciado sesión actualmente.");
                    return;
                }
                if (confirm(`¿Estás seguro de eliminar el usuario de plataforma ${user.usuario}?`)) {
                    remove(ref(db, `usuarios_sistema/${k}`))
                        .then(() => {
                            registrarAuditoria('Eliminación Usuario Plataforma', `Usuario eliminado: ${user.usuario} (ID Operador: ${user.id_operador})`);
                            crearToast('Usuario de plataforma eliminado.', 'success');
                        })
                        .catch(err => alert('Error al eliminar: ' + err));
                }
            });
            tr.querySelector('.edit-btn').addEventListener('click', () => {
                cargarFormularioWebUsuario(key, user);
            });
            listaUsuariosWeb.appendChild(tr);
        });
    } else {
        listaUsuariosWeb.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No hay usuarios de plataforma registrados.</td></tr>';
    }
});

function cargarFormularioWebUsuario(key, user) {
    if (!webUserOperatorId) return;
    webUserOperatorId.value = user.id_operador || '';
    webUserOperatorId.readOnly = true;
    webUserOperatorId.style.background = "rgba(0,0,0,0.2)";
    webUserOperatorId.style.cursor = "not-allowed";

    webUserUsername.value = user.usuario || '';
    webUserPassword.value = user.passwordWeb || '';
    webUserCorreo.value = user.correo || '';
    webUserRol.value = user.rol || 'Operador';

    webUserFormTitle.textContent = "Editar Usuario Web";
    btnGuardarWebUsuario.textContent = "Guardar Cambios";
    editingWebUserId = key;

    // Scroll smoothly
    webUserOperatorId.closest('.form-container').scrollIntoView({ behavior: 'smooth' });
}

if (btnGuardarWebUsuario) {
    btnGuardarWebUsuario.addEventListener('click', async () => {
        const opId = webUserOperatorId.value.trim();
        const username = webUserUsername.value.trim();
        const password = webUserPassword.value.trim();
        const correo = webUserCorreo.value.trim();
        const rol = webUserRol.value;

        if (!opId || !username || !password || !correo) {
            alert('Por favor, completa todos los campos del formulario.');
            return;
        }
        if (!validarEmail(correo)) {
            alert('El correo electrónico no tiene un formato válido.');
            return;
        }

        try {
            if (editingWebUserId) {
                // Modo Edición
                await update(ref(db, `usuarios_sistema/${editingWebUserId}`), {
                    usuario: username,
                    passwordWeb: password,
                    correo: correo,
                    rol: rol
                });

                await registrarAuditoria('Edición Usuario Plataforma', `Usuario editado: ${username} (ID: ${opId})`);
                crearToast(`[Edit] Usuario ${username} actualizado con éxito`, "success");

                // Reset state
                editingWebUserId = null;
                webUserOperatorId.readOnly = false;
                webUserOperatorId.style.background = "";
                webUserOperatorId.style.cursor = "";
                webUserFormTitle.textContent = "Registrar Nuevo Usuario Web";
                btnGuardarWebUsuario.textContent = "Registrar Usuario Web";
            } else {
                // Modo Agregar
                // Check duplicate operator ID or username first
                const snapshot = await get(ref(db, 'usuarios_sistema'));
                let exists = false;
                if (snapshot.exists()) {
                    const users = snapshot.val();
                    Object.keys(users).forEach(k => {
                        if (users[k].id_operador === opId || users[k].usuario === username) {
                            exists = true;
                        }
                    });
                }
                if (exists) {
                    alert("Error: El ID de Operador o Nombre de Usuario ya existe.");
                    return;
                }

                // Generar un ID del nodo basado en username o push
                const finalKey = username.toLowerCase();
                await set(ref(db, `usuarios_sistema/${finalKey}`), {
                    id_operador: opId,
                    usuario: username,
                    passwordWeb: password,
                    correo: correo,
                    rol: rol
                });

                await registrarAuditoria('Registro Usuario Plataforma', `Usuario registrado: ${username} (ID: ${opId})`);
                crearToast(`[OK] Usuario ${username} registrado con éxito`, "success");
            }

            // Limpiar formulario
            webUserOperatorId.value = '';
            webUserUsername.value = '';
            webUserPassword.value = '';
            webUserCorreo.value = '';
            webUserRol.value = 'Operador';

        } catch (e) {
            console.error(e);
            alert("Error al guardar usuario web.");
        }
    });
}

// --- FUNCIÓN: EDITAR USUARIO (UID BLOQUEADO) ---
let editingDocenteUid = null;

function validarEmail(email) {
    const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return re.test(email);
}

function generarUsuarioWeb(nombre) {
    if (!nombre) return "docente_" + Math.floor(1000 + Math.random() * 9000);
    const clean = nombre.trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9 ]/g, "");
    const parts = clean.split(" ");
    if (parts.length >= 2) {
        return parts[0] + parts[1].substring(0, 3) + Math.floor(10 + Math.random() * 90);
    }
    return parts[0] + Math.floor(10 + Math.random() * 90);
}

function generarPasswordTemporal() {
    return Math.floor(100000 + Math.random() * 900000).toString();
}

function cargarFormularioDocente(uid, user) {
    userUid.value = uid;
    userUid.readOnly = true;
    userUid.style.background = "rgba(0,0,0,0.2)";
    userUid.style.cursor = "not-allowed";
    userNombre.value = user.nombre;
    userRol.value = user.rol;
    document.getElementById('userCorreo').value = user.correo || '';
    btnGuardarUsuario.textContent = "Guardar Cambios";
    editingDocenteUid = uid;

    // Scroll smoothly to form
    userUid.closest('.form-container').scrollIntoView({ behavior: 'smooth' });
}

// --- ACCIÓN: REGISTRAR/EDITAR USUARIO RFID ---
btnGuardarUsuario.addEventListener('click', async () => {
    const uid = userUid.value.trim();
    const nombre = userNombre.value.trim();
    const rol = userRol.value.trim();
    const correoInput = document.getElementById('userCorreo');
    const correo = correoInput ? correoInput.value.trim() : '';

    if (!uid || !nombre || !rol || !correo) {
        alert('Por favor, completa todos los campos del docente incluyendo el Correo.');
        return;
    }
    if (!validarEmail(correo)) {
        alert('El correo electrónico no tiene un formato válido.');
        return;
    }

    btnGuardarUsuario.disabled = true;
    const originalText = btnGuardarUsuario.textContent;
    btnGuardarUsuario.textContent = "Procesando...";

    try {
        if (editingDocenteUid) {
            // Edit Mode
            await update(ref(db, 'usuarios/' + editingDocenteUid), {
                nombre: nombre,
                rol: rol,
                correo: correo
            });

            await registrarAuditoria('Edición Docente', `Docente editado: ${nombre} (UID: ${editingDocenteUid})`);
            crearToast(`[Edit] Docente ${editingDocenteUid} actualizado correctamente.`, 'success');

            // Reset Edit state
            editingDocenteUid = null;
            userUid.readOnly = false;
            userUid.style.background = "";
            userUid.style.cursor = "";
            btnGuardarUsuario.textContent = "Autorizar Tarjeta RFID";
        } else {
            // Add Mode
            const userWeb = generarUsuarioWeb(nombre);
            const passWeb = generarPasswordTemporal();

            await set(ref(db, 'usuarios/' + uid), {
                nombre: nombre,
                rol: rol,
                uid: uid,
                correo: correo,
                usuarioWeb: userWeb,
                passwordWeb: passWeb
            });

            // Clean unregistered UID in Firebase
            await set(ref(db, 'ultimo_uid_no_registrado'), null);

            // Send welcome email with credentials using SMTPJS (resilient)
            await enviarCorreoConFallback({
                Host: "smtp.gmail.com",
                Username: "smartstock97@gmail.com",
                Password: "F@jardo123",
                To: correo,
                From: "smartstock97@gmail.com",
                Subject: "Bienvenido a Smart Stock - Credenciales de Acceso",
                Body: `Estimado/a ${nombre},\n\nLe damos la bienvenida al sistema Smart Stock. Se ha registrado su tarjeta RFID con éxito.\n\nSus credenciales de acceso para el dashboard web son:\n- Usuario: ${userWeb}\n- Contraseña Temporal: ${passWeb}\n\nPor favor, conserve estas credenciales de forma segura.\n\nAtentamente,\nSmart Stock System`
            });

            await registrarAuditoria('Registro Docente', `Docente registrado: ${nombre} (UID: ${uid})`);
            crearToast('[OK] Docente autorizado y credenciales enviadas por correo.', 'success');
        }

        // Clear fields
        userUid.value = '';
        userNombre.value = '';
        userRol.value = '';
        if (correoInput) correoInput.value = '';
    } catch (e) {
        console.error(e);
        alert('Error al guardar datos o enviar correo.');
    } finally {
        btnGuardarUsuario.disabled = false;
        if (!editingDocenteUid) btnGuardarUsuario.textContent = "Autorizar Tarjeta RFID";
    }
});

// --- LÓGICA: GENERAR QR E INVENTARIO ---
// [QR legacy form removed — now handled by btnAgregarInventario in the inventory panel]


// --- ACCIÓN: SEED DATA (INYECTAR DATOS SEMILLA) ---
if (btnSeedData) btnSeedData.addEventListener('click', async () => {
    if (!confirm('¿Deseas inyectar datos de prueba en tu base de datos Firebase? Esto llenará los sensores, inventarios y docentes modelo para demostración.')) {
        return;
    }

    try {
        const seedData = {
            // Sincronizar estado monitoreo
            'monitoreo': {
                personas_dentro_actualmente: 2,
                estado_chapa: "CERRADA",
                alerta_pir: false,
                estado_foco: "ENCENDIDO"
            },
            // Semilla de Usuarios RFID autorizados
            'usuarios': {
                '12345678': {
                    nombre: 'Ing. Esteban Bravo',
                    rol: 'Técnico de Laboratorio'
                },
                '238472910': {
                    nombre: 'Dr. Marcelo Vásquez',
                    rol: 'Docente de Electrónica'
                },
                '928374829': {
                    nombre: 'Dra. Jomayra Valdez',
                    rol: 'Docente Investigadora'
                }
            },
            // Semilla de Inventario
            'inventario': {
                'QR_OSCILOSCOPIO_1': {
                    nombre_producto: 'Osciloscopio Digital Rigol DS1054Z 50MHz',
                    stock: 4
                },
                'QR_MULTIMETRO_2': {
                    nombre_producto: 'Multímetro Digital Fluke 115 True-RMS',
                    stock: 12
                },
                'QR_GENERADOR_3': {
                    nombre_producto: 'Generador de Funciones Arbitrarias GW Instek',
                    stock: 3
                }
            },
            // Semilla de Accesos
            'accesos': {
                '-Kaccess_01': {
                    docente: 'Dr. Marcelo Vásquez',
                    rol: 'Docente de Electrónica',
                    hora_ingreso: '2026-05-31 16:30:00',
                    hora_salida: '2026-05-31 18:00:00',
                    tiempo_permanencia_min: 90,
                    acompanantes_al_ingresar: 5,
                    saca_producto: true,
                    producto_extraido_id: 'QR_OSCILOSCOPIO_1'
                },
                '-Kaccess_02': {
                    docente: 'Dra. Jomayra Valdez',
                    rol: 'Docente Investigadora',
                    hora_ingreso: '2026-05-31 14:15:00',
                    hora_salida: '2026-05-31 15:45:00',
                    tiempo_permanencia_min: 90,
                    acompanantes_al_ingresar: 0,
                    saca_producto: false,
                    producto_extraido_id: ''
                }
            }
        };

        await update(ref(db), seedData);
        alert('[!] Base de datos inicializada con éxito. ¡Ya puedes navegar por el dashboard para ver el sistema en acción!');
    } catch (e) {
        console.error(e);
        alert('Error al inyectar datos semilla: ' + e.message);
    }
});

// --- FUNCIÓN: MOSTRAR ACTIVIDAD DE UN DOCENTE ---
function mostrarActividadDocente(nombreDocente) {
    let modal = document.getElementById('actividad-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'actividad-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(7,10,19,0.85);backdrop-filter:blur(15px);z-index:12000;display:flex;align-items:center;justify-content:center;';
        document.body.appendChild(modal);
    }
    modal.innerHTML = `
        <div class="glass-panel" style="background:var(--glass-bg);padding:30px;border-radius:24px;max-width:500px;width:95%;border:1px solid var(--glass-border);box-shadow:0 20px 50px rgba(0,0,0,0.6);max-height:80vh;overflow-y:auto;">
            <h2 style="font-size:1.2rem;font-weight:700;margin-bottom:5px;">[Lista] Actividad de ${nombreDocente}</h2>
            <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:20px;">Últimas acciones registradas en el sistema</p>
            <div id="actividad-list" style="display:flex;flex-direction:column;gap:10px;">
                <p style="color:var(--text-muted);text-align:center;padding:20px;">Cargando...</p>
            </div>
            <button class="secondary-btn" onclick="document.getElementById('actividad-modal').style.display='none'" style="margin-top:15px;">Cerrar</button>
        </div>
    `;
    modal.style.display = 'flex';

    // Load audit data for this user
    get(ref(db, 'auditoria')).then(snapshot => {
        const list = document.getElementById('actividad-list');
        if (!list) return;
        list.innerHTML = '';
        const data = snapshot.val();
        if (data) {
            const entries = Object.values(data)
                .filter(e => e.usuario === nombreDocente || (e.detalles && e.detalles.includes(nombreDocente)))
                .reverse()
                .slice(0, 20);
            if (entries.length === 0) {
                list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">Sin actividad registrada.</p>';
                return;
            }
            entries.forEach(entry => {
                const div = document.createElement('div');
                div.style.cssText = 'padding:10px 14px;background:rgba(0,0,0,0.2);border-radius:10px;border:1px solid var(--glass-border);';
                div.innerHTML = `
                    <p style="font-size:0.8rem;font-weight:600;color:var(--text-main);">${entry.accion || '—'}</p>
                    <p style="font-size:0.7rem;color:var(--text-muted);margin-top:4px;">${entry.detalles || ''}</p>
                    <p style="font-size:0.65rem;color:var(--text-muted);margin-top:2px;font-family:monospace;">${entry.timestamp || ''}</p>
                `;
                list.appendChild(div);
            });
        } else {
            list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">Sin actividad registrada.</p>';
        }
    });
}

// --- FUNCIÓN: CAMBIAR CONTRASEÑA ---
// (Se invoca desde el panel de perfil)
function agregarBotonCambiarContrasena() {
    const btnCerrar = document.getElementById('btnCerrarSesion');
    if (!btnCerrar) return;

    const btnCambiar = document.createElement('button');
    btnCambiar.className = 'primary-btn';
    btnCambiar.id = 'btnCambiarPass';
    btnCambiar.style.cssText = 'margin-top:10px;background:linear-gradient(135deg,#2980b9,#3498db);box-shadow:0 5px 15px rgba(52,152,219,0.3);';
    btnCambiar.innerHTML = '[Key] Cambiar Contraseña';
    btnCambiar.addEventListener('click', () => {
        let modal = document.getElementById('change-pass-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'change-pass-modal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(7,10,19,0.85);backdrop-filter:blur(15px);z-index:12000;display:flex;align-items:center;justify-content:center;';
            document.body.appendChild(modal);
        }
        modal.innerHTML = `
            <div class="glass-panel" style="background:var(--glass-bg);padding:30px;border-radius:24px;max-width:380px;width:95%;border:1px solid var(--glass-border);box-shadow:0 20px 50px rgba(0,0,0,0.6);">
                <h2 style="font-size:1.2rem;font-weight:700;margin-bottom:20px;">[Key] Cambiar Contraseña</h2>
                <div class="input-group"><label>Contraseña Actual</label><input type="password" id="oldPass" placeholder="••••••••"></div>
                <div class="input-group"><label>Nueva Contraseña</label><input type="password" id="newPass" placeholder="••••••••"></div>
                <div class="input-group"><label>Confirmar Nueva Contraseña</label><input type="password" id="confirmPass" placeholder="••••••••"></div>
                <button class="primary-btn" id="btnConfirmarPass">Actualizar Contraseña</button>
                <button class="secondary-btn" onclick="document.getElementById('change-pass-modal').style.display='none'" style="margin-top:8px;">Cancelar</button>
            </div>
        `;
        modal.style.display = 'flex';

        document.getElementById('btnConfirmarPass').addEventListener('click', async () => {
            const oldP = document.getElementById('oldPass').value.trim();
            const newP = document.getElementById('newPass').value.trim();
            const confP = document.getElementById('confirmPass').value.trim();

            if (!oldP || !newP || !confP) { alert('Completa todos los campos.'); return; }
            if (oldP !== usuarioActivo.passwordWeb) { alert('La contraseña actual es incorrecta.'); return; }
            if (newP !== confP) { alert('Las nuevas contraseñas no coinciden.'); return; }
            if (newP.length < 4) { alert('La nueva contraseña debe tener al menos 4 caracteres.'); return; }

            try {
                await update(ref(db, `usuarios_sistema/${usuarioActivo.usuario}`), { passwordWeb: newP });
                usuarioActivo.passwordWeb = newP;
                modal.style.display = 'none';
                crearToast('[OK] Contraseña actualizada correctamente.', 'success');
                await registrarAuditoria('Cambio de Contraseña', 'El usuario cambió su contraseña.');
            } catch (e) {
                console.error(e);
                alert('Error al actualizar la contraseña.');
            }
        });
    });
    btnCerrar.parentNode.insertBefore(btnCambiar, btnCerrar);
}

// Inicializar botón de cambiar contraseña al cargar
agregarBotonCambiarContrasena();

// --- SISTEMA DE ALERTA DE SEGURIDAD CRÍTICA Y AUDIO ---


function playAlarmSound() {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        osc.type = 'sawtooth';
        // Frecuencia alternante para efecto sirena
        const freq = (new Date().getSeconds() % 2 === 0) ? 988 : 659; // B5 o E5
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);

        gain.gain.setValueAtTime(0.06, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);

        osc.start();
        osc.stop(audioCtx.currentTime + 0.4);
    } catch (e) {
        console.warn("No se pudo reproducir el sonido de la alarma: ", e);
    }
}

function iniciarAlarmaSonora() {
    if (!beepInterval) {
        playAlarmSound();
        beepInterval = setInterval(playAlarmSound, 600);
    }
}

function detenerAlarmaSonora() {
    if (beepInterval) {
        clearInterval(beepInterval);
        beepInterval = null;
    }
}

function mostrarAlertaCritica(mensaje) {
    let alertBanner = document.getElementById('critical-alert-banner');
    if (!alertBanner) {
        alertBanner = document.createElement('div');
        alertBanner.id = 'critical-alert-banner';
        alertBanner.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(15, 7, 23, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 2px solid var(--danger);
            color: var(--text-main);
            padding: 18px 32px;
            border-radius: 16px;
            box-shadow: 0 20px 50px rgba(239, 68, 68, 0.4), inset 0 0 15px rgba(239, 68, 68, 0.2);
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 16px;
            font-weight: 700;
            font-size: 1.05rem;
            animation: alertBounce 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards, alertFlash 1s infinite alternate;
        `;

        if (!document.getElementById('critical-alert-styles')) {
            const styles = document.createElement('style');
            styles.id = 'critical-alert-styles';
            styles.innerHTML = `
                @keyframes alertBounce {
                    from { transform: translate(-50%, -100px); opacity: 0; }
                    to { transform: translate(-50%, 0); opacity: 1; }
                }
                @keyframes alertFlash {
                    0% { border-color: rgba(239, 68, 68, 0.5); box-shadow: 0 10px 30px rgba(239, 68, 68, 0.3); }
                    100% { border-color: rgba(239, 68, 68, 1); box-shadow: 0 10px 50px rgba(239, 68, 68, 0.6), 0 0 20px rgba(239, 68, 68, 0.4); }
                }
            `;
            document.head.appendChild(styles);
        }

        alertBanner.innerHTML = `
            <span style="font-size: 1.6rem; animation: iconShake 0.5s infinite;">[!]</span>
            <div style="display: flex; flex-direction: column;">
                <span style="letter-spacing: 1px; text-transform: uppercase; font-size: 0.75rem; color: var(--danger); font-weight: 800;">ALERTA DE SEGURIDAD CRÍTICA</span>
                <span id="critical-alert-text">${mensaje}</span>
            </div>
        `;
        document.body.appendChild(alertBanner);
    } else {
        document.getElementById('critical-alert-text').innerText = mensaje;
    }

    iniciarAlarmaSonora();
}

function detenerAlertaCritica() {
    const alertBanner = document.getElementById('critical-alert-banner');
    if (alertBanner) {
        alertBanner.remove();
    }
    detenerAlarmaSonora();
}

// --- ESCUCHAR ULTIMO UID NO REGISTRADO (REGISTRO RÁPIDO RFID) ---
onValue(ref(db, 'ultimo_uid_no_registrado'), (snapshot) => {
    const uidNoReg = snapshot.val();
    const userUidInput = document.getElementById('userUid');
    if (!userUidInput) return;

    const formContainer = userUidInput.closest('.form-container');
    if (!formContainer) return;

    if (uidNoReg) {
        // Pre-rellenar UID no registrado y bloquear campo
        userUidInput.value = uidNoReg;
        userUidInput.disabled = true;

        // Destacar visualmente el formulario en el panel de Gestión de Docentes
        formContainer.style.border = '2px solid var(--accent)';
        formContainer.style.boxShadow = '0 0 35px var(--accent-glow)';

        // Mostrar alerta/indicador superior
        mostrarAlertaCritica(`Tarjeta RFID no registrada detectada: ${uidNoReg}. Proceda a registrar el docente.`);
    } else {
        // Desbloquear y restaurar
        userUidInput.value = '';
        userUidInput.disabled = false;
        formContainer.style.border = '';
        formContainer.style.boxShadow = '';
    }
});

// --- FUNCIÓN: GENERAR Y MOSTRAR MODAL QR ---
function mostrarModalQR(idProd, nombreProd) {
    let modal = document.getElementById('qr-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'qr-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(7, 10, 19, 0.85);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            z-index: 11000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        modal.innerHTML = `
            <div class="glass-panel" style="background:var(--glass-bg); padding:30px; border-radius:24px; text-align:center; max-width:320px; border:1px solid var(--glass-border); box-shadow: 0 20px 50px rgba(0,0,0,0.6);">
                <h3 style="margin-bottom:10px; font-size:1.2rem; color:var(--text-main); font-weight:700;">Etiqueta QR</h3>
                <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:20px;" id="modal-product-name"></p>
                <div class="printable-badge" style="background:white; color:#0f172a; padding:20px; border-radius:12px; border:3px solid #0f172a; display:inline-block; margin-bottom:20px;">
                    <div class="badge-header" style="font-size:0.65rem; font-weight:900; letter-spacing:0.5px; margin-bottom:12px; text-transform:uppercase; border-bottom:1.5px solid #0f172a; padding-bottom:4px; width:100%; color:#0f172a;">UCUENCA - INVENTARIO IOT</div>
                    <div id="modal-qr-preview" style="background:white; padding:5px; display:flex; align-items:center; justify-content:center;"></div>
                    <div class="badge-footer" style="margin-top:10px; width:100%;">
                        <span id="modal-qr-label" style="font-family:monospace; font-size:0.85rem; font-weight:800; background:#f1f5f9; padding:4px 8px; border-radius:4px; display:block; word-break:break-all; border:1px dashed #64748b; color:#0f172a;"></span>
                    </div>
                </div>
                <div style="display:flex; gap:10px;">
                    <button class="primary-btn" id="modal-btn-print" style="padding:10px 20px; flex:1;">[Print] Imprimir</button>
                    <button class="secondary-btn" id="modal-btn-close" style="margin-top:0; padding:10px 20px; flex:1;">Cerrar</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    document.getElementById('modal-product-name').innerText = nombreProd;
    document.getElementById('modal-qr-label').innerText = idProd;

    // Generar URL del servidor dinámica apuntando al backend en el puerto 5000
    const qrUrl = `${window.location.origin}/retiro.html?id=${idProd}`;

    const qrContainer = document.getElementById('modal-qr-preview');
    qrContainer.innerHTML = '';

    if (typeof QRCode !== 'undefined') {
        new QRCode(qrContainer, {
            text: qrUrl,
            width: 140,
            height: 140,
            colorDark: "#0f172a",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H
        });
    } else {
        qrContainer.innerHTML = `<p style="color:#0f172a;font-size:0.75rem;padding:10px;font-weight:600;">Librería QR no cargada.<br><a href="${qrUrl}" target="_blank" style="color:var(--primary);">${qrUrl}</a></p>`;
    }

    modal.style.display = 'flex';

    document.getElementById('modal-btn-close').onclick = () => {
        modal.style.display = 'none';
    };

    document.getElementById('modal-btn-print').onclick = () => {
        const printContent = modal.querySelector('.printable-badge').outerHTML;
        const printWindow = window.open('', '', 'height=500,width=500');
        printWindow.document.write('<html><head><title>Imprimir QR</title>');
        printWindow.document.write('<style>');
        printWindow.document.write('body { display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: monospace; }');
        printWindow.document.write('.printable-badge { background: white; color: #000; padding: 20px; border: 3px solid #000; border-radius: 12px; width: 220px; text-align: center; }');
        printWindow.document.write('.badge-header { font-size: 10px; font-weight: bold; margin-bottom: 12px; text-transform: uppercase; border-bottom: 2px solid #000; padding-bottom: 4px; }');
        printWindow.document.write('#modal-qr-preview { padding: 5px; background: white; display: inline-block; margin-bottom: 10px; }');
        printWindow.document.write('#modal-qr-label { font-family: monospace; font-size: 12px; font-weight: bold; background: #eee; padding: 4px; border: 1px dashed #000; display: block; word-break: break-all; }');
        printWindow.document.write('</style></head><body>');
        printWindow.document.write(printContent);
        printWindow.document.write('</body></html>');
        printWindow.document.close();
        printWindow.focus();
        setTimeout(() => {
            printWindow.print();
            printWindow.close();
        }, 500);
    };
}

// --- FUNCIONES CRUD DE INVENTARIO ---
let editingProductId = null;

async function autogenerarProductId(nombre) {
    if (!nombre || nombre.length < 1) return "";
    const cleanName = nombre.trim().replace(/[^a-zA-Z]/g, "").toUpperCase();
    let code = cleanName.substring(0, 3);
    while (code.length < 3) code += "X";

    try {
        const snapshot = await get(ref(db, 'inventario'));
        let maxCounter = 0;
        if (snapshot.exists()) {
            const data = snapshot.val();
            Object.keys(data).forEach(key => {
                const parts = key.split('_');
                const num = parseInt(parts[0]);
                if (!isNaN(num) && num > maxCounter) {
                    maxCounter = num;
                }
            });
        }
        const nextNum = maxCounter + 1;
        const nextNumStr = String(nextNum).padStart(3, '0');
        return `${nextNumStr}_${code}`;
    } catch (e) {
        console.error("Error generating product ID:", e);
        return "001_" + code;
    }
}

// Escuchar cambios en nombre de producto para autogenerar el ID
const invNombreInput = document.getElementById('invNombre');
const invIdInput = document.getElementById('invId');
if (invNombreInput && invIdInput) {
    invNombreInput.addEventListener('input', async () => {
        if (editingProductId) return; // No autogenerar en edición
        const nameVal = invNombreInput.value.trim();
        if (nameVal.length >= 1) {
            const generatedId = await autogenerarProductId(nameVal);
            invIdInput.value = generatedId;
        } else {
            invIdInput.value = '';
        }
    });
}

async function eliminarProducto(id) {
    if (confirm(`¿Estás seguro de eliminar el producto ${id}?`)) {
        try {
            await remove(ref(db, `inventario/${id}`));
            await registrarAuditoria('Eliminación Producto', `Producto eliminado: ID ${id}`);
            crearToast(`[Delete] Producto ${id} eliminado con éxito`, "success");
        } catch (e) {
            console.error(e);
            alert("Error al eliminar producto.");
        }
    }
}

function cargarFormularioProducto(id, prod) {
    invIdInput.value = id;
    invNombreInput.value = prod.nombre_producto || '';
    document.getElementById('invStock').value = prod.stock || 0;
    document.getElementById('invUbicacion').value = prod.ubicacion || '';
    document.getElementById('invCategoria').value = prod.categoria || 'Hardware';
    document.getElementById('invEstado').value = prod.estado || 'Funcional';

    btnAgregarInventario.textContent = "Guardar Cambios";
    editingProductId = id;

    // Scroll smoothly to form
    invIdInput.closest('.form-container').scrollIntoView({ behavior: 'smooth' });
}

const btnAgregarInventario = document.getElementById('btnAgregarInventario');
if (btnAgregarInventario) {
    btnAgregarInventario.addEventListener('click', async () => {
        const id = invIdInput.value.trim();
        const nombre = invNombreInput.value.trim();
        const stock = parseInt(document.getElementById('invStock').value);
        const ubicacion = document.getElementById('invUbicacion').value.trim();
        const categoria = document.getElementById('invCategoria').value.trim();
        const estado = document.getElementById('invEstado').value.trim();

        if (!nombre || isNaN(stock)) {
            alert('Por favor, completa los campos Nombre y Stock.');
            return;
        }

        try {
            if (editingProductId) {
                // Modo Edición
                await update(ref(db, `inventario/${editingProductId}`), {
                    nombre_producto: nombre,
                    stock: stock,
                    ubicacion: ubicacion,
                    categoria: categoria,
                    estado: estado
                });

                await registrarAuditoria('Edición Producto', `Producto editado: ${nombre} (ID: ${editingProductId})`);
                crearToast(`[Edit] Producto ${editingProductId} actualizado con éxito`, "success");

                // Reset state
                editingProductId = null;
                btnAgregarInventario.textContent = "Agregar";
            } else {
                // Modo Agregar
                const finalId = id || (await autogenerarProductId(nombre));

                const snapshot = await get(ref(db, `inventario/${finalId}`));
                if (snapshot.exists()) {
                    alert("Error: El ID del producto autogenerado ya existe.");
                    return;
                }

                await set(ref(db, `inventario/${finalId}`), {
                    nombre_producto: nombre,
                    stock: stock,
                    ubicacion: ubicacion,
                    categoria: categoria,
                    estado: estado
                });

                await registrarAuditoria('Registro Producto', `Producto agregado: ${nombre} (ID: ${finalId})`);
                crearToast(`[OK] Producto ${nombre} agregado con éxito`, "success");
            }

            // Limpiar formulario
            invIdInput.value = '';
            invNombreInput.value = '';
            document.getElementById('invStock').value = '';
            document.getElementById('invUbicacion').value = '';
            document.getElementById('invCategoria').value = 'Hardware';
            document.getElementById('invEstado').value = 'Funcional';

        } catch (e) {
            console.error(e);
            alert("Error al procesar producto.");
        }
    });
}

// --- HELPER: ENVÍO DE CORREO VÍA BACKEND PYTHON ---
/**
 * Envía un correo usando el endpoint /api/send-email del backend Python.
 * El backend usa smtplib directamente — sin dependencias externas en el frontend.
 */
async function enviarCorreoConFallback(payload) {
    try {
        const response = await fetch('/api/send-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                to: payload.To,
                subject: payload.Subject,
                body: payload.Body
            })
        });

        const result = await response.json();

        if (response.ok && result.ok) {
            console.log('[Email] Correo enviado exitosamente a:', payload.To);
        } else {
            console.warn('[Email] El servidor respondió con error:', result.error);
            crearToast('[!] No se pudo enviar el correo. Usa el código de la consola (F12).', 'danger');
        }
    } catch (err) {
        console.error('[Email] Error al contactar el backend de correo:', err);
        crearToast('[!] Servicio de correo no disponible. Usa el código de la consola (F12).', 'danger');
    }
}

// --- SISTEMA DE LOGIN ---
const loginOverlay = document.getElementById('loginOverlay');
const formLogin = document.getElementById('formLogin');

const loginUser = document.getElementById('loginUser');
const loginPass = document.getElementById('loginPass');
const btnIngresar = document.getElementById('btnIngresar');

const dashboardContainer = document.querySelector('.dashboard-container');

btnIngresar.addEventListener('click', async () => {
    const user = loginUser ? loginUser.value.trim() : '';
    const pass = loginPass ? loginPass.value.trim() : '';

    if (!user || !pass) {
        alert("Por favor ingrese usuario y contraseña.");
        return;
    }

    btnIngresar.disabled = true;
    btnIngresar.textContent = "Verificando...";

    // --- Validar credenciales en Firebase ---
    let authenticatedUser = null;
    try {
        console.log('[Login] Consultando Firebase para usuario:', user);
        const snapshot = await get(ref(db, 'usuarios_sistema'));

        if (snapshot.exists()) {
            const users = snapshot.val();
            Object.keys(users).forEach(key => {
                const u = users[key];
                if (u.usuario === user && u.passwordWeb === pass) {
                    authenticatedUser = u;
                    console.log('[Login] [OK] Credenciales válidas para nodo:', key);
                }
            });
        }
    } catch (dbError) {
        console.error('[Login] ERROR al consultar Firebase:', dbError);
        alert('Error interno en Login: ' + dbError.message);
        btnIngresar.disabled = false;
        btnIngresar.textContent = "Ingresar";
        return;
    }

    if (!authenticatedUser) {
        alert("Credenciales incorrectas. Verifica tu usuario y contraseña.");
        btnIngresar.disabled = false;
        btnIngresar.textContent = "Ingresar";
        return;
    }

    // --- Acceso directo al Dashboard ---
    usuarioActivo = authenticatedUser;
    loginOverlay.style.display = "none";
    dashboardContainer.style.display = "flex";
    btnIngresar.disabled = false;
    btnIngresar.textContent = "Ingresar";
    crearToast("[Unlock] Acceso concedido. ¡Bienvenido, " + authenticatedUser.usuario + "!", "success");
    actualizarPerfil();
    aplicarVisibilidadAdmin();
    await registrarAuditoria('Inicio Sesión', `Usuario ${authenticatedUser.usuario} inició sesión.`);
});

// --- LÓGICA: PANEL DE PERFIL Y CERRAR SESIÓN ---
const profileNombre = document.getElementById('profileNombre');
const profileRol = document.getElementById('profileRol');
const profileUsuario = document.getElementById('profileUsuario');
const profileCorreo = document.getElementById('profileCorreo');
const profileIdOperador = document.getElementById('profileIdOperador');
const profileAuditoria = document.getElementById('profileAuditoria');
const btnCerrarSesion = document.getElementById('btnCerrarSesion');

function actualizarPerfil() {
    if (!usuarioActivo) return;
    profileNombre.textContent = usuarioActivo.usuario || '—';
    profileRol.textContent = usuarioActivo.rol || '—';
    profileUsuario.textContent = usuarioActivo.usuario || '—';
    profileCorreo.textContent = usuarioActivo.correo || '—';
    profileIdOperador.textContent = usuarioActivo.id_operador || '—';

    // Cargar actividad reciente del usuario
    const auditRef = ref(db, 'auditoria');
    onValue(auditRef, (snapshot) => {
        profileAuditoria.innerHTML = '';
        const data = snapshot.val();
        if (data) {
            const entries = Object.values(data)
                .filter(e => e.usuario === usuarioActivo.usuario)
                .reverse()
                .slice(0, 15);
            if (entries.length === 0) {
                profileAuditoria.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No hay registros de actividad.</p>';
                return;
            }
            entries.forEach(entry => {
                const div = document.createElement('div');
                div.style.cssText = 'padding: 10px 14px; background: rgba(0,0,0,0.2); border-radius: 10px; border: 1px solid var(--glass-border);';
                div.innerHTML = `
                    <p style="font-size: 0.8rem; font-weight: 600; color: var(--text-main);">${entry.accion || '—'}</p>
                    <p style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">${entry.detalles || ''}</p>
                    <p style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px; font-family: monospace;">${entry.timestamp || ''}</p>
                `;
                profileAuditoria.appendChild(div);
            });
        } else {
            profileAuditoria.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No hay registros de actividad.</p>';
        }
    });
}

if (btnCerrarSesion) {
    btnCerrarSesion.addEventListener('click', () => {
        if (confirm('¿Estás seguro de cerrar sesión?')) {
            usuarioActivo = null;
            dashboardContainer.style.display = "none";
            loginOverlay.style.display = "flex";
            loginUser.value = '';
            loginPass.value = '';
            // Ocultar panel de servidor al cerrar sesion
            const navServidor = document.querySelector('.nav-btn[data-target="panel-servidor"]');
            if (navServidor) navServidor.style.display = 'none';
            crearToast('[Bye] Sesion cerrada correctamente.', 'success');
        }
    });
}

// --- COMPONENTES DEL MODAL INTERACTIVO DE TARJETAS ---
const modalTarjeta = document.getElementById('modalTarjetaDesconocida');
const modalUidText = document.getElementById('modalUidText');
const modalUserNombre = document.getElementById('modalUserNombre');
const modalUserRol = document.getElementById('modalUserRol');
const btnCancelarModal = document.getElementById('btnCancelarModal');
const btnRegistrarModal = document.getElementById('btnRegistrarModal');
const toastContainer = document.getElementById('toastContainer');

let currentUnregisteredUid = "";

onValue(ref(db, 'ultimo_intento_invalido'), (snapshot) => {
    const data = snapshot.val();
    if (data && data.uid && data.procesado === false) {
        currentUnregisteredUid = data.uid;
        modalUidText.textContent = data.uid;
        modalUserNombre.value = "";
        modalUserRol.value = "";
        modalTarjeta.style.display = 'flex';
        crearToast(`[!] Intento de acceso denegado. UID: ${data.uid}`, "danger");
    }
});

btnRegistrarModal.addEventListener('click', async () => {
    const nombre = modalUserNombre.value.trim();
    const rol = modalUserRol.value.trim();
    const modalCorreoInput = document.getElementById('modalUserCorreo');
    const correo = modalCorreoInput ? modalCorreoInput.value.trim() : '';

    if (!nombre || !rol || !correo) {
        alert("Por favor ingrese el Nombre, Rol y Correo Electrónico para autorizar el acceso.");
        return;
    }
    if (!validarEmail(correo)) {
        alert('El correo electrónico no tiene un formato válido.');
        return;
    }

    btnRegistrarModal.disabled = true;
    btnRegistrarModal.textContent = "Registrando...";

    try {
        const userWeb = generarUsuarioWeb(nombre);
        const passWeb = generarPasswordTemporal();

        await set(ref(db, `usuarios/${currentUnregisteredUid}`), {
            nombre: nombre,
            rol: rol,
            uid: currentUnregisteredUid,
            correo: correo,
            usuarioWeb: userWeb,
            passwordWeb: passWeb
        });

        // Send welcome email with credentials using SMTPJS (resilient)
        await enviarCorreoConFallback({
            Host: "smtp.gmail.com",
            Username: "smartstock97@gmail.com",
            Password: "F@jardo123",
            To: correo,
            From: "smartstock97@gmail.com",
            Subject: "Bienvenido a Smart Stock - Credenciales de Acceso",
            Body: `Estimado/a ${nombre},\n\nLe damos la bienvenida al sistema Smart Stock. Se ha registrado su tarjeta RFID con éxito.\n\nSus credenciales de acceso para el dashboard web son:\n- Usuario: ${userWeb}\n- Contraseña Temporal: ${passWeb}\n\nPor favor, conserve estas credenciales de forma segura.\n\nAtentamente,\nSmart Stock System`
        });

        await update(ref(db, 'ultimo_intento_invalido'), {
            procesado: true
        });

        await registrarAuditoria('Registro Docente (Modal)', `Docente registrado vía modal: ${nombre} (UID: ${currentUnregisteredUid})`);

        if (modalCorreoInput) modalCorreoInput.value = '';
        modalTarjeta.style.display = 'none';
        crearToast(`[OK] ¡Tarjeta autorizada con éxito para ${nombre}!`, "success");
    } catch (e) {
        console.error(e);
        alert('Error al registrar o enviar correo de bienvenida.');
    } finally {
        btnRegistrarModal.disabled = false;
        btnRegistrarModal.textContent = "Registrar";
    }
});

btnCancelarModal.addEventListener('click', async () => {
    await update(ref(db, 'ultimo_intento_invalido'), {
        procesado: true
    });
    modalTarjeta.style.display = 'none';
});

// --- LÓGICA DE BÚSQUEDA AVANZADA Y EXPORTACIÓN DE ETIQUETAS QR ---


function actualizarEtiquetasQR() {
    if (!labelsPrintGrid) return;
    labelsPrintGrid.innerHTML = '';

    const query = qrSearchInput ? qrSearchInput.value.toLowerCase().trim() : '';

    let count = 0;
    Object.keys(todosLosProductos).forEach(key => {
        const prod = todosLosProductos[key];
        const nombre = (prod.nombre_producto || '').toLowerCase();
        const id = key.toLowerCase();
        const ubicacion = (prod.ubicacion || '').toLowerCase();
        const categoria = (prod.categoria || '').toLowerCase();

        if (query === '' || nombre.includes(query) || id.includes(query) || ubicacion.includes(query) || categoria.includes(query)) {
            count++;
            const div = document.createElement('div');
            div.className = 'printable-badge';
            div.innerHTML = `
                <div class="badge-header">UCUENCA - INVENTARIO IOT</div>
                <div class="qr-preview-img" id="qr-preview-${key}"></div>
                <div class="badge-footer">
                    <span>${key}</span>
                </div>
            `;
            labelsPrintGrid.appendChild(div);

            const qrUrl = `${window.location.origin}/retiro.html?id=${key}`;
            if (typeof QRCode !== 'undefined') {
                new QRCode(document.getElementById(`qr-preview-${key}`), {
                    text: qrUrl,
                    width: 130,
                    height: 130,
                    colorDark: "#0f172a",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.H
                });
            } else {
                document.getElementById(`qr-preview-${key}`).innerHTML = `<p style="font-size:0.6rem;color:#ef4444;word-break:break-all;">${qrUrl}</p>`;
            }
        }
    });

    if (count === 0) {
        labelsPrintGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px 0;">No se encontraron productos coincidentes.</p>';
    }
}

if (qrSearchInput) {
    qrSearchInput.addEventListener('input', actualizarEtiquetasQR);
}

if (btnExportarPdfLabels) {
    btnExportarPdfLabels.addEventListener('click', () => {
        window.print();
    });
}

// --- FIREBASE: RETIROS DE PRODUCTOS ---
const listaRetiros = document.getElementById('listaRetiros');
if (listaRetiros) {
    onValue(ref(db, 'retiros'), (snapshot) => {
        listaRetiros.innerHTML = '';
        const data = snapshot.val();
        if (data) {
            const keys = Object.keys(data).reverse();
            keys.forEach(key => {
                const r = data[key];
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${r.nombre_producto || '—'}</strong></td>
                    <td><span style="font-family:monospace; color:var(--primary);">${r.producto_id || '—'}</span></td>
                    <td>${r.cantidad_retirada || '—'}</td>
                    <td>${r.stock_anterior !== undefined ? r.stock_anterior : '—'}</td>
                    <td>${r.stock_nuevo !== undefined ? r.stock_nuevo : '—'}</td>
                    <td>${r.usuario || '—'}</td>
                    <td><span style="font-size:0.8rem; color:var(--text-muted);">${r.fecha || '—'}</span></td>
                `;
                listaRetiros.appendChild(tr);
            });
        } else {
            listaRetiros.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No hay retiros registrados.</td></tr>';
        }
    });
}

// --- MODULO: GAUGE DE AFORO EN TIEMPO REAL ---
const aforoArc = document.getElementById('aforoArc');
const aforoValue = document.getElementById('aforoValue');
const aforoLimiteEl = document.getElementById('aforoLimite');
const aforoPorcentaje = document.getElementById('aforoPorcentaje');
const aforoEstado = document.getElementById('aforoEstado');
const ARC_LENGTH = 251.33;
let limiteAforo = 25;

// Read limite_aforo from Firebase
onValue(ref(db, 'configuracion/limite_aforo'), (snapshot) => {
    const val = snapshot.val();
    if (val && val > 0) {
        limiteAforo = val;
        if (aforoLimiteEl) aforoLimiteEl.textContent = val;
        const inputEl = document.getElementById('inputLimiteAforo');
        if (inputEl && !inputEl.value) inputEl.value = val;
    }
});

function actualizarGaugeAforo(personas) {
    if (!aforoArc) return;
    const pct = Math.min(personas / limiteAforo, 1);
    const dashLen = pct * ARC_LENGTH;
    aforoArc.setAttribute('stroke-dasharray', `${dashLen} ${ARC_LENGTH}`);
    let color = '#6db87a', estado = 'NORMAL', pctColor = 'var(--success)';
    let estadoBg = 'rgba(109,184,122,0.15)', estadoBorder = 'rgba(109,184,122,0.3)';
    if (pct > 0.8) {
        color = '#e05252'; estado = 'CRITICO'; pctColor = 'var(--danger)';
        estadoBg = 'rgba(224,82,82,0.15)'; estadoBorder = 'rgba(224,82,82,0.3)';
    } else if (pct > 0.5) {
        color = '#d4a030'; estado = 'ALERTA'; pctColor = 'var(--warning)';
        estadoBg = 'rgba(212,160,48,0.15)'; estadoBorder = 'rgba(212,160,48,0.3)';
    }
    aforoArc.setAttribute('stroke', color);
    aforoValue.textContent = personas;
    aforoPorcentaje.textContent = Math.round(pct * 100) + '%';
    aforoPorcentaje.style.color = pctColor;
    aforoEstado.textContent = estado;
    aforoEstado.style.background = estadoBg;
    aforoEstado.style.color = pctColor;
    aforoEstado.style.borderColor = estadoBorder;
}

// Hook gauge into infrarrojo sensor
onValue(ref(db, 'aforo'), (snapshot) => {
    const val = snapshot.val();
    const personas = (val !== null && val !== undefined) ? parseInt(val) || 0 : 0;
    actualizarGaugeAforo(personas);
});

// --- MODULO: PANEL SERVIDOR (Solo Admin/SuperAdmin) ---
const panelServidor = document.getElementById('panel-servidor');
const inputLimiteAforo = document.getElementById('inputLimiteAforo');
const btnGuardarLimiteAforo = document.getElementById('btnGuardarLimiteAforo');
const aforoConfigStatus = document.getElementById('aforoConfigStatus');
const btnRestartServices = document.getElementById('btnRestartServices');
const btnShutdownPi = document.getElementById('btnShutdownPi');
const serverCmdStatus = document.getElementById('serverCmdStatus');

function esAdmin() {
    if (!usuarioActivo) return false;
    const rol = (usuarioActivo.rol || '').toLowerCase();
    return rol === 'superadmin' || rol === 'admin' || rol === 'super_admin';
}

function aplicarVisibilidadAdmin() {
    // Show/hide "Servidor" button for admin only
    const navBtn = document.querySelector('.nav-btn[data-target="panel-servidor"]');
    if (esAdmin()) {
        if (navBtn) navBtn.style.display = 'flex';
    } else {
        if (navBtn) navBtn.style.display = 'none';
    }

    // Role-based nav visibility using data-roles attribute
    const userRol = (usuarioActivo && usuarioActivo.rol) ? usuarioActivo.rol : '';
    document.querySelectorAll('.nav-btn[data-roles]').forEach(btn => {
        const allowedRoles = btn.dataset.roles.split(',');
        if (allowedRoles.includes(userRol)) {
            btn.style.display = 'flex';
        } else {
            btn.style.display = 'none';
        }
    });

    // Role-based edit restrictions for Docente
    if (userRol === 'Docente') {
        // Docente: can view docentes table but cannot edit/delete RFID users
        document.querySelectorAll('#listaUsuarios .edit-btn, #listaUsuarios .delete-btn').forEach(b => b.style.display = 'none');
        const docenteForm = document.querySelector('#panel-usuarios .form-container');
        if (docenteForm) docenteForm.style.display = 'none';
        // Docente CAN manage inventory and Usuarios de Plataforma (full access)
    }

    if (userRol === 'Estudiante') {
        // Estudiante: read-only inventory, no QR, no forms
        document.querySelectorAll('#listaInventario .edit-btn, #listaInventario .delete-btn').forEach(b => b.style.display = 'none');
        document.querySelectorAll('#listaInventario .qr-btn').forEach(b => b.style.display = 'none');
        const invForm = document.querySelector('#panel-inventario .form-container');
        if (invForm) invForm.style.display = 'none';
        // Hide Usuarios de Plataforma for Estudiante
        const webUsersNav = document.querySelector('.nav-btn[data-target="panel-usuarios-web"]');
        if (webUsersNav) webUsersNav.style.display = 'none';
    }
}

// Create admin nav button dynamically
(function crearBotonServidor() {
    const nav = document.querySelector('.nav-menu');
    if (!nav) return;
    const btn = document.createElement('button');
    btn.className = 'nav-btn';
    btn.dataset.target = 'panel-servidor';
    btn.style.display = 'none';
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" class="nav-icon"><path fill="currentColor" d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.04 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.68 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.04 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z"/></svg><span>Servidor</span>';
    btn.addEventListener('click', () => {
        nav.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('panel-servidor').classList.add('active');
    });
    const perfilBtn = nav.querySelector('.nav-btn[data-target="panel-perfil"]');
    if (perfilBtn) nav.insertBefore(btn, perfilBtn);
    else nav.appendChild(btn);
})();

// Apply admin visibility on login
onValue(ref(db, 'usuarios_sistema'), () => { if (usuarioActivo) aplicarVisibilidadAdmin(); });

// Save aforo limit
if (btnGuardarLimiteAforo) {
    btnGuardarLimiteAforo.addEventListener('click', async () => {
        const val = parseInt(inputLimiteAforo.value);
        if (!val || val < 1) { alert('Ingresa un valor valido mayor a 0.'); return; }
        try {
            await set(ref(db, 'configuracion/limite_aforo'), val);
            aforoConfigStatus.textContent = 'Limite actualizado a ' + val + ' personas.';
            aforoConfigStatus.style.color = 'var(--success)';
            await registrarAuditoria('Cambio Limite Aforo', 'Limite cambiado a ' + val);
            crearToast('[OK] Limite de aforo actualizado a ' + val, 'success');
        } catch (e) { console.error(e); aforoConfigStatus.textContent = 'Error al guardar.'; }
    });
}

// Restart services
if (btnRestartServices) {
    btnRestartServices.addEventListener('click', async () => {
        if (!confirm('Reiniciara Mosquitto y Node-RED en la Raspberry Pi. Continuar?')) return;
        try {
            await set(ref(db, 'sistema/comandos_servidor'), { accion: 'restart_services', timestamp: Date.now(), usuario: usuarioActivo.usuario });
            serverCmdStatus.textContent = 'Comando enviado. Reiniciando servicios...';
            serverCmdStatus.style.color = 'var(--warning)';
            await registrarAuditoria('Reinicio Servicios', 'Comando de reinicio enviado');
            crearToast('[OK] Comando de reinicio enviado.', 'success');
        } catch (e) { console.error(e); }
    });
}

// Shutdown
if (btnShutdownPi) {
    btnShutdownPi.addEventListener('click', async () => {
        if (!confirm('ATENCION: Apagara la Raspberry Pi. Continuar?')) return;
        try {
            await set(ref(db, 'sistema/comandos_servidor'), { accion: 'shutdown', timestamp: Date.now(), usuario: usuarioActivo.usuario });
            serverCmdStatus.textContent = 'Comando de apagado enviado.';
            serverCmdStatus.style.color = 'var(--danger)';
            await registrarAuditoria('Apagar RPi', 'Comando de apagado enviado');
            crearToast('[!] Comando de apagado enviado.', 'danger');
        } catch (e) { console.error(e); }
    });
}

// Funcion dinamica para alertas Toast en pantalla
function crearToast(mensaje, tipo = "danger") {
    const toast = document.createElement('div');
    toast.className = 'toast';
    if (tipo === "success") toast.style.borderLeftColor = "var(--success)";
    toast.textContent = mensaje;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 6000);
}
