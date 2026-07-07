# =============================================================================
# analisis_parlamentario.R
# Análisis de lenguaje político en proyectos de ley argentinos (2008-2025)
# Fuente: datos.hcdn.gob.ar + Composición Histórica Cámara de Diputados
# =============================================================================

library(tidyverse)
library(tidytext)
library(scales)

# =============================================================================
# 1. CLASIFICACIÓN DE FAMILIAS POLÍTICAS
# =============================================================================

familia_map <- function(bloque, anio) {
  case_when(
    bloque %in% c(
      "FRENTE PARA LA VICTORIA - PJ", "FRENTE PARA LA VICTORIA",
      "FRENTE DE TODOS", "UNIÓN POR LA PATRIA", "UNION POR LA PATRIA",
      "SI POR LA UNIDAD POPULAR"
    ) ~ "Kirchnerismo/Peronismo popular",
    bloque == "FRENTE RENOVADOR" & anio <= 2019 ~ "Peronismo no-K",
    bloque == "FRENTE RENOVADOR" & anio >= 2020 ~ "Kirchnerismo/Peronismo popular",
    bloque %in% c(
      "PRO", "UNION PRO"
    ) ~ "PRO/Cambiemos",
    bloque %in% c(
      "UCR", "UCR - UNIÓN CÍVICA RADICAL", "EVOLUCION RADICAL"
    ) ~ "UCR",
    bloque %in% c(
      "COALICION CIVICA", "COALICION CIVICA - ARI - GEN - UPT",
      "COALICION CIVICA ARI - UNEN", "COALICIÓN CÍVICA",
      "COALICION CIVICA - ARI", "ARI AUTONOMO 8 +"
    ) ~ "Coalición Cívica/ARI",
    bloque %in% c(
      "PERONISMO FEDERAL", "FRENTE PERONISTA", "JUSTICIALISTA",
      "PERONISTA", "FRENTE JUSTICIA UNION Y LIBERTAD - FREJULI",
      "PERONISMO PARA LA VICTORIA", "COMPROMISO FEDERAL",
      "IDENTIDAD BONAERENSE", "INNOVACIÓN FEDERAL", "CONSENSO FEDERAL",
      "FRENTE CIVICO - CORDOBA", "PERONISMO CORDOBES",
      "CORRIENTE DE PENSAMIENTO FEDERAL", "FRENTE PERONISTA FEDERAL",
      "UNION PERONISTA", "PARTIDO JUSTICIALISTA LA PAMPA",
      "PARTIDO JUSTICIALISTA PAMPEANO", "JUSTICIALISTA POR TUCUMAN",
      "JUSTICIALISTA DE LA PROVINCIA DE BUENOS AIRES",
      "JUSTICIALISTA NACIONAL", "PERONISMO JUJEÑO",
      "PERONISMO MAS AL SUR", "GUARDIA PERONISTA", "DIGNIDAD PERONISTA",
      "PRODUCCION Y TRABAJO"
    ) ~ "Peronismo no-K",
    bloque %in% c(
      "PARTIDO SOCIALISTA", "SOCIALISTA",
      "GEN", "LIBRES DEL SUR", "NUEVO ENCUENTRO POPULAR Y SOLIDARIO",
      "MOVIMIENTO PROYECTO SUR", "PROYECTO SUR - UNEN",
      "BUENOS AIRES PARA TODOS EN PROYECTO SUR",
      "DEMOCRACIA IGUALITARIA Y PARTICIPATIVA (D.I.P.)",
      "UNIDAD POPULAR", "FRENTE NUEVO ENCUENTRO", "NUEVO ENCUENTRO",
      "SUMA + UNEN", "FRENTE PROGRESISTA CIVICO Y SOCIAL",
      "ENCUENTRO POPULAR Y SOCIAL", "MEMORIA Y DEMOCRACIA"
    ) ~ "Centroizquierda/Progresismo",
    bloque %in% c(
      "FRENTE DE IZQUIERDA Y DE LOS TRABAJADORES",
      "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD",
      "PTS - FRENTE DE IZQUIERDA",
      "PTS - FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD",
      "PARTIDO OBRERO – FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNI",
      "PARTIDO OBRERO FRENTE DE IZQUIERDA Y DE TRABAJADORES UNIDAD",
      "IZQUIERDA SOCIALISTA - FRENTE DE IZQUIERDA",
      "IZQUIERDA SOCIALISTA FIT UNIDAD",
      "PARTIDO INTRANSIGENTE"
    ) ~ "Izquierda",
    bloque %in% c("LA LIBERTAD AVANZA", "AVANZA LIBERTAD") ~ "La Libertad Avanza",
    TRUE ~ "Otros/Provincial"
  )
}

# =============================================================================
# 2. CARGA Y PREPARACIÓN DE DATOS
# =============================================================================

df3 <- read_csv("proyectos_con_bloque.csv") %>%
  mutate(
    anio = year(as.POSIXct(PUBLICACION_FECHA)),
    familia_politica = familia_map(bloque, anio)
  ) %>%
  filter(TIPO == "LEY", anio >= 2008, anio <= 2025) %>%
  # Correcciones post-matching documentadas en el paper (sección 4.3.2):
  # FUNA: peronistas que apoyaron Cambiemos sin pertenecer orgánicamente al PRO
  mutate(
    familia_politica = case_when(
      bloque %in% c(
        "FEDERAL UNIDOS POR UNA NUEVA ARGENTINA",
        "UNIDOS POR UNA NUEVA ARGENTINA"
      ) ~ "Peronismo no-K",
      TRUE ~ familia_politica
    )
  )

cat("Distribución por familia política:\n")
df3 %>% count(familia_politica, sort = TRUE) %>% print()

# =============================================================================
# 3. STOPWORDS
# =============================================================================

stopwords_es <- get_stopwords("es") %>% pull(word)

stopwords_parlamentarios <- c(
  "proyecto", "ley", "art", "articulo", "camara", "honorable",
  "senado", "diputados", "nacional", "argentina", "republica",
  "declarar", "declarase", "crease", "modificacion", "poder",
  "ejecutivo", "pedido", "informes", "interes", "expresar",
  "provincia", "municipal", "regimen", "sistema", "programa",
  "fondo", "presente", "objeto", "establecer", "creacion",
  "modificar", "implementacion", "adhesion", "decreto",
  "mediante", "marco", "medidas", "medida", "promocion",
  "secretaria", "ministerio", "comision", "general", "federal"
)

todas_stopwords <- c(stopwords_es, stopwords_parlamentarios)

stopwords_extra_final6 <- c(
  "diversas", "relacionadas", "disponga", "celebrarse",
  "posibles", "nulidad", "ejercer", "interpelacion",
  "edicion", "fiesta", "copia", "revertir", "adherir",
  "remitir", "esencial", "celebrase", "disponer",
  "mitigacion", "desastres", "reconquista", "delegados",
  "santa", "luis", "saenz", "virasoro", "roque", "peña",
  "anibal", "catamarca", "misiones", "salta", "rioja",
  "pampa", "jujuy", "departamento", "rusa", "ucrania",
  "nombre", "carga", "designa", "asiento",
  "septiembre", "noviembre", "octubre", "agosto",
  "fuego", "martin", "parrafo", "insanable",
  "suiza", "drocarburifera", "corrientes",
  "localidad", "maria", "neuquen",
  "atlantico", "antartida", "armas", "aparatos",
  "fabricacion", "escolar", "modificatoria",
  "parlamentarias", "patrimonio", "autorizacion",
  "deber", "trans", "acuñacion", "inmaterial",
  "chubut", "perspectiva", "presuncion",
  "codigo", "incorporacion", "sustitucion",
  "modificaciones", "articulos", "nacion",
  "incorporese", "sustituyese", "derogase",
  "incorporase", "agregase", "ruta", "instituir",
  "instituyase", "mantienen", "monumento", "historico",
  "historica", "ginebra", "conferencia", "monto", "hurto",
  "continentales", "sujeto", "cases", "reunion",
  "anticipada", "situacion", "superior", "empleador",
  "organismo", "organismos", "exterior", "transito",
  "tierra", "islas", "sierra", "juan", "celebrada",
  "edificio", "escuela", "capital", "tucuman", "raul",
  "doctor", "casos", "protegidas", "naturales",
  "independientes", "azar", "tierras", "absoluta",
  "oficina", "padres", "tribunales", "menor", "sindical",
  "policia", "causa", "instruir", "instruyase", "lugar",
  "numero", "implementar", "lectivo", "examenes",
  "cobertura", "contengan", "rotulos", "segundo",
  "contrataciones", "procesos", "adoptado", "acuerdo",
  "pueblos", "casas", "hijos", "suprema", "escolar",
  "instalacion", "perspectiva", "presuncion"
)
# Nuevas stopwords identificadas durante el análisis (sesiones junio-julio 2026)
stopwords_analisis <- c(
  # Fórmulas procedimentales del género legislativo
  "texto", "ordenado", "aprobacion", "ratificacion", "terminos",
  "implementese", "expediente", "reproduccion",
  # Topónimos y nombres propios (artefactos geográficos)
  "chaco", "formosa", "manuel", "rosario", "buenos", "aires",
  "avenida", "calle",
  # Términos genéricos sin valor discriminante (IDF bajo en todas las familias)
  "cada", "personas", "ciudad", "media", "legisladores",
  # Términos legales transversales (aparecen en 6 de 7 familias)
  "penal", "civil", "vacunas"
)
stopwords_extra_final6 <- c(stopwords_extra_final6, stopwords_analisis)


# =============================================================================
# 4. TOKENIZACIÓN Y CONTEO
# =============================================================================

tokens3 <- df3 %>%
  filter(!is.na(familia_politica)) %>%
  select(PROYECTO_ID, TITULO, familia_politica) %>%
  unnest_tokens(word, TITULO) %>%
  mutate(word = tolower(word)) %>%
  filter(
    !word %in% todas_stopwords,
    !word %in% stopwords_extra_final6,
    !str_detect(word, "^[0-9]+$"),
    str_length(word) > 3
  )

conteo3 <- tokens3 %>%
  count(familia_politica, word, sort = TRUE)

rm(tokens3)
gc()

cat("Filas en conteo3:", nrow(conteo3), "\n")

# =============================================================================
# 5. TF-IDF Y GRÁFICO DEFINITIVO
# =============================================================================

tfidf_definitivo_final <- conteo3 %>%
  filter(
    n >= 10,
    !is.na(familia_politica),
    !familia_politica %in% c("Otros/Provincial", "La Libertad Avanza")
  ) %>%
  bind_tf_idf(word, familia_politica, n) %>%
  group_by(familia_politica) %>%
  slice_max(order_by = tf_idf, n = 10) %>%
  ungroup() %>%
  mutate(
    word = reorder_within(word, tf_idf, familia_politica),
    familia_politica = factor(familia_politica, levels = c(
      "Kirchnerismo/Peronismo popular", "PRO/Cambiemos",
      "UCR", "Peronismo no-K",
      "Izquierda", "Coalición Cívica/ARI",
      "Centroizquierda/Progresismo"
    ))
  )

ggplot(tfidf_definitivo_final, 
       aes(x = tf_idf, y = word, fill = familia_politica)) +
  geom_col(show.legend = FALSE) +
  facet_wrap(~familia_politica, scales = "free_y", ncol = 2) +
  scale_y_reordered() +
  labs(
    title = "¿De qué legisla cada fuerza política?",
    subtitle = "Palabras más distintivas en proyectos de ley por bloque (2008–2025)",
    x = "TF-IDF (distintividad)", y = NULL,
    caption = "Fuente: datos.hcdn.gob.ar | Elaboración propia\nAnálisis sobre títulos de proyectos de ley"
  ) +
  theme_minimal(base_size = 11) +
  theme(strip.text = element_text(face = "bold"))

ggsave("tfidf_DEFINITIVO.png", width = 14, height = 12, dpi = 150)
cat("Guardado tfidf_DEFINITIVO.png\n")
