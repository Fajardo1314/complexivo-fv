import os

fpath = os.path.join('Proyecto_grado', 'web_dashboard', 'app.js')
with open(fpath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add second Firebase instance for companion's DB
old_config = """const firebaseConfig = {
    databaseURL: "https://aula-4587b-default-rtdb.firebaseio.com/"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);"""

new_config = """// === OUR database (complexivo-fv) ===
const OUR_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/";
const ourApp = initializeApp({ databaseURL: OUR_DB_URL }, 'ours');
const db = getDatabase(ourApp);

// === COMPANION database (aula-4587b) - READ ONLY for hardware ===
const COMPANION_DB_URL = "https://aula-4587b-default-rtdb.firebaseio.com/";
let companionDb = null;
try {
    const companionApp = initializeApp({ databaseURL: COMPANION_DB_URL }, 'companion');
    companionDb = getDatabase(companionApp);
} catch (e) {
    console.warn('[DB] Companion DB init:', e.message);
}"""

c = c.replace(old_config, new_config)

# 2. Move sensor listeners to read from COMPANION db for hardware data
# These are the companion's nodes: puerta_fisica, accesos, usuarios (RFID)
c = c.replace(
    "onValue(ref(db, 'movimiento_pir'), (snapshot) => {\n    const val = snapshot.val();\n    currentPirState = (val === true",
    "onValue(ref(companionDb || db, 'movimiento_pir'), (snapshot) => {\n    const val = snapshot.val();\n    currentPirState = (val === true"
)
c = c.replace(
    "onValue(ref(db, 'puerta_fisica/estado'), (snapshot) => {",
    "onValue(ref(companionDb || db, 'puerta_fisica/estado'), (snapshot) => {"
)
c = c.replace(
    "onValue(ref(db, 'aforo'), (snapshot) => {\n    const val = snapshot.val();\n    const personas = (val !== null && val !== undefined) ? parseInt(val) || 0 : 0;\n    countPersonas.innerText = personas;",
    "onValue(ref(companionDb || db, 'aforo'), (snapshot) => {\n    const val = snapshot.val();\n    const personas = (val !== null && val !== undefined) ? parseInt(val) || 0 : 0;\n    countPersonas.innerText = personas;"
)
c = c.replace(
    "onValue(ref(db, 'accesos'), (snapshot) => {",
    "onValue(ref(companionDb || db, 'accesos'), (snapshot) => {"
)
c = c.replace(
    "onValue(ref(db, 'usuarios'), (snapshot) => {",
    "onValue(ref(companionDb || db, 'usuarios'), (snapshot) => {"
)
# Also fix the duplicate movimiento_pir listener for foco
c = c.replace(
    "// --- FIREBASE: CONTROL FOCO INTELIGENTE MERCURY ---\nonValue(ref(db, 'movimiento_pir'), (snapshot) => {",
    "// --- FIREBASE: CONTROL FOCO INTELIGENTE MERCURY ---\nonValue(ref(db, 'estado_foco'), (snapshot) => {"
)
# Fix the gauge listener
c = c.replace(
    "// Hook gauge into infrarrojo sensor\nonValue(ref(db, 'aforo'), (snapshot) => {",
    "// Hook gauge into aforo sensor\nonValue(ref(companionDb || db, 'aforo'), (snapshot) => {"
)

# 3. Login should use OUR db (already does since `db` = ourApp)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)
print('app.js: Restructured with dual database (complexivo-fv + aula-4587b)')