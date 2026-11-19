// El API devuelve los eventos del más lejano al más reciente; en la operación casi siempre
// interesa el que está en curso o el próximo, no el último de la agenda.
export function eventoInicial(eventos) {
  if (!eventos?.length) return null;
  const enCurso = eventos.find((e) => e.estado === "en curso");
  if (enCurso) return enCurso;
  const hoy = new Date().toISOString().slice(0, 10);
  const proximos = eventos.filter((e) => e.fecha >= hoy && e.estado !== "cerrado").sort((a, b) => a.fecha.localeCompare(b.fecha));
  return proximos[0] ?? eventos[0];
}
