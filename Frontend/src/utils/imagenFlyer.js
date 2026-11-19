// Prepara el archivo del flyer antes de subirlo. El hosting limita cada respuesta a ~4 MB, así que las
// imágenes grandes se reducen en el navegador (el flyer se ve igual de bien en pantalla).
export const MAX_IMAGEN_FINAL = 3_500_000;
export const MAX_VIDEO = 20 * 1024 * 1024;
export const MAX_IMAGEN_ORIGINAL = 40 * 1024 * 1024;

function aBlob(canvas, tipo, calidad) {
  return new Promise((resolver) => canvas.toBlob(resolver, tipo, calidad));
}

export async function prepararFlyer(archivo) {
  if (!archivo) return null;
  if (archivo.type.startsWith("video/") || archivo.type === "image/gif") return archivo;
  if (archivo.size <= MAX_IMAGEN_FINAL) return archivo;

  const bitmap = await createImageBitmap(archivo);
  let lado = Math.min(1, 2200 / Math.max(bitmap.width, bitmap.height));
  for (let intento = 0; intento < 6; intento += 1) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * lado));
    canvas.height = Math.max(1, Math.round(bitmap.height * lado));
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#0c1220";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    for (const calidad of [0.9, 0.8, 0.7, 0.6]) {
      const blob = await aBlob(canvas, "image/jpeg", calidad);
      if (blob && blob.size <= MAX_IMAGEN_FINAL) {
        bitmap.close?.();
        const nombre = archivo.name.replace(/\.[^.]+$/, "") + ".jpg";
        return new File([blob], nombre, { type: "image/jpeg" });
      }
    }
    lado *= 0.75;
  }
  bitmap.close?.();
  throw new Error("No se pudo reducir la imagen. Prueba con otra más pequeña.");
}
