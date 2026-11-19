const VARIANTE_POR_DEFECTO = "neutral";

export function Badge({ children, variante = VARIANTE_POR_DEFECTO }) {
  return <span className={`badge badge-${variante}`}>{children}</span>;
}

const NIVEL_A_VARIANTE = { bajo: "success", medio: "accent", alto: "danger" };
const RESULTADO_A_VARIANTE = { valido: "success", duplicado: "danger", rechazado: "danger" };
const ESTADO_A_VARIANTE = {
  pendiente: "neutral",
  usado: "success",
  liquidada: "success",
  activa: "danger",
  resuelta: "neutral",
};

export function BadgeNivel({ nivel }) {
  return <Badge variante={NIVEL_A_VARIANTE[nivel] ?? "neutral"}>{nivel}</Badge>;
}

export function BadgeResultado({ resultado }) {
  return <Badge variante={RESULTADO_A_VARIANTE[resultado] ?? "neutral"}>{resultado}</Badge>;
}

export function BadgeEstado({ estado }) {
  return <Badge variante={ESTADO_A_VARIANTE[estado] ?? "neutral"}>{estado}</Badge>;
}
