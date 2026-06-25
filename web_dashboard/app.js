import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue, update, remove, set, get, push } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

// --- CONFIGURACIÓN FIREBASE ---
const firebaseConfig = {
    databaseURL: "https://complexivo-fv-default-rtdb.firebaseio.com/"
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
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.08)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#8b5cf6',
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
onValue(ref(db, 'monitoreo_tiempo_real'), (snapshot) => {
    const data = snapshot.val();
    if (data) {
        // Personas
        const personas = data.personas_dentro_actualmente !== undefined ? data.personas_dentro_actualmente : 0;
        countPersonas.innerText = personas;

        // Gráfica
        const timeStr = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        updateChart(timeStr, personas);

        // Chapa
        const chapaState = data.estado_chapa || 'CERRADA';
        estadoChapa.innerText = chapaState;
        if (chapaState === 'ABIERTA') {
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

        // Foco (Manejado por listener independiente de monitoreo/estado_foco)

        // PIR y Alerta Combinada
        if (chapaState === "CERRADA" && data.alerta_pir) {
            estadoPir.innerText = "🚨 INTRUSIÓN";
            subAlerta.innerText = "¡Movimiento con puerta cerrada!";
            cardAlerta.classList.add('alert-danger');
            cardAlerta.classList.remove('card-secure');
            iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;

            mostrarAlertaCritica("¡Movimiento detectado con el cerrojo de la puerta CERRADO!");
        } else if (data.alerta_pir) {
            estadoPir.innerText = "🚨 ALERTA";
            subAlerta.innerText = "¡Movimiento detectado!";
            cardAlerta.classList.add('alert-danger');
            cardAlerta.classList.remove('card-secure');
            iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;

            detenerAlertaCritica(); // Limpiar intrusión si no aplica la combinación
        } else {
            estadoPir.innerText = "Seguro";
            subAlerta.innerText = "No se detecta movimiento";
            cardAlerta.classList.remove('alert-danger');
            cardAlerta.classList.add('card-secure');
            iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12,12A5,5 0 1,1 17,7A5,5 0 0,1 12,12M12,14C17.07,14 21,16.24 21,19v2H3V19C3,16.24 6.93,14 12,14Z"/></svg>`;

            detenerAlertaCritica();
        }
    }
});

// --- FIREBASE: CONTROL FOCO INTELIGENTE MERCURY ---
onValue(ref(db, 'monitoreo/estado_foco'), (snapshot) => {
    const isEncendido = snapshot.val();
    if (isEncendido === true || isEncendido === "true") {
        estadoFoco.innerHTML = '<span class="badge badge-green" style="box-shadow: 0 0 10px rgba(16,185,129,0.5);">💡 Encendido</span>';
        cardFoco.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        cardFoco.style.boxShadow = '0 10px 30px rgba(16, 185, 129, 0.15)';
        subFoco.innerText = "Luz artificial activada";
    } else {
        estadoFoco.innerHTML = '<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-muted); border: 1px solid rgba(148, 163, 184, 0.3);">⚫ Apagado</span>';
        cardFoco.style.borderColor = '';
        cardFoco.style.boxShadow = '';
        subFoco.innerText = "Luz artificial desactivada";
    }
});

// --- FIREBASE: CONTROL SENSORES ADICIONALES ---
// Sensor PIR
onValue(ref(db, 'monitoreo/pir'), (snapshot) => {
    const val = snapshot.val();
    const isMovimiento = (val === true || val === "true" || val === "Movimiento Detectado");
    if (isMovimiento) {
        estadoPir.innerText = "🚨 MOVIMIENTO";
        subAlerta.innerText = "¡Movimiento detectado!";
        cardAlerta.classList.add('alert-danger');
        cardAlerta.classList.remove('card-secure');
        iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;
    } else {
        estadoPir.innerText = "Seguro";
        subAlerta.innerText = "No se detecta movimiento";
        cardAlerta.classList.remove('alert-danger');
        cardAlerta.classList.add('card-secure');
        iconAlerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12,12A5,5 0 1,1 17,7A5,5 0 0,1 12,12M12,14C17.07,14 21,16.24 21,19v2H3V19C3,16.24 6.93,14 12,14Z"/></svg>`;
    }
});

// Sensor Puerta
onValue(ref(db, 'monitoreo/puerta'), (snapshot) => {
    const val = snapshot.val();
    const isOpen = (val === true || val === "true" || val === "ABIERTA");
    if (isOpen) {
        if (estadoPuerta) estadoPuerta.innerText = "ABIERTA";
        if (subPuerta) subPuerta.innerText = "Puerta física abierta";
        if (cardPuerta) {
            cardPuerta.style.borderColor = 'rgba(239, 68, 68, 0.4)';
            cardPuerta.style.boxShadow = '0 10px 30px rgba(239, 68, 68, 0.15)';
            cardPuerta.classList.remove('card-secure');
            cardPuerta.classList.add('alert-danger');
        }
        if (iconPuerta) iconPuerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M19,4H5A2,2 0 0,0 3,6V18A2,2 0 0,0 5,20H19A2,2 0 0,0 21,18V6A2,2 0 0,0 19,4M19,18H5V6H19V18Z"/></svg>`;
    } else {
        if (estadoPuerta) estadoPuerta.innerText = "CERRADA";
        if (subPuerta) subPuerta.innerText = "Puerta física cerrada";
        if (cardPuerta) {
            cardPuerta.style.borderColor = '';
            cardPuerta.style.boxShadow = '';
            cardPuerta.classList.add('card-secure');
            cardPuerta.classList.remove('alert-danger');
        }
        if (iconPuerta) iconPuerta.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M19,4H5A2,2 0 0,0 3,6V18A2,2 0 0,0 5,20H19A2,2 0 0,0 21,18V6A2,2 0 0,0 19,4M19,18H5V6H19V18Z"/></svg>`;
    }
});

// Sensor Infrarrojo
onValue(ref(db, 'monitoreo/infrarrojo'), (snapshot) => {
    const val = snapshot.val();
    const isCruce = (val === true || val === "true" || val === "Ingreso" || val === "Salida");
    if (isCruce) {
        if (estadoInfrarrojo) estadoInfrarrojo.innerText = val === true ? "DETECTADO" : val;
        if (subInfrarrojo) subInfrarrojo.innerText = `Cruce activo (${val === true ? 'Cruce' : val})`;
        if (cardInfrarrojo) {
            cardInfrarrojo.style.borderColor = 'rgba(245, 158, 11, 0.4)';
            cardInfrarrojo.style.boxShadow = '0 10px 30px rgba(245, 158, 11, 0.15)';
            cardInfrarrojo.classList.remove('card-secure');
            cardInfrarrojo.classList.add('alert-danger');
        }
    } else {
        if (estadoInfrarrojo) estadoInfrarrojo.innerText = "Normal";
        if (subInfrarrojo) subInfrarrojo.innerText = "Barrera despejada";
        if (cardInfrarrojo) {
            cardInfrarrojo.style.borderColor = '';
            cardInfrarrojo.style.boxShadow = '';
            cardInfrarrojo.classList.add('card-secure');
            cardInfrarrojo.classList.remove('alert-danger');
        }
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
                ? '<span class="badge badge-blue">⌨️ Teclado</span>'
                : '<span class="badge badge-purple">💳 RFID</span>';
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
            const credsWeb = user.usuarioWeb
                ? `<span style="font-size:0.8rem; font-family:monospace; color:var(--primary);">User: ${user.usuarioWeb}<br>Pass: ${user.passwordWeb}</span>`
                : '<span style="color:var(--text-muted);">---</span>';
            tr.innerHTML = `
                <td><span style="font-family:monospace; color:var(--accent); font-weight:700;">${key}</span></td>
                <td><strong>${user.nombre}</strong></td>
                <td>${user.rol}</td>
                <td><span style="font-size:0.8rem; color:var(--text-muted);">${user.correo || '---'}</span></td>
                <td>${credsWeb}</td>
                <td style="display:flex; gap:6px; flex-wrap:wrap;">
                    <button class="edit-btn" data-uid="${key}">Editar</button>
                    <button class="delete-btn" data-uid="${key}">Eliminar</button>
                </td>
            `;
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
                crearToast(`✏️ Usuario ${username} actualizado con éxito`, "success");

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
                crearToast(`✅ Usuario ${username} registrado con éxito`, "success");
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
            crearToast(`✏️ Docente ${editingDocenteUid} actualizado correctamente.`, 'success');

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
            await set(ref(db, 'monitoreo_tiempo_real/ultimo_uid_no_registrado'), null);

            // Send welcome email with credentials using SMTPJS (resilient)
            await enviarCorreoConFallback({
                Host: "smtp.gmail.com",
                Username: "smartstock97@gmail.com",
                Password: "TAIPT_M4a",
                To: correo,
                From: "smartstock97@gmail.com",
                Subject: "Bienvenido a Smart Stock - Credenciales de Acceso",
                Body: `Estimado/a ${nombre},\n\nLe damos la bienvenida al sistema Smart Stock. Se ha registrado su tarjeta RFID con éxito.\n\nSus credenciales de acceso para el dashboard web son:\n- Usuario: ${userWeb}\n- Contraseña Temporal: ${passWeb}\n\nPor favor, conserve estas credenciales de forma segura.\n\nAtentamente,\nSmart Stock System`
            });

            await registrarAuditoria('Registro Docente', `Docente registrado: ${nombre} (UID: ${uid})`);
            crearToast('✅ Docente autorizado y credenciales enviadas por correo.', 'success');
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
btnSeedData.addEventListener('click', async () => {
    if (!confirm('¿Deseas inyectar datos de prueba en tu base de datos Firebase? Esto llenará los sensores, inventarios y docentes modelo para demostración.')) {
        return;
    }

    try {
        const seedData = {
            // Sincronizar estado monitoreo
            'monitoreo_tiempo_real': {
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
        alert('⚡ Base de datos inicializada con éxito. ¡Ya puedes navegar por el dashboard para ver el sistema en acción!');
    } catch (e) {
        console.error(e);
        alert('Error al inyectar datos semilla: ' + e.message);
    }
});

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
            <span style="font-size: 1.6rem; animation: iconShake 0.5s infinite;">🚨</span>
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
onValue(ref(db, 'monitoreo_tiempo_real/ultimo_uid_no_registrado'), (snapshot) => {
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
                    <button class="primary-btn" id="modal-btn-print" style="padding:10px 20px; flex:1;">🖨️ Imprimir</button>
                    <button class="secondary-btn" id="modal-btn-close" style="margin-top:0; padding:10px 20px; flex:1;">Cerrar</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    document.getElementById('modal-product-name').innerText = nombreProd;
    document.getElementById('modal-qr-label').innerText = idProd;

    // Generar URL del servidor dinámica apuntando al backend en el puerto 5000
    const qrUrl = `https://smartstock.eu1.netbird.services/nodered/form-retiro?id_producto=${idProd}`;

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
            crearToast(`🗑️ Producto ${id} eliminado con éxito`, "success");
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
                crearToast(`✏️ Producto ${editingProductId} actualizado con éxito`, "success");

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
                crearToast(`✅ Producto ${nombre} agregado con éxito`, "success");
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

// --- HELPER: ENVÍO DE CORREO RESILIENTE CON TIMEOUT ---
/**
 * Intenta enviar un correo con Email.send de SMTPJS.
 * Si el envío tarda más de `timeoutMs` ms o falla, resuelve igualmente
 * (muestra un toast de aviso) para que la UI no quede bloqueada.
 */
async function enviarCorreoConFallback(payload, timeoutMs = 2500) {
    const envioPromise = new Promise((resolve, reject) => {
        try {
            Email.send(payload).then(resolve).catch(reject);
        } catch (e) {
            reject(e);
        }
    });

    const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('SMTP_TIMEOUT')), timeoutMs)
    );

    try {
        await Promise.race([envioPromise, timeoutPromise]);
        console.log('[Email] Correo enviado exitosamente a:', payload.To);
    } catch (err) {
        if (err.message === 'SMTP_TIMEOUT') {
            console.warn('[Email] Timeout: el servidor SMTP tardó más de', timeoutMs, 'ms. Continuando en modo de respaldo.');
            crearToast('⚠️ Conexión de correo lenta, usando modo de respaldo...', 'danger');
        } else {
            console.error('[Email] Error al enviar correo:', err);
            crearToast('⚠️ El correo no pudo enviarse. Continúa con el código OTP.', 'danger');
        }
        // No relanzamos: la UI avanza igual
    }
}

// --- SISTEMA DE LOGIN Y MFA (2FA) ---
const loginOverlay = document.getElementById('loginOverlay');
const formLogin = document.getElementById('formLogin');
const formOtp = document.getElementById('formOtp');

const loginUser = document.getElementById('loginUser');
const loginPass = document.getElementById('loginPass');
const btnIngresar = document.getElementById('btnIngresar');

const loginOtp = document.getElementById('loginOtp');
const btnVerificarOtp = document.getElementById('btnVerificarOtp');
const btnVolverLogin = document.getElementById('btnVolverLogin');
const dashboardContainer = document.querySelector('.dashboard-container');

let generatedOtp = "";

btnIngresar.addEventListener('click', async () => {
    const user = loginUser ? loginUser.value.trim() : '';
    const pass = loginPass ? loginPass.value.trim() : '';

    if (!user || !pass) {
        alert("Por favor ingrese usuario y contraseña.");
        return;
    }

    btnIngresar.disabled = true;
    btnIngresar.textContent = "Verificando...";

    // --- PASO 1: Validar credenciales en Firebase ---
    let authenticatedUser = null;
    try {
        console.log('[Login] Consultando Firebase para usuario:', user);
        const snapshot = await get(ref(db, 'usuarios_sistema'));

        if (snapshot.exists()) {
            const users = snapshot.val();
            console.log('[Login] Nodos encontrados en usuarios_sistema:', Object.keys(users));
            Object.keys(users).forEach(key => {
                const u = users[key];
                // Verificación estricta contra campo 'passwordWeb' (igual que en Firebase)
                if (u.usuario === user && u.passwordWeb === pass) {
                    authenticatedUser = u;
                    console.log('[Login] ✅ Credenciales válidas para nodo:', key);
                }
            });
        } else {
            console.warn('[Login] El nodo usuarios_sistema no existe o está vacío.');
        }
    } catch (dbError) {
        console.error('[Login] ERROR al consultar Firebase:', dbError);
        alert('Error interno en Login: ' + dbError.message);
        btnIngresar.disabled = false;
        btnIngresar.textContent = "Verificar Credenciales";
        return;
    }

    // --- PASO 2: Si las credenciales son incorrectas, avisar y salir ---
    if (!authenticatedUser) {
        alert("Credenciales incorrectas. Verifica tu usuario y contraseña.");
        btnIngresar.disabled = false;
        btnIngresar.textContent = "Verificar Credenciales";
        return;
    }

    // --- PASO 3: Generar OTP y cambiar pantalla INMEDIATAMENTE ---
    try {
        generatedOtp = Math.floor(100000 + Math.random() * 900000).toString();
        usuarioActivo = authenticatedUser;

        // [MFA DEBUG] Código visible en consola para soporte inmediato
        console.log('[MFA DEBUG] El código generado es: ' + generatedOtp);

        // Guardar OTP en Firebase (sin bloquear la UI)
        set(ref(db, 'monitoreo_tiempo_real/mfa_otp'), {
            code: generatedOtp,
            created_at: Date.now()
        }).catch(err => console.warn('[MFA] No se pudo guardar OTP en Firebase:', err));

        // ✅ CAMBIO DE PANTALLA INMEDIATO — no espera el correo
        formLogin.style.display = "none";
        formOtp.style.display = "block";
        btnIngresar.disabled = false;
        btnIngresar.textContent = "Verificar Credenciales";

        // 📧 Envío de correo en segundo plano (fire-and-forget, no bloquea la UI)
        const correoDestino = authenticatedUser.correo || '';
        console.log('[MFA] Enviando código al correo:', correoDestino);
        if (correoDestino) {
            enviarCorreoConFallback({
                Host: "smtp.gmail.com",
                Username: "smartstock97@gmail.com",
                Password: "TAIPT_M4a",
                To: correoDestino,
                From: "smartstock97@gmail.com",
                Subject: "Smart Stock - Código de Verificación MFA",
                Body: `Hola ${authenticatedUser.usuario},\n\nTu código de verificación de 6 dígitos para acceder al sistema Smart Stock es:\n\n${generatedOtp}\n\nEste código es confidencial.\n\nSaludos,\nSmart Stock System`
            }); // ← Sin await: corre en background
        } else {
            console.warn('[MFA] El usuario autenticado no tiene correo registrado. El OTP solo está en consola.');
        }

        crearToast('📧 Ingresa el código OTP enviado a tu correo.', 'success');

    } catch (otpError) {
        console.error('[Login] ERROR al generar OTP o cambiar pantalla:', otpError);
        alert('Error interno en Login: ' + otpError.message);
        btnIngresar.disabled = false;
        btnIngresar.textContent = "Verificar Credenciales";
    }
});

btnVerificarOtp.addEventListener('click', async () => {
    const pin = loginOtp.value.trim();
    if (pin === generatedOtp && pin !== "") {
        loginOverlay.style.display = "none";
        dashboardContainer.style.display = "flex";
        crearToast("🔓 Acceso concedido. ¡Bienvenido!", "success");
        await registrarAuditoria('Inicio Sesión', `Usuario de plataforma inició sesión.`);
    } else {
        alert("Código OTP incorrecto o expirado.");
    }
});

btnVolverLogin.addEventListener('click', () => {
    formOtp.style.display = "none";
    formLogin.style.display = "block";
    loginOtp.value = "";
});

// --- COMPONENTES DEL MODAL INTERACTIVO DE TARJETAS ---
const modalTarjeta = document.getElementById('modalTarjetaDesconocida');
const modalUidText = document.getElementById('modalUidText');
const modalUserNombre = document.getElementById('modalUserNombre');
const modalUserRol = document.getElementById('modalUserRol');
const btnCancelarModal = document.getElementById('btnCancelarModal');
const btnRegistrarModal = document.getElementById('btnRegistrarModal');
const toastContainer = document.getElementById('toastContainer');

let currentUnregisteredUid = "";

onValue(ref(db, 'monitoreo_tiempo_real/ultimo_intento_invalido'), (snapshot) => {
    const data = snapshot.val();
    if (data && data.uid && data.procesado === false) {
        currentUnregisteredUid = data.uid;
        modalUidText.textContent = data.uid;
        modalUserNombre.value = "";
        modalUserRol.value = "";
        modalTarjeta.style.display = 'flex';
        crearToast(`🚨 Intento de acceso denegado. UID: ${data.uid}`, "danger");
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
            Password: "TAIPT_M4a",
            To: correo,
            From: "smartstock97@gmail.com",
            Subject: "Bienvenido a Smart Stock - Credenciales de Acceso",
            Body: `Estimado/a ${nombre},\n\nLe damos la bienvenida al sistema Smart Stock. Se ha registrado su tarjeta RFID con éxito.\n\nSus credenciales de acceso para el dashboard web son:\n- Usuario: ${userWeb}\n- Contraseña Temporal: ${passWeb}\n\nPor favor, conserve estas credenciales de forma segura.\n\nAtentamente,\nSmart Stock System`
        });

        await update(ref(db, 'monitoreo_tiempo_real/ultimo_intento_invalido'), {
            procesado: true
        });

        await registrarAuditoria('Registro Docente (Modal)', `Docente registrado vía modal: ${nombre} (UID: ${currentUnregisteredUid})`);

        if (modalCorreoInput) modalCorreoInput.value = '';
        modalTarjeta.style.display = 'none';
        crearToast(`✅ ¡Tarjeta autorizada con éxito para ${nombre}!`, "success");
    } catch (e) {
        console.error(e);
        alert('Error al registrar o enviar correo de bienvenida.');
    } finally {
        btnRegistrarModal.disabled = false;
        btnRegistrarModal.textContent = "Registrar";
    }
});

btnCancelarModal.addEventListener('click', async () => {
    await update(ref(db, 'monitoreo_tiempo_real/ultimo_intento_invalido'), {
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

            const qrUrl = `https://smartstock.eu1.netbird.services/nodered/form-retiro?id_producto=${key}`;
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

// Función dinámica para alertas Toast en pantalla
function crearToast(mensaje, tipo = "danger") {
    const toast = document.createElement('div');
    toast.className = 'toast';
    if (tipo === "success") toast.style.borderLeftColor = "var(--success)";
    toast.textContent = mensaje;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 6000);
}
