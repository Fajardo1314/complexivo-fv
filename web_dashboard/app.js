import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue, update, remove, set } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

// --- CONFIGURACIÓN FIREBASE ---
const firebaseConfig = {
    databaseURL: "https://complexivo-fv-default-rtdb.firebaseio.com/"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

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

const listaInventario = document.getElementById('listaInventario');
const listaAccesos = document.getElementById('listaAccesos');
const listaUsuarios = document.getElementById('listaUsuarios');

// Formularios QR
const btnGuardarProd = document.getElementById('btnGuardarProd');
const qrResultArea = document.getElementById('qrResultArea');
const qrPreview = document.getElementById('qrPreview');
const qrLabel = document.getElementById('qrLabel');
const btnPrintQR = document.getElementById('btnPrintQR');

// Formulario Usuarios RFID
const btnGuardarUsuario = document.getElementById('btnGuardarUsuario');
const userUid = document.getElementById('userUid');
const userNombre = document.getElementById('userNombre');
const userRol = document.getElementById('userRol');

// Botón Datos Semilla
const btnSeedData = document.getElementById('btnSeedData');

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

        // Foco
        const focoState = data.estado_foco || 'APAGADO';
        estadoFoco.innerText = focoState;
        if (focoState === 'ENCENDIDO') {
            cardFoco.style.borderColor = 'rgba(245, 158, 11, 0.4)';
            cardFoco.style.boxShadow = '0 10px 30px rgba(245, 158, 11, 0.15)';
            subFoco.innerText = "Luz artificial activada";
        } else {
            cardFoco.style.borderColor = '';
            cardFoco.style.boxShadow = '';
            subFoco.innerText = "Luz artificial desactivada";
        }

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

// --- FIREBASE: INVENTARIO ---
onValue(ref(db, 'inventario'), (snapshot) => {
    listaInventario.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {
            const prod = data[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span style="font-family:monospace; color:var(--primary); font-weight:700;">${key}</span></td>
                <td>${prod.nombre_producto}</td>
                <td><span class="badge ${prod.stock > 0 ? 'badge-green' : 'badge-red'}">${prod.stock} unidades</span></td>
                <td>
                    <button class="qr-btn" data-id="${key}" data-nombre="${prod.nombre_producto}" style="padding:6px 12px; background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.4); color:var(--primary); border-radius:8px; font-weight:600; cursor:pointer; transition:all 0.2s;">👁️ Ver QR</button>
                </td>
            `;
            tr.querySelector('.qr-btn').addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                const nombre = e.target.dataset.nombre;
                mostrarModalQR(id, nombre);
            });
            listaInventario.appendChild(tr);
        });
    } else {
        listaInventario.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No hay productos registrados.</td></tr>';
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
            tr.innerHTML = `
                <td><span style="font-family:monospace; color:var(--accent); font-weight:700;">${key}</span></td>
                <td><strong>${user.nombre}</strong></td>
                <td>${user.rol}</td>
                <td>
                    <button class="delete-btn" data-uid="${key}">🗑️ Eliminar</button>
                </td>
            `;
            // Listener para el botón eliminar
            tr.querySelector('.delete-btn').addEventListener('click', (e) => {
                const uid = e.target.dataset.uid;
                if (confirm(`¿Estás seguro de revocar el acceso a ${user.nombre}?`)) {
                    remove(ref(db, `usuarios/${uid}`))
                        .then(() => alert('Usuario eliminado de Firebase.'))
                        .catch(err => alert('Error al eliminar: ' + err));
                }
            });
            listaUsuarios.appendChild(tr);
        });
    } else {
        listaUsuarios.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No hay docentes registrados en la base de datos.</td></tr>';
    }
});

// --- ACCIÓN: REGISTRAR USUARIO RFID ---
btnGuardarUsuario.addEventListener('click', async () => {
    const uid = userUid.value.trim();
    const nombre = userNombre.value.trim();
    const rol = userRol.value.trim();

    if (!uid || !nombre || !rol) {
        alert('Por favor, completa todos los campos del docente.');
        return;
    }

    try {
        await set(ref(db, 'usuarios/' + uid), {
            nombre: nombre,
            rol: rol
        });

        // Limpiar en Firebase el último UID no registrado
        await set(ref(db, 'monitoreo_tiempo_real/ultimo_uid_no_registrado'), null);

        userUid.value = '';
        userNombre.value = '';
        userRol.value = '';
        userUid.disabled = false;
        alert('Docente autorizado y guardado en Firebase.');
    } catch (e) {
        console.error(e);
        alert('Error al guardar en Firebase.');
    }
});

// --- LÓGICA: GENERAR QR E INVENTARIO ---
btnGuardarProd.addEventListener('click', async () => {
    const idProd = document.getElementById('prodId').value.trim();
    const nombre = document.getElementById('prodNombre').value.trim();
    const stock = parseInt(document.getElementById('prodStock').value);
    const categoria = "Laboratorio"; // Categoría por defecto para transacciones

    if (!idProd || !nombre || isNaN(stock)) {
        alert('Por favor, completa todos los campos del material.');
        return;
    }

    try {
        // Enviar al backend vía HTTP POST en puerto 5000 para asegurar transacción exitosa antes de generar QR
        const response = await fetch(`http://${window.location.hostname}:5000/api/inventario`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: idProd, nombre: nombre, stock: stock, categoria: categoria })
        });

        const result = await response.json();

        if (response.ok && result.status === "success") {
            const qrUrl = result.qr_url;

            // Generar QR visual apuntando al perfil del equipo
            qrPreview.innerHTML = '';
            if (typeof QRCode !== 'undefined') {
                new QRCode(qrPreview, {
                    text: qrUrl,
                    width: 130,
                    height: 130,
                    colorDark: "#0f172a",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.H
                });
            } else {
                qrPreview.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;padding:20px;">Librería QR no disponible offline. Enlace del equipo: <br><a href="${qrUrl}" target="_blank" style="color:var(--primary);">${qrUrl}</a></p>`;
            }

            qrLabel.innerText = idProd;
            qrResultArea.style.display = 'flex';

            // Limpiar inputs
            document.getElementById('prodId').value = '';
            document.getElementById('prodNombre').value = '';
            document.getElementById('prodStock').value = '';

            alert('Material registrado exitosamente y QR de perfil generado.');
        } else {
            alert('Error al guardar en base de datos: ' + result.message);
        }
    } catch (e) {
        console.error(e);
        alert('Error de red al conectar con el servidor.');
    }
});

// Imprimir QR
btnPrintQR.addEventListener('click', () => {
    const printContent = document.querySelector('.printable-badge').outerHTML;

    // Crear una ventana de impresión limpia
    const printWindow = window.open('', '', 'height=500,width=500');
    printWindow.document.write('<html><head><title>Imprimir Etiqueta</title>');
    printWindow.document.write('<style>');
    printWindow.document.write('body { display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: monospace; }');
    printWindow.document.write('.printable-badge { background: white; color: #000; padding: 20px; border: 3px solid #000; border-radius: 12px; width: 220px; text-align: center; }');
    printWindow.document.write('.badge-header { font-size: 10px; font-weight: bold; margin-bottom: 12px; text-transform: uppercase; border-bottom: 2px solid #000; padding-bottom: 4px; }');
    printWindow.document.write('#qrPreview { padding: 5px; background: white; display: inline-block; margin-bottom: 10px; }');
    printWindow.document.write('#qrLabel { font-family: monospace; font-size: 12px; font-weight: bold; background: #eee; padding: 4px; border: 1px dashed #000; display: block; word-break: break-all; }');
    printWindow.document.write('</style></head><body>');
    printWindow.document.write(printContent);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    printWindow.focus();

    // Ejecutar retraso para cargar el DOM y luego imprimir
    setTimeout(() => {
        printWindow.print();
        printWindow.close();
    }, 500);
});

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
let audioCtx = null;
let beepInterval = null;

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
    const qrUrl = `http://${window.location.hostname}:5000/dashboard/equipo/${idProd}`;
    
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
