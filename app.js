let sessionONNX = null;
// 1. Estado global de la aplicación (Memoria del usuario)
let mensajesLocales = [];

// 2. Inicialización
window.onload = async () => {
    cargarHistorialLocal(); // Cargar mensajes guardados antes de cargar la IA
    await cargarModelo();
};

async function cargarModelo() {
    try {
        console.log("Descargando modelo ONNX...");
        sessionONNX = await ort.InferenceSession.create('./modelo_produccion.onnx');
        console.log("Modelo cargado.");
    } catch (e) {
        console.error("Error al cargar el modelo:", e);
    }
}

// 3. Funciones de Persistencia (LocalStorage)
function cargarHistorialLocal() {
    const datosGuardados = localStorage.getItem('bandeja_privada_spam');
    if (datosGuardados) {
        mensajesLocales = JSON.parse(datosGuardados);
        renderizarBandejas(); // Dibujar la pantalla con los datos cargados
    }
}

function guardarHistorialLocal() {
    localStorage.setItem('bandeja_privada_spam', JSON.stringify(mensajesLocales));
}

function extraerCaracteristicas(texto) {
    const num_caracteres = texto.length;
    const num_mayusculas = (texto.match(/[A-Z]/g) || []).length;
    const num_digitos = (texto.match(/[0-9]/g) || []).length;
    let texto_limpio = texto.toLowerCase().replace(/http\S+/g, '').replace(/[^a-z\s]/g, ' ');

    return { texto_limpio, num_caracteres, num_mayusculas, num_digitos };
}

// Función extraída para reutilizar la IA tanto en manual como en masivo
async function clasificarTexto(texto) {
    const features = extraerCaracteristicas(texto);
    const inputs = {
        'texto_limpio': new ort.Tensor('string', [features.texto_limpio], [1, 1]),
        'num_caracteres': new ort.Tensor('float32', Float32Array.from([features.num_caracteres]), [1, 1]),
        'num_mayusculas': new ort.Tensor('float32', Float32Array.from([features.num_mayusculas]), [1, 1]),
        'num_digitos': new ort.Tensor('float32', Float32Array.from([features.num_digitos]), [1, 1])
    };
    
    const resultados = await sessionONNX.run(inputs);
    return (resultados.output_label.data[0] === 1n); // Retorna true si es spam
}

// 1. Modificación del procesamiento manual para usar la nueva función
async function procesarMensaje() {
    if (!sessionONNX) { alert("Modelo cargando..."); return; }
    
    const inputEl = document.getElementById("inputMensaje");
    const textoOriginal = inputEl.value.trim();
    if (!textoOriginal) return;

    try {
        const esSpam = await clasificarTexto(textoOriginal);
        
        mensajesLocales.push({
            id: Date.now(),
            texto: textoOriginal,
            esSpam: esSpam
        });
        
        guardarHistorialLocal();
        renderizarBandejas();
        inputEl.value = '';
    } catch (e) {
        console.error("Error en inferencia:", e);
    }
}

// 2. NUEVA FUNCION: Procesamiento Masivo desde CSV
async function procesarCSV() {
    if (!sessionONNX) { alert("El modelo aún no está listo."); return; }

    const inputArchivo = document.getElementById('archivoCSV');
    const btnProcesar = document.getElementById('btnProcesarCSV');

    if (inputArchivo.files.length === 0) {
        alert("Por favor, selecciona un archivo primero.");
        return;
    }

    const archivo = inputArchivo.files[0];
    const lector = new FileReader();

    // Lo que sucede cuando el archivo termina de cargarse en memoria
    lector.onload = async function(evento) {
        const contenido = evento.target.result;
        // Separar por saltos de línea (funciona para Windows \r\n y Linux/Mac \n)
        const lineas = contenido.split(/\r?\n/); 
        let procesados = 0;

        btnProcesar.innerText = "Procesando... (puede tardar)";
        btnProcesar.disabled = true;

        // Bucle asíncrono para evaluar cada línea
        for (let i = 0; i < lineas.length; i++) {
            let texto = lineas[i].trim();
            
            // Omitir líneas vacías o un posible encabezado común ("texto", "mensaje")
            if (!texto || texto.toLowerCase() === 'texto' || texto.toLowerCase() === 'v2') continue;

            // Limpiar comillas iniciales y finales si el CSV fue exportado desde Excel
            texto = texto.replace(/^"|"$/g, '');

            try {
                const esSpam = await clasificarTexto(texto);
                
                mensajesLocales.push({
                    // Date.now() + i asegura que el ID sea único incluso si se procesan milisegundos
                    id: Date.now() + i, 
                    texto: texto,
                    esSpam: esSpam
                });
                procesados++;
            } catch (err) {
                console.error(`Error procesando línea ${i}:`, err);
            }
        }

        // Actualizar interfaz una sola vez al terminar todo el lote
        guardarHistorialLocal();
        renderizarBandejas();

        btnProcesar.innerText = "Subir y Analizar";
        btnProcesar.disabled = false;
        inputArchivo.value = ''; // Resetear el input
        
        alert(`Se han clasificado y guardado ${procesados} mensajes exitosamente.`);
    };

    // Leer el archivo como texto plano
    lector.readAsText(archivo);
}

// 5. Renderizado dinámico desde el Estado
function renderizarBandejas() {
    const listaInbox = document.getElementById("listaInbox");
    const listaSpam = document.getElementById("listaSpam");
    
    // Limpiar contenedores
    listaInbox.innerHTML = '';
    listaSpam.innerHTML = '';

    // Dibujar cada mensaje en su lugar correspondiente
    mensajesLocales.forEach(msg => {
        const div = document.createElement("div");
        div.className = `mensaje ${msg.esSpam ? 'spam' : ''}`;
        div.innerHTML = `
            <p>${msg.texto}</p>
            <button class="btn-corregir" onclick="corregirMensaje(${msg.id})">
                Corregir: Marcar como ${msg.esSpam ? 'Ham (No Spam)' : 'Spam'}
            </button>
        `;
        
        if (msg.esSpam) {
            listaSpam.prepend(div);
        } else {
            listaInbox.prepend(div);
        }
    });
}

// 6. Lógica de Corrección (Trigger hacia la Base Madre)
async function corregirMensaje(id) {
    // Buscar el mensaje en la memoria
    const index = mensajesLocales.findIndex(m => m.id === id);
    if (index === -1) return;

    // Cambiar la etiqueta localmente
    mensajesLocales[index].esSpam = !mensajesLocales[index].esSpam;
    
    // Guardar cambios en el navegador y refrescar pantalla visualmente
    guardarHistorialLocal();
    renderizarBandejas();

    const msgCorregido = mensajesLocales[index];
    const etiquetaReal = msgCorregido.esSpam ? 1 : 0;

    console.log(`Enviando a Base Madre: "${msgCorregido.texto}" -> ${etiquetaReal}`);

    // Petición a Supabase / Firebase
    /*
    fetch('https://TU_PROYECTO.supabase.co/rest/v1/Errores_Reportados', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'apikey': 'TU_ANON_KEY'
        },
        body: JSON.stringify({
            texto_anonimizado: msgCorregido.texto,
            etiqueta_correcta: etiquetaReal,
            estado: 'pendiente'
        })
    }).catch(err => console.error("Error al reportar:", err));
    */
}
