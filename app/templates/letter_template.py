def construir_asunto(datos: dict) -> str:
    especie = datos.get("especie_predicha") or {}
    ubicacion = datos.get("ubicacion") or {}
    return (
        "Denuncia ciudadana ambiental - Posible afectación a fauna silvestre amenazada - "
        f"{especie.get('nombre_comun', 'especie no identificada')} - "
        f"{ubicacion.get('municipio', 's/d')}, {ubicacion.get('departamento', 's/d')}"
    )


def construir_cuerpo(datos: dict, resumen_hechos: str) -> str:
    anonima = datos.get("anonima", True)
    contacto = datos.get("contacto")
    ubicacion = datos.get("ubicacion") or {}
    especie = datos.get("especie_predicha") or {}
    entidad = datos.get("entidad_destino") or {}

    bloque_contacto = (
        "Denuncia anónima. No se registran datos de contacto."
        if anonima
        else (contacto or "No aportado por el denunciante.")
    )

    mapa_url = ""
    if ubicacion.get("lat") is not None and ubicacion.get("lon") is not None:
        mapa_url = (
            f"  (mapa: https://www.openstreetmap.org/?mlat={ubicacion['lat']}"
            f"&mlon={ubicacion['lon']})"
        )

    return f"""Señores
{entidad.get('nombre', 'Entidad ambiental competente')}

De manera {"anónima" if anonima else "con datos de contacto informados"}, un ciudadano \
reporta a través del sistema FaunaAlerta Bot (canal web) los siguientes hechos:

1. Fecha y hora del reporte: {datos.get('timestamp', 's/d')}
2. Ubicación reportada: {ubicacion.get('direccion_aprox', 'no especificada')}, \
{ubicacion.get('municipio', 's/d')}, {ubicacion.get('departamento', 's/d')}
   Coordenadas GPS: {ubicacion.get('lat', 's/d')}, {ubicacion.get('lon', 's/d')}{mapa_url}
3. Tipo de lugar: {datos.get('tipo_lugar', 'no especificado')}
   Descripción aportada por el denunciante: "{datos.get('descripcion_lugar', '')}"
4. Especie presuntamente involucrada: {especie.get('nombre_cientifico', 'no identificada')} \
({especie.get('nombre_comun', 'no identificada')})
   Categoría de amenaza de referencia: {especie.get('categoria_amenaza', 'no aplica')}
   Identificación automática (no oficial) - confianza: {especie.get('confianza', 'baja')}
5. Resumen de los hechos: {resumen_hechos}
6. Evidencia adjunta: fotografía aportada por el denunciante (archivo adjunto)
7. Datos de contacto del denunciante: {bloque_contacto}

Se solicita a la entidad competente adelantar las verificaciones y acciones a que haya \
lugar conforme a la normativa ambiental vigente.

-- Reporte generado automáticamente por FaunaAlerta Bot a partir de información \
suministrada voluntariamente por un ciudadano vía formulario web.
   Radicado interno: {datos.get('id', 's/d')}
"""
