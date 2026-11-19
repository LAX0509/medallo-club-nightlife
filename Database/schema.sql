-- =====================================================================
-- Medallo Club / Nightlife Data Scientist - Esquema de base de datos (PostgreSQL 14+)
-- Generado con pg_dump a partir de las migraciones de Alembic (0001 -> 0014), por lo que
-- es identico al que produce `alembic upgrade head`. Ejecutar sobre una base vacia:
--   psql -U postgres -d nightlife_db -f Database/schema.sql
-- Al final se registra la version de Alembic para poder seguir migrando despues.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.accesos_qr (
    id integer NOT NULL,
    invitado_id integer,
    evento_id integer NOT NULL,
    tipo character varying(20) NOT NULL,
    resultado character varying(20) NOT NULL,
    justificacion text,
    fecha_hora timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_accesos_qr_resultado CHECK (((resultado)::text = ANY ((ARRAY['valido'::character varying, 'duplicado'::character varying, 'rechazado'::character varying])::text[]))),
    CONSTRAINT ck_accesos_qr_tipo CHECK (((tipo)::text = ANY ((ARRAY['qr'::character varying, 'cortesia_manual'::character varying])::text[])))
);

CREATE SEQUENCE public.accesos_qr_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.accesos_qr_id_seq OWNED BY public.accesos_qr.id;

CREATE TABLE IF NOT EXISTS public.alembic_version (
    version_num character varying(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.alertas_riesgo (
    id integer NOT NULL,
    evento_id integer NOT NULL,
    tipo_alerta character varying(50) NOT NULL,
    nivel character varying(20) NOT NULL,
    descripcion character varying(255) NOT NULL,
    estado character varying(20) DEFAULT 'activa'::character varying NOT NULL,
    fecha_hora timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_alertas_estado CHECK (((estado)::text = ANY ((ARRAY['activa'::character varying, 'resuelta'::character varying])::text[]))),
    CONSTRAINT ck_alertas_nivel CHECK (((nivel)::text = ANY ((ARRAY['bajo'::character varying, 'medio'::character varying, 'alto'::character varying])::text[]))),
    CONSTRAINT ck_alertas_tipo CHECK (((tipo_alerta)::text = ANY ((ARRAY['sobreaforo'::character varying, 'comision_atipica'::character varying, 'cortesia_duplicada'::character varying])::text[])))
);

CREATE SEQUENCE public.alertas_riesgo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.alertas_riesgo_id_seq OWNED BY public.alertas_riesgo.id;

CREATE TABLE IF NOT EXISTS public.bot_configuracion (
    clave character varying(60) NOT NULL,
    valor text DEFAULT ''::text NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.chat_mensajes (
    id integer NOT NULL,
    sesion_id character varying(36) NOT NULL,
    autor character varying(10) NOT NULL,
    texto text,
    sentimiento character varying(20),
    puntaje numeric(4,2),
    emocion character varying(20),
    aspectos character varying(200),
    intencion character varying(30),
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_mensajes_autor CHECK (((autor)::text = ANY ((ARRAY['usuario'::character varying, 'bot'::character varying])::text[])))
);

CREATE SEQUENCE public.chat_mensajes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.chat_mensajes_id_seq OWNED BY public.chat_mensajes.id;

CREATE TABLE IF NOT EXISTS public.chat_sesiones (
    id character varying(36) NOT NULL,
    canal character varying(10) NOT NULL,
    contacto_hash character varying(64),
    estado_dialogo text DEFAULT '{}'::text NOT NULL,
    mensajes_total integer DEFAULT 0 NOT NULL,
    negativos integer DEFAULT 0 NOT NULL,
    sentimiento_promedio numeric(4,2) DEFAULT '0'::numeric NOT NULL,
    escalada boolean DEFAULT false NOT NULL,
    escalada_resuelta boolean DEFAULT false NOT NULL,
    reserva_id integer,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizada_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_sesiones_canal CHECK (((canal)::text = ANY ((ARRAY['web'::character varying, 'whatsapp'::character varying])::text[])))
);

CREATE TABLE IF NOT EXISTS public.comisiones (
    id integer NOT NULL,
    promotor_id integer NOT NULL,
    evento_id integer NOT NULL,
    porcentaje numeric(5,2) NOT NULL,
    monto numeric(10,2) DEFAULT '0'::numeric NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_liquidacion timestamp with time zone,
    CONSTRAINT ck_comisiones_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'liquidada'::character varying])::text[]))),
    CONSTRAINT ck_comisiones_monto_no_negativo CHECK ((monto >= (0)::numeric)),
    CONSTRAINT ck_comisiones_porcentaje CHECK (((porcentaje >= (0)::numeric) AND (porcentaje <= (100)::numeric)))
);

CREATE SEQUENCE public.comisiones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.comisiones_id_seq OWNED BY public.comisiones.id;

CREATE TABLE IF NOT EXISTS public.eventos (
    id integer NOT NULL,
    administrador_id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    fecha date NOT NULL,
    aforo_maximo integer NOT NULL,
    estado character varying(20) DEFAULT 'planeado'::character varying NOT NULL,
    tematica character varying(240),
    flyer_url character varying(500),
    CONSTRAINT ck_eventos_aforo_positivo CHECK ((aforo_maximo > 0)),
    CONSTRAINT ck_eventos_estado CHECK (((estado)::text = ANY ((ARRAY['planeado'::character varying, 'en curso'::character varying, 'cerrado'::character varying])::text[])))
);

CREATE SEQUENCE public.eventos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.eventos_id_seq OWNED BY public.eventos.id;

CREATE TABLE IF NOT EXISTS public.incidencias_puerta (
    id integer NOT NULL,
    evento_id integer NOT NULL,
    usuario_id integer,
    tipo character varying(24) NOT NULL,
    persona character varying(100),
    descripcion character varying(500) NOT NULL,
    fecha_hora timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_incidencias_puerta_tipo CHECK (((tipo)::text = ANY ((ARRAY['qr_duplicado'::character varying, 'qr_rechazado'::character varying, 'nombre_diferente'::character varying, 'otra'::character varying])::text[])))
);

CREATE SEQUENCE public.incidencias_puerta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.incidencias_puerta_id_seq OWNED BY public.incidencias_puerta.id;

CREATE TABLE IF NOT EXISTS public.inventario_items (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    categoria character varying(60),
    cantidad numeric(12,2) DEFAULT '0'::numeric NOT NULL,
    unidad character varying(20) DEFAULT 'unidades'::character varying NOT NULL,
    stock_minimo numeric(12,2) DEFAULT '0'::numeric NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    costo_unitario numeric(12,2),
    proveedor character varying(100),
    precio_venta numeric(12,2),
    CONSTRAINT ck_inventario_items_cantidad_no_negativa CHECK ((cantidad >= (0)::numeric)),
    CONSTRAINT ck_inventario_items_minimo_no_negativo CHECK ((stock_minimo >= (0)::numeric)),
    CONSTRAINT ck_inventario_items_precio_venta_no_negativo CHECK (((precio_venta IS NULL) OR (precio_venta >= (0)::numeric)))
);

CREATE SEQUENCE public.inventario_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.inventario_items_id_seq OWNED BY public.inventario_items.id;

CREATE TABLE IF NOT EXISTS public.inventario_movimientos (
    id integer NOT NULL,
    item_id integer NOT NULL,
    tipo character varying(10) NOT NULL,
    cantidad numeric(12,2) NOT NULL,
    cantidad_anterior numeric(12,2) NOT NULL,
    cantidad_nueva numeric(12,2) NOT NULL,
    motivo character varying(200),
    evento_id integer,
    usuario_id integer,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_inventario_movimientos_cantidad CHECK ((cantidad >= (0)::numeric)),
    CONSTRAINT ck_inventario_movimientos_tipo CHECK (((tipo)::text = ANY ((ARRAY['entrada'::character varying, 'salida'::character varying, 'consumo'::character varying, 'ajuste'::character varying])::text[])))
);

CREATE SEQUENCE public.inventario_movimientos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.inventario_movimientos_id_seq OWNED BY public.inventario_movimientos.id;

CREATE TABLE IF NOT EXISTS public.invitados (
    id integer NOT NULL,
    evento_id integer NOT NULL,
    promotor_id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    qr_code character varying(255) NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_registro timestamp with time zone DEFAULT now() NOT NULL,
    reserva_id integer,
    CONSTRAINT ck_invitados_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'usado'::character varying])::text[])))
);

CREATE SEQUENCE public.invitados_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.invitados_id_seq OWNED BY public.invitados.id;

CREATE TABLE IF NOT EXISTS public.notificaciones (
    id integer NOT NULL,
    tipo character varying(40) NOT NULL,
    titulo character varying(120) NOT NULL,
    mensaje character varying(400) NOT NULL,
    nivel character varying(10) DEFAULT 'info'::character varying NOT NULL,
    enlace character varying(200),
    referencia character varying(60),
    destinatario_rol character varying(20),
    destinatario_usuario_id integer,
    leida boolean DEFAULT false NOT NULL,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    leida_en timestamp with time zone,
    CONSTRAINT ck_notificaciones_nivel CHECK (((nivel)::text = ANY ((ARRAY['info'::character varying, 'alerta'::character varying, 'critica'::character varying])::text[])))
);

CREATE SEQUENCE public.notificaciones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.notificaciones_id_seq OWNED BY public.notificaciones.id;

CREATE TABLE IF NOT EXISTS public.promotores_metas_evento (
    id integer NOT NULL,
    promotor_id integer NOT NULL,
    evento_id integer NOT NULL,
    objetivo integer NOT NULL,
    CONSTRAINT ck_promotor_meta_objetivo_positivo CHECK ((objetivo > 0))
);

CREATE SEQUENCE public.promotores_metas_evento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.promotores_metas_evento_id_seq OWNED BY public.promotores_metas_evento.id;

CREATE TABLE IF NOT EXISTS public.reservas (
    id integer NOT NULL,
    evento_id integer NOT NULL,
    nombre_cliente character varying(100) NOT NULL,
    telefono character varying(24) NOT NULL,
    tipo character varying(10) NOT NULL,
    asistentes integer NOT NULL,
    notas text,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_solicitud timestamp with time zone DEFAULT now() NOT NULL,
    token_cancelacion_hash character varying(64),
    promotor_id integer,
    whatsapp_confirmacion_estado character varying(20) DEFAULT 'sin_configurar'::character varying NOT NULL,
    whatsapp_confirmacion_error text,
    whatsapp_confirmacion_message_id character varying(255),
    codigo_garantia character varying(24),
    garantizada_en timestamp with time zone,
    hora_limite character varying(5),
    ubicacion_asignada character varying(60),
    consumo_minimo numeric(12,2),
    CONSTRAINT ck_reservas_asistentes CHECK ((asistentes > 0)),
    CONSTRAINT ck_reservas_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'confirmada'::character varying, 'cancelada'::character varying])::text[]))),
    CONSTRAINT ck_reservas_tipo CHECK (((tipo)::text = ANY ((ARRAY['mesa'::character varying, 'palco'::character varying])::text[])))
);

CREATE SEQUENCE public.reservas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.reservas_id_seq OWNED BY public.reservas.id;

CREATE TABLE IF NOT EXISTS public.usuarios (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    password_hash character varying(255) NOT NULL,
    rol character varying(20) NOT NULL,
    telefono character varying(20),
    estado boolean DEFAULT true NOT NULL,
    fecha_registro timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_usuarios_rol CHECK (((rol)::text = ANY ((ARRAY['Administrador'::character varying, 'Promotor'::character varying, 'Puerta'::character varying])::text[])))
);

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;

CREATE TABLE IF NOT EXISTS public.whatsapp_inbound_messages (
    message_id character varying(255) NOT NULL,
    sender_hash character varying(64) NOT NULL,
    sentiment character varying(20) NOT NULL,
    score numeric(4,2) NOT NULL,
    response_status character varying(20) NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.accesos_qr ALTER COLUMN id SET DEFAULT nextval('public.accesos_qr_id_seq'::regclass);

ALTER TABLE ONLY public.alertas_riesgo ALTER COLUMN id SET DEFAULT nextval('public.alertas_riesgo_id_seq'::regclass);

ALTER TABLE ONLY public.chat_mensajes ALTER COLUMN id SET DEFAULT nextval('public.chat_mensajes_id_seq'::regclass);

ALTER TABLE ONLY public.comisiones ALTER COLUMN id SET DEFAULT nextval('public.comisiones_id_seq'::regclass);

ALTER TABLE ONLY public.eventos ALTER COLUMN id SET DEFAULT nextval('public.eventos_id_seq'::regclass);

ALTER TABLE ONLY public.incidencias_puerta ALTER COLUMN id SET DEFAULT nextval('public.incidencias_puerta_id_seq'::regclass);

ALTER TABLE ONLY public.inventario_items ALTER COLUMN id SET DEFAULT nextval('public.inventario_items_id_seq'::regclass);

ALTER TABLE ONLY public.inventario_movimientos ALTER COLUMN id SET DEFAULT nextval('public.inventario_movimientos_id_seq'::regclass);

ALTER TABLE ONLY public.invitados ALTER COLUMN id SET DEFAULT nextval('public.invitados_id_seq'::regclass);

ALTER TABLE ONLY public.notificaciones ALTER COLUMN id SET DEFAULT nextval('public.notificaciones_id_seq'::regclass);

ALTER TABLE ONLY public.promotores_metas_evento ALTER COLUMN id SET DEFAULT nextval('public.promotores_metas_evento_id_seq'::regclass);

ALTER TABLE ONLY public.reservas ALTER COLUMN id SET DEFAULT nextval('public.reservas_id_seq'::regclass);

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);

ALTER TABLE ONLY public.accesos_qr
    ADD CONSTRAINT accesos_qr_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);

ALTER TABLE ONLY public.alertas_riesgo
    ADD CONSTRAINT alertas_riesgo_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.bot_configuracion
    ADD CONSTRAINT bot_configuracion_pkey PRIMARY KEY (clave);

ALTER TABLE ONLY public.chat_mensajes
    ADD CONSTRAINT chat_mensajes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.chat_sesiones
    ADD CONSTRAINT chat_sesiones_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.eventos
    ADD CONSTRAINT eventos_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.incidencias_puerta
    ADD CONSTRAINT incidencias_puerta_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.inventario_items
    ADD CONSTRAINT inventario_items_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.inventario_movimientos
    ADD CONSTRAINT inventario_movimientos_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.invitados
    ADD CONSTRAINT invitados_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.notificaciones
    ADD CONSTRAINT notificaciones_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.promotores_metas_evento
    ADD CONSTRAINT promotores_metas_evento_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT reservas_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.promotores_metas_evento
    ADD CONSTRAINT uq_promotor_meta_evento UNIQUE (promotor_id, evento_id);

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT uq_reservas_codigo_garantia UNIQUE (codigo_garantia);

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT uq_reservas_token_cancelacion_hash UNIQUE (token_cancelacion_hash);

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.whatsapp_inbound_messages
    ADD CONSTRAINT whatsapp_inbound_messages_pkey PRIMARY KEY (message_id);

CREATE INDEX ix_accesos_qr_evento_id ON public.accesos_qr USING btree (evento_id);

CREATE INDEX ix_accesos_qr_fecha_hora ON public.accesos_qr USING btree (fecha_hora);

CREATE INDEX ix_accesos_qr_invitado_id ON public.accesos_qr USING btree (invitado_id);

CREATE INDEX ix_alertas_riesgo_evento_id ON public.alertas_riesgo USING btree (evento_id);

CREATE INDEX ix_alertas_riesgo_fecha_hora ON public.alertas_riesgo USING btree (fecha_hora);

CREATE INDEX ix_alertas_riesgo_nivel ON public.alertas_riesgo USING btree (nivel);

CREATE INDEX ix_chat_mensajes_creado_en ON public.chat_mensajes USING btree (creado_en);

CREATE INDEX ix_chat_mensajes_sesion_id ON public.chat_mensajes USING btree (sesion_id);

CREATE INDEX ix_chat_sesiones_actualizada ON public.chat_sesiones USING btree (actualizada_en);

CREATE INDEX ix_chat_sesiones_contacto_hash ON public.chat_sesiones USING btree (contacto_hash);

CREATE INDEX ix_comisiones_evento_id ON public.comisiones USING btree (evento_id);

CREATE INDEX ix_comisiones_promotor_id ON public.comisiones USING btree (promotor_id);

CREATE INDEX ix_eventos_administrador_id ON public.eventos USING btree (administrador_id);

CREATE INDEX ix_incidencias_puerta_evento_id ON public.incidencias_puerta USING btree (evento_id);

CREATE INDEX ix_incidencias_puerta_fecha_hora ON public.incidencias_puerta USING btree (fecha_hora);

CREATE INDEX ix_incidencias_puerta_usuario_id ON public.incidencias_puerta USING btree (usuario_id);

CREATE INDEX ix_inventario_items_nombre ON public.inventario_items USING btree (nombre);

CREATE INDEX ix_inventario_movimientos_creado_en ON public.inventario_movimientos USING btree (creado_en);

CREATE INDEX ix_inventario_movimientos_evento_id ON public.inventario_movimientos USING btree (evento_id);

CREATE INDEX ix_inventario_movimientos_item_id ON public.inventario_movimientos USING btree (item_id);

CREATE INDEX ix_invitados_evento_id ON public.invitados USING btree (evento_id);

CREATE INDEX ix_invitados_promotor_id ON public.invitados USING btree (promotor_id);

CREATE UNIQUE INDEX ix_invitados_qr_code ON public.invitados USING btree (qr_code);

CREATE INDEX ix_invitados_reserva_id ON public.invitados USING btree (reserva_id);

CREATE INDEX ix_notificaciones_destinatario_usuario_id ON public.notificaciones USING btree (destinatario_usuario_id);

CREATE INDEX ix_notificaciones_leida_creada ON public.notificaciones USING btree (leida, creada_en);

CREATE INDEX ix_notificaciones_referencia ON public.notificaciones USING btree (referencia);

CREATE INDEX ix_notificaciones_tipo ON public.notificaciones USING btree (tipo);

CREATE INDEX ix_promotores_metas_evento_evento_id ON public.promotores_metas_evento USING btree (evento_id);

CREATE INDEX ix_promotores_metas_evento_promotor_id ON public.promotores_metas_evento USING btree (promotor_id);

CREATE INDEX ix_reservas_evento_id ON public.reservas USING btree (evento_id);

CREATE INDEX ix_reservas_promotor_id ON public.reservas USING btree (promotor_id);

CREATE INDEX ix_reservas_whatsapp_confirmacion_message_id ON public.reservas USING btree (whatsapp_confirmacion_message_id);

CREATE UNIQUE INDEX ix_usuarios_email ON public.usuarios USING btree (email);

CREATE INDEX ix_whatsapp_inbound_received_at ON public.whatsapp_inbound_messages USING btree (received_at);

ALTER TABLE ONLY public.accesos_qr
    ADD CONSTRAINT accesos_qr_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.accesos_qr
    ADD CONSTRAINT accesos_qr_invitado_id_fkey FOREIGN KEY (invitado_id) REFERENCES public.invitados(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.alertas_riesgo
    ADD CONSTRAINT alertas_riesgo_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.chat_mensajes
    ADD CONSTRAINT chat_mensajes_sesion_id_fkey FOREIGN KEY (sesion_id) REFERENCES public.chat_sesiones(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.chat_sesiones
    ADD CONSTRAINT chat_sesiones_reserva_id_fkey FOREIGN KEY (reserva_id) REFERENCES public.reservas(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_promotor_id_fkey FOREIGN KEY (promotor_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.eventos
    ADD CONSTRAINT eventos_administrador_id_fkey FOREIGN KEY (administrador_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.invitados
    ADD CONSTRAINT fk_invitados_reserva_id FOREIGN KEY (reserva_id) REFERENCES public.reservas(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT fk_reservas_promotor_id_usuarios FOREIGN KEY (promotor_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.incidencias_puerta
    ADD CONSTRAINT incidencias_puerta_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.incidencias_puerta
    ADD CONSTRAINT incidencias_puerta_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.inventario_movimientos
    ADD CONSTRAINT inventario_movimientos_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.inventario_movimientos
    ADD CONSTRAINT inventario_movimientos_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.inventario_items(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.inventario_movimientos
    ADD CONSTRAINT inventario_movimientos_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.invitados
    ADD CONSTRAINT invitados_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.invitados
    ADD CONSTRAINT invitados_promotor_id_fkey FOREIGN KEY (promotor_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.notificaciones
    ADD CONSTRAINT notificaciones_destinatario_usuario_id_fkey FOREIGN KEY (destinatario_usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.promotores_metas_evento
    ADD CONSTRAINT promotores_metas_evento_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.promotores_metas_evento
    ADD CONSTRAINT promotores_metas_evento_promotor_id_fkey FOREIGN KEY (promotor_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT reservas_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.eventos(id) ON DELETE CASCADE;

-- Version de migracion aplicada (permite usar `alembic upgrade head` mas adelante).
INSERT INTO public.alembic_version (version_num) VALUES ('0014_alinear_indices_unicos');
