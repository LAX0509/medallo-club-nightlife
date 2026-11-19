import { useEffect, useRef } from "react";
import { Html5Qrcode } from "html5-qrcode";

const ELEMENT_ID = "qr-camera-reader";

/**
 * Envuelve html5-qrcode para leer códigos QR con la cámara del dispositivo.
 * Si no hay cámara disponible o el usuario no otorga permisos, el
 * componente falla de forma silenciosa y deja disponible el registro
 * manual de cortesía como alternativa (ver EscanerPage).
 */
export function QrCameraScanner({ activo, onLectura, onError }) {
  const scannerRef = useRef(null);

  useEffect(() => {
    if (!activo) return undefined;

    const scanner = new Html5Qrcode(ELEMENT_ID);
    scannerRef.current = scanner;
    let detenido = false;
    let camaraIniciada = false;

    scanner
      .start(
        { facingMode: "environment" },
        {
          fps: 10,
          aspectRatio: 1,
          // Zona de lectura: cuadrada y proporcional al visor (en el celular un tamaño fijo se salía del video).
          qrbox: (ancho, alto) => {
            const lado = Math.max(120, Math.floor(Math.min(ancho, alto) * 0.72));
            return { width: lado, height: lado };
          },
        },
        (decodedText) => {
          if (!detenido) onLectura(decodedText);
        },
        () => {
          // Se ignoran los frames sin QR detectado (evento muy frecuente).
        }
      )
      .then(() => {
        camaraIniciada = true;
      })
      .catch((err) => onError?.(err));

    return () => {
      detenido = true;
      // html5-qrcode lanza de forma síncrona (no como promesa rechazada) si
      // stop() se llama sin que la cámara haya llegado a iniciar (p. ej.
      // permiso denegado, o el doble montaje de React StrictMode en modo
      // desarrollo). Sin esta guarda, ese throw escapa del efecto de
      // limpieza y React desmonta el árbol completo.
      if (!camaraIniciada) return;
      try {
        scanner
          .stop()
          .then(() => scanner.clear())
          .catch(() => {});
      } catch {
        // La cámara nunca llegó a iniciar correctamente; no hay nada que detener.
      }
    };
  }, [activo, onLectura, onError]);

  return (
    <div className="qr-camera-frame">
      <div id={ELEMENT_ID} className="qr-camera-viewport" />
      <span className="qr-camera-guia" aria-hidden="true" />
    </div>
  );
}
