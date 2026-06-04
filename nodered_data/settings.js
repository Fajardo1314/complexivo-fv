module.exports = {
    uiPort: 1880,
    mqttReconnectTime: 15000,
    serialReconnectTime: 15000,
    debugMaxLength: 1000,
    httpAdminRoot: '/nodered/',
    httpNodeRoot: '/nodered/api',
    editorTheme: {
        projects: { enabled: false },
        palette: { editable: true },
        header: { title: "UCuenca TEC - Raspberry Pi" }
    },
    logging: {
        console: { level: "info", metrics: false, audit: false }
    },
    functionGlobalContext: {},
    credentialSecret: false
};
