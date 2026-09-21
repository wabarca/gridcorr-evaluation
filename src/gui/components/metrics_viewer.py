# -*- coding: utf-8 -*-
"""
Metrics and statistical rankings viewer UI component.
Includes scientific explanations, mathematical formulations, KGE decomposition,
rain detection contingency metrics, and interactive performance tables.
"""

import os
import streamlit as st
import pandas as pd
from ...application.models import AnalysisResult


def render_metrics_viewer(result: AnalysisResult) -> None:
    """
    Renderiza las tablas de métricas estadísticas, explicaciones matemáticas, referencias científicas y rankings de estaciones.
    """
    st.subheader("📊 Métricas Estadísticas, Fórmulas de Validación y Rankings")

    with st.expander("📖 **Tratado de Estadísticos Climatológicos, Justificación Científica y Referencias Bibliográficas**", expanded=False):
        st.markdown(
            r"""
            ### 🔬 1. Justificación y Fundamento de la Evaluación Climatológica
            La evaluación de productos grillados de precipitación y temperatura (CHIRPS/CHIRTS) frente a observaciones in-situ es indispensable para:
            1. **Cuantificar la ganancia de precisión**: Verificar si el proceso de asimilación y combinación espacial (CDT Merged) efectivamente redujo el error sistemático y la varianza residual del dato satelital.
            2. **Detectar sesgos orográficos y microclimáticos**: Identificar en qué zonas topográficas complejas (valles, cordilleras, costas) el satélite presentaba sobre o subestimación.
            3. **Validar la consistencia hidrológica y climática**: Garantizar que las series temporales reproducen fielmente tanto los valores medios como la variabilidad estacional y los eventos extremos.

            ---

            ### 📐 2. Métricas Continuas y de Error Absoluto

            #### A. Sesgo Medio (*Mean Bias*)
            $$\text{Bias} = \frac{1}{N} \sum_{i=1}^{N} (g_i - o_i)$$
            - **¿Por qué se calcula?**: Cuantifica el error sistemático unidireccional (tendencia persistente a sobrestimar o subestimar).
            - **Interpretación**:
              - $\text{Bias} > 0$: El satélite sobreestima la variable respecto a la estación terrestre.
              - $\text{Bias} < 0$: El satélite subestima la variable.
              - $\text{Bias} = 0$: Ausencia de sesgo medio sistemático (*Valor óptimo ideal*).

            #### B. Error Absoluto Medio (*MAE*)
            $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |g_i - o_i|$$
            - **¿Por qué se calcula?**: Mide la magnitud promedio lineal del error en las mismas unidades físicas ($\text{mm}$ o $^\circ\text{C}$), asignando un peso uniforme a todas las discrepancias sin sobreponderar valores atípicos (Willmott & Matsuura, 2005).
            - **Interpretación**: Valores cercanos a $0$ indican alta fidelidad punto a punto.

            #### C. Raíz del Error Cuadrático Medio (*RMSE*)
            $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (g_i - o_i)^2}$$
            - **¿Por qué se calcula?**: Al elevar los errores al cuadrado, penaliza severamente los desaciertos de gran magnitud y eventos extremos (tormentas intensas, olas de calor).
            - **Interpretación**: Es siempre $\ge \text{MAE}$. Una diferencia grande entre $\text{RMSE}$ y $\text{MAE}$ evidencia la presencia de errores atípicos severos.

            #### D. Sesgo Porcentual Relativo (*PBIAS*)
            $$\text{PBIAS} = 100 \times \frac{\sum_{i=1}^{N} (g_i - o_i)}{\sum_{i=1}^{N} o_i}$$
            - **¿Por qué se calcula?**: Expresa la desviación total acumulada como porcentaje relativo del volumen observado.
            - **Interpretación**: Moriasi et al. (2007) establecen que $|\text{PBIAS}| < 10\%$ es *Muy Bueno*, entre $10\text{–}15\%$ *Bueno*, y $> 25\%$ insatisfactorio.

            ---

            ### 📈 3. Métricas de Eficiencia de Estimación y Concordancia Climatológica

            #### A. Eficiencia de Kling-Gupta (*KGE*, Gupta et al., 2009; Kling et al., 2012)
            $$\text{KGE} = 1 - \sqrt{(r - 1)^2 + (\alpha - 1)^2 + (\beta - 1)^2}$$
            - **¿Por qué se calcula?**: Desarrollada originalmente en hidrometeorología y adoptada universalmente en climatología (temperatura y precipitación), descompone el desempeño en tres dimensiones independientes no correlacionadas:
              1. **$r$ (Correlación de Pearson)**: Sincronización temporal y espacial ($r \to 1.0$).
              2. **$\alpha = \sigma_{\text{sim}} / \sigma_{\text{obs}}$**: Preservación de la variabilidad/desviación estándar ($\alpha \to 1.0$).
              3. **$\beta = \mu_{\text{sim}} / \mu_{\text{obs}}$**: Sesgo relativo en la media ($\beta \to 1.0$).
            - **Interpretación**:
              - $\text{KGE} = 1.0$: Concordancia matemática perfecta.
              - $\text{KGE} > 0.75$: Desempeño excelente.
              - $\text{KGE} > 0.50$: Desempeño bueno / aceptable.
              - $\text{KGE} < 0.0$: La estimación es inferior a utilizar la media histórica observada.

            #### B. Eficiencia de Nash-Sutcliffe (*NSE*, Nash & Sutcliffe, 1970)
            $$\text{NSE} = 1 - \frac{\sum (g_i - o_i)^2}{\sum (o_i - \bar{o})^2}$$
            - **¿Por qué se calcula?**: Evalúa la habilidad predictiva de la rejilla comparada con la varianza natural de la serie observada.
            - **Interpretación**: $\text{NSE} \in (-\infty, 1]$. Valores $> 0.65$ indican una calibración sobresaliente.

            #### C. Índice Modificado de Concordancia (*d1*, Willmott et al., 2012)
            $$d_1 = 1 - \frac{\sum |g_i - o_i|}{\sum (|g_i - \bar{o}| + |o_i - \bar{o}|)}$$
            - **¿Por qué se calcula?**: Supera las limitaciones del coeficiente de correlación $r$ al ser sensible a diferencias en escala y desfases de magnitud absoluta.

            ---

            ### 🌧️ 4. Métricas Categóricas de Detección de Lluvia (CHIRPS)
            Basadas en la tabla de contingencia $2 \times 2$ para un umbral (ej. $\ge 1.0\text{ mm}$):
            - **POD (Probabilidad de Detección)** $= \frac{H}{H + M} \in [0, 1]$ (*Óptimo = 1.0*).
            - **FAR (Ratio de Falsas Alarmas)** $= \frac{F}{H + F} \in [0, 1]$ (*Óptimo = 0.0*).
            - **CSI (Critical Success Index / Threat Score)** $= \frac{H}{H + M + F} \in [0, 1]$ (*Óptimo = 1.0*).
            - **FBI (Frequency Bias Index)** $= \frac{H + F}{H + M}$ ($FBI > 1$: sobrestimación de días lluviosos; $FBI < 1$: subestimación).

            ---

            ### 📚 5. Referencias Bibliográficas Validadas y Enlaces DOI
            1. **Dinku, T., Funk, C., Peterson, P., Maidment, R., Tadesse, T., Gadain, H., & Ceccato, P. (2018)**. *Validation of the CHIRPS satellite rainfall estimates over eastern Africa*. **Quarterly Journal of the Royal Meteorological Society**, 144(S1), 292–312.  
               🔗 [DOI: 10.1002/qj.3244](https://doi.org/10.1002/qj.3244)
            2. **Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A., & Michaelsen, J. (2015)**. *The climate hazards infrared precipitation with stations—a new environmental record for monitoring extremes*. **Scientific Data (Nature)**, 2, 150066.  
               🔗 [DOI: 10.1038/sdata.2015.66](https://doi.org/10.1038/sdata.2015.66)
            3. **Funk, C., Peterson, P., Peterson, S., Shukla, S., Davenport, F., Michaelsen, J., Mobley, K., Joyce, R., & Verdin, J. (2019)**. *A High-Resolution 1983–2016 Tmax Climate Data Record Based on Infrared Temperatures and Stations by the Climate Hazard Center (CHIRTS-daily)*. **Journal of Climate**, 32(17), 5639–5658.  
               🔗 [DOI: 10.1175/JCLI-D-18-0698.1](https://doi.org/10.1175/JCLI-D-18-0698.1)
            4. **Gupta, H. V., Kling, H., Yilmaz, K. K., & Martinez, G. F. (2009)**. *Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling*. **Journal of Hydrology**, 377(1–2), 80–91.  
               🔗 [DOI: 10.1016/j.jhydrol.2009.08.003](https://doi.org/10.1016/j.jhydrol.2009.08.003)
            5. **Kling, H., Fuchs, M., & Paulin, M. (2012)**. *Runoff conditions in the upper Danube basin under an ensemble of climate change scenarios*. **Journal of Hydrology**, 424–425, 264–277.  
               🔗 [DOI: 10.1016/j.jhydrol.2012.01.011](https://doi.org/10.1016/j.jhydrol.2012.01.011)
            6. **Moriasi, D. N., Arnold, J. G., Van Liew, M. W., Bingner, R. L., Harmel, R. D., & Veith, T. L. (2007)**. *Model evaluation guidelines for systematic quantification of accuracy in watershed simulations*. **Transactions of the ASABE**, 50(3), 885–900.  
               🔗 [DOI: 10.13031/2013.23153](https://doi.org/10.13031/2013.23153)
            7. **Nash, J. E., & Sutcliffe, J. V. (1970)**. *River flow forecasting through conceptual models part I—A discussion of principles*. **Journal of Hydrology**, 10(3), 282–290.  
               🔗 [DOI: 10.1016/0022-1694(70)90255-6](https://doi.org/10.1016/0022-1694(70)90255-6)
            8. **Wilks, D. S. (2011)**. *Statistical Methods in the Atmospheric Sciences* (3rd Edition, Vol. 100). **Academic Press / Elsevier**, Oxford. ISBN: 978-0-12-385022-5.  
               🔗 [DOI: 10.1016/B978-0-12-385022-5.00001-4](https://doi.org/10.1016/B978-0-12-385022-5.00001-4)
            9. **Willmott, C. J., & Matsuura, K. (2005)**. *Advantages of the mean absolute error (MAE) over the root mean squared error (RMSE) in assessing average model performance*. **Climate Research**, 30(1), 79–82.  
               🔗 [DOI: 10.3354/cr030079](https://doi.org/10.3354/cr030079)
            10. **Willmott, C. J., Robeson, S. M., & Matsuura, K. (2012)**. *A refined index of model performance*. **International Journal of Climatology**, 32(13), 2088–2094.  
                🔗 [DOI: 10.1002/joc.2419](https://doi.org/10.1002/joc.2419)
            """
        )

    # Tarjetas de Resumen Global
    df_metrics = result.metrics_df
    if df_metrics is None or df_metrics.empty:
        if result.summary_global_df is not None and not result.summary_global_df.empty:
            df_metrics = result.summary_global_df
        else:
            m_csv = [c for c in result.generated_csvs if any(k in os.path.basename(c).lower() for k in ["metrics", "summary_daily_global"])]
            if m_csv and os.path.exists(m_csv[0]):
                try:
                    df_metrics = pd.read_csv(m_csv[0])
                except Exception:
                    pass

    if df_metrics is not None and not df_metrics.empty:
        st.markdown("#### 🎯 Resumen Promedio de Desempeño Multianual")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            rmse_r = df_metrics["RMSE_raw"].mean() if "RMSE_raw" in df_metrics else 0.0
            rmse_c = df_metrics["RMSE_corr"].mean() if "RMSE_corr" in df_metrics else 0.0
            st.metric("RMSE Original", f"{rmse_r:.2f}")
            st.metric("RMSE Corregido", f"{rmse_c:.2f}")

        with c2:
            d_rmse = (rmse_r - rmse_c)
            imp_pct = (100.0 * d_rmse / rmse_r) if rmse_r > 0 else 0.0
            st.metric("ΔRMSE (Mejora Neta)", f"{d_rmse:+.2f}", delta=f"{d_rmse:+.2f}")
            st.metric("% Mejora RMSE", f"{imp_pct:.1f} %", delta=f"{imp_pct:.1f} %")

        with c3:
            kge_r = df_metrics["KGE_raw"].mean() if "KGE_raw" in df_metrics else None
            kge_c = df_metrics["KGE_corr"].mean() if "KGE_corr" in df_metrics else None
            if kge_r is not None and kge_c is not None:
                st.metric("KGE Original", f"{kge_r:.2f}")
                st.metric("KGE Corregido", f"{kge_c:.2f}", delta=f"{(kge_c - kge_r):+.2f}")
            else:
                mae_r = df_metrics["MAE_raw"].mean() if "MAE_raw" in df_metrics else 0.0
                mae_c = df_metrics["MAE_corr"].mean() if "MAE_corr" in df_metrics else 0.0
                st.metric("MAE Original", f"{mae_r:.2f}")
                st.metric("MAE Corregido", f"{mae_c:.2f}")

        with c4:
            r_r = df_metrics["R_raw"].mean() if "R_raw" in df_metrics else 0.0
            r_c = df_metrics["R_corr"].mean() if "R_corr" in df_metrics else 0.0
            st.metric("Pearson r Original", f"{r_r:.3f}")
            st.metric("Pearson r Corregido", f"{r_c:.3f}", delta=f"{(r_c - r_r):+.3f}")

    # Pestañas de tablas
    tab_rankings, tab_error, tab_efficiency, tab_rain, tab_stations_daily = st.tabs([
        "🏆 Rankings de Estaciones (Mejor Desempeño)",
        "📉 Error Continuo (Bias, MAE, RMSE, PBIAS)",
        "🎯 Eficiencia & Concordancia (KGE, NSE, d1)",
        "🌧️ Detección de Lluvia (POD, FAR, CSI, FBI)",
        "📅 Resumen Diario por Estación",
    ])

    with tab_rankings:
        df_r = result.rankings_df
        if df_r is None or df_r.empty:
            if result.summary_station_df is not None and not result.summary_station_df.empty:
                df_r = result.summary_station_df
            else:
                r_csv = [c for c in result.generated_csvs if any(k in os.path.basename(c).lower() for k in ["ranking", "summary_daily_by_station", "improvement_stations"])]
                if r_csv and os.path.exists(r_csv[0]):
                    try:
                        df_r = pd.read_csv(r_csv[0])
                    except Exception:
                        pass

        if df_r is not None and not df_r.empty:
            st.markdown("#### 🏆 Ranking de Estaciones por Reducción de Error")
            with st.expander("ℹ️ **¿Qué representan estos datos y cómo interpretarlos?**", expanded=False):
                st.markdown(
                    """
                    - **Descripción**: Muestra el desempeño desagregado individualmente para cada estación meteorológica a lo largo de todo el período evaluado.
                    - **Métricas Clave**:
                      - `Delta_RMSE = RMSE_raw − RMSE_corr`: Reducción neta de error lograda por CDT en la estación (positivo = ganancia de exactitud).
                      - `% Improvement / % Mejora`: Porcentaje de reducción del error frente a la estación.
                      - `KGE_corr`, `NSE_corr`: Eficiencia de estimación y concordancia alcanzada por el producto corregido en cada punto.
                    - **Interpretación**: Permite identificar estaciones sobresalientes con alta consistencia in-situ y detectar estaciones locales complejas o con microclimas singulares.
                    """
                )
            # Asegurar station_id como primera columna
            if "station_id" in df_r.columns:
                reordered = ["station_id"] + [c for c in df_r.columns if c != "station_id"]
                df_r = df_r[reordered]

            numeric_cols = [c for c in df_r.columns if c not in ["station_id", "lon", "lat", "n", "estacion", "name", "var"]]
            col_sort1, col_sort2 = st.columns([2, 2])
            with col_sort1:
                default_idx = numeric_cols.index("Delta_RMSE") if "Delta_RMSE" in numeric_cols else 0
                sort_by = st.selectbox("Ordenar estaciones por métrica:", options=numeric_cols, index=default_idx, key="sort_ranking_col")
            with col_sort2:
                ascending = st.checkbox("Orden ascendente (menor a mayor)", value=False, key="sort_ranking_asc")

            df_sorted = df_r.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
            st.dataframe(df_sorted.style.format(precision=3), width="stretch")
            st.download_button("⬇️ Descargar Ranking de Estaciones (CSV)", data=df_sorted.to_csv(index=False), file_name="ranking_estaciones.csv", mime="text/csv", key="dl_ranking_csv")
        else:
            st.info("No hay tabla de rankings disponible para esta corrida.")

    with tab_error:
        if df_metrics is not None and not df_metrics.empty:
            st.markdown("#### 📉 Métricas de Error Continuo")
            with st.expander("ℹ️ **¿Qué representan estos datos y cómo interpretarlos?**", expanded=False):
                st.markdown(
                    r"""
                    - **Descripción**: Resumen temporal/anual que cuantifica la magnitud física del error entre las observaciones terrestres y las rejillas satelitales (Original vs Corregido).
                    - **Métricas Clave**:
                      - **`year` / `date`**: Período o fecha específica evaluada.
                      - **`Bias_raw` / `Bias_corr`**: Sesgo Medio ($^\circ\text{C}$ o $\text{mm}$). Óptimo $= 0.0$. Positivo = satélite sobreestima; Negativo = satélite subestima.
                      - **`MAE_raw` / `MAE_corr`**: Error Absoluto Medio lineal (Willmott & Matsuura, 2005).
                      - **`RMSE_raw` / `RMSE_corr`**: Raíz del Error Cuadrático Medio. Penaliza fuertemente eventos extremos y desviaciones severas.
                      - **`PBIAS_raw` / `PBIAS_corr`**: Sesgo Porcentual Relativo ($|\text{PBIAS}| < 10\%$ es Muy Bueno según Moriasi et al., 2007).
                      - **`Delta_RMSE` / `% Improvement`**: Magnitud y porcentaje de error reducido por la calibración CDT.
                    """
                )
            err_cols = [c for c in df_metrics.columns if any(k in c for k in ["station", "year", "date", "period", "Bias", "MAE", "RMSE", "PBIAS", "Delta", "Improvement"])]
            first_cols = [c for c in ["year", "date", "period", "station_id"] if c in err_cols]
            if first_cols:
                fc = first_cols[0]
                err_cols = [fc] + [c for c in err_cols if c != fc]
            st.dataframe(df_metrics[err_cols].style.format(precision=3), width="stretch")
            st.download_button("⬇️ Descargar Métricas de Error (CSV)", data=df_metrics[err_cols].to_csv(index=False), file_name="metricas_error_anual.csv", mime="text/csv", key="dl_err_csv")
        else:
            st.info("No hay tabla de métricas de error disponible.")

    with tab_efficiency:
        if df_metrics is not None and not df_metrics.empty:
            st.markdown("#### 🎯 Eficiencia de Estimación y Concordancia de Variabilidad")
            with st.expander("ℹ️ **¿Qué representan estos datos y cómo interpretarlos?**", expanded=False):
                st.markdown(
                    r"""
                    - **Descripción**: Evalúa la sincronización temporal, la preservación de la varianza natural y la fidelidad distributiva de las rejillas frente a las estaciones.
                    - **Métricas Clave**:
                      - **`year` / `date`**: Período evaluado.
                      - **`KGE_raw` / `KGE_corr`** (*Kling-Gupta Efficiency*, Gupta et al., 2009; Kling et al., 2012): Descompone el desempeño en correlación ($r$), variabilidad ($\alpha$) y sesgo ($\beta$). $\text{KGE} = 1.0$ (perfecto); $>0.75$ (excelente); $>0.50$ (bueno).
                      - **`NSE_raw` / `NSE_corr`** (*Nash-Sutcliffe Efficiency*, Nash & Sutcliffe, 1970): Habilidad predictiva frente a la media observada. $\text{NSE} > 0.65$ indica calibración sobresaliente.
                      - **`d1_raw` / `d1_corr`** (*Índice Modificado de Willmott*, Willmott et al., 2012): Mide concordancia absoluta sin sensibilidad indebida a extremos.
                      - **`R_raw` / `R_corr`**: Coeficiente de correlación lineal de Pearson.
                    """
                )
            eff_cols = [c for c in df_metrics.columns if any(k in c for k in ["station", "year", "date", "period", "R_", "KGE", "NSE", "Willmott", "Alpha", "Beta", "d1"])]
            first_cols = [c for c in ["year", "date", "period", "station_id"] if c in eff_cols]
            if first_cols:
                fc = first_cols[0]
                eff_cols = [fc] + [c for c in eff_cols if c != fc]
            if len(eff_cols) > 1:
                st.dataframe(df_metrics[eff_cols].style.format(precision=3), width="stretch")
                st.download_button("⬇️ Descargar Métricas de Eficiencia (CSV)", data=df_metrics[eff_cols].to_csv(index=False), file_name="metricas_eficiencia_anual.csv", mime="text/csv", key="dl_eff_csv")
            else:
                st.info("Las métricas de eficiencia (KGE, NSE, Willmott d1) se calculan en modo multianual con '--eval'.")
        else:
            st.info("No hay métricas de eficiencia disponibles.")

    with tab_rain:
        if df_metrics is not None and not df_metrics.empty:
            st.markdown("#### 🌧️ Métricas Categóricas de Detección de Lluvia")
            with st.expander("ℹ️ **¿Qué representan estos datos y cómo interpretarlos?**", expanded=False):
                st.markdown(
                    r"""
                    - **Descripción**: Evalúa la capacidad del producto satelital para discriminar la ocurrencia de precipitación (días secos vs días lluviosos para el umbral fijado).
                    - **Métricas Clave**:
                      - **`year` / `date`**: Período evaluado.
                      - **`POD`** (*Probability of Detection*): Proporción de días con lluvia real detectados correctamente ($[0, 1]$, Óptimo $= 1.0$).
                      - **`FAR`** (*False Alarm Ratio*): Proporción de eventos estimados que resultaron falsas alarmas ($[0, 1]$, Óptimo $= 0.0$).
                      - **`CSI`** (*Critical Success Index*): Éxito relativo combinando aciertos, fallos y falsas alarmas ($[0, 1]$, Óptimo $= 1.0$).
                      - **`FBI`** (*Frequency Bias Index*): Razón de frecuencia estimada vs observada ($FBI = 1.0$ balance perfecto; $>1$ sobreestima días lluviosos).
                    """
                )
            rain_cols = [c for c in df_metrics.columns if any(k in c for k in ["station", "year", "date", "period", "POD", "FAR", "CSI", "FBI", "ETS", "Accuracy"])]
            first_cols = [c for c in ["year", "date", "period", "station_id"] if c in rain_cols]
            if first_cols:
                fc = first_cols[0]
                rain_cols = [fc] + [c for c in rain_cols if c != fc]
            if len(rain_cols) > 1:
                st.dataframe(df_metrics[rain_cols].style.format(precision=3), width="stretch")
                st.download_button("⬇️ Descargar Métricas de Detección (CSV)", data=df_metrics[rain_cols].to_csv(index=False), file_name="metricas_deteccion_lluvia.csv", mime="text/csv", key="dl_rain_csv")
            else:
                st.info("Las métricas categóricas de lluvia se calculan para productos de precipitación (CHIRPS).")
        else:
            st.info("No hay métricas de detección de lluvia disponibles.")

    with tab_stations_daily:
        df_s = result.summary_station_df
        if df_s is None or df_s.empty:
            s_csv = [c for c in result.generated_csvs if "summary_daily_by_station" in c]
            if s_csv and os.path.exists(s_csv[0]):
                df_s = pd.read_csv(s_csv[0])

        if df_s is not None and not df_s.empty:
            st.markdown("#### 📅 Resumen Estadístico Diario por Estación")
            with st.expander("ℹ️ **¿Qué representan estos datos y cómo interpretarlos?**", expanded=False):
                st.markdown(
                    """
                    - **Descripción**: Resumen consolidado del conteo de observaciones válidas diarias, medias y desviaciones estándar para cada estación meteorológica individual.
                    """
                )
            if "station_id" in df_s.columns:
                reordered = ["station_id"] + [c for c in df_s.columns if c != "station_id"]
                df_s = df_s[reordered]
            st.dataframe(df_s.style.format(precision=3), width="stretch")
            st.download_button("⬇️ Descargar Resumen Diario por Estación (CSV)", data=df_s.to_csv(index=False), file_name="resumen_diario_estaciones.csv", mime="text/csv", key="dl_st_daily_csv")
        else:
            st.info("No hay resumen diario por estación disponible para esta corrida.")
