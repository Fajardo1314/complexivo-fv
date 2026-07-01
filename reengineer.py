import os

fpath = os.path.join('Proyecto_grado', 'web_dashboard', 'app.js')
with open(fpath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add SHA-256 helper function after the imports
sha256_func = '''
// --- SHA-256 HASH HELPER ---
async function sha256(text) {
    const msgBuffer = new TextEncoder().encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
'''

# Insert after the db initialization
c = c.replace(
    "const db = getDatabase(app);\n\n// --- GLOBAL STATE ---",
    "const db = getDatabase(app);\n\n" + sha256_func + "// --- GLOBAL STATE ---"
)

# 2. Update login to use SHA-256 hash comparison
old_login_check = """                if (u.usuario === user && u.passwordWeb === pass) {
                    authenticatedUser = u;
                    console.log('[Login] [OK] Credenciales válidas para nodo:', key);
                }"""
new_login_check = """                // Try plain text first, then hashed comparison
                const passMatch = (u.passwordWeb === pass) || (u.passwordHash && u.passwordHash === await sha256(pass));
                if (u.usuario === user && passMatch) {
                    authenticatedUser = u;
                    console.log('[Login] [OK] Credenciales válidas para nodo:', key);
                }"""
c = c.replace(old_login_check, new_login_check)

# 3. Update aplicarVisibilidadAdmin to handle 'admin' role
old_es_admin = """function esAdmin() {
    if (!usuarioActivo) return false;
    const rol = (usuarioActivo.rol || '').toLowerCase();
    return rol === 'superadmin' || rol === 'admin' || rol === 'super_admin';
}"""
new_es_admin = """function esAdmin() {
    if (!usuarioActivo) return false;
    const rol = (usuarioActivo.rol || '').toLowerCase();
    return rol === 'superadmin' || rol === 'admin' || rol === 'super_admin';
}

function esDocenteOOperador() {
    if (!usuarioActivo) return false;
    const rol = (usuarioActivo.rol || '').toLowerCase();
    return rol === 'docente' || rol === 'operador';
}"""
c = c.replace(old_es_admin, new_es_admin)

# 4. Update aplicarVisibilidadAdmin to show all tabs for admin, hide servidor for docente/operador
old_vis = """    // Role-based edit restrictions for Docente
    if (userRol === 'Docente') {"""
new_vis = """    // Docente/Operador: hide servidor panel
    if (esDocenteOOperador()) {
        const navServ = document.querySelector('.nav-btn[data-target="panel-servidor"]');
        if (navServ) navServ.style.display = 'none';
    }

    // Role-based edit restrictions for Docente
    if (userRol === 'Docente') {"""
c = c.replace(old_vis, new_vis)

# 5. Add password hashing when saving web user
old_save_user = """                await set(ref(db, `usuarios_sistema/${finalKey}`), {
                    id_operador: opId,
                    usuario: username,
                    passwordWeb: password,
                    correo: correo,
                    rol: rol
                });"""
new_save_user = """                const hashedPass = await sha256(password);
                await set(ref(db, `usuarios_sistema/${finalKey}`), {
                    id_operador: opId,
                    usuario: username,
                    passwordWeb: password,
                    passwordHash: hashedPass,
                    correo: correo,
                    rol: rol
                });"""
c = c.replace(old_save_user, new_save_user)

# 6. Update password change to use hash
old_change_pass = """            await update(ref(db, `usuarios_sistema/${usuarioActivo.usuario}`), { passwordWeb: newP });"""
new_change_pass = """            const hashedNewPass = await sha256(newP);
            await update(ref(db, `usuarios_sistema/${usuarioActivo.usuario}`), { passwordWeb: newP, passwordHash: hashedNewPass });"""
c = c.replace(old_change_pass, new_change_pass)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)
print('app.js: Core auth and role changes applied')