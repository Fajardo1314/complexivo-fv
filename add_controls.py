import os

fpath = os.path.join('Proyecto_grado', 'web_dashboard', 'app.js')
with open(fpath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add monitoring controls logic before the toast function
controls_code = '''
// --- CONTROLES DE MONITOREO ---
const btnToggleFoco = document.getElementById('btnToggleFoco');
const btnResetAlarma = document.getElementById('btnResetAlarma');

if (btnToggleFoco) {
    btnToggleFoco.addEventListener('click', async () => {
        try {
            const snap = await get(ref(db, 'estado_foco'));
            const current = (snap.val() || '').toString().trim().toUpperCase();
            const nuevoEstado = (current === 'ENCENDIDO' || current === 'ON' || current === 'TRUE' || current === '1') ? 'APAGADO' : 'ENCENDIDO';
            await set(ref(db, 'estado_foco'), nuevoEstado);
            crearToast('Iluminacion: ' + nuevoEstado, 'success');
            await registrarAuditoria('Control Iluminacion', 'Estado cambiado a ' + nuevoEstado);
        } catch (e) {
            console.error(e);
            crearToast('Error al controlar iluminacion', 'danger');
        }
    });
}

if (btnResetAlarma) {
    btnResetAlarma.addEventListener('click', async () => {
        try {
            await set(ref(db, 'movimiento_pir'), false);
            detenerAlertaCritica();
            crearToast('Alarma PIR reseteada', 'success');
            await registrarAuditoria('Reset Alarma', 'Alarma PIR reseteada manualmente');
        } catch (e) {
            console.error(e);
            crearToast('Error al resetear alarma', 'danger');
        }
    });
}

// Show alarm reset button when PIR is active
if (btnResetAlarma) {
    onValue(ref(db, 'movimiento_pir'), (snapshot) => {
        const val = snapshot.val();
        const active = (val === true || val === 'true' || val === 1 || val === '1');
        btnResetAlarma.style.display = active ? 'block' : 'none';
    });
}

// --- BOTON REINICIAR RASPBERRY PI (Admin) ---
const btnRebootPi = document.getElementById('btnRebootPi');
if (btnRebootPi) {
    btnRebootPi.addEventListener('click', async () => {
        if (!confirm('ATENCION: Reiniciara la Raspberry Pi completamente. Continuar?')) return;
        try {
            await set(ref(db, 'sistema/comando'), 'REBOOT');
            const statusEl = document.getElementById('serverCmdStatus');
            if (statusEl) {
                statusEl.textContent = 'Comando REBOOT enviado. La Pi se reiniciara en unos segundos.';
                statusEl.style.color = 'var(--warning)';
            }
            await registrarAuditoria('Reboot RPi', 'Comando REBOOT enviado a la Raspberry Pi');
            crearToast('[OK] Comando de reinicio enviado.', 'success');
        } catch (e) { console.error(e); }
    });
}

'''

# Insert before the toast function
c = c.replace(
    '// Funcion dinamica para alertas Toast en pantalla\nfunction crearToast(',
    controls_code + '// Funcion dinamica para alertas Toast en pantalla\nfunction crearToast('
)

# 2. Update the accesos listener to handle new format from aula-4587b
old_accesos = """onValue(ref(db, 'accesos'), (snapshot) => {
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
});"""

new_accesos = """onValue(ref(db, 'accesos'), (snapshot) => {
    listaAccesos.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        const entries = [];
        snapshot.forEach(child => {
            entries.push({ key: child.key, ...child.val() });
        });
        entries.reverse().forEach(acc => {
            const tIngreso = acc.fecha_hora || acc.hora_ingreso || '--';
            const metodo = acc.metodo || acc.metodo_acceso || 'rfid';
            const metodoBadge = metodo.includes('RFID')
                ? '<span class="badge badge-purple">[RFID] RFID</span>'
                : '<span class="badge badge-blue">[CODIGO] Codigo</span>';
            const exito = acc.exitoso !== undefined ? (acc.exitoso ? '<span class="badge badge-green">Exitoso</span>' : '<span class="badge badge-red">Denegado</span>') : '--';
            const motivo = acc.motivo || acc.rol || '';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${acc.docente || acc.nombre || '--'}</strong></td>
                <td>${metodoBadge}</td>
                <td><span style="color:var(--text-muted); font-size:0.85rem;">${motivo}</span></td>
                <td>${tIngreso}</td>
                <td>${acc.hora_salida || 'Activo'}</td>
                <td>${acc.tiempo_permanencia_min ? acc.tiempo_permanencia_min + ' min' : '--'}</td>
                <td><span style="font-weight:700;">${acc.acompanantes_al_ingresar || '--'}</span></td>
                <td>${exito}</td>
            `;
            listaAccesos.appendChild(tr);
        });
    } else {
        listaAccesos.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No hay registros de acceso.</td></tr>';
    }
});"""

c = c.replace(old_accesos, new_accesos)

# 3. Update usuarios listener to filter docente/operador
old_usuarios = """onValue(ref(db, 'usuarios'), (snapshot) => {
    listaUsuarios.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).forEach(key => {"""
new_usuarios = """onValue(ref(db, 'usuarios'), (snapshot) => {
    listaUsuarios.innerHTML = '';
    const data = snapshot.val();
    if (data) {
        Object.keys(data).filter(key => {
            const r = (data[key].rol || '').toLowerCase();
            return r === 'docente' || r === 'operador';
        }).forEach(key => {"""
c = c.replace(old_usuarios, new_usuarios)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)
print('app.js: Monitoring controls, accesos update, and usuario filter applied')