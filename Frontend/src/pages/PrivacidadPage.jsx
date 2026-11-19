import { Link } from "react-router-dom";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import "./PrivacidadPage.css";

const ACTUALIZACION = "26 de octubre de 2026";

export function PrivacidadPage() {
  return (
    <div className="privacidad-pagina">
      <header className="privacidad-cabecera">
        <Link to="/" className="privacidad-marca">
          <img src={medalloLogo} alt="" width="40" height="40" />
          <span>Medallo Club</span>
        </Link>
        <Link to="/" className="privacidad-volver">Volver al inicio</Link>
      </header>

      <main className="privacidad-contenido">
        <p className="privacidad-kicker">TUS DATOS</p>
        <h1>Política de privacidad y tratamiento de datos personales</h1>
        <p className="privacidad-fecha">Última actualización: {ACTUALIZACION}</p>

        <p>
          Medallo Club es una plataforma web para gestionar reservas, accesos, promotores e inventario de un club nocturno.
          Fue desarrollada como proyecto de trabajo de grado de Ingeniería de Sistemas en la Universidad Católica Luis Amigó
          (Medellín, Colombia). Esta política explica qué datos recibimos, para qué los usamos y cómo puedes ejercer tus derechos,
          de acuerdo con la Ley 1581 de 2012 de protección de datos personales de Colombia.
        </p>

        <h2>1. Responsable del tratamiento</h2>
        <p>
          El responsable es el equipo de desarrollo de Medallo Club (Juan Camilo Nieto Arboleda y Manuel Alejandro Hernández Lizcano),
          estudiantes de la Universidad Católica Luis Amigó. Puedes contactarnos por el chat de reservas de esta misma página,
          con la opción «Hablar con el equipo».
        </p>

        <h2>2. Qué datos recopilamos</h2>
        <ul>
          <li><strong>Clientes que reservan:</strong> nombre, número de teléfono o WhatsApp, evento elegido, tipo de espacio, número de personas y las notas que escribas.</li>
          <li><strong>Conversaciones con el asistente:</strong> los mensajes que escribes en el chat o por WhatsApp. De cada conversación guardamos un análisis (si el mensaje es positivo, neutral o negativo y los temas que menciona) y una huella cifrada del contacto, no el número en claro.</li>
          <li><strong>Invitados:</strong> el nombre que registra el promotor o que se toma de la reserva y el código de su pase.</li>
          <li><strong>Equipo del club (administradores, promotores y puerta):</strong> nombre, correo, teléfono opcional, rol y contraseña, que se guarda cifrada.</li>
          <li><strong>Registros de uso:</strong> la hora en que se escanea un pase y su resultado.</li>
        </ul>
        <p>No pedimos documentos de identidad, datos de tarjetas ni otros datos sensibles. Te pedimos que no los escribas en el chat.</p>

        <h2>3. Para qué usamos los datos</h2>
        <ul>
          <li>Gestionar tu reserva, confirmarla y emitir los pases de ingreso.</li>
          <li>Validar el ingreso en la puerta y evitar que un mismo pase se use dos veces.</li>
          <li>Responder tus mensajes y mejorar la atención del club.</li>
          <li>Calcular las comisiones de los promotores y controlar el aforo y el inventario.</li>
          <li>Enviarte avisos relacionados con tu reserva, por ejemplo la confirmación por WhatsApp.</li>
        </ul>
        <p>No vendemos ni cedemos tus datos para publicidad de terceros.</p>

        <h2>4. Con quién se comparten</h2>
        <p>Para que el servicio funcione usamos proveedores que procesan datos en nuestro nombre:</p>
        <ul>
          <li><strong>Vercel y Neon:</strong> alojan la aplicación y la base de datos.</li>
          <li><strong>Meta (WhatsApp Cloud API):</strong> entrega los mensajes de WhatsApp, como el aviso de nueva reserva y la confirmación al cliente.</li>
          <li><strong>Google (Gemini) y Groq:</strong> procesan el texto libre que escribes en el chat para entender lo que pides. Los pasos en los que das tu nombre y tu teléfono se resuelven con reglas propias del sistema, sin enviarlos a la IA.</li>
        </ul>

        <h2>5. Cuánto tiempo los conservamos</h2>
        <p>
          Guardamos los datos mientras sean necesarios para gestionar reservas y accesos, y mientras dure el proyecto académico.
          Cuando pidas la eliminación de tus datos, los borramos o los anonimizamos, salvo lo que debamos conservar por obligación legal.
        </p>

        <h2>6. Tus derechos</h2>
        <p>Como titular de los datos puedes:</p>
        <ul>
          <li>Conocer, actualizar y rectificar tus datos.</li>
          <li>Pedir prueba de la autorización que nos diste.</li>
          <li>Saber cómo usamos tus datos.</li>
          <li>Revocar tu autorización y pedir que eliminemos tus datos.</li>
          <li>Presentar quejas ante la Superintendencia de Industria y Comercio.</li>
        </ul>

        <h2>7. Cómo pedir la eliminación de tus datos</h2>
        <p>
          Escríbenos por el chat de reservas con la opción «Hablar con el equipo» e indica tu nombre y el teléfono con el que reservaste.
          Verificamos que seas el titular y eliminamos tus datos de reservas, pases y conversaciones asociadas. También puedes cancelar tu reserva
          desde el enlace privado que recibiste.
        </p>

        <h2>8. Seguridad</h2>
        <p>
          Las contraseñas se guardan cifradas, el acceso al panel depende del rol de cada persona, las comunicaciones usan HTTPS y los enlaces
          de reserva son privados. Aun así, ningún sistema es infalible: si notas algo raro, avísanos.
        </p>

        <h2>9. Menores de edad</h2>
        <p>El ingreso al club es solo para mayores de 18 años y esta plataforma no está dirigida a menores.</p>

        <h2>10. Cambios en esta política</h2>
        <p>Si cambiamos esta política, publicaremos la nueva versión en esta página con su fecha de actualización.</p>
      </main>

      <footer className="privacidad-pie">© Medallo Club · Medellín, Colombia</footer>
    </div>
  );
}
