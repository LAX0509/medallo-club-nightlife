export const ROLES = Object.freeze({
  ADMINISTRADOR: "Administrador",
  PROMOTOR: "Promotor",
  PUERTA: "Puerta",
});

export const RUTA_INICIO_POR_ROL = Object.freeze({
  [ROLES.ADMINISTRADOR]: "/dashboard",
  [ROLES.PROMOTOR]: "/promotor/resumen",
  [ROLES.PUERTA]: "/escaner",
});
